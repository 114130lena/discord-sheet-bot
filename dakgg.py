import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime

DATA_DIR = "data"
CACHE_PATH = os.path.join(DATA_DIR, "dakgg_cache.json")
CACHE_TTL = 24 * 60 * 60
os.makedirs(DATA_DIR, exist_ok=True)


def _norm(value):
    return " ".join(str(value or "").strip().lower().split())


def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {}


def _save_cache(data):
    with open(CACHE_PATH, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)


def _http_text(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; DiscordSheetBot/1.0)", "Accept-Language": "ko,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def _walk(value, character_counts):
    if isinstance(value, dict):
        keys = {str(k).lower(): k for k in value.keys()}
        name = next((value[keys[k]].strip() for k in ("charactername", "character_name", "character", "name") if k in keys and isinstance(value[keys[k]], str)), None)
        count = None
        for key in ("games", "gamecount", "game_count", "matches", "count", "playcount", "play_count"):
            if key in keys:
                try: count = int(float(value[keys[key]])); break
                except Exception: pass
        if name and count and count > 0 and len(name) <= 40: character_counts[name] += count
        for child in value.values(): _walk(child, character_counts)
    elif isinstance(value, list):
        for child in value: _walk(child, character_counts)


def _extract_next_data(html):
    marker = '<script id="__NEXT_DATA__" type="application/json">'
    start = html.find(marker)
    if start < 0: return None
    start += len(marker); end = html.find("</script>", start)
    if end < 0: return None
    try: return json.loads(html[start:end])
    except Exception: return None


def _extract_from_html(html):
    counts = Counter(); next_data = _extract_next_data(html)
    if next_data is not None: _walk(next_data, counts)
    return counts


def _season_ids(html):
    seasons = sorted({int(x) for x in re.findall(r"SEASON_(\d+)", html)})
    return [f"SEASON_{x}" for x in seasons]


def _character_url(game_nick, season=None):
    encoded = urllib.parse.quote(str(game_nick or ""), safe="")
    url = f"https://dak.gg/er/players/{encoded}/character?gameMode=ALL&hl=ko"
    if season: url += "&season=" + urllib.parse.quote(season)
    return url


def _fetch_season_counts(game_nick):
    checked = []; errors = []; per_season = {}; merged = Counter()
    base_url = _character_url(game_nick)
    try:
        base_html = _http_text(base_url); checked.append(base_url)
        seasons = _season_ids(base_html)
        # If no season identifiers are exposed, use the verified page itself instead of inventing seasons.
        if not seasons:
            counts = _extract_from_html(base_html)
            merged.update(counts)
            return merged, per_season, checked, errors, "single public page (season list unavailable)"
        for season in seasons:
            url = _character_url(game_nick, season)
            try:
                html = _http_text(url); checked.append(url)
                counts = _extract_from_html(html)
                if counts:
                    per_season[season] = dict(counts)
                    merged.update(counts)
                time.sleep(0.25)
            except Exception as exc:
                errors.append(f"{season}:{type(exc).__name__}")
        return merged, per_season, checked, errors, f"{len(per_season)} verified seasons aggregated"
    except Exception as exc:
        errors.append(type(exc).__name__)
        return merged, per_season, checked, errors, "unavailable"


def get_character_stats(game_nick, top_n=3, force_refresh=False):
    game_nick = str(game_nick or "").strip(); top_n = max(1, min(int(top_n or 3), 10))
    if not game_nick: return {"status": "error", "error": "empty_game_nick", "characters": []}
    key = _norm(game_nick); cache = _load_cache(); cached = cache.get(key); now = time.time()
    if cached and not force_refresh and now - cached.get("cached_at", 0) < CACHE_TTL:
        result = dict(cached.get("result", {})); result["cached"] = True; result["characters"] = result.get("characters", [])[:top_n]; return result
    merged, per_season, checked, errors, scope = _fetch_season_counts(game_nick)
    characters = [{"name": name, "games": games} for name, games in merged.most_common(10)]
    total = sum(item["games"] for item in characters)
    for item in characters: item["share"] = round((item["games"] / total * 100), 1) if total else 0
    result = {"status": "ok" if characters else "unavailable", "game_nick": game_nick, "characters": characters, "source": "DAK.GG public page", "checked_urls": checked, "errors": errors, "queried_at": datetime.now().isoformat(timespec="seconds"), "scope": scope, "seasons": sorted(per_season), "season_stats": per_season}
    cache[key] = {"cached_at": now, "result": result}; _save_cache(cache)
    result["characters"] = result["characters"][:top_n]; result["cached"] = False
    return result

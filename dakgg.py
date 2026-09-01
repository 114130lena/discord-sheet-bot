import json
import os
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
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _http_text(url, timeout=10):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; DiscordSheetBot/1.0)",
        "Accept-Language": "ko,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def _walk(value, character_counts):
    if isinstance(value, dict):
        keys = {str(k).lower(): k for k in value.keys()}
        name = None
        count = None
        for key in ("charactername", "character_name", "character", "name"):
            if key in keys and isinstance(value[keys[key]], str):
                name = value[keys[key]].strip()
                break
        for key in ("games", "gamecount", "game_count", "matches", "count", "playcount", "play_count"):
            if key in keys:
                try:
                    count = int(float(value[keys[key]]))
                    break
                except Exception:
                    pass
        if name and count and count > 0 and len(name) <= 40:
            character_counts[name] += count
        for child in value.values():
            _walk(child, character_counts)
    elif isinstance(value, list):
        for child in value:
            _walk(child, character_counts)


def _extract_next_data(html):
    marker = '<script id="__NEXT_DATA__" type="application/json">'
    start = html.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = html.find("</script>", start)
    if end < 0:
        return None
    try:
        return json.loads(html[start:end])
    except Exception:
        return None


def _extract_from_html(html):
    counts = Counter()
    next_data = _extract_next_data(html)
    if next_data is not None:
        _walk(next_data, counts)
    # Some builds expose serialized JSON directly in scripts; intentionally conservative.
    return counts


def _candidate_urls(game_nick):
    encoded = urllib.parse.quote(str(game_nick or ""), safe="")
    return [
        f"https://dak.gg/er/players/{encoded}/character?gameMode=ALL&hl=ko",
        f"https://dak.gg/er/players/{encoded}/character?gameMode=RANK&hl=ko",
    ]


def get_character_stats(game_nick, top_n=3, force_refresh=False):
    game_nick = str(game_nick or "").strip()
    top_n = max(1, min(int(top_n or 3), 10))
    if not game_nick:
        return {"status": "error", "error": "empty_game_nick", "characters": []}
    key = _norm(game_nick)
    cache = _load_cache()
    cached = cache.get(key)
    now = time.time()
    if cached and not force_refresh and now - cached.get("cached_at", 0) < CACHE_TTL:
        result = dict(cached.get("result", {}))
        result["cached"] = True
        result["characters"] = result.get("characters", [])[:top_n]
        return result
    merged = Counter()
    checked = []
    errors = []
    for url in _candidate_urls(game_nick):
        try:
            html = _http_text(url)
            checked.append(url)
            counts = _extract_from_html(html)
            merged.update(counts)
        except Exception as exc:
            errors.append(type(exc).__name__)
    characters = [{"name": name, "games": games} for name, games in merged.most_common(10)]
    total = sum(item["games"] for item in characters)
    if characters:
        for item in characters:
            item["share"] = round((item["games"] / total * 100), 1) if total else 0
        result = {
            "status": "ok",
            "game_nick": game_nick,
            "characters": characters,
            "source": "DAK.GG public page",
            "checked_urls": checked,
            "errors": errors,
            "queried_at": datetime.now().isoformat(timespec="seconds"),
            "scope": "public page data that could be verified",
        }
    else:
        result = {
            "status": "unavailable",
            "game_nick": game_nick,
            "characters": [],
            "source": "DAK.GG public page",
            "checked_urls": checked,
            "errors": errors,
            "queried_at": datetime.now().isoformat(timespec="seconds"),
            "scope": "unavailable",
        }
    cache[key] = {"cached_at": now, "result": result}
    _save_cache(cache)
    result["characters"] = result.get("characters", [])[:top_n]
    result["cached"] = False
    return result

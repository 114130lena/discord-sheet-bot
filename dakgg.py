import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

DATA_DIR = "data"
CACHE_PATH = os.path.join(DATA_DIR, "dakgg_cache.json")
CHARACTER_CACHE_PATH = os.path.join(DATA_DIR, "dakgg_characters.json")
CACHE_TTL = 24 * 60 * 60
CHARACTER_CACHE_TTL = 7 * 24 * 60 * 60
DAKGG_API_BASE = "https://er.dakgg.io"
DAKGG_DATA_BASE = "https://er-data.dakgg.net/db/20260825064704"
os.makedirs(DATA_DIR, exist_ok=True)


def _norm(value):
    return " ".join(str(value or "").strip().lower().split())


def _load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_cache():
    return _load_json_file(CACHE_PATH, {})


def _save_cache(data):
    _save_json_file(CACHE_PATH, data)


def _http_text(url, timeout=10):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; DiscordSheetBot/1.0)",
            "Accept-Language": "ko,en;q=0.8",
            "Dakgg-Language": "ko",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def _http_json(url, timeout=10):
    return json.loads(_http_text(url, timeout=timeout))


def _player_profile_url(game_nick, season=None):
    encoded = urllib.parse.quote(str(game_nick or ""), safe="")
    url = f"{DAKGG_API_BASE}/api/v1/players/{encoded}/profile"
    if season is not None:
        url += "?season=" + urllib.parse.quote(str(season), safe="")
    return url


def _player_profile(game_nick):
    encoded = urllib.parse.quote(str(game_nick or "").strip(), safe="")
    url = f"{DAKGG_API_BASE}/api/v1/players/{encoded}/profile"
    data = _http_json(url)
    return data, url


def _extract_character_map(value):
    result = {}

    def walk(item):
        if isinstance(item, dict):
            keys = {str(k).lower(): k for k in item}
            char_id = None
            char_name = None

            for field in ("id", "key", "characterid", "character_id"):
                if field in keys:
                    try:
                        char_id = int(item[keys[field]])
                        break
                    except (TypeError, ValueError):
                        pass

            for field in ("name", "nameko", "name_ko", "charactername", "character_name"):
                if field in keys:
                    candidate = item[keys[field]]
                    if isinstance(candidate, str) and candidate.strip():
                        char_name = candidate.strip()
                        break

            if char_id is not None and char_name:
                result[char_id] = char_name

            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return result


def get_character_name_map(force_refresh=False):
    cached = _load_json_file(CHARACTER_CACHE_PATH, {})
    now = time.time()

    if (
        cached
        and not force_refresh
        and now - cached.get("cached_at", 0) < CHARACTER_CACHE_TTL
    ):
        return {int(k): v for k, v in cached.get("characters", {}).items()}

    candidates = [
        f"{DAKGG_DATA_BASE}/characters.json",
        f"{DAKGG_DATA_BASE}/character.json",
        f"{DAKGG_DATA_BASE}/Character.json",
        f"{DAKGG_DATA_BASE}/data.json",
    ]

    for url in candidates:
        try:
            data = _http_json(url)
            characters = _extract_character_map(data)
            if characters:
                _save_json_file(
                    CHARACTER_CACHE_PATH,
                    {
                        "cached_at": now,
                        "source": url,
                        "characters": characters,
                    },
                )
                return characters
        except Exception:
            continue

    if cached:
        return {int(k): v for k, v in cached.get("characters", {}).items()}

    return {}


def _find_current_season_id(profile):
    player = profile.get("player", {}) if isinstance(profile, dict) else {}
    season_id = player.get("lastPlayedSeasonId")
    if season_id is not None:
        try:
            return int(season_id)
        except (TypeError, ValueError):
            pass

    seasons = profile.get("playerSeasons", []) if isinstance(profile, dict) else []
    for season in seasons:
        if season.get("seasonId") is not None:
            try:
                return int(season["seasonId"])
            except (TypeError, ValueError):
                pass
    return None


def _pick_overview(profile, season_id):
    overviews = profile.get("playerSeasonOverviews", []) if isinstance(profile, dict) else []

    candidates = []
    for overview in overviews:
        if season_id is not None and overview.get("seasonId") != season_id:
            continue
        candidates.append(overview)

    if not candidates:
        candidates = list(overviews)

    # matchingModeId 0 / teamModeId 0 is the main overview exposed for ALL.
    candidates.sort(
        key=lambda x: (
            x.get("matchingModeId") != 0,
            x.get("teamModeId") != 0,
            -int(x.get("play", 0) or 0),
        )
    )
    return candidates[0] if candidates else None


def _build_character_stats(character_stats, top_n, name_map):
    characters = []
    for stat in character_stats or []:
        try:
            character_key = int(stat.get("key"))
        except (TypeError, ValueError):
            continue

        games = int(stat.get("play", 0) or 0)
        if games <= 0:
            continue

        wins = int(stat.get("win", 0) or 0)
        top3 = int(stat.get("top3", 0) or 0)
        kills = int(stat.get("playerKill", 0) or 0)
        damage = int(stat.get("damageToPlayer", 0) or 0)

        characters.append(
            {
                "key": character_key,
                "name": name_map.get(character_key, f"Unknown ({character_key})"),
                "games": games,
                "wins": wins,
                "top3": top3,
                "kills": kills,
                "damage": damage,
            }
        )

    characters.sort(key=lambda item: item["games"], reverse=True)
    total_games = sum(item["games"] for item in characters)

    for item in characters:
        item["share"] = round(item["games"] / total_games * 100, 1) if total_games else 0
        item["win_rate"] = round(item["wins"] / item["games"] * 100, 1) if item["games"] else 0

    return characters[:top_n]


def get_character_stats(game_nick, top_n=3, force_refresh=False):
    game_nick = str(game_nick or "").strip()
    top_n = max(1, min(int(top_n or 3), 10))

    if not game_nick:
        return {
            "status": "error",
            "error": "empty_game_nick",
            "characters": [],
        }

    key = _norm(game_nick)
    cache = _load_cache()
    cached = cache.get(key)
    now = time.time()

    if (
        cached
        and not force_refresh
        and now - cached.get("cached_at", 0) < CACHE_TTL
    ):
        result = dict(cached.get("result", {}))
        result["characters"] = result.get("characters", [])[:top_n]
        result["cached"] = True
        return result

    try:
        profile, checked_url = _player_profile(game_nick)
        season_id = _find_current_season_id(profile)
        overview = _pick_overview(profile, season_id)

        if not overview:
            return {
                "status": "unavailable",
                "game_nick": game_nick,
                "characters": [],
                "source": "DAK.GG API",
                "checked_urls": [checked_url],
                "season_id": season_id,
                "cached": False,
            }

        name_map = get_character_name_map()
        characters = _build_character_stats(
            overview.get("characterStats", []),
            top_n=10,
            name_map=name_map,
        )

        result = {
            "status": "ok" if characters else "unavailable",
            "game_nick": game_nick,
            "characters": characters,
            "source": "DAK.GG API",
            "checked_urls": [checked_url],
            "queried_at": datetime.now().isoformat(timespec="seconds"),
            "season_id": season_id,
            "cached": False,
        }

        cache[key] = {"cached_at": now, "result": result}
        _save_cache(cache)

        result["characters"] = result["characters"][:top_n]
        return result

    except Exception as exc:
        return {
            "status": "error",
            "game_nick": game_nick,
            "error": f"{type(exc).__name__}: {exc}",
            "characters": [],
            "cached": False,
        }

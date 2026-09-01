import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

DATA_DIR = "data"
IDENTITIES_PATH = os.path.join(DATA_DIR, "player_identities.json")
os.makedirs(DATA_DIR, exist_ok=True)


def _norm(value):
    return " ".join(str(value or "").strip().lower().split())


def load_identities():
    if not os.path.exists(IDENTITIES_PATH):
        return {}
    try:
        with open(IDENTITIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_identities(data):
    with open(IDENTITIES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_identity(display_name):
    return load_identities().get(_norm(display_name))


def save_identity(display_name, game_nick, source="manual", confidence="high", aliases=None):
    display_name = str(display_name or "").strip()
    game_nick = str(game_nick or "").strip()
    if not display_name or not game_nick:
        return None
    data = load_identities()
    key = _norm(display_name)
    old = data.get(key, {})
    item = {
        "display_name": display_name,
        "game_nick": game_nick,
        "source": source,
        "confidence": confidence,
        "aliases": list(dict.fromkeys([str(x).strip() for x in (aliases or old.get("aliases", [])) if str(x).strip()])),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    data[key] = item
    save_identities(data)
    return item


def _http_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; DiscordSheetBot/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def _http_text(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; DiscordSheetBot/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def _extract_game_nick_from_text(text):
    # Keep this conservative: only accept explicit labels that commonly appear in player profiles.
    patterns = [
        r"(?:인게임\s*닉네임|게임\s*닉네임|In[- ]?game\s*(?:ID|Nickname)|IGN)\s*[:：]\s*([^\n|<]{2,60})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" []()")
            if value:
                return value
    return None


def search_bori(display_name):
    """Best-effort bori.wiki lookup using the public MediaWiki API when available."""
    query = str(display_name or "").strip()
    if not query:
        return None
    try:
        api = "https://bori.wiki/w/api.php?action=query&list=search&format=json&srlimit=5&srsearch=" + urllib.parse.quote(query)
        payload = _http_json(api)
        results = payload.get("query", {}).get("search", [])
        if not results:
            return None
        best = results[0]
        title = best.get("title", "")
        if not title:
            return None
        page_url = "https://bori.wiki/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        text = _http_text(page_url)
        nick = _extract_game_nick_from_text(re.sub(r"<[^>]+>", " ", text))
        if nick:
            return {"display_name": query, "game_nick": nick, "source": "bori.wiki", "confidence": "medium", "url": page_url}
        return {"display_name": query, "game_nick": None, "source": "bori.wiki", "confidence": "low", "url": page_url}
    except Exception:
        return None


def resolve_identity(display_name, try_bori=True):
    cached = get_identity(display_name)
    if cached:
        return {**cached, "status": "resolved", "kind": "cached"}
    if try_bori:
        found = search_bori(display_name)
        if found and found.get("game_nick"):
            saved = save_identity(display_name, found["game_nick"], source="bori.wiki", confidence=found.get("confidence", "medium"))
            return {**saved, "status": "resolved", "kind": "bori"}
        if found:
            return {"display_name": display_name, "game_nick": None, "source": "bori.wiki", "confidence": "low", "status": "unresolved", "kind": "bori_no_nick", "url": found.get("url")}
    return {"display_name": display_name, "game_nick": None, "source": "", "confidence": "none", "status": "unresolved", "kind": "manual_required"}


def classify_name(display_name):
    """Conservative classification: known mapping wins; otherwise the image name remains unconfirmed."""
    identity = get_identity(display_name)
    if identity:
        if _norm(identity.get("game_nick")) == _norm(display_name):
            return {"type": "in_game", "confidence": identity.get("confidence", "high"), "identity": identity}
        return {"type": "tournament", "confidence": identity.get("confidence", "high"), "identity": identity}
    return {"type": "unknown", "confidence": "none", "identity": None}

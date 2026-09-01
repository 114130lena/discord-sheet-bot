import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime

DATA_DIR = "data"
IDENTITIES_PATH = os.path.join(DATA_DIR, "player_identities.json")
BORI_API = "https://bori.wiki/w/api.php"
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
        "aliases": list(dict.fromkeys([
            str(x).strip() for x in (aliases or old.get("aliases", [])) if str(x).strip()
        ])),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    data[key] = item
    save_identities(data)
    return item


def _http_json(url, timeout=8):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; DiscordSheetBot/1.0)",
            "Accept-Language": "ko,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def _api(params):
    query = urllib.parse.urlencode({**params, "format": "json", "origin": "*"})
    return _http_json(BORI_API + "?" + query)


def _clean_nick(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<!--.*?-->", "", value, flags=re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", value)
    value = re.sub(r"\[\[([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\{\{[^{}]*\}\}", "", value)
    value = re.sub(r"'''?|''", "", value)
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n|,:：;[](){}")
    if not value or len(value) > 60:
        return None
    # Reject values that clearly look like explanatory prose instead of a nickname.
    if value.lower() in {"없음", "미상", "unknown", "n/a", "-"}:
        return None
    return value


def _extract_game_nick_from_text(text):
    labels = (
        "인게임 닉네임|게임 닉네임|인게임닉네임|게임닉네임|"
        "닉네임|소환사명|플레이어명|In[- ]?game(?: ID| Nickname)?|IGN|ID"
    )
    patterns = [
        rf"(?:{labels})\s*[:：=]\s*([^\n|<]{{1,100}})",
        rf"(?:{labels})\s*</(?:th|dt)>\s*<(?:td|dd)[^>]*>\s*([^<]{{1,100}})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            nick = _clean_nick(match.group(1))
            if nick:
                return nick
    return None


def _extract_game_nick_from_wikitext(text):
    # Bori pages often expose profile fields as template parameters.
    labels = (
        "인게임\s*닉네임|게임\s*닉네임|인게임닉네임|게임닉네임|"
        "닉네임|소환사명|플레이어명|ingame|in_game|in-game|game_nick|ign"
    )
    for match in re.finditer(
        rf"^\s*\|\s*(?:{labels})\s*=\s*([^\n]+)",
        text,
        flags=re.I | re.M,
    ):
        nick = _clean_nick(match.group(1))
        if nick:
            return nick
    return _extract_game_nick_from_text(text)


def _page_wikitext(title):
    payload = _api({
        "action": "query",
        "prop": "revisions",
        "titles": title,
        "rvprop": "content",
        "rvslots": "main",
        "redirects": 1,
    })
    pages = payload.get("query", {}).get("pages", {})
    for page in pages.values():
        revisions = page.get("revisions") or []
        if revisions:
            slots = revisions[0].get("slots", {})
            main = slots.get("main", {})
            content = main.get("*") or main.get("content") or revisions[0].get("*")
            if content:
                return str(content)
    return ""


def _page_url(title):
    return "https://bori.wiki/wiki/" + urllib.parse.quote(str(title).replace(" ", "_"))


def _candidate_score(query, result):
    title = str(result.get("title") or "")
    snippet = re.sub(r"<[^>]+>", " ", str(result.get("snippet") or ""))
    q = _norm(query)
    t = _norm(title)
    score = 0
    if t == q:
        score += 1000
    elif q in t:
        score += 400
    elif t in q:
        score += 200
    if q and q in _norm(snippet):
        score += 50
    if "선수" in title or "player" in title.lower():
        score += 10
    return score


def search_bori(display_name):
    """Resolve a tournament/player name to an in-game nickname from Bori Wiki."""
    query = str(display_name or "").strip()
    if not query:
        return None
    try:
        payload = _api({
            "action": "query",
            "list": "search",
            "srlimit": 10,
            "srsearch": query,
        })
        results = payload.get("query", {}).get("search", [])
        if not results:
            return None

        results = sorted(results, key=lambda item: _candidate_score(query, item), reverse=True)
        checked = []
        for result in results[:10]:
            title = str(result.get("title") or "").strip()
            if not title:
                continue
            url = _page_url(title)
            checked.append(url)
            text = _page_wikitext(title)
            nick = _extract_game_nick_from_wikitext(text)
            if nick:
                confidence = "high" if _norm(title) == _norm(query) else "medium"
                return {
                    "display_name": query,
                    "game_nick": nick,
                    "source": "bori.wiki",
                    "confidence": confidence,
                    "url": url,
                    "checked_urls": checked,
                    "title": title,
                }

        return {
            "display_name": query,
            "game_nick": None,
            "source": "bori.wiki",
            "confidence": "low",
            "checked_urls": checked,
        }
    except Exception:
        return None


def resolve_identity(display_name, try_bori=True):
    cached = get_identity(display_name)
    if cached:
        return {**cached, "status": "resolved", "kind": "cached"}
    if try_bori:
        found = search_bori(display_name)
        if found and found.get("game_nick"):
            saved = save_identity(
                display_name,
                found["game_nick"],
                source="bori.wiki",
                confidence=found.get("confidence", "medium"),
            )
            return {**saved, "status": "resolved", "kind": "bori", "url": found.get("url")}
        if found:
            return {
                "display_name": display_name,
                "game_nick": None,
                "source": "bori.wiki",
                "confidence": "low",
                "status": "unresolved",
                "kind": "bori_no_nick",
                "checked_urls": found.get("checked_urls", []),
            }
    return {
        "display_name": display_name,
        "game_nick": None,
        "source": "",
        "confidence": "none",
        "status": "unresolved",
        "kind": "manual_required",
    }


def classify_name(display_name):
    """Conservative classification: known mapping wins; otherwise the image name remains unconfirmed."""
    identity = get_identity(display_name)
    if identity:
        if _norm(identity.get("game_nick")) == _norm(display_name):
            return {"type": "in_game", "confidence": identity.get("confidence", "high"), "identity": identity}
        return {"type": "tournament", "confidence": identity.get("confidence", "high"), "identity": identity}
    return {"type": "unknown", "confidence": "none", "identity": None}

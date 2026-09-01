import json
import os
from datetime import datetime

DATA_DIR = "data"
IN_GAME_NICKS_PATH = os.path.join(DATA_DIR, "in_game_nicks.json")
TOURNAMENT_NICKS_PATH = os.path.join(DATA_DIR, "tournament_nicks.json")
os.makedirs(DATA_DIR, exist_ok=True)


def _norm(value):
    return " ".join(str(value or "").strip().casefold().split())


def _load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_in_game_nicks():
    return _load(IN_GAME_NICKS_PATH)


def load_tournament_nicks():
    return _load(TOURNAMENT_NICKS_PATH)


def save_in_game_nicks(data):
    _save(IN_GAME_NICKS_PATH, data)


def save_tournament_nicks(data):
    _save(TOURNAMENT_NICKS_PATH, data)


def register_in_game_nick(name):
    """Register a name explicitly as an in-game nickname."""
    name = str(name or "").strip()
    if not name:
        return None
    key = _norm(name)
    in_game = load_in_game_nicks()
    tournament = load_tournament_nicks()
    item = {
        "name": name,
        "game_nick": name,
        "name_type": "in_game",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    in_game[key] = item
    tournament.pop(key, None)
    save_in_game_nicks(in_game)
    save_tournament_nicks(tournament)
    return item


def register_tournament_nick(tournament_nick, game_nick):
    """Register a tournament nickname and its actual in-game nickname."""
    tournament_nick = str(tournament_nick or "").strip()
    game_nick = str(game_nick or "").strip()
    if not tournament_nick or not game_nick:
        return None
    key = _norm(tournament_nick)
    tournament = load_tournament_nicks()
    in_game = load_in_game_nicks()
    item = {
        "name": tournament_nick,
        "game_nick": game_nick,
        "name_type": "tournament",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    tournament[key] = item
    in_game.pop(key, None)
    save_tournament_nicks(tournament)
    save_in_game_nicks(in_game)
    return item


def get_nickname_record(name):
    key = _norm(name)
    if not key:
        return None
    in_game = load_in_game_nicks().get(key)
    if in_game:
        return in_game
    tournament = load_tournament_nicks().get(key)
    if tournament:
        return tournament
    return None


def get_nickname_type(name):
    record = get_nickname_record(name)
    return record.get("name_type") if record else None


def get_game_nick(name):
    record = get_nickname_record(name)
    return record.get("game_nick") if record else None

import json
import os
import uuid
from datetime import datetime

DATA_DIR = "data"
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
PLAYERS_PATH = os.path.join(DATA_DIR, "players.json")
TEAMS_PATH = os.path.join(DATA_DIR, "teams.json")
os.makedirs(DATA_DIR, exist_ok=True)


def create_project():
    project = {"id": str(uuid.uuid4())[:8], "teams": [], "image_path": None}
    save_project(project)
    return project


def save_project(project):
    with open(os.path.join(DATA_DIR, f"{project['id']}.json"), "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)


def load_project(project_id):
    path = os.path.join(DATA_DIR, f"{project_id}.json")
    if not os.path.exists(path): return None
    with open(path, "r", encoding="utf-8") as f: return json.load(f)


def delete_project(project_id):
    path = os.path.join(DATA_DIR, f"{project_id}.json")
    if os.path.exists(path): os.remove(path)


def load_config():
    if not os.path.exists(CONFIG_PATH): return {"analysis_channels": []}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f: data = json.load(f)
        data.setdefault("analysis_channels", [])
        return data
    except Exception: return {"analysis_channels": []}


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(config, f, ensure_ascii=False, indent=2)


def load_players():
    if not os.path.exists(PLAYERS_PATH): return {}
    try:
        with open(PLAYERS_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {}


def save_players(players):
    with open(PLAYERS_PATH, "w", encoding="utf-8") as f: json.dump(players, f, ensure_ascii=False, indent=2)


def normalize_player_name(name):
    return " ".join(str(name).strip().lower().split())


def add_player(name, tag="", team="", notes=""):
    name = str(name).strip()
    if not name: return False
    players = load_players()
    key = normalize_player_name(name)
    existing = players.get(key, {})
    history = existing.get("history", [])
    players[key] = {
        "name": name,
        "tag": str(tag).strip() or existing.get("tag", ""),
        "team": str(team).strip() or existing.get("team", ""),
        "notes": str(notes).strip() or existing.get("notes", ""),
        "history": history,
    }
    save_players(players)
    return True


def remove_player(name):
    players = load_players()
    key = normalize_player_name(name)
    if key not in players: return False
    del players[key]
    save_players(players)
    return True


def get_player(name): return load_players().get(normalize_player_name(name))


def search_players(query):
    q = normalize_player_name(query)
    return [p for p in load_players().values() if q in normalize_player_name(p.get("name", ""))]


def update_player_team(name, new_team):
    name = str(name).strip()
    new_team = str(new_team).strip()
    if not name or not new_team: return {"status": "invalid", "name": name}
    players = load_players()
    key = normalize_player_name(name)
    player = players.get(key)
    if not player:
        add_player(name, team=new_team)
        return {"status": "new", "name": name, "team": new_team}

    old_team = str(player.get("team", "")).strip()
    if not old_team:
        player["team"] = new_team
        players[key] = player
        save_players(players)
        return {"status": "set", "name": player.get("name", name), "old_team": "", "team": new_team}

    if normalize_team(old_team) == normalize_team(new_team):
        return {"status": "same", "name": player.get("name", name), "old_team": old_team, "team": new_team}

    history = player.setdefault("history", [])
    now = datetime.now().strftime("%Y-%m-%d")
    if not any(normalize_team(h.get("team", "")) == normalize_team(old_team) and h.get("to") is None for h in history):
        history.append({"team": old_team, "from": None, "to": now})
    player["team"] = new_team
    players[key] = player
    save_players(players)
    return {"status": "changed", "name": player.get("name", name), "old_team": old_team, "team": new_team, "date": now}


def load_teams():
    if not os.path.exists(TEAMS_PATH): return {}
    try:
        with open(TEAMS_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {}


def save_teams(teams):
    with open(TEAMS_PATH, "w", encoding="utf-8") as f: json.dump(teams, f, ensure_ascii=False, indent=2)


def normalize_team(value):
    return " ".join(str(value).strip().lower().split())


def add_team(name, tag="", notes=""):
    name = str(name).strip()
    tag = str(tag).strip()
    if not name and not tag: return False
    teams = load_teams()
    key = normalize_team(name or tag)
    teams[key] = {"name": name, "tag": tag, "notes": str(notes).strip()}
    save_teams(teams)
    return True


def remove_team(value):
    teams = load_teams()
    key = normalize_team(value)
    if key in teams:
        del teams[key]
        save_teams(teams)
        return True
    for k, team in list(teams.items()):
        if normalize_team(team.get("name", "")) == key or normalize_team(team.get("tag", "")) == key:
            del teams[k]
            save_teams(teams)
            return True
    return False


def get_team(value):
    teams = load_teams()
    key = normalize_team(value)
    if key in teams: return teams[key]
    for team in teams.values():
        if normalize_team(team.get("name", "")) == key or normalize_team(team.get("tag", "")) == key:
            return team
    return None


def search_teams(query):
    q = normalize_team(query)
    return [t for t in load_teams().values() if q in normalize_team(t.get("name", "")) or q in normalize_team(t.get("tag", ""))]


def auto_register_player(name, team=""):
    name = str(name).strip()
    if not name or name == "[확인 필요]": return False
    if get_player(name): return False
    return add_player(name, team=team)


def auto_register_team(name, tag=""):
    name = str(name).strip()
    tag = str(tag).strip()
    if not name and not tag: return False
    if get_team(name or tag): return False
    return add_team(name, tag=tag)

import json
import os
import uuid

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
    players[key] = {"name": name, "tag": str(tag).strip(), "team": str(team).strip(), "notes": str(notes).strip()}
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

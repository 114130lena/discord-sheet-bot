import json
import os
import uuid

DATA_DIR = "data"
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
PLAYERS_PATH = os.path.join(DATA_DIR, "players.json")
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


def get_player(name):
    return load_players().get(normalize_player_name(name))


def search_players(query):
    q = normalize_player_name(query)
    return [p for p in load_players().values() if q in normalize_player_name(p.get("name", ""))]

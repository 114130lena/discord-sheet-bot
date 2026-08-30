import json
import os
import uuid
import shutil
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


def _edit_distance(a, b):
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    if len(a) > len(b): a, b = b, a
    prev = list(range(len(a) + 1))
    for i, cb in enumerate(b, 1):
        cur = [i]
        for j, ca in enumerate(a, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _fuzzy_match(query, candidates, normalizer):
    q = normalizer(query)
    if not q: return None
    scored = []
    for candidate in candidates:
        value = normalizer(candidate)
        if not value or value == q: continue
        distance = _edit_distance(q, value)
        max_len = max(len(q), len(value))
        ratio = 1 - (distance / max_len)
        if max_len <= 2: continue
        allowed = 1 if max_len <= 5 else 2
        if distance <= allowed and ratio >= (0.67 if max_len <= 5 else 0.75):
            scored.append((distance, -ratio, candidate))
    if not scored: return None
    scored.sort(key=lambda x: (x[0], x[1]))
    best = scored[0]
    if len(scored) > 1:
        second = scored[1]
        if best[0] == second[0] and abs(best[1] - second[1]) < 0.08:
            return None
    return best[2]


def add_player(name, tag="", team="", notes=""):
    name = str(name).strip()
    if not name: return False
    players = load_players(); key = normalize_player_name(name); existing = players.get(key, {})
    players[key] = {"name": name, "tag": str(tag).strip() or existing.get("tag", ""), "team": str(team).strip() or existing.get("team", ""), "notes": str(notes).strip() or existing.get("notes", ""), "history": existing.get("history", [])}
    save_players(players); return True


def remove_player(name):
    players = load_players(); key = normalize_player_name(name)
    if key not in players: return False
    del players[key]; save_players(players); return True


def get_player(name):
    players = load_players(); key = normalize_player_name(name)
    if key in players: return players[key]
    match = _fuzzy_match(name, [p.get("name", "") for p in players.values()], normalize_player_name)
    if match: return players.get(normalize_player_name(match))
    return None


def search_players(query):
    q = normalize_player_name(query); players = load_players()
    found = [p for p in players.values() if q in normalize_player_name(p.get("name", ""))]
    if found: return found
    match = _fuzzy_match(query, [p.get("name", "") for p in players.values()], normalize_player_name)
    if match: return [players[normalize_player_name(match)]]
    return []


def update_player_team(name, new_team):
    name = str(name).strip(); new_team = str(new_team).strip()
    if not name or not new_team: return {"status": "invalid", "name": name}
    players = load_players(); key = normalize_player_name(name); player = players.get(key)
    if not player:
        matched = get_player(name)
        if matched:
            key = normalize_player_name(matched.get("name", name)); player = players.get(key)
    if not player:
        add_player(name, team=new_team); return {"status": "new", "name": name, "team": new_team}
    old_team = str(player.get("team", "")).strip()
    if not old_team:
        player["team"] = new_team; players[key] = player; save_players(players)
        return {"status": "set", "name": player.get("name", name), "old_team": "", "team": new_team}
    if normalize_team(old_team) == normalize_team(new_team):
        return {"status": "same", "name": player.get("name", name), "old_team": old_team, "team": new_team}
    history = player.setdefault("history", []); now = datetime.now().strftime("%Y-%m-%d")
    history.append({"team": old_team, "from": None, "to": now})
    player["team"] = new_team; players[key] = player; save_players(players)
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
    name = str(name).strip(); tag = str(tag).strip()
    if not name and not tag: return False
    teams = load_teams(); key = normalize_team(name or tag)
    teams[key] = {"name": name, "tag": tag, "notes": str(notes).strip()}
    save_teams(teams); return True


def remove_team(value):
    teams = load_teams(); key = normalize_team(value)
    if key in teams:
        del teams[key]; save_teams(teams); return True
    for k, team in list(teams.items()):
        if normalize_team(team.get("name", "")) == key or normalize_team(team.get("tag", "")) == key:
            del teams[k]; save_teams(teams); return True
    return False


def get_team(value):
    teams = load_teams(); key = normalize_team(value)
    if key in teams: return teams[key]
    for team in teams.values():
        if normalize_team(team.get("name", "")) == key or normalize_team(team.get("tag", "")) == key: return team
    candidates = []
    for team in teams.values():
        if team.get("name"): candidates.append(team.get("name"))
        if team.get("tag"): candidates.append(team.get("tag"))
    match = _fuzzy_match(value, candidates, normalize_team)
    if match:
        for team in teams.values():
            if normalize_team(team.get("name", "")) == normalize_team(match) or normalize_team(team.get("tag", "")) == normalize_team(match): return team
    return None


def search_teams(query):
    q = normalize_team(query); teams = load_teams()
    found = [t for t in teams.values() if q in normalize_team(t.get("name", "")) or q in normalize_team(t.get("tag", ""))]
    if found: return found
    candidates = []
    for team in teams.values():
        if team.get("name"): candidates.append(team.get("name"))
        if team.get("tag"): candidates.append(team.get("tag"))
    match = _fuzzy_match(query, candidates, normalize_team)
    if match:
        return [t for t in teams.values() if normalize_team(t.get("name", "")) == normalize_team(match) or normalize_team(t.get("tag", "")) == normalize_team(match)]
    return []


def auto_register_player(name, team=""):
    name = str(name).strip()
    if not name or name == "[확인 필요]" or get_player(name): return False
    return add_player(name, team=team)


def auto_register_team(name, tag=""):
    name = str(name).strip(); tag = str(tag).strip()
    if (not name and not tag) or get_team(name or tag): return False
    return add_team(name, tag=tag)


def backup_databases(keep=30):
    backup_dir = os.path.join(DATA_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backed = []
    for path in (PLAYERS_PATH, TEAMS_PATH):
        if os.path.exists(path):
            dst = os.path.join(backup_dir, f"{os.path.basename(path)[:-5]}_{stamp}.json")
            shutil.copy2(path, dst); backed.append(dst)
    files = sorted((os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".json")), key=os.path.getmtime, reverse=True)
    for old in files[keep * 2:]:
        try: os.remove(old)
        except OSError: pass
    return backed

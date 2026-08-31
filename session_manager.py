import os
from datetime import datetime

from data import DATA_DIR, create_project, save_project, load_project, delete_project, normalize_team

MAX_TEAMS = 8


def new_session():
    project = create_project()
    now = datetime.now().isoformat(timespec="seconds")
    project.update({
        "session_id": project["id"],
        "session_created_at": now,
        "session_updated_at": now,
        "session_status": "active",
        "session_batches": [],
        "sheet_title": f"전력분석_세션_{project['id']}",
    })
    save_project(project)
    return project


def ensure_session(project):
    if not project:
        return None
    now = datetime.now().isoformat(timespec="seconds")
    project.setdefault("session_id", project.get("id"))
    project.setdefault("session_created_at", now)
    project.setdefault("session_updated_at", now)
    project.setdefault("session_status", "active")
    project.setdefault("session_batches", [])
    project.setdefault("sheet_title", f"전력분석_세션_{project.get('id','unknown')}")
    return project


def list_sessions():
    sessions = []
    try:
        filenames = os.listdir(DATA_DIR)
    except OSError:
        return sessions
    ignored = {"config.json", "players.json", "teams.json"}
    for filename in filenames:
        if not filename.endswith(".json") or filename in ignored or filename.startswith("players_") or filename.startswith("teams_"):
            continue
        if not os.path.isdir(os.path.join(DATA_DIR, filename)):
            try:
                project = ensure_session(load_project(filename[:-5]))
                if project and project.get("id") and "teams" in project:
                    sessions.append(project)
            except Exception:
                continue
    sessions.sort(key=lambda p: p.get("session_updated_at", ""), reverse=True)
    return sessions


def get_session(session_id):
    project = load_project(str(session_id).strip())
    return ensure_session(project)


def session_count(project):
    return len(project.get("teams", [])) if project else 0


def _team_key(team):
    name = normalize_team(team.get("team_name", ""))
    tag = normalize_team(team.get("team_tag", ""))
    return name or tag


def merge_teams(project, incoming):
    existing = project.setdefault("teams", [])
    normalized_existing = {_team_key(team): team for team in existing if _team_key(team)}
    added = 0
    duplicates = 0
    for team in incoming or []:
        key = _team_key(team)
        if key and key in normalized_existing:
            old = normalized_existing[key]
            for k, value in team.items():
                if value not in (None, "", [], {}):
                    old[k] = value
            duplicates += 1
        else:
            if len(existing) >= MAX_TEAMS:
                return {"ok": False, "added": added, "duplicates": duplicates, "reason": "max"}
            existing.append(team)
            if key:
                normalized_existing[key] = team
            added += 1
    return {"ok": True, "added": added, "duplicates": duplicates, "reason": "ok"}


def add_batch(project, incoming, image_count):
    incoming = incoming or []
    if len(project.get("teams", [])) > MAX_TEAMS:
        return {"ok": False, "reason": "max", "added": 0, "duplicates": 0}
    result = merge_teams(project, incoming)
    if not result["ok"]:
        return result
    project["session_updated_at"] = datetime.now().isoformat(timespec="seconds")
    project["session_status"] = "active"
    batches = project.setdefault("session_batches", [])
    batches.append({
        "batch": len(batches) + 1,
        "timestamp": project["session_updated_at"],
        "image_count": int(image_count),
        "teams_found": len(incoming),
        "teams_added": result["added"],
        "teams_merged": result["duplicates"],
    })
    save_project(project)
    return result


def mark_status(project, status):
    project["session_status"] = status
    project["session_updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_project(project)
    return project

import os
import shutil
from datetime import datetime

from data import DATA_DIR, create_project, save_project, load_project, delete_project, normalize_team

MAX_TEAMS = 8
BACKUP_DIR = os.path.join(DATA_DIR, "session_backups")
os.makedirs(BACKUP_DIR, exist_ok=True)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _session_path(project):
    return os.path.join(DATA_DIR, f"{project.get('id')}.json")


def _normalize_status(status):
    return status if status in {"active", "paused", "completed"} else "active"


def ensure_session(project):
    if not project:
        return None
    now = _now()
    project.setdefault("session_id", project.get("id"))
    project.setdefault("session_name", f"세션 {project.get('id', 'unknown')}")
    project.setdefault("event_name", "")
    project.setdefault("session_created_at", now)
    project.setdefault("session_updated_at", now)
    project["session_status"] = _normalize_status(project.get("session_status", "active"))
    project.setdefault("session_batches", [])
    project.setdefault("session_guild_id", None)
    project.setdefault("session_channel_id", None)
    project.setdefault("session_owner_id", None)
    project.setdefault("session_backup_count", 0)
    project.setdefault("sheet_title", f"전력분석_{project.get('session_id', 'unknown')}")
    return project


def new_session(event_name="", session_name="", guild_id=None, channel_id=None, owner_id=None):
    project = ensure_session(create_project())
    now = _now()
    sid = project["id"]
    project.update({
        "session_id": sid,
        "session_name": (str(session_name).strip() or f"세션 {sid}"),
        "event_name": str(event_name).strip(),
        "session_created_at": now,
        "session_updated_at": now,
        "session_status": "active",
        "session_batches": [],
        "session_guild_id": str(guild_id) if guild_id is not None else None,
        "session_channel_id": str(channel_id) if channel_id is not None else None,
        "session_owner_id": str(owner_id) if owner_id is not None else None,
        "session_backup_count": 0,
        "sheet_title": f"전력분석_{sid}",
    })
    save_project(project)
    backup_session(project)
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
        path = os.path.join(DATA_DIR, filename)
        if os.path.isdir(path):
            continue
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


def _team_aliases(team):
    values = []
    for key in ("team_name", "team_tag"):
        value = normalize_team(team.get(key, ""))
        if value:
            values.append(value)
    return values


def merge_teams(project, incoming):
    project = ensure_session(project)
    existing = project.setdefault("teams", [])
    normalized_existing = {}
    for team in existing:
        for alias in _team_aliases(team):
            normalized_existing[alias] = team
    added = 0
    duplicates = 0
    for team in incoming or []:
        aliases = _team_aliases(team)
        match = next((normalized_existing[a] for a in aliases if a in normalized_existing), None)
        if match is not None:
            for k, value in team.items():
                if value not in (None, "", [], {}):
                    match[k] = value
            duplicates += 1
            continue
        if len(existing) >= MAX_TEAMS:
            return {"ok": False, "added": added, "duplicates": duplicates, "reason": "max"}
        existing.append(team)
        for alias in aliases:
            normalized_existing[alias] = team
        added += 1
    return {"ok": True, "added": added, "duplicates": duplicates, "reason": "ok"}


def add_batch(project, incoming, image_count):
    project = ensure_session(project)
    incoming = incoming or []
    result = merge_teams(project, incoming)
    if not result["ok"]:
        return result
    project["session_updated_at"] = _now()
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
    backup_session(project)
    return result


def backup_session(project):
    project = ensure_session(project)
    path = _session_path(project)
    if not os.path.exists(path):
        save_project(project)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    sid = project.get("session_id", project.get("id", "unknown"))
    dst = os.path.join(BACKUP_DIR, f"{sid}_{stamp}.json")
    shutil.copy2(path, dst)
    project["session_backup_count"] = int(project.get("session_backup_count", 0)) + 1
    # Update the source project without recursively backing it up.
    save_project(project)
    files = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".json")]
    files.sort(key=os.path.getmtime, reverse=True)
    for old in files[100:]:
        try:
            os.remove(old)
        except OSError:
            pass
    return dst


def can_access(project, guild_id=None, channel_id=None, user_id=None, allow_admin=False):
    project = ensure_session(project)
    if project.get("session_guild_id") and guild_id is not None and str(project["session_guild_id"]) != str(guild_id):
        return False
    if project.get("session_channel_id") and channel_id is not None and str(project["session_channel_id"]) != str(channel_id):
        return bool(allow_admin)
    if project.get("session_owner_id") and user_id is not None and str(project["session_owner_id"]) != str(user_id):
        return bool(allow_admin)
    return True


def mark_status(project, status):
    project = ensure_session(project)
    project["session_status"] = _normalize_status(status)
    project["session_updated_at"] = _now()
    save_project(project)
    backup_session(project)
    return project

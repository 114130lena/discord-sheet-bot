from player_resolver import classify_name, resolve_identity, save_identity
from dakgg import get_character_stats


def enrich_project_identities(project, try_bori=True):
    identities = {}
    for team in project.get("teams", []):
        for index in range(1, 5):
            name = str(team.get(f"player{index}", "")).strip()
            if not name or name == "[확인 필요]":
                continue
            classified = classify_name(name)
            if classified.get("type") == "in_game":
                identity = classified.get("identity") or {}
                identities[name] = {"display_name": name, "game_nick": identity.get("game_nick", name), "name_type": "in_game", "source": identity.get("source", "cache"), "confidence": identity.get("confidence", "high")}
                continue
            resolved = resolve_identity(name, try_bori=try_bori)
            identities[name] = {"display_name": name, "game_nick": resolved.get("game_nick"), "name_type": "tournament" if resolved.get("game_nick") else "unknown", "source": resolved.get("source", ""), "confidence": resolved.get("confidence", "none"), "status": resolved.get("status", "unresolved")}
    project["player_identities"] = identities
    return identities


def set_manual_game_nick(project, display_name, game_nick):
    saved = save_identity(display_name, game_nick, source="manual", confidence="high")
    identities = project.setdefault("player_identities", {})
    identities[str(display_name).strip()] = {"display_name": str(display_name).strip(), "game_nick": saved["game_nick"], "name_type": "tournament" if saved["game_nick"].lower() != str(display_name).strip().lower() else "in_game", "source": "manual", "confidence": "high", "status": "resolved"}
    return identities[str(display_name).strip()]


def analyze_player(project, display_name, top_n=3, force_refresh=False):
    identities = project.setdefault("player_identities", {})
    identity = identities.get(display_name)
    if not identity:
        identity = resolve_identity(display_name, try_bori=True)
        identity = {"display_name": display_name, "game_nick": identity.get("game_nick"), "source": identity.get("source", ""), "confidence": identity.get("confidence", "none")}
        identities[display_name] = identity
    game_nick = identity.get("game_nick")
    if not game_nick:
        return {"status": "manual_required", "display_name": display_name, "characters": []}
    stats = get_character_stats(game_nick, top_n=top_n, force_refresh=force_refresh)
    stats["display_name"] = display_name
    stats["identity_source"] = identity.get("source", "")
    project.setdefault("player_stats", {})[display_name] = stats
    return stats


def analyze_all_players(project, top_n=3, force_refresh=False):
    results = {}
    for team in project.get("teams", []):
        for index in range(1, 5):
            name = str(team.get(f"player{index}", "")).strip()
            if name and name != "[확인 필요]":
                results[name] = analyze_player(project, name, top_n=top_n, force_refresh=force_refresh)
    return results

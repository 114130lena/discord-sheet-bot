from player_resolver import classify_name, resolve_identity, save_identity
from nickname_db import get_nickname_record, register_in_game_nick, register_tournament_nick
from dakgg import get_character_stats


def _explicit_identity(name):
    record = get_nickname_record(name)
    if not record:
        return None

    name_type = record.get("name_type")
    if name_type == "in_game":
        return {
            "display_name": name,
            "game_nick": record.get("game_nick") or name,
            "name_type": "in_game",
            "source": "in_game_nicks_db",
            "confidence": "high",
            "status": "resolved",
        }

    if name_type == "tournament":
        return {
            "display_name": name,
            "game_nick": record.get("game_nick"),
            "name_type": "tournament",
            "source": "tournament_nicks_db",
            "confidence": "high",
            "status": "resolved" if record.get("game_nick") else "unresolved",
        }

    return None


def enrich_project_identities(project, try_bori=True):
    identities = {}
    for team in project.get("teams", []):
        for index in range(1, 5):
            name = str(team.get(f"player{index}", "")).strip()
            if not name or name == "[확인 필요]":
                continue

            # Explicit nickname-type DB always has priority over auto detection.
            explicit = _explicit_identity(name)
            if explicit:
                identities[name] = explicit
                continue

            classified = classify_name(name)
            if classified.get("type") == "in_game":
                identity = classified.get("identity") or {}
                identities[name] = {
                    "display_name": name,
                    "game_nick": identity.get("game_nick", name),
                    "name_type": "in_game",
                    "source": identity.get("source", "cache"),
                    "confidence": identity.get("confidence", "high"),
                    "status": identity.get("status", "resolved"),
                }
                continue

            resolved = resolve_identity(name, try_bori=try_bori)
            identities[name] = {
                "display_name": name,
                "game_nick": resolved.get("game_nick"),
                "name_type": "tournament" if resolved.get("game_nick") else "unknown",
                "source": resolved.get("source", ""),
                "confidence": resolved.get("confidence", "none"),
                "status": resolved.get("status", "unresolved"),
            }

    project["player_identities"] = identities
    return identities


def set_manual_game_nick(project, display_name, game_nick):
    display_name = str(display_name).strip()
    game_nick = str(game_nick).strip()
    if display_name.lower() == game_nick.lower():
        return set_manual_in_game_nick(project, display_name)

    saved = save_identity(
        display_name,
        game_nick,
        source="manual",
        confidence="high",
    )
    register_tournament_nick(display_name, game_nick)

    identities = project.setdefault("player_identities", {})
    identities[display_name] = {
        "display_name": display_name,
        "game_nick": saved["game_nick"],
        "name_type": "tournament",
        "source": "tournament_nicks_db",
        "confidence": "high",
        "status": "resolved",
    }
    return identities[display_name]


def set_manual_in_game_nick(project, display_name):
    display_name = str(display_name).strip()
    saved = register_in_game_nick(display_name)
    if not saved:
        raise ValueError("빈 닉네임은 인게임 닉네임으로 등록할 수 없습니다.")

    identities = project.setdefault("player_identities", {})
    identities[display_name] = {
        "display_name": display_name,
        "game_nick": saved["game_nick"],
        "name_type": "in_game",
        "source": "in_game_nicks_db",
        "confidence": "high",
        "status": "resolved",
    }
    return identities[display_name]


def analyze_player(project, display_name, top_n=3, force_refresh=False):
    display_name = str(display_name).strip()
    identities = project.setdefault("player_identities", {})

    # Explicit nickname DB must override an old unresolved identity cached in
    # the current project. This fixes nicknames that are registered after the
    # first roster analysis but still fail during the full analysis.
    explicit = _explicit_identity(display_name)
    if explicit:
        identity = explicit
    else:
        identity = identities.get(display_name)

    if not identity or not identity.get("game_nick"):
        resolved = resolve_identity(display_name, try_bori=True)
        identity = {
            "display_name": display_name,
            "game_nick": resolved.get("game_nick"),
            "name_type": "tournament" if resolved.get("game_nick") else "unknown",
            "source": resolved.get("source", ""),
            "confidence": resolved.get("confidence", "none"),
            "status": resolved.get("status", "unresolved"),
        }

    identities[display_name] = identity
    game_nick = identity.get("game_nick")
    if not game_nick:
        return {
            "status": "manual_required",
            "display_name": display_name,
            "characters": [],
        }

    stats = get_character_stats(
        game_nick,
        top_n=top_n,
        force_refresh=force_refresh,
    )
    stats["display_name"] = display_name
    stats["identity_source"] = identity.get("source", "")
    stats["name_type"] = identity.get("name_type", "unknown")
    project.setdefault("player_stats", {})[display_name] = stats
    return stats


def analyze_all_players(project, top_n=3, force_refresh=False):
    results = {}
    seen = set()

    for team in project.get("teams", []):
        for index in range(1, 5):
            name = str(team.get(f"player{index}", "")).strip()
            if not name or name == "[확인 필요]" or name in seen:
                continue

            seen.add(name)
            results[name] = analyze_player(
                project,
                name,
                top_n=top_n,
                force_refresh=force_refresh,
            )

    return results

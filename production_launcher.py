import re

BOT_PATH = "bot.py"
source = open(BOT_PATH, "r", encoding="utf-8").read()

# Use the enhanced session-aware UI and session manager without rewriting the
# repository's original bot.py command implementations.
source = source.replace(
    "from ui import ProjectView, project_embed",
    "from session_ui import ProjectView, project_embed",
    1,
)
source = source.replace(
    "from sheets import update_spreadsheet",
    "from sheets import update_spreadsheet\nfrom session_manager import new_session, get_session, list_sessions, add_batch, mark_status, can_access, MAX_TEAMS, backup_session",
    1,
)
source = "from datetime import datetime\n" + source
source = source.replace(
    "analysis_waiting = {}\ncurrent_projects = {}",
    "analysis_waiting = {}\ncurrent_projects = {}\nresult_delete_tasks = {}",
    1,
)

helpers = r'''

def _is_admin(interaction):
    try:
        return bool(interaction.user.guild_permissions.manage_guild)
    except Exception:
        return False


def _can_use_session(project, interaction, allow_admin=True):
    return can_access(
        project,
        guild_id=interaction.guild_id,
        channel_id=interaction.channel_id,
        user_id=interaction.user.id,
        allow_admin=allow_admin and _is_admin(interaction),
    )


def _session_label(project):
    return project.get("session_name") or project.get("event_name") or project.get("session_id") or project.get("id", "-")


async def _start_session_batch(channel, status_message, project):
    old_delete = result_delete_tasks.pop(channel.id, None)
    if old_delete:
        old_delete.cancel()
    state = {
        "status_message": status_message,
        "images": [],
        "timer_task": None,
        "debounce_task": None,
        "project": project,
    }
    analysis_waiting[channel.id] = state
    state["timer_task"] = asyncio.create_task(analysis_timeout(channel, state))
    return state
'''
source = source.replace("def persist_channels():", helpers + "\n\ndef persist_channels():", 1)

run_analysis_pattern = r"async def run_analysis\(channel, state\):.*?(?=\n\nasync def debounce_analysis)"
run_analysis_replacement = r'''async def run_analysis(channel, state):
    if analysis_waiting.get(channel.id) is not state:
        return
    status = state["status_message"]
    try:
        analysis_waiting.pop(channel.id, None)
        timer = state.get("timer_task")
        if timer and timer is not asyncio.current_task():
            timer.cancel()
        await status.edit(content="🔍 **사진을 분석하고 있습니다.**\n잠시만 기다려 주세요.", embed=None, view=None)
        images = list(state["images"])
        result = await asyncio.to_thread(analyze_images, images)

        project = state.get("project") or current_projects.get(channel.id)
        if project is None:
            project = new_session(guild_id=channel.guild.id if channel.guild else None, channel_id=channel.id)
        merge = add_batch(project, result.get("teams", []), len(images))
        if not merge.get("ok"):
            await status.edit(
                content=f"❌ **세션은 최대 {MAX_TEAMS}팀까지 등록할 수 있습니다.**\n현재 {len(project.get('teams', []))}팀이 등록되어 있어 이번 분석 결과는 반영하지 않았습니다.",
                embed=project_embed(project),
                view=ProjectView(project, save_project_to_sheet, apply_db_updates),
            )
            current_projects[channel.id] = project
            result_delete_tasks[channel.id] = asyncio.create_task(delete_result_later(status, 300))
            return

        canonicalize_teams(project)
        transfer_changes = canonicalize_players(project)
        current_projects[channel.id] = project
        save_project(project)
        backup_session(project)

        suggestions = project.get("db_suggestions", {})
        total = len(project.get("teams", []))
        batches = project.get("session_batches", [])
        message = (
            f"📋 **세션 분석 완료.**\n"
            f"세션: **{_session_label(project)}**\n"
            f"이번 분석: **{len(result.get('teams', []))}팀** · 추가 **{merge.get('added', 0)}팀** · "
            f"중복 병합 **{merge.get('duplicates', 0)}팀** · 누적 **{total}/{MAX_TEAMS}팀**\n"
            f"📦 분석 묶음: **{len(batches)}회** · 최근 분석: `{project.get('session_updated_at', '-')}`\n"
            f"필요하면 `/세션추가 {project.get('session_id')}`로 이 세션을 계속 이어서 작업할 수 있습니다."
        )
        if suggestions.get("players"):
            message += f"\n🆕 신규 선수 **{len(suggestions['players'])}명** 발견"
        if suggestions.get("teams"):
            message += f"\n🆕 신규 팀 **{len(suggestions['teams'])}개** 발견"
        if transfer_changes:
            message += "\n🔄 **이적 의심**\n" + "\n".join(
                f"• **{c['name']}** {c.get('old_team') or '무소속'} → **{c['team']}**"
                for c in transfer_changes
            )

        await status.edit(
            content=message,
            embed=project_embed(project),
            view=ProjectView(project, save_project_to_sheet, apply_db_updates),
        )
        result_delete_tasks[channel.id] = asyncio.create_task(delete_result_later(status, 300))
        print(
            f"Gemini 분석 완료: 세션 {project['session_id']} / 묶음 {len(batches)} / "
            f"누적 {total}/{MAX_TEAMS}팀 / 이미지 {len(images)}장"
        )
    except asyncio.CancelledError:
        return
    except Exception as e:
        analysis_waiting.pop(channel.id, None)
        print("분석 오류:", repr(e))
        try:
            await status.edit(
                content=f"❌ **분석 중 오류가 발생했습니다.**\n`{type(e).__name__}: {e}`",
                embed=None,
                view=None,
            )
        except Exception:
            pass'''
source = re.sub(run_analysis_pattern, run_analysis_replacement, source, count=1, flags=re.S)

start_pattern = r"@bot\.tree\.command\(name=\"전력분석\", description=\".*?\"\)\nasync def start_analysis\(interaction\):.*?(?=\n\n@bot\.tree\.command\(name=\"전력분석초기화\")"
start_replacement = r'''@bot.tree.command(name="전력분석", description="새 전력분석 세션을 시작합니다.")
async def start_analysis(interaction, 대회명: str = "", 세션명: str = ""):
    channel_id = interaction.channel_id
    if channel_id not in analysis_channels:
        await interaction.response.send_message(
            "❌ 이 채널은 전력분석 채널이 아닙니다. 먼저 `/분석채널설정`을 사용해 주세요.",
            ephemeral=True,
        )
        return
    if channel_id in analysis_waiting:
        await interaction.response.send_message("⏳ 이미 사진을 기다리고 있습니다.", ephemeral=True)
        return

    project = new_session(
        event_name=대회명,
        session_name=세션명,
        guild_id=interaction.guild_id,
        channel_id=interaction.channel_id,
        owner_id=interaction.user.id,
    )
    current_projects[channel_id] = project

    label = project.get("session_name") or project.get("event_name") or project.get("session_id")
    description = "🆕 **새 전력분석 세션을 시작했습니다.**"
    if 대회명:
        description += f"\n🏆 대회: **{대회명}**"
    if 세션명:
        description += f"\n📂 세션: **{세션명}**"
    else:
        description += f"\n📂 세션: **{label}**"
    description += "\n사진을 업로드해 주세요. 여러 장을 연속으로 업로드할 수 있습니다.\n⏱️ **30초 후 자동 분석됩니다.**"
    await interaction.response.send_message(description)
    status = await interaction.original_response()
    await _start_session_batch(interaction.channel, status, project)'''
source = re.sub(start_pattern, start_replacement, source, count=1, flags=re.S)

on_ready_pattern = r"@bot\.event\nasync def on_ready\(\):.*?(?=\n@bot\.tree\.command)"
on_ready_replacement = '''@bot.event
async def on_ready():
    print("=" * 50)
    print(f"로그인 완료: {bot.user}")
    print(f"서버 수: {len(bot.guilds)} / 분석 채널: {len(analysis_channels)}개")
    print("=" * 50)
    try:
        commands_to_sync = list(bot.tree.get_commands())
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        for guild in bot.guilds:
            bot.tree.clear_commands(guild=guild)
            for command in commands_to_sync:
                bot.tree.add_command(command, guild=guild, override=True)
            synced = await bot.tree.sync(guild=guild)
            print(f"[{guild.name}] Slash Command {len(synced)}개 동기화 완료")
            print("등록 명령어:", ", ".join(command.name for command in synced))
        for command in commands_to_sync:
            bot.tree.add_command(command, override=True)
    except Exception as e:
        print(f"Slash Command 동기화 오류: {type(e).__name__}: {e}")'''
source = re.sub(on_ready_pattern, on_ready_replacement, source, count=1, flags=re.S)

# Replace the persistent-session command block with a protected, user-friendly one.
session_commands_pattern = r"from session_manager import list_sessions, get_session, mark_status.*?\n\nif not TOKEN:"
session_commands_replacement = r'''from session_manager import list_sessions, get_session, mark_status


@bot.tree.command(name="세션목록", description="저장된 전력분석 세션 목록을 확인합니다.")
async def session_list_command(interaction):
    sessions = list_sessions()
    visible = [p for p in sessions if p.get("session_guild_id") in (None, str(interaction.guild_id)) and (p.get("session_owner_id") in (None, str(interaction.user.id)) or _is_admin(interaction))]
    if not visible:
        await interaction.response.send_message("📂 저장된 전력분석 세션이 없습니다.", ephemeral=True)
        return
    lines = []
    for p in visible[:20]:
        sid = p.get("session_id", p.get("id", "-"))
        name = _session_label(p)
        status = p.get("session_status", "active")
        status_text = {"active": "진행 중", "paused": "보류", "completed": "완료"}.get(status, status)
        created = p.get("session_created_at", "-").replace("T", " ")
        event = p.get("event_name") or "대회 미지정"
        lines.append(f"• **{name}** · `{sid}` · {event} · {len(p.get('teams', []))}/{MAX_TEAMS}팀 · {status_text} · {created}")
    await interaction.response.send_message("📂 **전력분석 세션 목록**\n" + "\n".join(lines) + "\n\n`/세션추가 세션ID`로 기존 세션을 이어서 작업할 수 있습니다.", ephemeral=True)


@bot.tree.command(name="세션정보", description="전력분석 세션의 상세 정보를 확인합니다.")
async def session_info_command(interaction, 세션ID: str):
    project = get_session(세션ID)
    if not project or not _can_use_session(project, interaction):
        await interaction.response.send_message("❌ 해당 세션을 찾을 수 없거나 접근 권한이 없습니다.", ephemeral=True)
        return
    batches = project.get("session_batches", [])
    lines = [
        f"📂 **{_session_label(project)}**",
        f"세션 ID: `{project.get('session_id', project.get('id'))}`",
        f"대회: **{project.get('event_name') or '-'}**",
        f"상태: **{project.get('session_status', 'active')}**",
        f"팀: **{len(project.get('teams', []))}/{MAX_TEAMS}**",
        f"생성: `{project.get('session_created_at', '-')}`",
        f"최근 수정: `{project.get('session_updated_at', '-')}`",
        f"분석 묶음: **{len(batches)}회**",
    ]
    if batches:
        lines.append("분석 이력: " + " / ".join(f"#{b.get('batch')} {b.get('teams_found', 0)}팀 {b.get('timestamp', '')}" for b in batches[-6:]))
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bot.tree.command(name="세션불러오기", description="저장된 전력분석 세션을 현재 채널에서 불러옵니다.")
async def session_load_command(interaction, 세션ID: str):
    project = get_session(세션ID)
    if not project or not _can_use_session(project, interaction):
        await interaction.response.send_message("❌ 해당 세션을 찾을 수 없거나 접근 권한이 없습니다.", ephemeral=True)
        return
    if len(project.get("teams", [])) > MAX_TEAMS:
        await interaction.response.send_message(f"❌ 세션 데이터가 {MAX_TEAMS}팀 제한을 초과했습니다.", ephemeral=True)
        return
    current_projects[interaction.channel_id] = project
    project["session_status"] = "active"
    project["session_updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_project(project)
    backup_session(project)
    await interaction.response.send_message(
        content=f"📂 **세션을 불러왔습니다.**\n**{_session_label(project)}** · `{project.get('session_id', project.get('id'))}` · 현재 **{len(project.get('teams', []))}/{MAX_TEAMS}팀**",
        embed=project_embed(project),
        view=ProjectView(project, save_project_to_sheet, apply_db_updates),
        ephemeral=True,
    )


@bot.tree.command(name="세션추가", description="저장된 세션에 추가 분석 사진을 입력합니다.")
async def session_add_command(interaction, 세션ID: str):
    channel_id = interaction.channel_id
    if channel_id not in analysis_channels:
        await interaction.response.send_message("❌ 이 채널은 전력분석 채널이 아닙니다.", ephemeral=True)
        return
    if channel_id in analysis_waiting:
        await interaction.response.send_message("⏳ 이미 사진을 기다리고 있습니다.", ephemeral=True)
        return
    project = get_session(세션ID)
    if not project or not _can_use_session(project, interaction):
        await interaction.response.send_message("❌ 해당 세션을 찾을 수 없거나 접근 권한이 없습니다.", ephemeral=True)
        return
    if len(project.get("teams", [])) >= MAX_TEAMS:
        await interaction.response.send_message(f"❌ 이 세션은 이미 {MAX_TEAMS}팀으로 완료되었습니다.", ephemeral=True)
        return
    current_projects[channel_id] = project
    await interaction.response.send_message(
        f"➕ **{_session_label(project)}**에 추가 분석을 시작합니다.\n현재 **{len(project.get('teams', []))}/{MAX_TEAMS}팀**\n사진을 업로드해 주세요.\n⏱️ **30초 후 자동 분석됩니다.**"
    )
    status = await interaction.original_response()
    await _start_session_batch(interaction.channel, status, project)


@bot.tree.command(name="세션보류", description="전력분석 세션을 보류 상태로 저장합니다.")
async def session_pause_command(interaction, 세션ID: str):
    project = get_session(세션ID)
    if not project or not _can_use_session(project, interaction):
        await interaction.response.send_message("❌ 해당 세션을 찾을 수 없거나 접근 권한이 없습니다.", ephemeral=True)
        return
    mark_status(project, "paused")
    if current_projects.get(interaction.channel_id, {}).get("id") == project.get("id"):
        current_projects.pop(interaction.channel_id, None)
    await interaction.response.send_message(f"⏸️ **{_session_label(project)}** 세션을 보류 상태로 저장했습니다.", ephemeral=True)


@bot.tree.command(name="세션완료", description="전력분석 세션을 완료 상태로 저장합니다.")
async def session_complete_command(interaction, 세션ID: str):
    project = get_session(세션ID)
    if not project or not _can_use_session(project, interaction):
        await interaction.response.send_message("❌ 해당 세션을 찾을 수 없거나 접근 권한이 없습니다.", ephemeral=True)
        return
    mark_status(project, "completed")
    if current_projects.get(interaction.channel_id, {}).get("id") == project.get("id"):
        current_projects.pop(interaction.channel_id, None)
    await interaction.response.send_message(f"✅ **{_session_label(project)}** 세션을 완료 상태로 저장했습니다.", ephemeral=True)


@bot.tree.command(name="세션삭제", description="저장된 전력분석 세션을 삭제합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def session_delete_command(interaction, 세션ID: str):
    project = get_session(세션ID)
    if not project or not _can_use_session(project):
        await interaction.response.send_message("❌ 해당 세션을 찾을 수 없거나 접근 권한이 없습니다.", ephemeral=True)
        return
    delete_project(project.get("id", 세션ID))
    if current_projects.get(interaction.channel_id, {}).get("id") == project.get("id"):
        current_projects.pop(interaction.channel_id, None)
    await interaction.response.send_message(f"🗑️ **{_session_label(project)}** 세션을 삭제했습니다.", ephemeral=True)


if not TOKEN:'''
source = re.sub(session_commands_pattern, session_commands_replacement, source, count=1, flags=re.S)

if 'name="세션목록"' not in source or 'name="세션추가"' not in source:
    raise RuntimeError("session command injection failed")

exec(compile(source, BOT_PATH, "exec"), {"__name__": "__main__", "__file__": BOT_PATH})

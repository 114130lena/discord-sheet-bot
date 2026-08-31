import re

BOT_PATH = "bot.py"
source = open(BOT_PATH, "r", encoding="utf-8").read()

source = "from datetime import datetime\n" + source
source = source.replace("analysis_waiting = {}\ncurrent_projects = {}", "analysis_waiting = {}\ncurrent_projects = {}\nresult_delete_tasks = {}")

helpers = r'''

def _merge_team_results(existing, incoming):
    added = 0
    duplicate = 0
    for new_team in incoming or []:
        new_name = str(new_team.get("team_name", "")).strip().lower()
        new_tag = str(new_team.get("team_tag", "")).strip().lower()
        match = None
        for old_team in existing:
            old_name = str(old_team.get("team_name", "")).strip().lower()
            old_tag = str(old_team.get("team_tag", "")).strip().lower()
            if new_name and (new_name == old_name or new_name == old_tag):
                match = old_team
                break
            if new_tag and (new_tag == old_name or new_tag == old_tag):
                match = old_team
                break
        if match is None:
            if len(existing) >= 8:
                return {"ok": False, "added": added, "duplicate": duplicate, "reason": "max"}
            existing.append(new_team)
            added += 1
        else:
            for key, value in new_team.items():
                if value not in (None, "", [], {}):
                    match[key] = value
            duplicate += 1
    return {"ok": True, "added": added, "duplicate": duplicate, "reason": "ok"}


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
            project = create_project()
            project["session_id"] = project.get("id")
            project["session_created_at"] = datetime.now().isoformat(timespec="seconds")
            project["session_updated_at"] = project["session_created_at"]
            project["session_status"] = "active"
            project["session_batches"] = []
            project["sheet_title"] = f"전력분석_세션_{project['session_id']}"

        incoming = result.get("teams", [])
        merge = _merge_team_results(project.setdefault("teams", []), incoming)
        if not merge["ok"]:
            await status.edit(content=f"❌ **세션은 최대 8팀까지 등록할 수 있습니다.**\n현재 {len(project.get('teams', []))}팀이 등록되어 있어 이번 분석 결과를 추가하지 않았습니다.", embed=project_embed(project), view=ProjectView(project, save_project_to_sheet, apply_db_updates))
            current_projects[channel.id] = project
            save_project(project)
            result_delete_tasks[channel.id] = asyncio.create_task(delete_result_later(status, 300))
            return

        project["session_updated_at"] = datetime.now().isoformat(timespec="seconds")
        project["session_status"] = "active"
        batch_no = len(project.setdefault("session_batches", [])) + 1
        project["session_batches"].append({
            "batch": batch_no,
            "timestamp": project["session_updated_at"],
            "image_count": len(images),
            "teams_found": len(incoming),
            "teams_added": merge["added"],
            "teams_merged": merge["duplicate"],
        })

        canonicalize_teams(project)
        transfer_changes = canonicalize_players(project)
        current_projects[channel.id] = project
        suggestions = project.get("db_suggestions", {})
        total = len(project.get("teams", []))
        message = f"📋 **세션 분석 완료.**\n이번 분석: **{len(incoming)}팀** · 추가 **{merge['added']}팀** · 중복 병합 **{merge['duplicate']}팀** · 누적 **{total}/8팀**\n필요하면 `/전력분석`을 실행해 새 세션을 시작하거나 `/세션추가 세션ID`로 기존 세션을 이어서 분석할 수 있습니다."
        if suggestions.get("players"):
            message += f"\n🆕 신규 선수 **{len(suggestions['players'])}명** 발견"
        if suggestions.get("teams"):
            message += f"\n🆕 신규 팀 **{len(suggestions['teams'])}개** 발견"
        if transfer_changes:
            message += "\n🔄 **이적 의심**\n" + "\n".join(f"• **{c['name']}** {c.get('old_team') or '무소속'} → **{c['team']}**" for c in transfer_changes)

        await status.edit(content=message, embed=project_embed(project), view=ProjectView(project, save_project_to_sheet, apply_db_updates))
        save_project(project)
        result_delete_tasks[channel.id] = asyncio.create_task(delete_result_later(status, 300))
        print(f"Gemini 분석 완료: 세션 {project['session_id']} / 묶음 {batch_no} / 누적 {total}/8팀 / 이미지 {len(images)}장")
    except asyncio.CancelledError:
        return
    except Exception as e:
        analysis_waiting.pop(channel.id, None)
        print("분석 오류:", repr(e))
        try:
            await status.edit(content=f"❌ **분석 중 오류가 발생했습니다.**\n`{type(e).__name__}: {e}`", embed=None, view=None)
        except Exception:
            pass'''
source = re.sub(run_analysis_pattern, run_analysis_replacement, source, count=1, flags=re.S)

start_pattern = r"@bot\.tree\.command\(name=\"전력분석\", description=\".*?\"\)\nasync def start_analysis\(interaction\):.*?(?=\n\n@bot\.tree\.command\(name=\"전력분석초기화\")"
start_replacement = r'''@bot.tree.command(name="전력분석", description="새 전력분석 세션을 시작합니다.")
async def start_analysis(interaction):
    channel_id = interaction.channel_id
    if channel_id not in analysis_channels:
        await interaction.response.send_message("❌ 이 채널은 전력분석 채널이 아닙니다. 먼저 `/분석채널설정`을 사용해 주세요.", ephemeral=True)
        return
    if channel_id in analysis_waiting:
        await interaction.response.send_message("⏳ 이미 사진을 기다리고 있습니다.", ephemeral=True)
        return

    project = create_project()
    now = datetime.now().isoformat(timespec="seconds")
    project.update({
        "session_id": project.get("id"),
        "session_created_at": now,
        "session_updated_at": now,
        "session_status": "active",
        "session_batches": [],
        "sheet_title": f"전력분석_세션_{project.get('id')}"
    })
    save_project(project)
    current_projects[channel_id] = project

    await interaction.response.send_message("🆕 **새 전력분석 세션을 시작했습니다.**\n사진을 업로드해 주세요. 여러 장을 연속으로 업로드할 수 있습니다.\n⏱️ **30초 후 자동 분석됩니다.**")
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

session_commands = r'''

from session_manager import list_sessions, get_session, mark_status


@bot.tree.command(name="세션목록", description="저장된 전력분석 세션 목록을 확인합니다.")
async def session_list_command(interaction):
    sessions = list_sessions()
    if not sessions:
        await interaction.response.send_message("📂 저장된 전력분석 세션이 없습니다.", ephemeral=True)
        return
    lines = []
    for p in sessions[:20]:
        sid = p.get("session_id", p.get("id", "-"))
        status = p.get("session_status", "active")
        status_text = "진행 중" if status == "active" else ("보류" if status == "paused" else "완료")
        created = p.get("session_created_at", "-").replace("T", " ")
        lines.append(f"• **{sid}** · {len(p.get('teams', []))}/8팀 · {status_text} · {created}")
    await interaction.response.send_message("📂 **전력분석 세션 목록**\n" + "\n".join(lines) + "\n\n세션을 이어서 분석하려면 `/세션추가 세션ID`를 사용하세요.", ephemeral=True)


@bot.tree.command(name="세션정보", description="전력분석 세션의 상세 정보를 확인합니다.")
async def session_info_command(interaction, 세션ID: str):
    project = get_session(세션ID)
    if not project:
        await interaction.response.send_message("❌ 해당 세션을 찾지 못했습니다.", ephemeral=True)
        return
    batches = project.get("session_batches", [])
    lines = [
        f"📂 **세션 {project.get('session_id', project.get('id'))}**",
        f"상태: {project.get('session_status', 'active')}",
        f"팀: **{len(project.get('teams', []))}/8**",
        f"생성: {project.get('session_created_at', '-')}",
        f"최근 수정: {project.get('session_updated_at', '-')}",
        f"분석 묶음: **{len(batches)}회**",
    ]
    if batches:
        lines.append("최근 묶음: " + " / ".join(f"#{b.get('batch')} {b.get('teams_found', 0)}팀" for b in batches[-5:]))
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bot.tree.command(name="세션불러오기", description="저장된 전력분석 세션을 현재 채널에서 불러옵니다.")
async def session_load_command(interaction, 세션ID: str):
    project = get_session(세션ID)
    if not project:
        await interaction.response.send_message("❌ 해당 세션을 찾지 못했습니다.", ephemeral=True)
        return
    if len(project.get("teams", [])) > 8:
        await interaction.response.send_message("❌ 세션 데이터가 8팀 제한을 초과했습니다. 수동 정리가 필요합니다.", ephemeral=True)
        return
    current_projects[interaction.channel_id] = project
    project["session_status"] = "active"
    project["session_updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_project(project)
    await interaction.response.send_message(content=f"📂 **세션을 불러왔습니다.**\n세션: `{project.get('session_id', project.get('id'))}`\n현재 **{len(project.get('teams', []))}/8팀**", embed=project_embed(project), view=ProjectView(project, save_project_to_sheet, apply_db_updates), ephemeral=True)


@bot.tree.command(name="세션추가", description="저장된 세션에 추가 분석 사진을 입력합니다.")
async def session_add_command(interaction, 세션ID: str):
    channel_id = interaction.channel_id
    if channel_id not in analysis_channels:
        await interaction.response.send_message("❌ 이 채널은 전력분석 채널이 아닙니다. 먼저 `/분석채널설정`을 사용해 주세요.", ephemeral=True)
        return
    if channel_id in analysis_waiting:
        await interaction.response.send_message("⏳ 이미 사진을 기다리고 있습니다.", ephemeral=True)
        return
    project = get_session(세션ID)
    if not project:
        await interaction.response.send_message("❌ 해당 세션을 찾지 못했습니다.", ephemeral=True)
        return
    if len(project.get("teams", [])) >= 8:
        await interaction.response.send_message("❌ 이 세션은 이미 8팀으로 가득 찼습니다.", ephemeral=True)
        return
    current_projects[channel_id] = project
    await interaction.response.send_message(f"➕ **세션 `{세션ID}`에 추가 분석을 시작합니다.**\n현재 **{len(project.get('teams', []))}/8팀**\n사진을 업로드해 주세요.\n⏱️ **30초 후 자동 분석됩니다.**")
    status = await interaction.original_response()
    await _start_session_batch(interaction.channel, status, project)


@bot.tree.command(name="세션보류", description="세션을 보류 상태로 저장합니다.")
async def session_pause_command(interaction, 세션ID: str):
    project = get_session(세션ID)
    if not project:
        await interaction.response.send_message("❌ 해당 세션을 찾지 못했습니다.", ephemeral=True)
        return
    mark_status(project, "paused")
    await interaction.response.send_message(f"⏸️ 세션 `{세션ID}`를 보류 상태로 저장했습니다.", ephemeral=True)


@bot.tree.command(name="세션삭제", description="저장된 전력분석 세션을 삭제합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def session_delete_command(interaction, 세션ID: str):
    project = get_session(세션ID)
    if not project:
        await interaction.response.send_message("❌ 해당 세션을 찾지 못했습니다.", ephemeral=True)
        return
    delete_project(project.get("id", 세션ID))
    if current_projects.get(interaction.channel_id, {}).get("id") == project.get("id"):
        current_projects.pop(interaction.channel_id, None)
    await interaction.response.send_message(f"🗑️ 세션 `{세션ID}`를 삭제했습니다.", ephemeral=True)
'''
source = source.replace("if not TOKEN:", session_commands + "\n\nif not TOKEN:", 1)

if "name=\"세션목록\"" not in source or "name=\"세션추가\"" not in source:
    raise RuntimeError("session command patch failed")

exec(compile(source, BOT_PATH, "exec"), {"__name__": "__main__", "__file__": BOT_PATH})

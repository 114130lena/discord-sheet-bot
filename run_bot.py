import re

BOT_PATH = "bot.py"
source = open(BOT_PATH, "r", encoding="utf-8").read()

# Runtime-only helpers. The repository's main bot.py stays compatible with the
# existing codebase while this launcher adds session behavior safely.
source = "from datetime import datetime\n" + source
source = source.replace("analysis_waiting = {}\ncurrent_projects = {}", "analysis_waiting = {}\ncurrent_projects = {}\nresult_delete_tasks = {}\nSESSION_IDLE_SECONDS = 1800")

helpers = r'''

def _session_is_active(project):
    updated = project.get("session_updated_at")
    if not updated:
        return True
    try:
        return (datetime.now() - datetime.fromisoformat(updated)).total_seconds() < SESSION_IDLE_SECONDS
    except Exception:
        return True


def _merge_team_results(existing, incoming):
    added = 0
    for new_team in incoming:
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
            existing.append(new_team)
            added += 1
        else:
            for key, value in new_team.items():
                if value not in (None, "", [], {}):
                    match[key] = value
    return added


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
            project["session_batches"] = []
            project["sheet_title"] = f"전력분석_세션_{project['session_id']}"
        project["session_updated_at"] = datetime.now().isoformat(timespec="seconds")

        incoming = result.get("teams", [])
        before = len(project.get("teams", []))
        added = _merge_team_results(project.setdefault("teams", []), incoming)
        batch_no = len(project.setdefault("session_batches", [])) + 1
        project["session_batches"].append({
            "batch": batch_no,
            "image_count": len(images),
            "teams_found": len(incoming),
            "teams_added": added,
            "timestamp": project["session_updated_at"],
        })

        canonicalize_teams(project)
        transfer_changes = canonicalize_players(project)
        current_projects[channel.id] = project
        suggestions = project.get("db_suggestions", {})
        total = len(project.get("teams", []))
        message = f"📋 **세션 분석 완료.**\n이번 묶음: **{len(incoming)}팀** · 새로 추가: **{added}팀** · 누적: **{total}팀**\n같은 세션에서 `/전력분석`을 다시 실행하면 추가 분석으로 누적됩니다."
        if suggestions.get("players"):
            message += f"\n🆕 신규 선수 **{len(suggestions['players'])}명** 발견"
        if suggestions.get("teams"):
            message += f"\n🆕 신규 팀 **{len(suggestions['teams'])}개** 발견"
        if transfer_changes:
            message += "\n🔄 **이적 의심**\n" + "\n".join(f"• **{c['name']}** {c.get('old_team') or '무소속'} → **{c['team']}**" for c in transfer_changes)

        await status.edit(content=message, embed=project_embed(project), view=ProjectView(project, save_project_to_sheet, apply_db_updates))
        result_delete_tasks[channel.id] = asyncio.create_task(delete_result_later(status, 300))
        save_project(project)
        print(f"Gemini 분석 완료: 세션 {project['session_id']} / 묶음 {batch_no} / 누적 {total}팀 / 이미지 {len(images)}장")
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
start_replacement = r'''@bot.tree.command(name="전력분석", description="30초 동안 사진을 받아 세션에 추가합니다.")
async def start_analysis(interaction):
    channel_id = interaction.channel_id
    if channel_id not in analysis_channels:
        await interaction.response.send_message("❌ 이 채널은 전력분석 채널이 아닙니다. 먼저 `/분석채널설정`을 사용해 주세요.", ephemeral=True)
        return
    if channel_id in analysis_waiting:
        await interaction.response.send_message("⏳ 이미 사진을 기다리고 있습니다.", ephemeral=True)
        return

    project = current_projects.get(channel_id)
    if project and not _session_is_active(project):
        project = None
        current_projects.pop(channel_id, None)
    if project is None:
        project = create_project()
        project["session_id"] = project.get("id")
        project["session_created_at"] = datetime.now().isoformat(timespec="seconds")
        project["session_updated_at"] = project["session_created_at"]
        project["session_batches"] = []
        project["sheet_title"] = f"전력분석_세션_{project['session_id']}"
        current_projects[channel_id] = project
        text = "🆕 **새 전력분석 세션을 시작했습니다.**"
    else:
        text = f"🔁 **기존 전력분석 세션에 추가 분석을 시작합니다.**\n현재 누적 **{len(project.get('teams', []))}팀**"

    await interaction.response.send_message(text + "\n사진을 업로드해 주세요. 여러 장을 연속으로 업로드할 수 있습니다.\n⏱️ **30초 후 자동 분석됩니다.**")
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

if "_merge_team_results" not in source or "async def start_analysis" not in source:
    raise RuntimeError("세션 패치에 실패했습니다.")

exec(compile(source, BOT_PATH, "exec"), {"__name__": "__main__", "__file__": BOT_PATH})

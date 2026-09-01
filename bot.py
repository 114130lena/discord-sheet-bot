import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from ai import analyze_images
from data import create_project, save_project, delete_project, load_config, save_config, add_player, remove_player, get_player, search_players, add_team, remove_team, get_team, search_teams, update_player_team, backup_databases
from sheets import update_spreadsheet
from ui import ProjectView, project_embed
from player_analysis import enrich_project_identities, set_manual_game_nick, analyze_player, analyze_all_players

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
config = load_config()
analysis_channels = set(int(x) for x in config.get("analysis_channels", []))
analysis_waiting = {}
current_projects = {}


def persist_channels():
    config["analysis_channels"] = sorted(analysis_channels)
    save_config(config)


def save_project_to_sheet(project):
    url = update_spreadsheet(project)
    save_project(project)
    return url


def canonicalize_teams(project):
    suggestions = []
    for team in project.get("teams", []):
        name = str(team.get("team_name", "")).strip()
        tag = str(team.get("team_tag", "")).strip()
        known = get_team(name) if name else None
        if known is None and tag:
            known = get_team(tag)
        if known:
            if known.get("name"): team["team_name"] = known["name"]
            if known.get("tag"): team["team_tag"] = known["tag"]
        elif name or tag:
            suggestions.append({"name": name, "tag": tag})
    project["db_suggestions"] = {"teams": suggestions, "players": [], "transfers": []}
    return suggestions


def canonicalize_players(project):
    suggestions = project.setdefault("db_suggestions", {"teams": [], "players": [], "transfers": []})
    for team in project.get("teams", []):
        team_name = str(team.get("team_name", "")).strip()
        for i in range(1, 5):
            name = str(team.get(f"player{i}", "")).strip()
            if not name or name == "[확인 필요]":
                continue
            exact = get_player(name)
            matches = search_players(name)
            canonical_name = name
            if exact:
                canonical_name = exact.get("name", name)
                old_team = str(exact.get("team", "")).strip()
                if team_name and old_team and old_team.lower() != team_name.lower():
                    suggestions["transfers"].append({"name": canonical_name, "old_team": old_team, "team": team_name})
                elif team_name and not old_team:
                    suggestions["transfers"].append({"name": canonical_name, "old_team": "", "team": team_name})
            elif len(matches) == 1:
                canonical_name = matches[0].get("name", name)
                old_team = str(matches[0].get("team", "")).strip()
                if team_name and old_team and old_team.lower() != team_name.lower():
                    suggestions["transfers"].append({"name": canonical_name, "old_team": old_team, "team": team_name})
                elif team_name and not old_team:
                    suggestions["transfers"].append({"name": canonical_name, "old_team": "", "team": team_name})
            else:
                suggestions["players"].append({"name": name, "team": team_name})
            team[f"player{i}"] = canonical_name
    return suggestions["transfers"]


def apply_db_updates(project):
    backup_databases()
    suggestions = project.get("db_suggestions", {})
    added_teams = 0
    added_players = 0
    transfers = 0
    for team in suggestions.get("teams", []):
        if add_team(team.get("name", ""), tag=team.get("tag", "")):
            added_teams += 1
    for player in suggestions.get("players", []):
        if add_player(player.get("name", ""), team=player.get("team", "")):
            added_players += 1
    for change in suggestions.get("transfers", []):
        result = update_player_team(change.get("name", ""), change.get("team", ""))
        if result.get("status") in {"changed", "set", "new"}:
            transfers += 1
    project["db_suggestions_applied"] = True
    project["db_suggestion_result"] = {"teams": added_teams, "players": added_players, "transfers": transfers}
    save_project(project)
    return project["db_suggestion_result"]


def get_current_project(channel_id):
    return current_projects.get(channel_id)


async def delete_result_later(message, delay=300):
    try:
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
    except asyncio.CancelledError:
        return


async def run_analysis(channel, state):
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
        project = create_project()
        project["teams"] = result.get("teams", [])
        canonicalize_teams(project)
        transfer_changes = canonicalize_players(project)
        await status.edit(content="👤 **선수 닉네임을 확인하고 있습니다.**\nDB → bori.wiki 순서로 확인합니다.", embed=None, view=None)
        identities = await asyncio.to_thread(enrich_project_identities, project, True)
        current_projects[channel.id] = project
        save_project(project)
        suggestions = project.get("db_suggestions", {})
        unresolved = sum(1 for item in identities.values() if not item.get("game_nick"))
        message = "📋 **분석 완료.**\n오류가 있으면 `✏️ 수정`으로 수정한 뒤 DB 반영 여부를 선택해 주세요."
        if suggestions.get("players"):
            message += f"\n🆕 신규 선수 **{len(suggestions['players'])}명** 발견"
        if suggestions.get("teams"):
            message += f"\n🆕 신규 팀 **{len(suggestions['teams'])}개** 발견"
        if transfer_changes:
            message += "\n🔄 **이적 의심** " + ", ".join(c["name"] for c in transfer_changes[:5])
        if unresolved:
            message += f"\n⚠️ 인게임 닉네임 확인 필요: **{unresolved}명**"
        await status.edit(content=message, embed=project_embed(project), view=ProjectView(project, save_project_to_sheet, apply_db_updates))
        asyncio.create_task(delete_result_later(status, 300))
        print(f"Gemini 분석 완료: {len(project['teams'])}개 팀 / 이미지 {len(images)}장 / 닉네임 미확인 {unresolved}명")
    except asyncio.CancelledError:
        return
    except Exception as e:
        analysis_waiting.pop(channel.id, None)
        print("분석 오류:", repr(e))
        try:
            await status.edit(content=f"❌ **분석 중 오류가 발생했습니다.**\n`{type(e).__name__}: {e}`", embed=None, view=None)
        except Exception:
            pass


async def debounce_analysis(channel, state):
    try:
        await asyncio.sleep(2)
        await run_analysis(channel, state)
    except asyncio.CancelledError:
        return


async def analysis_timeout(channel, state):
    try:
        await asyncio.sleep(30)
        if analysis_waiting.get(channel.id) is not state:
            return
        if state.get("debounce_task"):
            state["debounce_task"].cancel()
        if state["images"]:
            await run_analysis(channel, state)
        else:
            analysis_waiting.pop(channel.id, None)
            status_message = state["status_message"]
            await status_message.edit(content="⏱️ **전력분석 모드가 자동으로 종료되었습니다.**\n다시 `/전력분석`을 사용해 주세요.", embed=None, view=None)
            await asyncio.sleep(3)
            try:
                await status_message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
    except asyncio.CancelledError:
        return


@bot.event
async def on_ready():
    print("=" * 50)
    print(f"로그인 완료: {bot.user}")
    print(f"서버 수: {len(bot.guilds)} / 분석 채널: {len(analysis_channels)}개")
    print("=" * 50)
    try:
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"[{guild.name}] Slash Command {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"Slash Command 동기화 오류: {type(e).__name__}: {e}")


@bot.tree.command(name="분석채널설정", description="현재 채널을 전력분석 채널로 설정합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def set_analysis_channel(interaction):
    analysis_channels.add(interaction.channel_id)
    persist_channels()
    await interaction.response.send_message("📊 **전력분석 채널로 설정되었습니다.** `/전력분석`을 실행했을 때만 사진을 분석합니다.", delete_after=5)


@bot.tree.command(name="분석채널해제", description="현재 채널의 전력분석 채널 설정을 해제합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def unset_analysis_channel(interaction):
    channel_id = interaction.channel_id
    analysis_channels.discard(channel_id)
    persist_channels()
    state = analysis_waiting.pop(channel_id, None)
    if state:
        for key in ("timer_task", "debounce_task"):
            if state.get(key):
                state[key].cancel()
    await interaction.response.send_message("🛑 **전력분석 채널 설정이 해제되었습니다.**", delete_after=5)


@bot.tree.command(name="전력분석", description="30초 동안 로스터 사진을 받습니다.")
async def start_analysis(interaction):
    channel_id = interaction.channel_id
    if channel_id not in analysis_channels:
        await interaction.response.send_message("❌ 이 채널은 전력분석 채널이 아닙니다. 먼저 `/분석채널설정`을 사용해 주세요.", ephemeral=True)
        return
    if channel_id in analysis_waiting:
        await interaction.response.send_message("⏳ 이미 사진을 기다리고 있습니다.", ephemeral=True)
        return
    await interaction.response.send_message("📷 **전력분석 준비 완료.**\n사진을 업로드해 주세요. 여러 장이면 연속으로 업로드할 수 있습니다.\n⏱️ **30초 후 자동 종료**")
    status = await interaction.original_response()
    state = {"status_message": status, "images": [], "timer_task": None, "debounce_task": None}
    analysis_waiting[channel_id] = state
    state["timer_task"] = asyncio.create_task(analysis_timeout(interaction.channel, state))


@bot.tree.command(name="전력분석초기화", description="현재 채널의 마지막 분석 프로젝트를 초기화합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def reset_analysis(interaction):
    channel_id = interaction.channel_id
    state = analysis_waiting.pop(channel_id, None)
    if state:
        for key in ("timer_task", "debounce_task"):
            if state.get(key): state[key].cancel()
    project = current_projects.pop(channel_id, None)
    if project: delete_project(project["id"])
    await interaction.response.send_message("🧹 **현재 분석 데이터가 초기화되었습니다.**", delete_after=5)


@bot.tree.command(name="인게임닉등록", description="대회 닉네임과 인게임 닉네임을 직접 연결합니다.")
async def register_game_nick(interaction, 대회닉네임: str, 인게임닉네임: str):
    project = get_current_project(interaction.channel_id)
    if project:
        set_manual_game_nick(project, 대회닉네임, 인게임닉네임)
        save_project(project)
    else:
        from player_resolver import save_identity
        save_identity(대회닉네임, 인게임닉네임, source="manual", confidence="high")
    await interaction.response.send_message(f"🎮 **{대회닉네임} → {인게임닉네임}** 저장 완료. 다음부터 자동으로 사용합니다.", ephemeral=True)


@bot.tree.command(name="선수전적", description="현재 분석의 선수 실험체 통계를 조회합니다. Top 1~10 선택 가능.")
async def player_stats(interaction, 선수명: str, top: int = 3, 새로고침: bool = False):
    if top < 1 or top > 10:
        await interaction.response.send_message("❌ Top은 1~10 사이만 선택할 수 있습니다.", ephemeral=True)
        return
    project = get_current_project(interaction.channel_id)
    if not project:
        await interaction.response.send_message("❌ 현재 채널에 분석 결과가 없습니다. 먼저 `/전력분석`을 실행해 주세요.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    result = await asyncio.to_thread(analyze_player, project, 선수명, top, 새로고침)
    save_project(project)
    if result.get("status") == "manual_required":
        await interaction.followup.send(f"⚠️ **{선수명}**의 인게임 닉네임을 확인하지 못했습니다. `/인게임닉등록`으로 직접 등록해 주세요.", ephemeral=True)
        return
    if result.get("status") != "ok":
        await interaction.followup.send(f"⚠️ **{선수명}** 전적을 자동으로 확인하지 못했습니다. DAK.GG 공개 페이지 구조 또는 접근 상태를 확인해야 합니다.", ephemeral=True)
        return
    lines = []
    for idx, item in enumerate(result.get("characters", [])[:top], 1):
        lines.append(f"{idx}. **{item['name']}** — {item['games']}경기 ({item.get('share', 0)}%)")
    cache_text = "캐시 사용" if result.get("cached") else "새로 조회"
    await interaction.followup.send(f"🎮 **{선수명}** → `{result.get('game_nick')}`\n📊 **장기 실험체 통계 Top {top}**\n" + "\n".join(lines) + f"\n\n출처: {result.get('source')} · {cache_text}\n범위: {result.get('scope')}", ephemeral=True)


@bot.tree.command(name="전체전적분석", description="현재 분석의 모든 선수 실험체 통계를 조회합니다.")
async def all_player_stats(interaction, top: int = 3, 새로고침: bool = False):
    if top < 1 or top > 10:
        await interaction.response.send_message("❌ Top은 1~10 사이만 선택할 수 있습니다.", ephemeral=True)
        return
    project = get_current_project(interaction.channel_id)
    if not project:
        await interaction.response.send_message("❌ 현재 채널에 분석 결과가 없습니다.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    results = await asyncio.to_thread(analyze_all_players, project, top, 새로고침)
    save_project(project)
    success = sum(1 for r in results.values() if r.get("status") == "ok")
    unresolved = sum(1 for r in results.values() if r.get("status") == "manual_required")
    unavailable = len(results) - success - unresolved
    await interaction.followup.send(f"📊 **전체 선수 전적 분석 완료**\n성공: **{success}명** · 닉네임 확인 필요: **{unresolved}명** · 조회 불가: **{unavailable}명**\n`/선수전적 선수명 top:10`으로 개별 상세 확인 가능")


@bot.tree.command(name="선수등록", description="선수 DB에 선수를 등록합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def player_add(interaction, 선수명: str, 팀: str = "", 메모: str = ""):
    add_player(선수명, team=팀, notes=메모)
    await interaction.response.send_message(f"✅ 선수 DB에 **{선수명}** 등록 완료.", ephemeral=True)


@bot.tree.command(name="선수삭제", description="선수 DB에서 선수를 삭제합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def player_remove(interaction, 선수명: str):
    ok = remove_player(선수명)
    await interaction.response.send_message("🗑️ 삭제 완료." if ok else "❌ 등록된 선수를 찾지 못했습니다.", ephemeral=True)


@bot.tree.command(name="선수검색", description="선수 DB에서 선수를 검색합니다.")
async def player_search(interaction, 검색어: str):
    found = search_players(검색어)
    text = "❌ 검색 결과가 없습니다." if not found else "\n".join(f"• **{p['name']}**" + (f" — {p['team']}" if p.get('team') else "") for p in found[:20])
    await interaction.response.send_message("👤 **선수 DB 검색**\n" + text, ephemeral=True)


@bot.tree.command(name="선수정보", description="선수 DB의 상세 정보를 확인합니다.")
async def player_info(interaction, 선수명: str):
    p = get_player(선수명)
    if not p:
        await interaction.response.send_message("❌ 등록된 선수를 찾지 못했습니다.", ephemeral=True)
        return
    history = p.get("history", [])
    history_text = "\n".join(f"• {h.get('team', '-')} ({h.get('from') or '?'} ~ {h.get('to') or '현재 이전'})" for h in history[-10:]) or "없음"
    await interaction.response.send_message(f"👤 **{p['name']}**\n현재 팀: {p.get('team') or '-'}\n이전 팀 기록:\n{history_text}\n메모: {p.get('notes') or '-'}", ephemeral=True)


@bot.tree.command(name="팀등록", description="팀 DB에 정식 팀명과 약칭을 등록합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def team_add(interaction, 팀명: str, 약칭: str = "", 메모: str = ""):
    add_team(팀명, tag=약칭, notes=메모)
    await interaction.response.send_message(f"✅ 팀 DB에 **{팀명} [{약칭}]** 등록 완료.", ephemeral=True)


@bot.tree.command(name="팀삭제", description="팀 DB에서 팀을 삭제합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def team_remove(interaction, 팀명또는약칭: str):
    ok = remove_team(팀명또는약칭)
    await interaction.response.send_message("🗑️ 팀 DB에서 삭제 완료." if ok else "❌ 등록된 팀을 찾지 못했습니다.", ephemeral=True)


@bot.tree.command(name="팀검색", description="팀 DB에서 팀명 또는 약칭을 검색합니다.")
async def team_search(interaction, 검색어: str):
    found = search_teams(검색어)
    text = "❌ 검색 결과가 없습니다." if not found else "\n".join(f"• **{t.get('name') or '-'}**" + (f" [{t.get('tag')}]" if t.get('tag') else "") for t in found[:20])
    await interaction.response.send_message("🏷️ **팀 DB 검색**\n" + text, ephemeral=True)


@bot.tree.command(name="팀정보", description="팀 DB의 상세 정보를 확인합니다.")
async def team_info(interaction, 팀명또는약칭: str):
    t = get_team(팀명또는약칭)
    if not t:
        await interaction.response.send_message("❌ 등록된 팀을 찾지 못했습니다.", ephemeral=True)
        return
    await interaction.response.send_message(f"🏷️ **{t.get('name') or '-'}**\n약칭: {t.get('tag') or '-'}\n메모: {t.get('notes') or '-'}", ephemeral=True)


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    state = analysis_waiting.get(message.channel.id)
    if state is None:
        await bot.process_commands(message)
        return
    attachments = [a for a in message.attachments if (a.content_type or "").startswith("image/")]
    if not attachments:
        await bot.process_commands(message)
        return
    for attachment in attachments:
        try:
            state["images"].append((await attachment.read(), attachment.content_type or "image/png"))
        except Exception as e:
            print(f"이미지 읽기 오류: {e}")
    count = len(state["images"])
    await state["status_message"].edit(content=f"📷 **사진 {count}장 수신.**\n계속 업로드할 수 있습니다. 잠시 후 분석합니다.")
    if state.get("debounce_task"):
        state["debounce_task"].cancel()
    state["debounce_task"] = asyncio.create_task(debounce_analysis(message.channel, state))
    await bot.process_commands(message)


@set_analysis_channel.error
@unset_analysis_channel.error
@reset_analysis.error
@player_add.error
@player_remove.error
@team_add.error
@team_remove.error
async def permission_error(interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ 이 명령어는 **서버 관리** 권한이 필요합니다.", ephemeral=True)
    elif not interaction.response.is_done():
        await interaction.response.send_message("❌ 명령어 실행 중 오류가 발생했습니다.", ephemeral=True)


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN 환경변수를 찾을 수 없습니다.")
bot.run(TOKEN)

import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from ai import analyze_images
from data import create_project, save_project, delete_project, load_config, save_config, add_player, remove_player, get_player, search_players
from sheets import update_spreadsheet
from ui import ProjectView, project_embed

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

def canonicalize_players(project):
    for team in project.get("teams", []):
        for i in range(1, 5):
            name = str(team.get(f"player{i}", "")).strip()
            if not name or name == "[확인 필요]": continue
            exact = get_player(name)
            matches = search_players(name)
            if exact: team[f"player{i}"] = exact.get("name", name)
            elif len(matches) == 1: team[f"player{i}"] = matches[0].get("name", name)

async def run_analysis(channel, state):
    if analysis_waiting.get(channel.id) is not state: return
    status = state["status_message"]
    try:
        analysis_waiting.pop(channel.id, None)
        timer = state.get("timer_task")
        if timer and timer is not asyncio.current_task(): timer.cancel()
        await status.edit(content="🔍 **사진을 분석하고 있어...**\n잠깐만 기다려줘!", embed=None, view=None)
        images = list(state["images"])
        result = await asyncio.to_thread(analyze_images, images)
        project = create_project()
        project["teams"] = result.get("teams", [])
        canonicalize_players(project)
        current_projects[channel.id] = project
        await status.edit(content="📋 **분석 완료!**\n틀린 부분은 `✏️ 수정`으로 고치고 확인이 끝나면 저장해줘.", embed=project_embed(project), view=ProjectView(project, save_project_to_sheet))
        print(f"Gemini 분석 완료: {len(project['teams'])}개 팀 / 이미지 {len(images)}장")
    except asyncio.CancelledError: return
    except Exception as e:
        analysis_waiting.pop(channel.id, None)
        print("분석 오류:", repr(e))
        try: await status.edit(content=f"❌ **분석 중 오류가 발생했어.**\n`{type(e).__name__}: {e}`", embed=None, view=None)
        except Exception: pass

async def debounce_analysis(channel, state):
    try:
        await asyncio.sleep(2)
        await run_analysis(channel, state)
    except asyncio.CancelledError: return

async def analysis_timeout(channel, state):
    try:
        await asyncio.sleep(30)
        if analysis_waiting.get(channel.id) is not state: return
        if state.get("debounce_task"): state["debounce_task"].cancel()
        if state["images"]:
            await run_analysis(channel, state)
        else:
            analysis_waiting.pop(channel.id, None)
            status_message = state["status_message"]
            await status_message.edit(content="⏱️ **전력분석 모드가 자동으로 종료됐어.**\n다시 `/전력분석`을 사용해줘!", embed=None, view=None)
            await asyncio.sleep(3)
            try:
                await status_message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
    except asyncio.CancelledError: return

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"로그인 완료: {bot.user}")
    print(f"서버 수: {len(bot.guilds)} / 분석 채널: {len(analysis_channels)}개")
    print("=" * 50)
    try:
        for guild in bot.guilds:
            synced = await bot.tree.sync(guild=guild)
            print(f"[{guild.name}] Slash Command {len(synced)}개 동기화 완료")
    except Exception as e: print(f"Slash Command 동기화 오류: {e}")

@bot.tree.command(name="분석채널설정", description="현재 채널을 전력분석 채널로 설정합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def set_analysis_channel(interaction):
    analysis_channels.add(interaction.channel_id); persist_channels()
    await interaction.response.send_message("📊 **전력분석 채널로 설정했어!** 이제 `/전력분석`을 실행했을 때만 사진을 분석해.", delete_after=5)

@bot.tree.command(name="분석채널해제", description="현재 채널의 전력분석 채널 설정을 해제합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def unset_analysis_channel(interaction):
    channel_id = interaction.channel_id; analysis_channels.discard(channel_id); persist_channels()
    state = analysis_waiting.pop(channel_id, None)
    if state:
        for key in ("timer_task", "debounce_task"):
            if state.get(key): state[key].cancel()
    await interaction.response.send_message("🛑 **전력분석 채널 설정을 해제했어!**", delete_after=5)

@bot.tree.command(name="전력분석", description="30초 동안 로스터 사진을 받습니다.")
async def start_analysis(interaction):
    channel_id = interaction.channel_id
    if channel_id not in analysis_channels:
        await interaction.response.send_message("❌ 이 채널은 전력분석 채널이 아니야. 먼저 `/분석채널설정`을 사용해줘!", ephemeral=True); return
    if channel_id in analysis_waiting:
        await interaction.response.send_message("⏳ 이미 사진을 기다리고 있어!", ephemeral=True); return
    await interaction.response.send_message("📷 **전력분석 준비 완료!**\n사진을 올려줘. 여러 장이면 연속으로 올려도 돼.\n⏱️ **30초 후 자동 종료**")
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
    await interaction.response.send_message("🧹 **현재 분석 데이터를 초기화했어.**", delete_after=5)

@bot.tree.command(name="선수등록", description="선수 DB에 선수를 등록합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def player_add(interaction, 선수명: str, 팀: str = "", 메모: str = ""):
    add_player(선수명, team=팀, notes=메모)
    await interaction.response.send_message(f"✅ 선수 DB에 **{선수명}** 등록 완료.", ephemeral=True)

@bot.tree.command(name="선수삭제", description="선수 DB에서 선수를 삭제합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def player_remove(interaction, 선수명: str):
    ok = remove_player(선수명)
    await interaction.response.send_message("🗑️ 삭제 완료." if ok else "❌ 등록된 선수를 찾지 못했어.", ephemeral=True)

@bot.tree.command(name="선수검색", description="선수 DB에서 선수를 검색합니다.")
async def player_search(interaction, 검색어: str):
    found = search_players(검색어)
    if not found: text = "❌ 검색 결과가 없어."
    else: text = "\n".join(f"• **{p['name']}**" + (f" — {p['team']}" if p.get('team') else "") for p in found[:20])
    await interaction.response.send_message("👤 **선수 DB 검색**\n" + text, ephemeral=True)

@bot.tree.command(name="선수정보", description="선수 DB의 상세 정보를 확인합니다.")
async def player_info(interaction, 선수명: str):
    p = get_player(선수명)
    if not p:
        await interaction.response.send_message("❌ 등록된 선수를 찾지 못했어.", ephemeral=True); return
    text = f"👤 **{p['name']}**\n팀: {p.get('team') or '-'}\n메모: {p.get('notes') or '-'}"
    await interaction.response.send_message(text, ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot: return
    state = analysis_waiting.get(message.channel.id)
    if state is None:
        await bot.process_commands(message); return
    attachments = [a for a in message.attachments if (a.content_type or "").startswith("image/")]
    if not attachments:
        await bot.process_commands(message); return
    for attachment in attachments:
        try: state["images"].append((await attachment.read(), attachment.content_type or "image/png"))
        except Exception as e: print(f"이미지 읽기 오류: {e}")
    count = len(state["images"])
    await state["status_message"].edit(content=f"📷 **사진 {count}장 받았어!**\n계속 올려도 돼. 잠시 후 분석할게.")
    if state.get("debounce_task"): state["debounce_task"].cancel()
    state["debounce_task"] = asyncio.create_task(debounce_analysis(message.channel, state))
    await bot.process_commands(message)

@set_analysis_channel.error
@unset_analysis_channel.error
@reset_analysis.error
@player_add.error
@player_remove.error
async def permission_error(interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ 이 명령어는 **서버 관리** 권한이 필요해!", ephemeral=True)
    elif not interaction.response.is_done():
        await interaction.response.send_message("❌ 명령어 실행 중 오류가 발생했어.", ephemeral=True)

if not TOKEN: raise RuntimeError("DISCORD_TOKEN 환경변수를 찾을 수 없습니다.")
bot.run(TOKEN)

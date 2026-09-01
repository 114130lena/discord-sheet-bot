import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from ai import analyze_images
from data import create_project, save_project, delete_project, load_config, save_config, load_players, add_player, remove_player, get_player, search_players, add_team, remove_team, get_team, search_teams, update_player_team, backup_databases
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
    for transfer in suggestions.get("transfers", []):
        result = update_player_team(transfer.get("name", ""), transfer.get("team", ""))
        if result.get("status") in ("changed", "set", "new"):
            transfers += 1
    canonicalize_teams(project)
    canonicalize_players(project)
    save_project(project)
    return {"teams": added_teams, "players": added_players, "transfers": transfers}


async def analysis_timeout(channel, state):
    try:
        await asyncio.sleep(30)
        if analysis_waiting.get(channel.id) is state and state.get("images"):
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


async def run_analysis(channel, state):
    if analysis_waiting.get(channel.id) is not state:
        return
    status = state["status_message"]
    try:
        analysis_waiting.pop(channel.id, None)
        await status.edit(content="🔍 **사진을 분석하고 있습니다.**\n잠시만 기다려 주세요.", embed=None, view=None)
        images = list(state["images"])
        result = await asyncio.to_thread(analyze_images, images)
        project = current_projects.get(channel.id) or create_project()
        project.setdefault("teams", []).extend(result.get("teams", []))
        canonicalize_teams(project)
        canonicalize_players(project)
        current_projects[channel.id] = project
        save_project(project)
        await status.edit(content="📊 **전력분석이 완료되었습니다.**\nDB와 비교해 가능한 오타를 자동 보정했습니다.", embed=project_embed(project), view=ProjectView(project, save_project_to_sheet, apply_db_updates))
    except asyncio.CancelledError:
        return
    except Exception as e:
        print("분석 오류:", repr(e))
        try:
            await status.edit(content=f"❌ **분석 중 오류가 발생했습니다.**\n`{type(e).__name__}: {e}`", embed=None, view=None)
        except Exception:
            pass


async def debounce_analysis(channel, state):
    try:
        await asyncio.sleep(5)
        if analysis_waiting.get(channel.id) is state and state.get("images"):
            await run_analysis(channel, state)
    except asyncio.CancelledError:
        return


@bot.event
async def on_ready():
    print(f"로그인 완료: {bot.user}")
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"Slash Command 동기화 오류: {type(e).__name__}: {e}")


@bot.tree.command(name="분석채널설정", description="현재 채널을 전력분석 채널로 설정합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def set_analysis_channel(interaction):
    analysis_channels.add(interaction.channel_id)
    persist_channels()
    await interaction.response.send_message("📊 **전력분석 채널로 설정되었습니다.**", ephemeral=True)


@bot.tree.command(name="분석채널해제", description="현재 채널의 전력분석 채널 설정을 해제합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def unset_analysis_channel(interaction):
    analysis_channels.discard(interaction.channel_id)
    persist_channels()
    await interaction.response.send_message("🗑️ **전력분석 채널 설정을 해제했습니다.**", ephemeral=True)


@bot.tree.command(name="전력분석", description="전력분석을 시작하고 사진 업로드를 기다립니다.")
async def start_analysis(interaction):
    if interaction.channel_id not in analysis_channels:
        await interaction.response.send_message("❌ 이 채널은 전력분석 채널이 아닙니다.", ephemeral=True)
        return
    if interaction.channel_id in analysis_waiting:
        await interaction.response.send_message("⏳ 이미 사진을 기다리고 있습니다.", ephemeral=True)
        return
    await interaction.response.send_message("📷 **전력분석을 시작했습니다.**\n사진을 업로드해 주세요. 30초 동안 추가 사진을 받을 수 있습니다.")
    status = await interaction.original_response()
    state = {"status_message": status, "images": [], "timer_task": None, "debounce_task": None}
    analysis_waiting[interaction.channel_id] = state
    state["timer_task"] = asyncio.create_task(analysis_timeout(interaction.channel, state))


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    state = analysis_waiting.get(message.channel.id)
    if not state:
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
async def permission_error(interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 이 명령어는 **서버 관리** 권한이 필요합니다.", ephemeral=True)


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN 환경변수를 찾을 수 없습니다.")
bot.run(TOKEN)

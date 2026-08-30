import os
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv

from ai import analyze_images
from data import create_project, save_project, delete_project, load_config, save_config
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
    # Sheets 저장이 성공한 뒤 로컬 JSON도 저장한다.
    url = update_spreadsheet(project)
    save_project(project)
    return url


async def finish_analysis(channel, state):
    channel_id = channel.id
    try:
        await asyncio.sleep(2)
        if analysis_waiting.get(channel_id) is not state:
            return

        analysis_waiting.pop(channel_id, None)
        state["timer_task"].cancel()

        status = state["status_message"]
        await status.edit(content="🔍 **사진을 분석하고 있어...**\n잠깐만 기다려줘!", embed=None, view=None)

        images = state["images"]
        result = await asyncio.to_thread(analyze_images, images)

        project = create_project()
        project["teams"] = result.get("teams", [])
        project["image_path"] = None
        current_projects[channel_id] = project

        await status.edit(
            content="📋 **분석 완료!**\n틀린 부분은 `✏️ 수정`으로 고친 뒤, 확인이 끝나면 `💾 시트에 저장`을 눌러줘.",
            embed=project_embed(project),
            view=ProjectView(project, save_project_to_sheet),
        )
        print(f"Gemini 분석 완료: {len(project['teams'])}개 팀 / 이미지 {len(images)}장")

    except asyncio.CancelledError:
        return
    except Exception as e:
        analysis_waiting.pop(channel_id, None)
        print("=" * 50)
        print("❌ 분석 오류")
        print(repr(e))
        print("=" * 50)
        try:
            await state["status_message"].edit(content=f"❌ **분석 중 오류가 발생했어.**\n`{type(e).__name__}: {e}`", embed=None, view=None)
        except Exception:
            pass


async def analysis_timeout(channel, state):
    try:
        await asyncio.sleep(30)
        if analysis_waiting.get(channel.id) is not state:
            return
        analysis_waiting.pop(channel.id, None)
        if state.get("debounce_task"):
            state["debounce_task"].cancel()
        if state["images"]:
            await finish_analysis(channel, state)
            return
        await state["status_message"].edit(content="⏱️ **전력분석 모드가 자동으로 종료됐어.**\n다시 분석하려면 `/전력분석`을 사용해줘!", embed=None, view=None)
    except asyncio.CancelledError:
        return


@bot.event
async def on_ready():
    print("=" * 50)
    print(f"로그인 완료: {bot.user}")
    print(f"서버 수: {len(bot.guilds)}")
    print(f"분석 채널: {len(analysis_channels)}개")
    print("=" * 50)
    try:
        for guild in bot.guilds:
            synced = await bot.tree.sync(guild=guild)
            print(f"[{guild.name}] Slash Command {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"Slash Command 동기화 오류: {e}")


@bot.tree.command(name="분석채널설정", description="현재 채널을 전력분석 채널로 설정합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def set_analysis_channel(interaction: discord.Interaction):
    analysis_channels.add(interaction.channel_id)
    persist_channels()
    await interaction.response.send_message("📊 **전력분석 채널로 설정했어!**\n이제 `/전력분석`을 실행했을 때만 사진을 분석해.", delete_after=5)


@bot.tree.command(name="분석채널해제", description="현재 채널의 전력분석 채널 설정을 해제합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def unset_analysis_channel(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    analysis_channels.discard(channel_id)
    persist_channels()
    state = analysis_waiting.pop(channel_id, None)
    if state:
        for key in ("timer_task", "debounce_task"):
            if state.get(key):
                state[key].cancel()
    await interaction.response.send_message("🛑 **전력분석 채널 설정을 해제했어!**", delete_after=5)


@bot.tree.command(name="전력분석", description="30초 동안 로스터 사진을 받습니다.")
async def start_analysis(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id not in analysis_channels:
        await interaction.response.send_message("❌ 이 채널은 전력분석 채널이 아니야. 먼저 `/분석채널설정`을 사용해줘!", ephemeral=True)
        return
    if channel_id in analysis_waiting:
        await interaction.response.send_message("⏳ 이미 사진을 기다리고 있어!", ephemeral=True)
        return

    await interaction.response.send_message("📷 **전력분석 준비 완료!**\n사진을 올려줘. 여러 장이면 연속으로 올려도 돼.\n⏱️ **30초 후 자동 종료**")
    status = await interaction.original_response()
    state = {"status_message": status, "images": [], "timer_task": None, "debounce_task": None}
    analysis_waiting[channel_id] = state
    state["timer_task"] = asyncio.create_task(analysis_timeout(interaction.channel, state))


@bot.tree.command(name="전력분석초기화", description="현재 채널의 마지막 분석 프로젝트를 초기화합니다.")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def reset_analysis(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    state = analysis_waiting.pop(channel_id, None)
    if state:
        for key in ("timer_task", "debounce_task"):
            if state.get(key):
                state[key].cancel()
    project = current_projects.pop(channel_id, None)
    if project:
        delete_project(project["id"])
    await interaction.response.send_message("🧹 **현재 분석 데이터를 초기화했어.**", delete_after=5)


@bot.event
async def on_message(message: discord.Message):
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
            data = await attachment.read()
            state["images"].append((data, attachment.content_type or "image/png"))
        except Exception as e:
            print(f"이미지 읽기 오류: {e}")

    count = len(state["images"])
    await state["status_message"].edit(content=f"📷 **사진 {count}장 받았어!**\n잠시 더 받을게. 여러 장이면 계속 올려줘.\n🔍 곧 분석을 시작해.")

    if state.get("debounce_task"):
        state["debounce_task"].cancel()
    state["debounce_task"] = asyncio.create_task(finish_analysis(message.channel, state))
    await bot.process_commands(message)


@set_analysis_channel.error
async def set_analysis_channel_error(interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ 이 명령어는 **서버 관리** 권한이 필요해!", ephemeral=True)
    else:
        print(f"분석채널설정 오류: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 명령어 실행 중 오류가 발생했어.", ephemeral=True)


@unset_analysis_channel.error
async def unset_analysis_channel_error(interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ 이 명령어는 **서버 관리** 권한이 필요해!", ephemeral=True)
    else:
        print(f"분석채널해제 오류: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 명령어 실행 중 오류가 발생했어.", ephemeral=True)


@reset_analysis.error
async def reset_analysis_error(interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ 이 명령어는 **서버 관리** 권한이 필요해!", ephemeral=True)
    else:
        print(f"전력분석초기화 오류: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 명령어 실행 중 오류가 발생했어.", ephemeral=True)


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN 환경변수를 찾을 수 없습니다.")

bot.run(TOKEN)

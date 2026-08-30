import os
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv

from ai import analyze_image
from data import create_project, save_project
from ui import ProjectView, project_embed


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")


intents = discord.Intents.default()
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# 전력분석 전용 채널
analysis_channels = set()

# 현재 사진 분석을 기다리는 채널
analysis_waiting = {}


@bot.event
async def on_ready():

    print(f"로그인 완료: {bot.user}")

    try:

        synced = await bot.tree.sync()

        print(
            f"Slash Command "
            f"{len(synced)}개 동기화 완료"
        )

    except Exception as e:

        print(
            f"동기화 오류: {e}"
        )


# =========================================================
# 분석 채널 설정
# =========================================================

@bot.tree.command(
    name="분석채널설정",
    description="현재 채널을 전력분석 채널로 설정합니다."
)
@discord.app_commands.checks.has_permissions(
    manage_guild=True
)
async def set_analysis_channel(
    interaction: discord.Interaction
):

    channel_id = interaction.channel_id

    analysis_channels.add(
        channel_id
    )

    await interaction.response.send_message(
        "📊 **전력분석 채널로 설정했어!**\n\n"
        "이 채널에서는 `/전력분석`을 사용해야 "
        "사진을 분석해.\n\n"
        "그냥 사진을 올리는 건 분석하지 않아."
    )


# =========================================================
# 분석 채널 해제
# =========================================================

@bot.tree.command(
    name="분석채널해제",
    description="현재 채널의 전력분석 설정을 해제합니다."
)
@discord.app_commands.checks.has_permissions(
    manage_guild=True
)
async def unset_analysis_channel(
    interaction: discord.Interaction
):

    channel_id = interaction.channel_id

    analysis_channels.discard(
        channel_id
    )

    analysis_waiting.pop(
        channel_id,
        None
    )

    await interaction.response.send_message(
        "🛑 **전력분석 채널 설정을 해제했어.**"
    )


# =========================================================
# 전력분석 시작
# =========================================================

@bot.tree.command(
    name="전력분석",
    description="30초 동안 팀 명단 사진을 기다립니다."
)
async def start_analysis(
    interaction: discord.Interaction
):

    channel_id = interaction.channel_id

    # 분석 전용 채널인지 확인
    if channel_id not in analysis_channels:

        await interaction.response.send_message(
            "❌ 이 채널은 전력분석 채널로 설정되어 있지 않아.\n"
            "`/분석채널설정`을 먼저 사용해줘.",
            ephemeral=True
        )

        return

    # 이미 대기 중이면 방지
    if channel_id in analysis_waiting:

        await interaction.response.send_message(
            "⏳ 이미 사진을 기다리고 있어!",
            ephemeral=True
        )

        return

    # 대기 상태 시작
    analysis_waiting[channel_id] = True

    await interaction.response.send_message(
        "📷 **전력분석 준비 완료!**\n\n"
        "팀 명단 사진을 올려줘.\n"
        "⏱️ **30초 동안만 기다릴게!**"
    )

    # 30초 후 자동 종료
    await asyncio.sleep(30)

    # 아직 대기 상태라면 종료
    if analysis_waiting.get(
        channel_id
    ):

        analysis_waiting.pop(
            channel_id,
            None
        )

        await interaction.channel.send(
            "⏱️ **전력분석 모드가 자동으로 종료됐어.**\n"
            "다시 분석하려면 `/전력분석`을 사용해줘!"
        )


# =========================================================
# 메시지 처리
# =========================================================

@bot.event
async def on_message(
    message
):

    if message.author.bot:
        return

    channel_id = message.channel.id

    # =====================================================
    # 분석 대기 상태가 아니면 사진 무시
    # =====================================================

    if channel_id not in analysis_waiting:

        await bot.process_commands(
            message
        )

        return

    # =====================================================
    # 이미지 찾기
    # =====================================================

    image = None

    for attachment in message.attachments:

        if not attachment.content_type:
            continue

        if attachment.content_type.startswith(
            "image/"
        ):

            image = attachment
            break

    # 사진이 아니면 무시
    if image is None:

        await bot.process_commands(
            message
        )

        return

    # =====================================================
    # 사진 발견 → 분석 상태 즉시 종료
    # =====================================================

    analysis_waiting.pop(
        channel_id,
        None
    )

    await message.channel.send(
        "🔍 **표를 분석하고 있어...**\n"
        "잠깐만 기다려줘!"
    )

    try:

        image_data = await image.read()

        result = analyze_image(
            image_data,
            image.content_type
        )

        project = create_project()

        project["teams"] = result.get(
            "teams",
            []
        )

        project["image_path"] = image.url

        save_project(
            project
        )

        embed = project_embed(
            project
        )

        await message.channel.send(
            content=(
                "📋 **분석 결과야!**\n"
                "틀린 부분이 있으면 `✏️ 수정`으로 고쳐줘."
            ),
            embed=embed,
            view=ProjectView(
                project,
                save_project
            )
        )

    except Exception as e:

        print(
            f"분석 오류: {e}"
        )

        await message.channel.send(
            "❌ **분석 중 오류가 발생했어.**\n"
            f"```text\n{e}\n```"
        )

    await bot.process_commands(
        message
    )


# =========================================================
# 권한 오류 처리
# =========================================================

@set_analysis_channel.error
async def set_analysis_channel_error(
    interaction,
    error
):

    if isinstance(
        error,
        discord.app_commands.errors.MissingPermissions
    ):

        await interaction.response.send_message(
            "❌ 서버 관리 권한이 필요해!",
            ephemeral=True
        )

    else:

        raise error


@unset_analysis_channel.error
async def unset_analysis_channel_error(
    interaction,
    error
):

    if isinstance(
        error,
        discord.app_commands.errors.MissingPermissions
    ):

        await interaction.response.send_message(
            "❌ 서버 관리 권한이 필요해!",
            ephemeral=True
        )

    else:

        raise error


# =========================================================
# 실행
# =========================================================

bot.run(
    TOKEN
)

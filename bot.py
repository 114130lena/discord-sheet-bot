import os
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv

from ai import analyze_image
from data import create_project, save_project
from ui import ProjectView, project_embed


# =========================================================
# 환경변수
# =========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")


# =========================================================
# Discord 설정
# =========================================================

intents = discord.Intents.default()

# 사진 메시지를 감지하기 위해 필요
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# 전력분석 설정
# =========================================================

# 전력분석 전용으로 설정된 채널
analysis_channels = set()

# 현재 /전력분석 명령어를 실행해서
# 사진을 기다리고 있는 채널
analysis_waiting = {}


# =========================================================
# 봇 시작
# =========================================================

@bot.event
async def on_ready():

    print("=" * 50)
    print(f"로그인 완료: {bot.user}")
    print(f"봇 ID: {bot.user.id}")
    print(f"서버 수: {len(bot.guilds)}")
    print("=" * 50)

    # ---------------------------------------------
    # 서버별 Slash Command 동기화
    # ---------------------------------------------

    try:

        for guild in bot.guilds:

            synced = await bot.tree.sync(
                guild=guild
            )

            print(
                f"[{guild.name}] "
                f"Slash Command "
                f"{len(synced)}개 동기화 완료"
            )

    except Exception as e:

        print(
            f"Slash Command 동기화 오류: {e}"
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
        "이제 이 채널에서는 `/전력분석`을 "
        "사용했을 때만 사진을 분석해.\n\n"
        "그냥 사진을 올리는 건 분석하지 않아! 👍"
    )


# =========================================================
# 분석 채널 해제
# =========================================================

@bot.tree.command(
    name="분석채널해제",
    description="현재 채널의 전력분석 채널 설정을 해제합니다."
)
@discord.app_commands.checks.has_permissions(
    manage_guild=True
)
async def unset_analysis_channel(
    interaction: discord.Interaction
):

    channel_id = interaction.channel_id

    # 채널 설정 제거
    analysis_channels.discard(
        channel_id
    )

    # 혹시 분석 대기 중이었다면 제거
    analysis_waiting.pop(
        channel_id,
        None
    )

    await interaction.response.send_message(
        "🛑 **전력분석 채널 설정을 해제했어!**"
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

    # ---------------------------------------------
    # 분석 채널인지 확인
    # ---------------------------------------------

    if channel_id not in analysis_channels:

        await interaction.response.send_message(
            "❌ 이 채널은 전력분석 채널로 설정되어 있지 않아.\n\n"
            "먼저 `/분석채널설정`을 사용해줘!",
            ephemeral=True
        )

        return

    # ---------------------------------------------
    # 이미 분석 대기 중인지 확인
    # ---------------------------------------------

    if channel_id in analysis_waiting:

        await interaction.response.send_message(
            "⏳ 이미 사진을 기다리고 있어!\n"
            "사진을 올려줘.",
            ephemeral=True
        )

        return

    # ---------------------------------------------
    # 분석 대기 시작
    # ---------------------------------------------

    analysis_waiting[channel_id] = True

    await interaction.response.send_message(
        "📷 **전력분석 준비 완료!**\n\n"
        "팀 명단 사진을 올려줘.\n"
        "⏱️ **30초 동안 기다릴게!**\n\n"
        "사진을 올리면 바로 분석을 시작해."
    )

    # ---------------------------------------------
    # 30초 대기
    # ---------------------------------------------

    await asyncio.sleep(30)

    # ---------------------------------------------
    # 30초 동안 사진이 없었다면 자동 종료
    # ---------------------------------------------

    if analysis_waiting.get(
        channel_id
    ):

        analysis_waiting.pop(
            channel_id,
            None
        )

        try:

            await interaction.channel.send(
                "⏱️ **전력분석 모드가 자동으로 종료됐어.**\n\n"
                "다시 분석하려면 `/전력분석`을 사용해줘!"
            )

        except Exception as e:

            print(
                f"자동 종료 메시지 오류: {e}"
            )


# =========================================================
# 메시지 감지
# =========================================================

@bot.event
async def on_message(
    message: discord.Message
):

    # 봇 자신의 메시지 무시
    if message.author.bot:

        return

    channel_id = message.channel.id

    # =====================================================
    # 현재 분석 대기 상태가 아니면 아무것도 하지 않음
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

    # =====================================================
    # 이미지가 아니면 무시
    # =====================================================

    if image is None:

        await bot.process_commands(
            message
        )

        return

    # =====================================================
    # 사진 발견
    # =====================================================

    # 사진 하나를 받았으므로 분석 대기 종료
    analysis_waiting.pop(
        channel_id,
        None
    )

    await message.channel.send(
        "🔍 **표를 분석하고 있어...**\n"
        "잠깐만 기다려줘!"
    )

    # =====================================================
    # Gemini 분석
    # =====================================================

    try:

        image_data = await image.read()

        result = analyze_image(
            image_data,
            image.content_type
        )

        print(
            f"Gemini 분석 완료: "
            f"{len(result.get('teams', []))}개 팀"
        )

        # =================================================
        # 프로젝트 생성
        # =================================================

        project = create_project()

        project["teams"] = result.get(
            "teams",
            []
        )

        project["image_path"] = image.url

        # =================================================
        # 프로젝트 저장
        # =================================================

        save_project(
            project
        )

        # =================================================
        # Discord 결과 표시
        # =================================================

        embed = project_embed(
            project
        )

        await message.channel.send(
            content=(
                "📋 **분석 결과야!**\n\n"
                "내용을 확인하고 틀린 부분이 있으면 "
                "`✏️ 수정`으로 고쳐줘."
            ),
            embed=embed,
            view=ProjectView(
                project,
                save_project
            )
        )

    # =====================================================
    # 오류
    # =====================================================

    except Exception as e:

        print(
            "=" * 50
        )

        print(
            "❌ 분석 오류"
        )

        print(
            repr(e)
        )

        print(
            "=" * 50
        )

        await message.channel.send(
            "❌ **분석 중 오류가 발생했어.**\n\n"
            "터미널에 자세한 오류가 출력됐어.\n"
            "잠시 후 다시 시도해줘."
        )

    # =====================================================
    # 명령어 처리
    # =====================================================

    await bot.process_commands(
        message
    )


# =========================================================
# Slash Command 권한 오류
# =========================================================

@set_analysis_channel.error
async def set_analysis_channel_error(
    interaction: discord.Interaction,
    error
):

    if isinstance(
        error,
        discord.app_commands.errors.MissingPermissions
    ):

        await interaction.response.send_message(
            "❌ 이 명령어를 사용하려면 "
            "**서버 관리** 권한이 필요해!",
            ephemeral=True
        )

    else:

        print(
            f"분석채널설정 오류: {error}"
        )

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ 명령어 실행 중 오류가 발생했어.",
                ephemeral=True
            )


@unset_analysis_channel.error
async def unset_analysis_channel_error(
    interaction: discord.Interaction,
    error
):

    if isinstance(
        error,
        discord.app_commands.errors.MissingPermissions
    ):

        await interaction.response.send_message(
            "❌ 이 명령어를 사용하려면 "
            "**서버 관리** 권한이 필요해!",
            ephemeral=True
        )

    else:

        print(
            f"분석채널해제 오류: {error}"
        )

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ 명령어 실행 중 오류가 발생했어.",
                ephemeral=True
            )


# =========================================================
# 봇 실행
# =========================================================

if not TOKEN:

    print(
        "❌ DISCORD_TOKEN이 설정되어 있지 않아!"
    )

    raise RuntimeError(
        "DISCORD_TOKEN 환경변수를 찾을 수 없습니다."
    )


bot.run(
    TOKEN
)

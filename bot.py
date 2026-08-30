import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from ai import analyze_image
from data import create_project, save_project
from ui import ProjectView, project_embed


load_dotenv()


TOKEN = os.getenv(
    "DISCORD_TOKEN"
)


intents = discord.Intents.default()

intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():

    print(
        f"로그인 완료: {bot.user}"
    )

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


@bot.tree.command(
    name="시트생성",
    description="팀 명단 사진을 분석합니다."
)
async def create_sheet(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        "📷 팀 명단 사진을 올려주세요!"
    )


@bot.event
async def on_message(
    message
):

    if message.author.bot:
        return

    for attachment in message.attachments:

        if not attachment.content_type:
            continue

        if not attachment.content_type.startswith(
            "image/"
        ):
            continue

        await message.channel.send(
            "🔍 사진을 분석하고 있어..."
        )

        try:

            image_data = await attachment.read()

            result = analyze_image(
                image_data,
                attachment.content_type
            )

            project = create_project()

            project["teams"] = result.get(
                "teams",
                []
            )

            save_project(
                project
            )

            embed = project_embed(
                project
            )

            await message.channel.send(
                content=(
                    "📋 **분석 결과를 확인해주세요!**\n"
                    "AI가 판단한 로스터 인원도 확인해주세요."
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
                "❌ 분석 중 오류가 발생했어.\n"
                f"```text\n{e}\n```"
            )

    await bot.process_commands(
        message
    )


bot.run(
    TOKEN
)

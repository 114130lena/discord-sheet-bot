import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():
    print(f"로그인 완료: {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Slash Command {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"동기화 오류: {e}")


@bot.tree.command(
    name="시트생성",
    description="팀 명단 사진을 분석합니다."
)
async def create_sheet(interaction: discord.Interaction):
    await interaction.response.send_message(
        "📷 팀 명단 사진을 이 채널에 올려주세요!"
    )


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                print(f"이미지 수신: {attachment.filename}")

                await message.channel.send(
                    f"📷 `{attachment.filename}` 사진을 받았어!\n"
                    "🔍 이제 표 내용을 분석하는 기능을 연결할 예정이야."
                )

    await bot.process_commands(message)


bot.run(TOKEN)

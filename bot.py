import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()

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


@bot.tree.command(name="시트생성", description="새로운 팀 명단 시트를 생성합니다.")
async def create_sheet(interaction: discord.Interaction):
    await interaction.response.send_message(
        "📊 시트 생성 기능 준비 중!"
    )


bot.run(TOKEN)

import os
import base64

import discord
from discord.ext import commands
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

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

    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            await message.channel.send("🔍 사진을 분석하고 있어...")

            try:
                image_data = await attachment.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")

                response = client.responses.create(
                    model="gpt-4.1-mini",
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": """
이 이미지는 팀 명단 표야.

표에서 다음 정보를 찾아줘:
- 팀명
- 선수 1
- 선수 2
- 선수 3
- 선수 4
- 한줄 설명

읽을 수 없는 부분은 추측하지 말고 [확인 필요]라고 표시해.

결과는 다음 형식으로만 작성해:

팀 1:
팀명:
선수1:
선수2:
선수3:
선수4:
설명:

팀 2:
팀명:
선수1:
선수2:
선수3:
선수4:
설명:

이미지에 있는 팀 수만큼 작성해.
"""
                                },
                                {
                                    "type": "input_image",
                                    "image_url": f"data:{attachment.content_type};base64,{base64_image}"
                                }
                            ]
                        }
                    ]
                )

                result = response.output_text

                if len(result) > 1900:
                    result = result[:1900] + "\n...(결과가 너무 길어 일부 생략됨)"

                await message.channel.send(
                    f"📋 **사진 분석 결과**\n```text\n{result}\n```"
                )

            except Exception as e:
                print(f"AI 분석 오류: {e}")
                await message.channel.send(
                    "❌ 사진 분석 중 오류가 발생했어.\n"
                    f"```{e}```"
                )

    await bot.process_commands(message)


bot.run(DISCORD_TOKEN)

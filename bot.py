import os
import base64

import discord
from discord.ext import commands
from dotenv import load_dotenv
from google import genai

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini = genai.Client(api_key=GEMINI_API_KEY)

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

        if not attachment.content_type:
            continue

        if not attachment.content_type.startswith("image/"):
            continue

        await message.channel.send("🔍 사진을 분석하고 있어...")

        try:
            image_data = await attachment.read()

            prompt = """
이 이미지는 이터널 리턴 대회 팀 명단 표다.

표에 있는 모든 팀을 찾아서 정보를 추출해줘.

각 팀에서 다음 정보를 찾아줘:

- 팀명
- 선수 1
- 선수 2
- 선수 3
- 선수 4
- 한줄 설명

중요:
1. 이미지에 실제로 적혀 있는 내용만 사용해.
2. 글자가 불확실하면 추측하지 말고 [확인 필요]라고 적어.
3. 팀이 7개라면 7개 모두 출력해.
4. 표의 행과 열 구조를 최대한 유지해.
5. 설명이 없다면 "없음"이라고 적어.

반드시 다음 형식으로 출력해:

팀 1
팀명:
선수1:
선수2:
선수3:
선수4:
설명:

팀 2
팀명:
선수1:
선수2:
선수3:
선수4:
설명:

팀 3
...

이미지에 존재하는 팀 수만큼 계속 작성해.
"""

            response = gemini.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[
                    prompt,
                    {
                        "inline_data": {
                            "mime_type": attachment.content_type,
                            "data": base64.b64encode(image_data).decode("utf-8")
                        }
                    }
                ]
            )

            result = response.text

            if len(result) > 1900:
                result = result[:1900] + "\n...(결과가 너무 길어 일부 생략됨)"

            await message.channel.send(
                f"📋 **사진 분석 결과**\n```text\n{result}\n```"
            )

        except Exception as e:
            print(f"Gemini 분석 오류: {e}")

            await message.channel.send(
                "❌ 사진 분석 중 오류가 발생했어.\n"
                f"```text\n{e}\n```"
            )

    await bot.process_commands(message)


bot.run(DISCORD_TOKEN)

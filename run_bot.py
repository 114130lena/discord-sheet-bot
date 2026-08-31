import re

BOT_PATH = "bot.py"

source = open(BOT_PATH, "r", encoding="utf-8").read()
pattern = r"@bot\.event\nasync def on_ready\(\):.*?(?=\n@bot\.tree\.command)"
replacement = '''@bot.event
async def on_ready():
    print("=" * 50)
    print(f"로그인 완료: {bot.user}")
    print(f"서버 수: {len(bot.guilds)} / 분석 채널: {len(analysis_channels)}개")
    print("=" * 50)
    try:
        # 현재 코드에 정의된 전역 명령어를 복사해 길드 전용으로 등록합니다.
        # 과거에 남아 있던 전역 명령어는 먼저 동기화하여 제거합니다.
        commands_to_sync = [command.copy() for command in bot.tree.get_commands()]
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()

        for guild in bot.guilds:
            bot.tree.clear_commands(guild=guild)
            for command in commands_to_sync:
                bot.tree.add_command(command.copy(), guild=guild, override=True)
            synced = await bot.tree.sync(guild=guild)
            print(f"[{guild.name}] Slash Command {len(synced)}개 동기화 완료")
            print("등록 명령어:", ", ".join(command.name for command in synced))
    except Exception as e:
        print(f"Slash Command 동기화 오류: {type(e).__name__}: {e}")'''

patched = re.sub(pattern, replacement, source, count=1, flags=re.S)
if patched == source:
    raise RuntimeError("on_ready 블록을 찾지 못했습니다.")

exec(compile(patched, BOT_PATH, "exec"), {"__name__": "__main__", "__file__": BOT_PATH})

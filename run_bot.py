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
        # 현재 코드에 정의된 명령어를 먼저 확보합니다.
        commands_to_sync = list(bot.tree.get_commands())

        # 전역 명령어는 사용하지 않도록 원격 전역 등록을 비웁니다.
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()

        # 각 서버에 동일한 명령어 세트를 길드 전용으로 등록합니다.
        for guild in bot.guilds:
            bot.tree.clear_commands(guild=guild)
            for command in commands_to_sync:
                bot.tree.add_command(command, guild=guild, override=True)
            synced = await bot.tree.sync(guild=guild)
            print(f"[{guild.name}] Slash Command {len(synced)}개 동기화 완료")
            print("등록 명령어:", ", ".join(command.name for command in synced))

        # 다음 준비 이벤트에서도 원래 전역 명령어를 다시 사용할 수 있도록 복구합니다.
        for command in commands_to_sync:
            bot.tree.add_command(command, override=True)
    except Exception as e:
        print(f"Slash Command 동기화 오류: {type(e).__name__}: {e}")'''

patched = re.sub(pattern, replacement, source, count=1, flags=re.S)
if patched == source:
    raise RuntimeError("on_ready 블록을 찾지 못했습니다.")

exec(compile(patched, BOT_PATH, "exec"), {"__name__": "__main__", "__file__": BOT_PATH})

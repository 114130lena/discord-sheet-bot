import re

TARGET = "production_launcher.py"
source = open(TARGET, "r", encoding="utf-8").read()

# Keep replacement strings literal. production_launcher.py injects Python source
# containing \n escapes, so callable replacements are required.
source = re.sub(
    r"source = re\.sub\((\w+_pattern), (\w+_replacement), source, count=1, flags=re\.S\)",
    r"source = re.sub(\1, lambda _m: \2, source, count=1, flags=re.S)",
    source,
)

# Replace the production launcher's generated on_ready handler before it runs.
# Do not clear the global tree: clearing it before sync removes decorated commands.
sync_handler = '''on_ready_replacement = \'\'\'@bot.event
async def on_ready():
    print("=" * 50, flush=True)
    print(f"로그인 완료: {bot.user}", flush=True)
    print(f"서버 수: {len(bot.guilds)} / 분석 채널: {len(analysis_channels)}개", flush=True)
    print("=" * 50, flush=True)
    try:
        global_synced = await bot.tree.sync()
        print(f"글로벌 Slash Command {len(global_synced)}개 동기화 완료", flush=True)

        for guild in bot.guilds:
            bot.tree.clear_commands(guild=guild)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"[{guild.name}] Slash Command {len(synced)}개 동기화 완료", flush=True)
            print("등록 명령어:", ", ".join(command.name for command in synced), flush=True)
    except Exception as e:
        print(f"Slash Command 동기화 오류: {type(e).__name__}: {e}", flush=True)\'\'\''''

# The source may contain either the original direct re.sub call or the callable
# form above. Replace the whole generated handler assignment in one pass.
handler_pattern = (
    r"on_ready_replacement = '''.*?'''\n"
    r"source = re\.sub\(on_ready_pattern, .*?\)"
)
replacement_line = (
    sync_handler
    + "\nsource = re.sub(on_ready_pattern, lambda _m: on_ready_replacement, source, count=1, flags=re.S)"
)
source, replaced = re.subn(
    handler_pattern,
    lambda _m: replacement_line,
    source,
    count=1,
    flags=re.S,
)

if replaced != 1:
    raise RuntimeError("production_launcher.py의 on_ready 동기화 패치를 적용하지 못했습니다.")

print("[SAFE] 명령어 동기화 런처 패치 적용 완료", flush=True)
compile(source, TARGET, "exec")
exec(compile(source, TARGET, "exec"), {"__name__": "__main__", "__file__": TARGET})

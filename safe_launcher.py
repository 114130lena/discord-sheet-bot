import re

TARGET = "production_launcher.py"
source = open(TARGET, "r", encoding="utf-8").read()

# re.sub interprets backslash escapes in a string replacement. The session
# launcher uses replacement strings containing literal \\n sequences for Python
# source code; passing a callable prevents those sequences from being altered.
replacements = {
    "source = re.sub(run_analysis_pattern, run_analysis_replacement, source, count=1, flags=re.S)":
        "source = re.sub(run_analysis_pattern, lambda _m: run_analysis_replacement, source, count=1, flags=re.S)",
    "source = re.sub(start_pattern, start_replacement, source, count=1, flags=re.S)":
        "source = re.sub(start_pattern, lambda _m: start_replacement, source, count=1, flags=re.S)",
    "source = re.sub(on_ready_pattern, on_ready_replacement, source, count=1, flags=re.S)":
        "source = re.sub(on_ready_pattern, lambda _m: on_ready_replacement, source, count=1, flags=re.S)",
}
for old, new in replacements.items():
    source = source.replace(old, new)

# Catch any future session regex replacements of the same form.
source = re.sub(
    r"source = re\.sub\((\w+_pattern), (\w+_replacement), source, count=1, flags=re\.S\)",
    r"source = re.sub(\1, lambda _m: \2, source, count=1, flags=re.S)",
    source,
)

# The production launcher replaces bot.py's on_ready handler. The old version
# cleared the global command tree before synchronizing, which could leave the
# guild command list incomplete. Replace that generated handler with a direct
# guild/global sync that keeps every decorated command registered.
sync_handler = '''on_ready_replacement = \'\'\'@bot.event
async def on_ready():
    print("=" * 50)
    print(f"로그인 완료: {bot.user}")
    print(f"서버 수: {len(bot.guilds)} / 분석 채널: {len(analysis_channels)}개")
    print("=" * 50)
    try:
        # Global commands remain registered in the tree.
        global_synced = await bot.tree.sync()
        print(f"글로벌 Slash Command {len(global_synced)}개 동기화 완료")

        # Copy the currently registered global commands to each guild for
        # immediate testing instead of waiting for global propagation.
        for guild in bot.guilds:
            bot.tree.clear_commands(guild=guild)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"[{guild.name}] Slash Command {len(synced)}개 동기화 완료")
            print("등록 명령어:", ", ".join(command.name for command in synced))
    except Exception as e:
        print(f"Slash Command 동기화 오류: {type(e).__name__}: {e}")\'\'\''''

source, replaced = re.subn(
    r"on_ready_replacement = '''.*?'''\nsource = re\.sub\(on_ready_pattern, lambda _m: on_ready_replacement, source, count=1, flags=re\.S\)",
    sync_handler + "\nsource = re.sub(on_ready_pattern, lambda _m: on_ready_replacement, source, count=1, flags=re.S)",
    source,
    count=1,
    flags=re.S,
)
if not replaced:
    print("경고: on_ready 동기화 패치를 적용하지 못했습니다.")

compile(source, TARGET, "exec")
exec(compile(source, TARGET, "exec"), {"__name__": "__main__", "__file__": TARGET})

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

compile(source, TARGET, "exec")
exec(compile(source, TARGET, "exec"), {"__name__": "__main__", "__file__": TARGET})

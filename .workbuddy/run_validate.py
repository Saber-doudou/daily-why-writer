# -*- coding: utf-8 -*-
import subprocess, sys, datetime, json

result_file = r"F:\WorkBuddy\daily-why\.workbuddy\runner_result.txt"
out_lines = []

# 1) timestamp
ts = datetime.datetime.now().astimezone().isoformat()
out_lines.append("TIMESTAMP:" + ts)

# 2) validate script
cmd = [
    r"C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe",
    r"F:/WorkBuddy/daily-why/scripts/validate_article.py",
    "--json",
    r"F:\WorkBuddy\daily-why\articles\2026-09\2026-09-16-优化版-每日冷知识-金星日比年长.md",
]
try:
    p = subprocess.run(cmd, capture_output=True, timeout=120)
    out_lines.append("VALIDATE_RETURN_CODE:" + str(p.returncode))
    out_lines.append("VALIDATE_STDOUT_BEGIN")
    out_lines.append(p.stdout.decode("utf-8", errors="replace"))
    out_lines.append("VALIDATE_STDOUT_END")
    out_lines.append("VALIDATE_STDERR_BEGIN")
    out_lines.append(p.stderr.decode("utf-8", errors="replace"))
    out_lines.append("VALIDATE_STDERR_END")
except Exception as e:
    out_lines.append("VALIDATE_ERROR:" + repr(e))

with open(result_file, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))
print("done")

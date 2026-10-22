# -*- coding: utf-8 -*-
"""临时包装：以 UTF-8 捕获子进程输出到文件（绕过 shell 输出捕获失灵 + PS UTF-16 重定向问题）"""
import subprocess
import sys

PY = r"C:\Users\admin\.workbuddy\binaries\python\versions\3.13.12\python.exe"
SCRIPT = r"F:\WorkBuddy\daily-why\scripts\validate_article.py"
OUT = r"F:\WorkBuddy\daily-why\.workbuddy\tmp_validate_out.json"

def run_json(target_path: str, out_path: str = OUT):
    r = subprocess.run(
        [PY, SCRIPT, "--json", target_path],
        capture_output=True,
    )
    text = r.stdout.decode("utf-8", errors="replace")
    err = r.stderr.decode("utf-8", errors="replace")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
        if err:
            f.write("\n[STDERR]\n" + err)
    return r.returncode

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else r"F:\WorkBuddy\daily-why\articles\2026-09\2026-09-16-每日冷知识-金星日比年长.md"
    outp = sys.argv[2] if len(sys.argv) > 2 else OUT
    code = run_json(target, outp)
    sys.exit(0 if code == 0 else 1)

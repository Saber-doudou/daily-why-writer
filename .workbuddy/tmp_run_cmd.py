# -*- coding: utf-8 -*-
"""通用命令包装：以 UTF-8 捕获子进程输出到文件（绕过 shell 输出捕获失灵）"""
import subprocess
import sys

PY = r"C:\Users\admin\.workbuddy\binaries\python\versions\3.13.12\python.exe"

def main():
    # argv[1] = 输出文件, argv[2:] = 命令（首个若是脚本路径则用同版本 python 执行）
    out_path = sys.argv[1]
    args = sys.argv[2:]
    if args and args[0].lower().endswith(".py"):
        args = [PY] + args
    r = subprocess.run(args, capture_output=True, cwd=r"F:\WorkBuddy\daily-why")
    text = r.stdout.decode("utf-8", errors="replace")
    err = r.stderr.decode("utf-8", errors="replace")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
        if err:
            f.write("\n[STDERR]\n" + err)
    sys.exit(0 if r.returncode == 0 else 1)

if __name__ == "__main__":
    main()

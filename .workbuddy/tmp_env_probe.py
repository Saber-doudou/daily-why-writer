# -*- coding: utf-8 -*-
"""收集 WorkBuddy 安装信息：当前版本号 + 关键文件修改时间"""
import os
import datetime

BASE = r"D:\Program Files\WorkBuddy"
OUT = r"F:\WorkBuddy\daily-why\.workbuddy\tmp_env_probe.txt"

lines = []

def probe(path):
    try:
        st = os.stat(path)
        lines.append("%s | %s | %d bytes" % (
            path,
            datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            st.st_size,
        ))
    except OSError as e:
        lines.append("%s | ERROR: %s" % (path, e))

# 版本来源1: resources 下的 package.json / 版本文件
for rel in [
    r"resources\app.asar",
    r"resources\app.asar.unpacked",
    r"WorkBuddy.exe",
    r"resources\package.json",
]:
    probe(os.path.join(BASE, rel))

# 版本来源2: cli shim（上午报 dirname not found 的正是它）
cli = os.path.join(BASE, r"resources\app.asar.unpacked\cli")
if os.path.isdir(cli):
    for name in sorted(os.listdir(cli))[:20]:
        probe(os.path.join(cli, name))
    shim = os.path.join(cli, "vendor")
    if os.path.isdir(shim):
        for root, dirs, files in os.walk(shim):
            for fn in files:
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, cli)
                lines.append("shim-file | %s | %s" % (rel, datetime.datetime.fromtimestamp(os.stat(p).st_mtime).strftime("%Y-%m-%d %H:%M:%S")))

# 版本来源3: app.asar.unpacked 下 package.json / version 文件
unpacked = os.path.join(BASE, r"resources\app.asar.unpacked")
for root, dirs, files in os.walk(unpacked):
    for fn in files:
        if fn.lower() in ("package.json", "version", "version.json"):
            probe(os.path.join(root, fn))

# PortableGit（Bash 的二进制来源）
pg = r"C:\Users\admin\.workbuddy\binaries\PortableGit"
if os.path.isdir(pg):
    probe(pg)
    bashexe = os.path.join(pg, r"versions\1.2.0\bin\bash.exe")
    probe(bashexe)
    for root, dirs, files in os.walk(os.path.join(pg, "versions\1.2.0")):
        depth = root[len(pg):].count(os.sep)
        if depth >= 2:
            dirs[:] = []
            continue
        for fn in files:
            probe(os.path.join(root, fn))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("done")

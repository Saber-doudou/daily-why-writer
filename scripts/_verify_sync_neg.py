#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负面验证：证明 trends_sync_check.py（会话级 v2）能拦出两类漏行。
临时副本，跑完自删。可重跑。"""
import subprocess
import pathlib

base = pathlib.Path(r"F:\WorkBuddy\daily-why")
trends = base / ".workbuddy/memory/topics/trends.md"
tmp = base / "scripts/_trends_test.md"
py = r"C:\Users\admin\.workbuddy\binaries\python\versions\3.13.12\python.exe"
script = base / "scripts/trends_sync_check.py"


def run_case(name, keep, must_contain):
    """keep: 行过滤谓词（True=保留）。断言 exit!=0 且输出含 must_contain。"""
    lines = [l for l in trends.read_text(encoding="utf-8").splitlines() if keep(l)]
    tmp.write_text("\n".join(lines), encoding="utf-8")
    r = subprocess.run([py, str(script), "--trends", str(tmp)], capture_output=True, text=True)
    print(f"===== 负面测试 {name} STDOUT =====")
    print(r.stdout.strip())
    print(f"===== 负面测试 {name} EXIT =====", r.returncode)
    assert r.returncode != 0, f"❌ {name} 失败：脚本未拦截（应 exit!=0）"
    assert must_contain in r.stdout, f"❌ {name} 失败：输出未含「{must_contain}」"
    print(f"✅ {name} 通过\n")


# 用例1：整行删掉 09-16，模拟"某日停更" → 日期缺失应被拦
run_case(
    "1-日期缺失",
    lambda l: "2026-09-16" not in l,
    "2026-09-16",
)

# 用例2：只删 09-15 的熊猫第六指行（同日云有多重行还在）→
# 日期级校验拦不住（09-15 仍在表中），会话级校验应拦出 2次/1行 不匹配
run_case(
    "2-同日第二会话漏行",
    lambda l: "熊猫第六指" not in l,
    "会话数不匹配: 2026-09-15 主账本 2 次 / 仪表盘 1 行",
)

tmp.unlink(missing_ok=True)
print("✅ 两类负面校验均通过：日期缺失与同日第二会话漏行都能拦截")
print("✅ 已清理临时文件:", tmp.name)

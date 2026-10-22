#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trends_sync_check.py — Daily Why L2 质量仪表盘同步校验（会话级 v2，09-29 升级）

校验「主账本 (automation memory.md) 的 L2 投喂记录」与
「质量仪表盘 (trends.md) 表格行」是否完全一致，双重口径：
  1. 日期集合：任一方缺失 / 多余即失败
  2. 会话数：同日多次 L2 会话须各占一行（09-29 第三方复验发现的盲区：
     09-15 当天有「云有多重」+「熊猫第六指」两次会话，日期级校验拦不住同日第二会话漏行）

任一不一致即退出码非 0，供 L2 Phase 6 落盘前机械把关。

用法：
  python scripts/trends_sync_check.py
  python scripts/trends_sync_check.py --memory <path> --trends <path>

依据：EXP-004 约束优于指令（防 SOP 漂移导致派生表停更；09-07 重构后
质量仪表盘从 MEMORY.md 迁至 trends.md，SOP 曾漂移致停更 13 天，故加脚本把关，
把"记得回填派生表"从建议变成机械校验门槛）

注：automation memory.md 各日期块的 L2 标记格式不统一（"- **L2投喂**" /
"- **L2投喂学习**" / "- L2投喂学习（" / 标题 "## ...(L2 投喂学习)" 块内由
"- 触发：... L2 四AI投喂学习" 行承载标记），故用宽松的「L2..投喂 / 投喂学习」
提示匹配识别 L2 会话。标题行自身的提示**不计**（该类块内必有触发行，避免重复计数）。
"""
import argparse
import re
import sys
from pathlib import Path

DEFAULT_MEMORY = r"F:\WorkBuddy\daily-why\.workbuddy\automations\automation-1778312519754\memory.md"
DEFAULT_TRENDS = r"F:\WorkBuddy\daily-why\.workbuddy\memory\topics\trends.md"

DATE_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})")
L2_HINT_RE = re.compile(r"L2.{0,8}?投喂|投喂学习")
TABLE_DATE_RE = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|")


def collect_memory_l2_sessions(memory_text: str) -> dict:
    """提取 memory.md 中各日期的 L2 投喂会话数（格式不统一，宽松匹配）。

    返回 {日期: 会话数}。标题行（## 日期 ...）自身的 L2 提示不计——
    「## YYYY-MM-DD (L2 投喂学习)」这类标题块的会话由块内
    「- 触发：... L2 四AI投喂学习」行承载，标题行计了就会重复。
    """
    sessions = {}
    current = None
    for line in memory_text.splitlines():
        s = line.strip()
        m = DATE_RE.match(s)
        if m:
            current = m.group(1)
            continue
        if current and L2_HINT_RE.search(s):
            sessions[current] = sessions.get(current, 0) + 1
    return sessions


def collect_trends_rows(trends_text: str) -> dict:
    """提取 trends.md 表格中各日期的行数。返回 {日期: 行数}。"""
    rows = {}
    for line in trends_text.splitlines():
        m = TABLE_DATE_RE.match(line.strip())
        if m:
            rows[m.group(1)] = rows.get(m.group(1), 0) + 1
    return rows


def main():
    ap = argparse.ArgumentParser(description="Daily Why L2 质量仪表盘同步校验（会话级）")
    ap.add_argument("--memory", default=DEFAULT_MEMORY, help="自动化执行记录 memory.md 路径")
    ap.add_argument("--trends", default=DEFAULT_TRENDS, help="质量仪表盘 trends.md 路径")
    args = ap.parse_args()

    mem_p = Path(args.memory)
    tr_p = Path(args.trends)
    if not mem_p.exists():
        print(f"❌ 主账本不存在: {mem_p}")
        sys.exit(2)
    if not tr_p.exists():
        print(f"❌ 质量仪表盘不存在: {tr_p}")
        sys.exit(2)

    mem_text = mem_p.read_text(encoding="utf-8")
    tr_text = tr_p.read_text(encoding="utf-8")

    mem_sessions = collect_memory_l2_sessions(mem_text)
    tr_rows = collect_trends_rows(tr_text)

    mem_dates = set(mem_sessions)
    tr_dates = set(tr_rows)

    total_sessions = sum(mem_sessions.values())
    total_rows = sum(tr_rows.values())

    print(f"主账本 L2 日期数: {len(mem_dates)}（会话总数 {total_sessions}）")
    print(f"仪表盘 日期数: {len(tr_dates)}（表格行总数 {total_rows}）")

    ok = True

    missing = sorted(mem_dates - tr_dates)  # 主账本有、仪表盘缺
    extra = sorted(tr_dates - mem_dates)    # 仪表盘有、主账本无
    if missing:
        ok = False
        print(f"❌ 仪表盘缺失 {len(missing)} 个: {', '.join(missing)}")
    if extra:
        ok = False
        print(f"⚠️ 仪表盘多余 {len(extra)} 个(主账本无): {', '.join(extra)}")

    # 会话级校验：同日多次 L2 会话须各占一行
    count_mismatch = []
    for d in sorted(mem_dates & tr_dates):
        if mem_sessions[d] != tr_rows[d]:
            count_mismatch.append((d, mem_sessions[d], tr_rows[d]))
    if count_mismatch:
        ok = False
        for d, ms, ts in count_mismatch:
            print(f"❌ 会话数不匹配: {d} 主账本 {ms} 次 / 仪表盘 {ts} 行")

    if ok:
        print("✅ 主账本与质量仪表盘完全一致（日期集合 + 会话数）")
        sys.exit(0)
    else:
        print("❌ 质量仪表盘未同步，禁止结束 Phase 6")
        sys.exit(1)


if __name__ == "__main__":
    main()

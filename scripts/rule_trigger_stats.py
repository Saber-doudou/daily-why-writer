#!/usr/bin/env python3
"""
rule_trigger_stats.py — 统计 FORBIDDEN(FP) / CHECKLIST(§) 每条规则的实际触发次数

触发来源：
  - FEEDBACK_LOG.md    活跃教训（近30天，高权重 x2）
  - FEEDBACK_ARCHIVE.md 休眠教训（历史归档，低权重 x1）

用法：
  python rule_trigger_stats.py          # 全量统计
  python rule_trigger_stats.py --top 10 # 只看触发最多的
  python rule_trigger_stats.py --cold   # 只看从未触发的（零触发候选）
"""
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict

REF = Path.home() / ".workbuddy" / "skills" / "daily-why-writer" / "references"
FORBIDDEN = REF / "FORBIDDEN.md"
CHECKLIST = REF / "CHECKLIST.md"
LOG = REF / "FEEDBACK_LOG.md"
ARCHIVE = REF / "FEEDBACK_ARCHIVE.md"


def extract_rule_ids(filepath):
    """从文件提取所有被引用的 FP-XX 和 §XX（CHECKLIST §XX / §XX）"""
    fp = Counter()
    chk = Counter()
    try:
        text = Path(filepath).read_text(encoding="utf-8")
    except Exception:
        return fp, chk
    for m in re.finditer(r"FP-(\d+)", text):
        fp[int(m.group(1))] += 1
    for m in re.finditer(r"(?:CHECKLIST\s*)?§(\d+)", text):
        chk[int(m.group(1))] += 1
    # 排除 "§XX: 标题" 定义行的自引用（定义处不算触发）
    return fp, chk


def existing_rules(filepath, pattern):
    """FORBIDDEN/CHECKLIST 中实际定义的规则编号"""
    ids = set()
    try:
        text = Path(filepath).read_text(encoding="utf-8")
    except Exception:
        return ids
    for m in re.finditer(pattern, text, re.MULTILINE):
        ids.add(int(m.group(1)))
    return ids


def main():
    args = sys.argv[1:]
    top_n = None
    cold_only = False
    if "--top" in args:
        top_n = int(args[args.index("--top") + 1])
    if "--cold" in args:
        cold_only = True

    # 实际定义的规则
    fp_defs = existing_rules(FORBIDDEN, r"^## FP-(\d+)")
    chk_defs = existing_rules(CHECKLIST, r"^## (\d+)\.")

    # 触发统计（活跃教训权重2，休眠归档权重1）
    fp_trig = Counter()
    chk_trig = Counter()
    for path, w in [(LOG, 2), (ARCHIVE, 1)]:
        f, c = extract_rule_ids(path)
        for k, v in f.items():
            fp_trig[k] += v * w
        for k, v in c.items():
            chk_trig[k] += v * w

    # 合并输出
    print("=" * 72)
    print("规则触发率统计（活跃教训x2 / 休眠归档x1）")
    print("=" * 72)

    print("\n【FORBIDDEN.md — FP 规则】")
    print(f"{'编号':<6}{'触发':<6}{'状态':<10}{'说明'}")
    print("-" * 72)
    fp_rows = []
    for rid in sorted(fp_defs):
        t = fp_trig.get(rid, 0)
        status = "🔥高频" if t >= 4 else ("🟡低频" if t >= 2 else ("⚪低频" if t == 1 else "💤零触发"))
        fp_rows.append((rid, t, status))
    for rid, t, status in sorted(fp_rows, key=lambda x: -x[1]):
        if cold_only and t > 0:
            continue
        if top_n and not cold_only:
            continue
        print(f"FP-{rid:<4}{t:<6}{status:<10}")

    print("\n【CHECKLIST.md — § 自检项】")
    print(f"{'编号':<6}{'触发':<6}{'状态':<10}{'说明'}")
    print("-" * 72)
    chk_rows = []
    for rid in sorted(chk_defs):
        t = chk_trig.get(rid, 0)
        status = "🔥高频" if t >= 4 else ("🟡低频" if t >= 2 else ("⚪低频" if t == 1 else "💤零触发"))
        chk_rows.append((rid, t, status))
    for rid, t, status in sorted(chk_rows, key=lambda x: -x[1]):
        if cold_only and t > 0:
            continue
        if top_n and not cold_only:
            continue
        print(f"§{rid:<5}{t:<6}{status:<10}")

    if top_n and not cold_only:
        print("\n【触发 TOP{}】".format(top_n))
        print(f"{'类型':<8}{'编号':<8}{'触发':<6}")
        print("-" * 40)
        all_r = [(f"FP-{r}", t) for r, t in fp_trig.items() if r in fp_defs] + \
                [(f"§{r}", t) for r, t in chk_trig.items() if r in chk_defs]
        for name, t in sorted(all_r, key=lambda x: -x[1])[:top_n]:
            print(f"{name:<8}{t:<8}")

    # 汇总
    zero_fp = sum(1 for r in fp_defs if fp_trig.get(r, 0) == 0)
    zero_chk = sum(1 for r in chk_defs if chk_trig.get(r, 0) == 0)
    print()
    print("=" * 72)
    print(f"FP 总数 {len(fp_defs)} | 零触发 {zero_fp} ({zero_fp/len(fp_defs)*100:.0f}%)")
    print(f"§ 总数 {len(chk_defs)} | 零触发 {zero_chk} ({zero_chk/len(chk_defs)*100:.0f}%)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
rule_lifecycle.py — 规则健康度分析 + CHECKLIST 升降级分区

核心洞察（Master 2026-08-26）：
  规则零触发 ≠ 无用。很多规则"写了之后问题就不再发生"——这是预防有效。
  真正的判断维度是：
    1. 该规则是否有对应的"原始教训"（即教训记录里提过它）→ 有=确实解决过问题
    2. 创建后是否再犯（活跃教训里是否再次引用）→ 再犯=预防失败需关注

模式：
  分析模式（默认）：输出三类统计
    ✅ 预防有效   — 有原始教训 + 近30天零触发（规则起作用了，保留）
    🔥 持续再犯   — 活跃教训里仍高频引用（规则执行不到位，需升级关注）
    ⚠️ 从未验证   — 连原始教训都没有（新规则/待验证，保留）

  分区模式（--update）：重写 CHECKLIST.md 为 活跃区/预防区/待验证区 三区结构
    - 不删除任何规则，编号不变
    - 活跃区 = 近30天被引用（必查）
    - 预防区 = 有教训但近期零触发（按需）
    - 待验证区 = 从未被引用（新规则，保留）
    - 支持 --dry-run 预览

用法：
  python rule_lifecycle.py [--fp | --chk]          # 分析
  python rule_lifecycle.py --update [--dry-run]    # 重写 CHECKLIST 分区
"""
import re
import sys
import datetime
from pathlib import Path
from collections import Counter

REF = Path.home() / ".workbuddy" / "skills" / "daily-why-writer" / "references"
FORBIDDEN_P = REF / "FORBIDDEN.md"
CHECKLIST_P = REF / "CHECKLIST.md"
LOG_P = REF / "FEEDBACK_LOG.md"
ARCHIVE_P = REF / "FEEDBACK_ARCHIVE.md"

FORBIDDEN = FORBIDDEN_P.read_text(encoding="utf-8")
CHECKLIST = CHECKLIST_P.read_text(encoding="utf-8")
LOG = LOG_P.read_text(encoding="utf-8")
ARCHIVE = ARCHIVE_P.read_text(encoding="utf-8")


def defined_rules(text, pat):
    return {int(m) for m in re.findall(pat, text, re.MULTILINE)}


def ref_counts(text, pat):
    return Counter(int(x) for x in re.findall(pat, text))


def analyze_chk():
    chk_defs = defined_rules(CHECKLIST, r"^## (\d+)\.")
    chk_log = ref_counts(LOG, r"(?:CHECKLIST\s*)?§(\d+)")
    chk_arch = ref_counts(ARCHIVE, r"(?:CHECKLIST\s*)?§(\d+)")
    active, preventive, new = [], [], []
    for rid in sorted(chk_defs):
        log_n = chk_log.get(rid, 0)
        arch_n = chk_arch.get(rid, 0)
        if log_n > 0:
            active.append((rid, log_n))
        elif arch_n > 0:
            preventive.append((rid, arch_n))
        else:
            new.append(rid)
    return active, preventive, new


def split_checklist():
    """把 CHECKLIST.md 拆成 (头部, {编号: 完整条目块})

    修复（2026-10-19）：原逻辑把非数字二级标题（## 🔥/🛡️/🔬 区标题）误并入上一个
    ## N. 条目块，导致每次 --update 重建时区标题被携带并叠加，文件累积膨胀（实测
    1340 行、35 个重复待验证区标题）。现改为：任何二级标题均为块边界，非数字标题
    直接丢弃（不并入、不开启块），仅 ## N. 构成条目块。头部不再从脏文件提取，改由
    rebuild_checklist 生成固定干净头部。
    """
    text = CHECKLIST
    lines = text.split("\n")
    blocks = {}
    cur_num = None
    cur_lines = []
    for line in lines:
        if line.startswith("## "):
            # 任何二级标题都先闭合当前块
            if cur_num is not None:
                blocks[cur_num] = "\n".join(cur_lines).rstrip() + "\n"
                cur_num = None
                cur_lines = []
            m = re.match(r"^## (\d+)\.", line)
            if m:
                cur_num = int(m.group(1))
                cur_lines = [line]
            # 非数字二级标题（区标题）直接丢弃，不开启块也不并入
        elif cur_num is not None:
            cur_lines.append(line)
    if cur_num is not None:
        blocks[cur_num] = "\n".join(cur_lines).rstrip() + "\n"
    return "", blocks


def rebuild_checklist(active, preventive, new):
    """重建三区结构

    修复（2026-10-19）：头部由本函数生成固定干净内容，不再拼接 split_checklist
    返回的旧头部（旧头部可能含历史累积的重复说明块），避免文件再次膨胀。
    """
    _, blocks = split_checklist()
    active_ids = {r for r, _ in active}
    preventive_ids = {r for r, _ in preventive}
    new_ids = set(new)

    # 检查是否有未捕获的编号
    all_ids = active_ids | preventive_ids | new_ids
    missing = [i for i in blocks if i not in all_ids]
    if missing:
        print(f"⚠️ 警告: {len(missing)} 个条目未被分类: {missing}")

    today = datetime.date.today().isoformat()
    header = (
        "> **分区说明**：活跃区=近30天被引用（写后必查）；预防区=有教训但近期零触发（按需）；"
        "待验证区=从未被引用（新规则保留）\n\n"
        f"> **更新时间**：{today}（rule_lifecycle.py --update 自动维护）\n"
    )
    sections = [header]

    # 活跃区
    sections.append("---\n\n## 🔥 活跃区（写后自检必查）\n")
    active_sorted = sorted(active, key=lambda x: -x[1])
    sections.append(f"> 共 {len(active)} 条 | 近30天仍被教训引用，是当前高发问题\n")
    for rid, n in active_sorted:
        if rid in blocks:
            sections.append(blocks[rid])
    sections.append("\n")

    # 预防区
    sections.append("---\n\n## 🛡️ 预防区（预防有效，按需查阅）\n")
    preventive_sorted = sorted(preventive, key=lambda x: -x[1])
    sections.append(f"> 共 {len(preventive)} 条 | 有原始教训但近期零触发，规则起作用了，保留\n")
    for rid, n in preventive_sorted:
        if rid in blocks:
            sections.append(blocks[rid])
    sections.append("\n")

    # 待验证区
    sections.append("---\n\n## 🔬 待验证区（新规则，手动查阅）\n")
    sections.append(f"> 共 {len(new)} 条 | 从未被教训引用，可能尚未遇到或规则较新，保留等待验证\n")
    for rid in sorted(new_ids):
        if rid in blocks:
            sections.append(blocks[rid])
    sections.append("\n")

    return "\n".join(sections)


def main():
    args = sys.argv[1:]
    if "--update" in args:
        dry_run = "--dry-run" in args
        active, preventive, new = analyze_chk()
        total = len(active) + len(preventive) + len(new)
        print(f"📊 CHECKLIST 状态: 活跃 {len(active)} / 预防 {len(preventive)} / 待验证 {len(new)} / 共 {total}")
        new_text = rebuild_checklist(active, preventive, new)
        if dry_run:
            print("\n=== 分区预览 ===")
            print(f"头部长度: {len(header_of(new_text))} 字符")
            print(f"活跃区条目: {[r for r, _ in sorted(active, key=lambda x: -x[1])][:10]} ...")
            print(f"预防区条目数: {len(preventive)}")
            print(f"待验证区条目数: {len(new)}")
            print(f"新文件总长: {len(new_text)} 字符（原 {len(CHECKLIST)}）")
            print("\n✅ 干跑完成，未写入")
            return
        CHECKLIST_P.write_text(new_text, encoding="utf-8")
        print(f"✅ CHECKLIST.md 已重写为三区结构")
        print(f"   活跃 {len(active)} | 预防 {len(preventive)} | 待验证 {len(new)}")
        print(f"   大小: {len(CHECKLIST)} → {len(new_text)} 字符")
        return

    # 分析模式
    if "--chk" in args or "all" not in args:
        active, preventive, new = analyze_chk()
        print("=" * 70)
        print(f"【CHECKLIST §】共 {len(active)+len(preventive)+len(new)} 条")
        print(f"  🔥 活跃/再犯(近30天有引用): {len(active)} 条")
        print(f"  ✅ 预防有效(有教训+近期零触发): {len(preventive)} 条")
        print(f"  🔬 待验证(从未被引用): {len(new)} 条")
        print("-" * 70)
        print("🔥 活跃规则 TOP10:")
        for rid, n in sorted(active, key=lambda x: -x[1])[:10]:
            print(f"  §{rid}: {n}次")
        print()
        print("🔬 待验证明细:")
        for rid in new:
            print(f"  §{rid}")


def header_of(text):
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("## "):
            return "\n".join(lines[:i])
    return text


if __name__ == "__main__":
    main()

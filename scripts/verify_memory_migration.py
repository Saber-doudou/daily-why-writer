#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verify_memory_migration.py —— 记忆下沉「零损失」通用校验（v3 闸门 0）

背景（EXP-004「约束优于指令」+ 数据可信度铁律）：
    记忆治理每一步都在把 MEMORY.md 的内容下沉到 topics/ 分片。
    人工「我看着删的，应该没丢」不可信，也不可复现。
    历次教训：09-07 分片重构靠人工核对；09-08 架构区削减时，
    若不用脚本，至少 2 处遗漏（L2「四AI投喂」/ L3「IMA+GitHub」定位）会静默丢失。

作用：
    对比「下沉前快照」与「当前 MEMORY.md」，自动提取被删行中的关键 token
    （反引号内容 / 数字 / 标识符 / 中文专名），再到 topics/ 分片与权威源
    （scripts/config.json）中逐一检索。找不回的标记为 LOST 并 exit 1。

    与人工列清单相比的好处：**不会漏列**——你没想到的 token 也会被提取。

用法：
    python verify_memory_migration.py --snapshot archive/XXX.md
    python verify_memory_migration.py --snapshot archive/XXX.md --current path/to/MEMORY.md
    python verify_memory_migration.py --snapshot archive/XXX.md --json
    python verify_memory_migration.py --snapshot archive/XXX.md --search-dir .workbuddy/memory/topics

退出码：
    0 = 无丢失（或 N/A 项不计）
    1 = 存在 LOST（被删事实在分片中找不回）
    2 = 参数/文件错误

v1.0 2026-09-08  初版（架构区削减时，替代手写 18 条清单的临时脚本）
"""
import argparse
import io
import json
import os
import re
import sys

BASE = "F:/WorkBuddy/daily-why"

# 提取 token 的规则：按优先级，命中即收集
PATTERNS = [
    (re.compile(r"`([^`]{3,})`"), "反引号"),          # `scripts/config.json`
    (re.compile(r"\b([A-Za-z_][A-Za-z0-9_.\-]{5,})\b"), "标识符"),  # general-purpose
    (re.compile(r"(\d{4,})\b"), "数字"),               # 7457707061698771
    (re.compile(r"(\d{4}-\d{2}-\d{2})"), "日期"),       # 2026-09-07
    (re.compile(r"([一-龥]{2,6}?AI[一-龥]{0,4})"), "AI专名"),  # 四AI投喂
]

# 噪声词：提取出来但无检索意义，跳过
NOISE = {
    "写作", "手动", "自动", "内容", "全文", "权威", "索引", "文章", "版本",
    "压缩", "备份", "追加", "重构", "优化版", "设计如此", "非缺陷",
    "true", "false", "name", "path", "lines", "chars",
}

# 权威源（除 topics/ 分片外，也允许在这些文件中找回）
EXTRA_SOURCES = [
    f"{BASE}/scripts/config.json",
]


def expand_variants(token):
    """展开简写记法：/ 表并列、(x) 表可选。

    例：dailywhy学习(总结)/投喂 → [dailywhy学习, dailywhy学习总结, 投喂]
    不展开的话，简写记法本身会被误报为「丢失」——但它不是事实，只是记法。
    """
    out = []
    for part in token.split("/"):
        part = part.strip()
        if not part:
            continue
        m = re.search(r"\(([^)]*)\)", part)
        if m:
            out.append(part.replace(m.group(0), "").strip())
            out.append(part.replace(m.group(0), m.group(1)).strip())
        else:
            out.append(part)
    return [o for o in out if o] or [token]


def extract_tokens(line):
    out = []
    for pat, kind in PATTERNS:
        for m in pat.findall(line):
            t = m if isinstance(m, str) else m[0]
            t = t.strip()
            if len(t) < 2 or t in NOISE:
                continue
            out.append((t, kind))
    return out


def load_corpus(search_dirs):
    """返回 [(路径, 正文)]"""
    corpus = []
    for d in search_dirs:
        if os.path.isfile(d):
            corpus.append((d, io.open(d, encoding="utf-8", errors="ignore").read()))
            continue
        for root, _, files in os.walk(d):
            for fn in files:
                if fn.endswith((".md", ".json")):
                    p = os.path.join(root, fn)
                    try:
                        corpus.append((p, io.open(p, encoding="utf-8", errors="ignore").read()))
                    except OSError:
                        pass
    for p in EXTRA_SOURCES:
        if os.path.exists(p):
            corpus.append((p, io.open(p, encoding="utf-8", errors="ignore").read()))
    return corpus


def main():
    ap = argparse.ArgumentParser(description="记忆下沉零损失校验")
    ap.add_argument("--snapshot", required=True, help="下沉前的快照文件")
    ap.add_argument("--current", default=f"{BASE}/.workbuddy/memory/MEMORY.md",
                    help="当前 MEMORY.md")
    ap.add_argument("--search-dir", action="append", default=None,
                    help="找回检索目录/文件，可重复；默认 topics/ 与 memory/")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="连「主文件仍保留」的 token 也打印")
    args = ap.parse_args()

    if not os.path.exists(args.snapshot):
        print(f"错误：快照不存在 {args.snapshot}", file=sys.stderr)
        return 2
    if not os.path.exists(args.current):
        print(f"错误：当前文件不存在 {args.current}", file=sys.stderr)
        return 2

    snap = io.open(args.snapshot, encoding="utf-8").read()
    cur = io.open(args.current, encoding="utf-8").read()

    # 检索时排除快照自身与当前文件（否则「当前仍保留」会被误判成「已找回」）
    snap_abs = os.path.abspath(args.snapshot)
    cur_abs = os.path.abspath(args.current)

    search_dirs = args.search_dir or [
        f"{BASE}/.workbuddy/memory/topics",
        f"{BASE}/.workbuddy/memory/MEMORY.md",
    ]
    corpus = [(p, b) for p, b in load_corpus(search_dirs)
              if os.path.abspath(p) not in (snap_abs, cur_abs)]

    snap_lines = set(l.strip() for l in snap.split("\n") if l.strip())
    cur_lines = set(l.strip() for l in cur.split("\n") if l.strip())
    deleted = [l for l in snap.split("\n")
               if l.strip() and l.strip() not in cur_lines]

    rows, lost = [], 0
    for line in deleted:
        for token, kind in extract_tokens(line):
            if token in cur:
                rows.append({"token": token, "kind": kind, "status": "KEEP",
                             "where": "主文件仍保留"})
                continue  # 该 token 未丢失；继续检查本行其余 token，不降覆盖率
            # 简写记法按变体逐个找回，任一命中即算可找回
            matched = None
            for v in expand_variants(token):
                h = next((p for p, b in corpus if v in b), None)
                if h:
                    matched = (v, h)
                    break
            if matched:
                v, h = matched
                rows.append({"token": token, "kind": kind, "status": "OK",
                             "where": os.path.relpath(h, BASE) + (f"  ←{v}" if v != token else "")})
            else:
                lost += 1
                rows.append({"token": token, "kind": kind, "status": "LOST",
                             "where": ""})

    if args.json:
        print(json.dumps({"deleted_lines": len(deleted), "lost": lost, "rows": rows},
                         ensure_ascii=False, indent=2))
        return 1 if lost else 0

    print("=" * 66)
    print("零损失校验：记忆下沉")
    print("=" * 66)
    print(f"快照 {len(snap)} 字符 → 当前 {len(cur)} 字符（-{len(snap) - len(cur)}）")
    keep = sum(1 for r in rows if r["status"] == "KEEP")
    found = sum(1 for r in rows if r["status"] == "OK")
    print(f"被删/改写行：{len(deleted)} 行，提取 token：{len(rows)} 个"
          f"（已下沉找回 {found}、主文件保留 {keep}）\n")
    for r in rows:
        if r["status"] == "KEEP" and not args.verbose:
            continue
        mark = {"KEEP": "KEEP", "OK": " OK ", "LOST": "❌"}.get(r["status"], r["status"])
        print(f"  [{mark}] {r['token']:<34} {r['where']}")
    if not args.verbose and keep:
        print(f"  （{keep} 个 token 仍在主文件，未显示；--verbose 查看全部）")
    print("\n" + "=" * 66)
    print(f"结果：{found} 已下沉找回 / {keep} 主文件保留 / {lost} 丢失")
    print("=" * 66)
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main())

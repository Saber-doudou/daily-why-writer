#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
memory_budget.py —— MEMORY.md 写入前预算闸门（v3 闸门 5「写入准入」）

背景（数据可信度铁律 + EXP-004「约束优于指令」）：
    09-07 一次审计就往 MEMORY.md 写了 250 到 400 字符，而当时余量只有 356；
    09-08 我只把一行 kb_id 的指向改长，§4 区就从 147 涨到 161 当场告警。
    两次都是「心算觉得放得下」造成的。AI 估算字符数必失真，必须机器算。

作用：
    写入前先算账，回答三个问题：
    1. 加 N 字符后总量还合规吗
    2. 加到指定区后该区还合规吗（**总量合规但单区爆掉才是常态**）
    3. 放不下时，明确告知要从哪个区砍多少

用法：
    python memory_budget.py                              # 盘点当前余量
    python memory_budget.py --add 200                    # 只算总量
    python memory_budget.py --add 200 --section "1. 架构与自动化"   # 精确到区
    python memory_budget.py --add 200 --json             # 机器可读

退出码：
    0 = 放得下（或仅盘点）
    1 = 放不下（总量或指定区会超限）
    2 = 参数/文件错误

v1.0 2026-09-08  初版（记忆治理 v3 第 5 步「写入准入」）
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_memory_size as cms  # noqa: E402  复用分区配额定义，避免两处维护

MEMORY = cms.DEFAULT_TARGETS[0][1]
LIMIT = cms.DEFAULT_TARGETS[0][2]
WARN_AT = cms.DEFAULT_TARGETS[0][3]


def _norm(s):
    """归一化：只保留中英文数字，去掉 emoji、标点、空格。

    背景：区标题形如「## 3. ⚠️ 铁律（常驻 5 条…）」，而人自然输入的是「3. 铁律」，
    直接子串匹配必失败（09-08 实测）。归一化后「3铁律」可命中。
    """
    return re.sub(r"[^0-9A-Za-z一-龥]", "", s)


def scan(path):
    """返回 (总字符, [(区标题, 字符数, 条目数, 配额)])，按剩余余量升序。"""
    text = io.open(path, encoding="utf-8").read()
    buckets, cur, n, items = [], "(文件头/无章节)", 0, 0
    for line in text.split("\n"):
        if line.startswith("## "):
            buckets.append((cur, n, items))
            cur, n, items = line.strip(), 0, 0
        else:
            n += len(line) + 1
            s = line.strip()
            if s.startswith(("- ", "* ")):
                items += 1
    buckets.append((cur, n, items))
    rows = []
    for title, chars, items in buckets:
        q = cms.quota_of(title, items)
        rows.append({"section": title, "chars": chars, "quota": q,
                     "items": items,
                     "free": (q - chars) if q else None})
    rows.sort(key=lambda r: (r["free"] is None, r["free"] if r["free"] is not None else 0))
    return len(text), rows


def main():
    ap = argparse.ArgumentParser(description="MEMORY.md 写入前预算闸门")
    ap.add_argument("--add", type=int, default=0, help="本次预计新增字符数")
    ap.add_argument("--section", default="", help="写到哪个区（标题包含该串即命中）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(MEMORY):
        print(f"错误：文件不存在 {MEMORY}", file=sys.stderr)
        return 2

    total, rows = scan(MEMORY)
    total_after = total + args.add
    total_ok = total_after <= LIMIT

    hit = None
    if args.section:
        q = args.section
        hit = next((r for r in rows if q in r["section"]), None)          # 精确子串
        if hit is None:                                                    # 归一化兜底
            nq = _norm(q)
            hit = next((r for r in rows if nq and nq in _norm(r["section"])), None)
        if hit is None:
            print(f"错误：未找到匹配「{args.section}」的分区。现有分区：",
                  file=sys.stderr)
            for r in rows:
                print(f"  - {r['section']}", file=sys.stderr)
            return 2

    sec_ok = True
    sec_over = 0
    if hit and hit["quota"]:
        after = hit["chars"] + args.add
        sec_ok = after <= hit["quota"]
        sec_over = max(0, after - hit["quota"])

    if args.json:
        print(json.dumps({
            "total": total, "add": args.add, "total_after": total_after,
            "limit": LIMIT, "total_ok": total_ok,
            "section": hit["section"] if hit else None,
            "section_ok": sec_ok, "section_over": sec_over,
            "rows": rows,
        }, ensure_ascii=False, indent=2))
        return 0 if (total_ok and sec_ok) else 1

    print("=" * 64)
    print("MEMORY.md 写入预算")
    print("=" * 64)
    print(f"当前 {total} / {LIMIT}（余量 {LIMIT - total}）")
    if args.add:
        flag = "✅" if total_ok else "❌"
        tag = "仍在预警线内" if total_after <= WARN_AT else "已过预警线"
        print(f"新增 {args.add} → {total_after} / {LIMIT}"
              f"（{round(total_after / LIMIT, 2)}x，{tag}）  {flag}")

    if hit:
        print()
        print(f"目标区：{hit['section']}")
        q = hit["quota"]
        if q is None:
            print(f"  该区无配额定义（{hit['chars']} 字符），不受分区闸门约束")
        else:
            print(f"  当前 {hit['chars']} / {q}（余量 {q - hit['chars']}）")
            after = hit["chars"] + args.add
            if sec_ok:
                print(f"  新增 {args.add} → {after} / {q}  ✅ 放得下")
            else:
                print(f"  新增 {args.add} → {after} / {q}  ❌ 超 {sec_over}")
                print(f"  → 必须先从本区砍掉至少 {sec_over} 字符（下沉到 topics/ 分片），"
                      f"或改写到余量充足的区")

    print()
    print("各区余量（升序，优先砍最上面的）：")
    for r in rows:
        if r["quota"] is None:
            print(f"  {'—':>6}  {r['section'][:50]}  （无配额，{r['chars']} 字符）")
        else:
            mark = "❌" if r["free"] < 0 else ("⚠️" if r["free"] < 20 else " ")
            print(f"  {r['free']:>6}  {r['section'][:50]} {mark}")
    print("=" * 64)

    if not total_ok:
        print(f"结论：❌ 放不下。总量会超 {total_after - LIMIT} 字符，"
              f"须先下沉或精简后再写")
    elif hit and not sec_ok:
        print(f"结论：❌ 放不下。目标区会超 {sec_over} 字符（总量虽合规，单区已爆）")
    elif args.add:
        print("结论：✅ 放得下，可以写入（写后仍需跑 check_memory_size.py 复核）")
    else:
        print("结论：仅盘点，未声明增量")
    return 0 if (total_ok and sec_ok) else 1


if __name__ == "__main__":
    sys.exit(main())

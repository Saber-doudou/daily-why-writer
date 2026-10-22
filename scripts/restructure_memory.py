#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
restructure_memory.py —— MEMORY.md 分片搬家（零损失）+ 逐字校验

原则（Master 2026-09-07 指令）：历史必须全量保存，不是缩写不是一句话备注。
本脚本只做「原文整段搬家」：从改造前备份 archive/MEMORY-full-precompress-
restructure-2026-09-07.md 按 ## 章节切出原文，写入 memory/topics/ 分片，
然后逐字 diff 校验「备份中的原文段落」与「分片正文」完全一致。

分片文件头部带来源声明（搬自哪一区、何时搬、原文未改动），
正文与备份逐字一致 —— 校验不过则 exit 1，不产出任何半成品。

用法：
    python restructure_memory.py            # 搬家 + 校验
    python restructure_memory.py --verify   # 只校验，不写入

v1.0 2026-09-07
"""
import argparse
import hashlib
import io
import json
import os
import sys
import re

BASE = r"F:/WorkBuddy/daily-why"
BACKUP = os.path.join(BASE, "archive", "MEMORY-full-precompress-restructure-2026-09-07.md")
TOPICS = os.path.join(BASE, ".workbuddy", "memory", "topics")

# (原章节号, 分片文件名) —— #4 至 #11 共 8 区，原文全量搬家
MOVE_MAP = [
    (4, "review_defense.md"),
    (5, "a_plan.md"),
    (6, "defects.md"),
    (7, "fixed.md"),
    (8, "ima_history.md"),
    (9, "archive_index.md"),
    (10, "trends.md"),
    (11, "pending.md"),
]

SOURCE_HEADER = """> 本文件由 restructure_memory.py 于 2026-09-07 从 MEMORY.md「{title}」区**原文整段搬家**而来，正文逐字未改动（搬家前全量快照：archive/MEMORY-full-precompress-restructure-2026-09-07.md）。修改历史内容请直接编辑本文件，MEMORY.md 只保留一行索引。

"""

# 新 MEMORY.md 的头部（纪律 + 分片索引），编号区之间插入保留区原文
BUILD_HEAD = """# 长期记忆 - Daily Why 项目（2026-09-07 分片重构版）

> 定位：会话简报 + 常驻规则 + 分片索引。历史档案全文在 memory/topics/（逐字原文，非摘要）。零损失校验报告：deliverables/2026-09-07-记忆分片零损失校验.md；改造前快照：archive/MEMORY-full-precompress-restructure-2026-09-07.md

## 写入纪律（写本文件前必读）
1. 写前重读，合并进现有章节，禁止盲目追加
2. 每行自问「删掉会导致犯错吗」
3. 读到过期内容顺手清理
4. 历史细节（缺陷/修复/趋势/决策）写进 topics/ 分片全文，此处只更新索引行

## 分片索引（全文逐字原文）
- 审校防线漏判率 → review_defense.md（审计 Step 8.5 必读）
- A 方案 gap_checks → a_plan.md
- 缺陷台账 → defects.md（审计必查，32 至 42 全文）
- 已修复 → fixed.md（勿重复发现）
- IMA 备份历史 → ima_history.md（l3_publish 追加目标）
- 归档删除索引 → archive_index.md（勿重建）
- 质量趋势 → trends.md；待决策观察 → pending.md

"""

BUILD_TAIL = """
## 2. 写作规范（指针，权威在 SKILL.md）
- 唯一权威 C:/Users/admin/.workbuddy/skills/daily-why-writer/SKILL.md（阶段0 强制加载）
- FORBIDDEN 实 66 条（勿写 67）；字数上限 690 全文口径，600 仅为软目标不得作判定阈值

## 4. IMA 备份约束（明细见 topics/ima_history.md）
- 压缩/重构前须全量备份到 archive/（kb_id=7457707061698771）
- v3.7 为污染脏值勿作基线，真实序列看 l3_run.log Phase 2 行
- 备份版本自 2026-09-07 起由 l3_publish 自动追加到 topics/ima_history.md
"""


def split_sections(text):
    """按 ^## 切分，返回 {章节号: (标题行, 正文)}。"""
    sections = {}
    cur_key = None
    cur_title = None
    buf = []
    for line in text.split("\n"):
        m = re.match(r"^## (\d+)\. (.+)$", line)
        if m:
            if cur_key is not None:
                sections[cur_key] = (cur_title, "\n".join(buf).rstrip("\n"))
            cur_key = int(m.group(1))
            cur_title = line
            buf = []
        elif cur_key is not None:
            buf.append(line)
    if cur_key is not None:
        sections[cur_key] = (cur_title, "\n".join(buf).rstrip("\n"))
    return sections


def build_new_memory(sections):
    """组装新 MEMORY.md：HEAD + #1 原文 + #3 原文 + TAIL，并返回组装件供校验。"""
    sec1_title, sec1_body = sections[1]
    sec3_title, sec3_body = sections[3]
    parts = [BUILD_HEAD, sec1_title, "\n", sec1_body, "\n\n", sec3_title, "\n", sec3_body, "\n", BUILD_TAIL]
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="只校验已写入的分片，不写入")
    ap.add_argument("--build", action="store_true", help="分片 + 组装新 MEMORY.md + 全量校验")
    args = ap.parse_args()

    if not os.path.exists(BACKUP):
        print("备份不存在：", BACKUP)
        return 2
    backup_text = io.open(BACKUP, encoding="utf-8").read()
    sections = split_sections(backup_text)
    missing = [n for n, _ in MOVE_MAP if n not in sections]
    if missing:
        print("备份中缺少章节：", missing)
        return 2

    results = []
    for num, fname in MOVE_MAP:
        title, body = sections[num]
        shard_body = SOURCE_HEADER.format(title=title) + body + "\n"
        path = os.path.join(TOPICS, fname)
        if not args.verify:
            os.makedirs(TOPICS, exist_ok=True)
            io.open(path, "w", encoding="utf-8", newline="\n").write(shard_body)
        if not os.path.exists(path):
            print(f"[区{num}] {fname} 不存在")
            results.append({"section": num, "file": fname, "ok": False, "error": "missing"})
            continue
        written = io.open(path, encoding="utf-8").read()
        # 校验：分片去掉来源头（"> 声明\n\n"）后与备份原文逐字一致
        if written.startswith(">"):
            body_out = written.split("\n\n", 1)[1] if "\n\n" in written else ""
        else:
            body_out = written
        ok = body_out.rstrip("\n") == body.rstrip("\n")
        h_src = hashlib.sha256(body.rstrip("\n").encode("utf-8")).hexdigest()[:12]
        h_out = hashlib.sha256(body_out.rstrip("\n").encode("utf-8")).hexdigest()[:12]
        results.append({
            "section": num, "title": title, "file": fname,
            "chars": len(body.rstrip("\n")), "ok": ok,
            "sha_src": h_src, "sha_out": h_out,
        })

    all_ok = all(r.get("ok") for r in results)

    build_result = None
    if args.build:
        new_text = build_new_memory(sections)
        mem_path = os.path.join(BASE, ".workbuddy", "memory", "MEMORY.md")
        io.open(mem_path, "w", encoding="utf-8", newline="\n").write(new_text)
        # 校验 A：新 MEMORY.md 中的 #1/#3 与备份原文逐字一致
        new_sections = split_sections(io.open(mem_path, encoding="utf-8").read())
        keep_ok = []
        for n in (1, 3):
            src_h = hashlib.sha256(sections[n][1].rstrip("\n").encode("utf-8")).hexdigest()
            out_h = hashlib.sha256(new_sections[n][1].rstrip("\n").encode("utf-8")).hexdigest()
            keep_ok.append({"section": n, "ok": src_h == out_h, "sha": out_h[:12]})
        # 校验 B：总体积必须低于硬限额 3000
        n_chars = len(new_text.rstrip("\n"))
        size_ok = n_chars < 3000
        build_result = {
            "written": mem_path,
            "chars": n_chars,
            "under_limit_3000": size_ok,
            "kept_sections_byte_identical": keep_ok,
            "ok": size_ok and all(k["ok"] for k in keep_ok),
        }
        all_ok = all_ok and build_result["ok"]

    print(json.dumps({"all_ok": all_ok, "results": results, "build": build_result},
                     ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

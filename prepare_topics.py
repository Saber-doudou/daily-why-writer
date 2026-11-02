#!/usr/bin/env python3
"""
prepare_topics.py — 扫描所有历史文章和 memory.md，提取已用话题
输出 topics_context.json，供 automation-2 prompt 使用，替代 prompt 中硬编码的话题列表。

用法：
    python prepare_topics.py
    python prepare_topics.py --workspace F:/WorkBuddy/daily-why
    python prepare_topics.py --output topics_context.json --limit 50
    python prepare_topics.py --compact

2026-10-23 R1（P1-5 双文件 SSOT）：--compact 不再"只写 compact 后提前 return"。
L1 每日只调用 --compact，旧实现下 full 永久停在最后一次全量运行（09-15，40 条），
而 check_topic.py 读的正是 full，形成双文件漂移（本日实测 full=40/compact=50，
compact 独有 26 条、full 独有 16 条）。现两种模式都由同一次 scan_all() 结果写入
full 与 compact，并在写后回读断言 generated_at / total_count / topic_summaries 三项一致。
"""

import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 导入公共模块
from topic_utils import (
    clean_text,
    normalize_topic,
    is_valid_topic,
    extract_topic_from_article,
    extract_topics_from_memory,
    extract_keywords,
)

FULL_NAME = "config/topics_context.json"
COMPACT_NAME = "config/topics_context_compact.json"


def scan_all(workspace: Path, limit: int = 50) -> dict:
    """扫描所有来源，生成 topics_context"""
    all_topics = []

    # 1. 扫描文章文件（排除 _废弃 软删除标记文件，与 check_topic 同规则，09-15）
    md_files = sorted(workspace.glob("articles/**/*-每日冷知识*.md"), reverse=True)
    for fp in md_files[:limit]:
        if "_废弃" in fp.name:
            continue
        info = extract_topic_from_article(fp)
        if info:
            info["source"] = "article"
            all_topics.append(info)

    # 2. 从 memory.md 补充（可能有文章文件没覆盖的）
    memory_paths = [
        workspace / ".workbuddy" / "automations" / "automation-1778312519754" / "memory.md",
        workspace / ".workbuddy" / "automations" / "automation-2" / "memory.md",
        workspace / ".codebuddy" / "automations" / "automation-2" / "memory.md",
    ]
    existing_dates = {t["date"] for t in all_topics}

    for mp in memory_paths:
        mem_topics = extract_topics_from_memory(mp)
        for t in mem_topics:
            if t["date"] not in existing_dates:
                all_topics.append(t)
                existing_dates.add(t["date"])

    # 按日期倒序
    all_topics.sort(key=lambda x: x["date"], reverse=True)

    # 第一轮去重：同一日期+同一话题，只保留最新
    seen = set()
    unique_topics = []
    for t in all_topics:
        key = f"{t['date']}:{t['topic']}"
        if key not in seen:
            seen.add(key)
            # 提取关键词
            t["keywords"] = extract_keywords(t["topic"])
            unique_topics.append(t)

    # 第二轮：标准化话题格式（去 emoji、去前缀等）
    for t in unique_topics:
        t["topic"] = normalize_topic(t["topic"])

    # 第三轮去重：同一话题（标准化后）只保留最新一条
    seen_topic = set()
    deduped_topics = []
    for t in unique_topics:
        if t["topic"] not in seen_topic:
            seen_topic.add(t["topic"])
            deduped_topics.append(t)

    # 标记非标准格式话题（供 prompt 选题时参考）
    for t in deduped_topics:
        t["is_standard"] = is_valid_topic(t["topic"])

    unique_topics = deduped_topics

    # 提取所有已用话题的摘要（仅标准格式，用于去重）
    topic_summaries = [t["topic"] for t in unique_topics if t["is_standard"]]

    # 按分类统计
    category_counts = {}
    for t in unique_topics:
        cat = t.get("category", "未分类")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "generated_at": datetime.now().isoformat(),
        "total_count": len(unique_topics),
        "topic_summaries": topic_summaries,
        "category_stats": category_counts,
        "topics": unique_topics,
    }


def build_compact(result: dict) -> dict:
    """compact 是 full 的子集视图，必须由同一个 result 派生，不允许独立扫描。"""
    return {
        "generated_at": result["generated_at"],
        "total_count": result["total_count"],
        "topic_summaries": result["topic_summaries"],
    }


def verify_pair(full_path: Path, compact_path: Path) -> None:
    """写后回读断言：两文件的三项去重关键字段必须逐项相等（EXP-014 可观测性）。"""
    full = json.loads(full_path.read_text(encoding="utf-8"))
    comp = json.loads(compact_path.read_text(encoding="utf-8"))
    bad = [k for k in ("generated_at", "total_count", "topic_summaries")
           if full.get(k) != comp.get(k)]
    if bad:
        print(f"[prepare_topics] ❌ 同源一致性断言失败: full 与 compact 的 "
              f"{', '.join(bad)} 不一致", file=sys.stderr)
        sys.exit(1)
    print(f"[prepare_topics] ✅ 同源派生校验通过: generated_at / total_count / "
          f"topic_summaries 三项全一致 (total_count={full.get('total_count')}, "
          f"summaries={len(full.get('topic_summaries', []))})")


def main():
    parser = argparse.ArgumentParser(description="扫描历史文章提取已用话题")
    parser.add_argument("--workspace", default=r"F:\WorkBuddy\daily-why",
                        help="工作目录路径")
    parser.add_argument("--output", default=FULL_NAME,
                        help="输出文件名（相对于工作目录）")
    parser.add_argument("--limit", type=int, default=50,
                        help="最多扫描的文章数")
    parser.add_argument("--pretty", action="store_true", default=True,
                        help="美化 JSON 输出")
    parser.add_argument("--compact", action="store_true",
                        help="输出精简版，只保留去重所需信息（topic_summaries、total_count、generated_at）；"
                             "默认路径下同时刷新 full，保证 check_topic 读到最新事实")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    full_path = workspace / FULL_NAME
    compact_path = workspace / COMPACT_NAME

    # 输出目标解析（R1：默认精简模式必须同时刷新 full）
    if args.compact and args.output == FULL_NAME:
        full_out, compact_out = full_path, compact_path
        print("[prepare_topics] 精简版模式：full 与 compact 由本次扫描同源写入")
    elif args.compact:
        # 显式指定 --output 时保持旧行为：只写指定文件，不触碰默认话题库
        full_out, compact_out = None, workspace / args.output
    else:
        full_out, compact_out = workspace / args.output, compact_path

    print(f"[prepare_topics] 扫描工作目录: {workspace}")

    result = scan_all(workspace, limit=args.limit)  # 唯一一次扫描（09-15 同源原则）
    indent = 2 if args.pretty else None

    if full_out:
        full_out.write_text(json.dumps(result, ensure_ascii=False, indent=indent),
                            encoding="utf-8")
        print(f"[prepare_topics] 输出 full: {full_out} "
              f"({len(result['topic_summaries'])} 个话题标题)")
    if compact_out:
        compact = build_compact(result)
        compact_out.write_text(json.dumps(compact, ensure_ascii=False, indent=indent),
                               encoding="utf-8")
        print(f"[prepare_topics] 输出 compact: {compact_out} "
              f"({len(compact['topic_summaries'])} 个话题标题)")

    # 只有两文件都写默认路径时才断言，显式 --output 场景不参与
    if full_out == full_path and compact_out == compact_path:
        verify_pair(full_path, compact_path)

    print(f"[prepare_topics] 完成! 共 {result['total_count']} 个话题")

    if full_out:
        print("\n--- 分类统计 ---")
        for cat, count in sorted(result["category_stats"].items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count} 篇")
        print("\n--- 最近 5 个话题 ---")
        for t in result["topics"][:5]:
            print(f"  {t['date']}: {t['topic']}")
    else:
        print("\n--- 最近 5 个话题（精简版） ---")
        for t in result["topic_summaries"][:5]:
            print(f"  {t}")

    return result


if __name__ == "__main__":
    main()

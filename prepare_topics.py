#!/usr/bin/env python3
"""
prepare_topics.py — 扫描所有历史文章和 memory.md，提取已用话题
输出 topics_context.json，供 automation-2 prompt 使用，替代 prompt 中硬编码的话题列表。

用法：
    python prepare_topics.py
    python prepare_topics.py --workspace F:/WorkBuddy/daily-why
    python prepare_topics.py --output topics_context.json --limit 50
"""

import re
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


def scan_all(workspace: Path, limit: int = 50) -> dict:
    """扫描所有来源，生成 topics_context"""
    all_topics = []

    # 1. 扫描文章文件
    md_files = sorted(workspace.glob("*-每日冷知识.md"), reverse=True)
    for fp in md_files[:limit]:
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


def main():
    parser = argparse.ArgumentParser(description="扫描历史文章提取已用话题")
    parser.add_argument("--workspace", default=r"F:\WorkBuddy\daily-why",
                        help="工作目录路径")
    parser.add_argument("--output", default="topics_context.json",
                        help="输出文件名（相对于工作目录）")
    parser.add_argument("--limit", type=int, default=50,
                        help="最多扫描的文章数")
    parser.add_argument("--pretty", action="store_true", default=True,
                        help="美化 JSON 输出")
    parser.add_argument("--compact", action="store_true",
                        help="输出精简版，只保留去重所需信息（topic_summaries、total_count、generated_at）")
    args = parser.parse_args()

    workspace = Path(args.workspace)

    # 精简版模式：自动切换输出路径（除非用户显式指定了 --output）
    if args.compact and args.output == "topics_context.json":
        output_filename = "topics_context_compact.json"
    else:
        output_filename = args.output
    output_path = workspace / output_filename

    print(f"[prepare_topics] 扫描工作目录: {workspace}")

    result = scan_all(workspace, limit=args.limit)

    # 精简版：只保留去重所需信息
    if args.compact:
        compact_result = {
            "generated_at": result["generated_at"],
            "total_count": result["total_count"],
            "topic_summaries": result["topic_summaries"],
        }
        result = compact_result
        print(f"[prepare_topics] 精简版模式：只保留 {len(result['topic_summaries'])} 个话题标题用于去重")

    # 写入文件
    indent = 2 if args.pretty else None
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=indent),
                           encoding="utf-8")

    print(f"[prepare_topics] 完成! 共 {result['total_count']} 个话题")
    print(f"[prepare_topics] 输出: {output_path}")

    # 打印摘要（精简版不打印分类统计）
    if not args.compact:
        print(f"\n--- 分类统计 ---")
        for cat, count in sorted(result["category_stats"].items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count} 篇")

        print(f"\n--- 最近 5 个话题 ---")
        for t in result["topics"][:5]:
            print(f"  {t['date']}: {t['topic']}")
    else:
        print(f"\n--- 最近 5 个话题（精简版） ---")
        for t in result["topic_summaries"][:5]:
            print(f"  {t}")

    return result


if __name__ == "__main__":
    main()

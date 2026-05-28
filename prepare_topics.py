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


def clean_text(text: str) -> str:
    """清理零宽空格、不可见字符和前导 emoji"""
    # 去掉零宽空格、BOM、零宽非断行空格等
    text = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad\u2060\ufe0f]", "", text)
    # 去掉行首 emoji（保留标题中的 emoji）
    return text.strip()


def extract_topic_from_article(filepath: Path) -> dict:
    """从单篇文章提取话题信息"""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return None

    # 提取日期
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filepath.name)
    date_str = date_match.group(1) if date_match else "unknown"

    # 提取话题：优先从 "今日话题" 行
    topic = ""
    category = ""

    # 方式1: > **本期话题**：xxx / ## 🌊 今日话题：xxx
    m = re.search(r"(?:\*\*)?(?:今日|本期)话题(?:\*\*)?[：:]\s*\*?\*?(.+?)(?:\*\*)?\s*$", content, re.MULTILINE)
    if m:
        topic = m.group(1).strip().rstrip("*")
        # 去掉尾部的括号分类标注 (xxx/xxx)
        cat_match = re.search(r"[（(](.+?)[）)]\s*$", topic)
        if cat_match:
            category = cat_match.group(1)
            topic = re.sub(r"\s*[（(].+?[）)]\s*$", "", topic).strip()

    # 方式2: 从标题 # 🐙 xxx 或 # 🌟 每日一个为什么 | 第xx期 下方的提示提取
    if not topic:
        title_match = re.search(r"^#\s+.+\n\n.*?话题[：:]\s*(.+)", content, re.MULTILINE)
        if title_match:
            topic = title_match.group(1).strip()

    # 方式3: 从标题提取（如 "为什么打哈欠会传染"）
    if not topic:
        title_match = re.search(r"^#\s+(?:[\U0001F300-\U0001F9FF]\s*)*(.+)", content, re.MULTILINE)
        if title_match:
            raw_title = title_match.group(1).strip()
            # 跳过 "每日一个为什么 | 第xx期" 这种泛标题
            if "每日" not in raw_title and "期" not in raw_title:
                topic = raw_title

    # 方式4: 从 memory.md 记录的 "话题：xxx" 格式提取（兼容）
    if not topic:
        m = re.search(r"话题[：:]\s*(.+?)[（(]", content)
        if m:
            topic = m.group(1).strip()

    # 方式5: 从 h1 中 "每日冷知识" / "每日一个为什么" 后面提取话题
    # 跳过纯日期结果（如 "2026-04-09"），交给方式6从 h2 提取
    if not topic:
        m = re.search(r"^#\s+(?:每日冷知识|每日一个为什么)\s*[|·\-]\s*(.+)", content, re.MULTILINE)
        if m:
            candidate = m.group(1).strip()
            if not re.match(r"^\d{4}-\d{2}-\d{2}", candidate):
                topic = candidate

    # 方式6: 从二级标题提取（如 ## 为什么打哈欠会"传染"？）
    if not topic:
        m = re.search(r"^##\s+(?:[\U0001F300-\U0001F9FF]\s*)*(.+)", content, re.MULTILINE)
        if m:
            topic = m.group(1).strip()

    if not topic:
        # 兜底：用文件名做标识
        topic = filepath.stem

    # 清理话题中的零宽空格和不可见字符
    topic = clean_text(topic)

    # 提取分类
    if not category:
        # 新格式：| 分类 | xxx |
        cat_match = re.search(r"\|\s*分类\s*\|\s*(.+?)\s*\|", content)
        if cat_match:
            category = cat_match.group(1).strip()
        else:
            # 旧格式：话题分类** | xxx |
            cat_match = re.search(r"话题分类\*\*\s*\|\s*(.+?)\s*\|", content)
            if cat_match:
                category = cat_match.group(1).strip()
            else:
                # 从 memory.md 格式中提取 (分类/子分类)
                cat_match = re.search(r"[（(](.+?/)", content)
                if cat_match:
                    category = cat_match.group(1).rstrip("/")

    return {
        "date": date_str,
        "topic": topic,
        "category": category or "未分类",
        "file": filepath.name,
    }


def extract_topics_from_memory(memory_path: Path) -> list:
    """从 memory.md 提取历史话题记录"""
    if not memory_path.exists():
        return []

    content = memory_path.read_text(encoding="utf-8")
    topics = []

    # 匹配格式: - 2026-04-22: 为什么打嗝停不下来？（人体奥秘/生理学）
    pattern = r"-\s+(\d{4}-\d{2}-\d{2}):\s+(.+?)(?:（(.+?)）|$)"
    for m in re.finditer(pattern, content):
        date_str = m.group(1)
        topic = m.group(2).strip()
        category = m.group(3) or "未分类"
        topics.append({
            "date": date_str,
            "topic": topic,
            "category": category,
            "source": "memory.md",
        })

    return topics


def extract_keywords(topic_text: str) -> list:
    """从话题文本提取关键词（简单分词）"""
    # 去掉常见前缀
    text = re.sub(r"^为什么", "", topic_text)
    text = re.sub(r"[？?]+$", "", text)

    # 分割常见连接词
    parts = re.split(r"[的了会是在与和跟有]", text)
    keywords = [p.strip() for p in parts if len(p.strip()) >= 2]
    return keywords


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

    # 去重（同一日期可能有多条，保留最新的）
    seen = set()
    unique_topics = []
    for t in all_topics:
        key = f"{t['date']}:{t['topic']}"
        if key not in seen:
            seen.add(key)
            # 提取关键词
            t["keywords"] = extract_keywords(t["topic"])
            unique_topics.append(t)

    # 提取所有已用话题的摘要
    topic_summaries = [t["topic"] for t in unique_topics]

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
    args = parser.parse_args()

    workspace = Path(args.workspace)
    output_path = workspace / args.output

    print(f"[prepare_topics] 扫描工作目录: {workspace}")

    result = scan_all(workspace, limit=args.limit)

    # 写入文件
    indent = 2 if args.pretty else None
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=indent),
                           encoding="utf-8")

    print(f"[prepare_topics] 完成! 共 {result['total_count']} 个话题")
    print(f"[prepare_topics] 输出: {output_path}")

    # 打印摘要
    print(f"\n--- 分类统计 ---")
    for cat, count in sorted(result["category_stats"].items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} 篇")

    print(f"\n--- 最近 5 个话题 ---")
    for t in result["topics"][:5]:
        print(f"  {t['date']}: {t['topic']}")

    return result


if __name__ == "__main__":
    main()

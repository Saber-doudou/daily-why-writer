#!/usr/bin/env python3
"""
topic_utils.py — 话题处理公共模块
统一 prepare_topics.py 和 update_history.py 中的重复代码。

功能：
- clean_text: 清理零宽空格、不可见字符
- normalize_topic: 标准化话题格式（去 emoji、去前缀等）
- extract_topic_from_article: 从文章提取话题信息
- extract_keywords: 从话题文本提取关键词
- extract_topics_from_memory: 从 memory.md 提取历史话题记录
"""

import re
from pathlib import Path
from typing import Optional


def clean_text(text: str) -> str:
    """清理零宽空格、不可见字符和前导 emoji"""
    # 去掉零宽空格、BOM、零宽非断行空格等
    text = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad\u2060\ufe0f]", "", text)
    # 去掉行首 emoji（保留标题中的 emoji）
    return text.strip()


def normalize_topic(topic: str) -> str:
    """标准化话题格式，提升 topics_context.json 的话题质量"""
    if not topic:
        return topic

    # 1. 去掉开头的 emoji（❄🪞⚡🫖 等，覆盖全范围 emoji + 组合字符）
    topic = re.sub(r"^[\U0001F300-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
                   r"\u2600-\u26FF\u2700-\u27BF\u200b\ufe0f\u200d]+\s*", "", topic)

    # 2. 去掉"今日冷知识："前缀
    topic = re.sub(r"^今日冷知识[：:]\s*", "", topic)

    # 3. 去掉尾部 emoji（包括 🫖 等不在常用范围的）
    topic = re.sub(r"\s*[\U0001F300-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
                   r"\u2600-\u26FF\u2700-\u27BF\u200b\ufe0f\u200d]+$", "", topic)

    # 4. 去掉尾部的括号分类标注 (xxx/xxx) 或 （xxx/xxx）
    topic = re.sub(r"\s*[（(].+?[）)]\s*$", "", topic)

    # 5. 去掉尾部的标点（问号保留，感叹号/句号去掉）
    topic = re.sub(r"[！!。.]+$", "", topic)

    # 6. 清理中文引号（" "「」→ 去掉）
    topic = re.sub(r'[""「」]', '', topic)

    return topic.strip()


def extract_topic_from_article(filepath: Path, include_keywords: bool = False) -> Optional[dict]:
    """从单篇文章提取话题信息

    Args:
        filepath: 文章文件路径
        include_keywords: 是否提取关键词（update_history.py 需要）

    Returns:
        dict 包含 date、topic、category、file、keywords（可选）
        如果提取失败返回 None
    """
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

    # 标准化话题格式（去 emoji 前缀、去"今日冷知识："前缀等）
    topic = normalize_topic(topic)

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

    result = {
        "date": date_str,
        "topic": topic,
        "category": category or "未分类",
        "file": filepath.name,
    }

    # 可选：提取关键词
    if include_keywords:
        keywords = re.findall(r"\*\*(.+?)\*\*", content)
        keywords = [k for k in keywords if len(k) <= 10 and not k.startswith("Q")
                    and k not in ("本期话题", "今日话题", "话题")]
        result["keywords"] = keywords[:5]

    return result


def extract_keywords(topic_text: str) -> list:
    """从话题文本提取关键词（简单分词）"""
    # 去掉常见前缀
    text = re.sub(r"^为什么", "", topic_text)
    text = re.sub(r"[？?]+$", "", text)

    # 分割常见连接词
    parts = re.split(r"[的了会是在与和跟有]", text)
    keywords = [p.strip() for p in parts if len(p.strip()) >= 2]
    return keywords


def extract_topics_from_memory(memory_path: Path) -> list:
    """从 memory.md 提取历史话题记录（兼容新旧两种格式）

    新格式（当前 automation 实际写入）：
        ## 2026-08-13
        - 话题：为什么辣椒会让人觉得辣？（人体奥秘）
    旧格式（历史遗留）：
        - 2026-04-22: 为什么打嗝停不下来？（人体奥秘/生理学）
    """
    if not memory_path.exists():
        return []

    content = memory_path.read_text(encoding="utf-8")
    topics = []
    seen = set()

    def add(date_str: str, topic: str, category: str = "未分类"):
        key = (date_str.strip(), topic.strip())
        if not key[1]:
            return
        if key not in seen:
            seen.add(key)
            topics.append({
                "date": key[0],
                "topic": key[1],
                "category": category or "未分类",
                "source": "memory.md",
            })

    # ── 新格式：## YYYY-MM-DD 标题 + "- 话题：xxx（分类）" ──
    # 按 "## 日期" 分段，段体内匹配 "话题：" 行
    sections = re.split(r"(?m)^##\s+(\d{4}-\d{2}-\d{2})\s*$", content)
    # sections = [头部, 日期1, 段体1, 日期2, 段体2, ...]
    for i in range(1, len(sections), 2):
        date_str = sections[i].strip()
        body = sections[i + 1] if i + 1 < len(sections) else ""
        # 兼容 "- 话题：xxx（分类）" 与 "- 话题：xxx"
        m = re.search(r"话题[：:]\s*(.+?)(?:（(.+?)）|$)", body)
        if m:
            add(date_str, m.group(1), m.group(2))

    # ── 旧格式：- 2026-04-22: xxx（分类） ──
    pattern = r"-\s+(\d{4}-\d{2}-\d{2}):\s+(.+?)(?:（(.+?)）|$)"
    for m in re.finditer(pattern, content):
        add(m.group(1), m.group(2), m.group(3))

    return topics


def is_valid_topic(topic: str) -> bool:
    """判断话题是否为标准的"为什么xxx？"格式（用于过滤非标准标题）"""
    if not topic:
        return False

    # 标准格式：以"为什么"开头，或包含"为什么"
    if "为什么" in topic:
        return True

    # 宽松格式：以问号结尾的疑问句（如"蝴蝶的舌头长在脚上？"）
    if topic.endswith("？") or topic.endswith("?"):
        return True

    # 非标准格式：标题式（如"深海三心迷踪"）、陈述式（如"蜜蜂一生只能酿一勺蜂蜜"）
    return False

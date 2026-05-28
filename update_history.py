#!/usr/bin/env python3
"""
update_history.py — 从新文章中提取话题，自动更新 memory.md
替代 AI 手动更新 memory 的步骤，节省 token。

用法：
    python update_history.py                              # 自动找最新文章并更新
    python update_history.py 2026-05-07-每日冷知识.md     # 指定文件
    python update_history.py --dry-run 2026-05-07-每日冷知识.md  # 预览不写入
"""

import re
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Windows GBK 终端兼容
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# memory.md 路径优先级
MEMORY_PATHS = [
    Path(r"F:\WorkBuddy\daily-why\.workbuddy\automations\automation-1778312519754\memory.md"),
    Path(r"F:\WorkBuddy\daily-why\.workbuddy\automations\automation-2\memory.md"),
    Path(r"F:\WorkBuddy\daily-why\.codebuddy\automations\automation-2\memory.md"),
]


def find_memory_file() -> Path:
    """找到存在的 memory.md，若都不存在则创建 .workbuddy 路径"""
    for p in MEMORY_PATHS:
        if p.exists():
            return p
    # 创建 .workbuddy 路径
    target = MEMORY_PATHS[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Automation-2 执行记录\n", encoding="utf-8")
    return target


def extract_date_from_filename(filename: str) -> str:
    """从文件名提取日期"""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else datetime.now().strftime("%Y-%m-%d")


def extract_topic_from_article(filepath: Path) -> dict:
    """从文章提取话题信息"""
    content = filepath.read_text(encoding="utf-8")

    topic = ""
    category = ""
    keywords = []

    # 话题提取：今日话题/本期话题（支持 > **本期话题**：xxx 格式）
    m = re.search(r"(?:\*\*)?(?:今日|本期)话题(?:\*\*)?[：:]\s*\*?\*?(.+?)(?:\*\*)?\s*$", content, re.MULTILINE)
    if m:
        topic = m.group(1).strip().rstrip("*")
        cat_match = re.search(r"[（(](.+?)[）)]\s*$", topic)
        if cat_match:
            category = cat_match.group(1)
            topic = re.sub(r"\s*[（(].+?[）)]\s*$", "", topic).strip()

    if not topic:
        title_match = re.search(r"^#\s+(?:[\U0001F300-\U0001F9FF]\s*)*(.+)",
                                content, re.MULTILINE)
        if title_match:
            raw = title_match.group(1).strip()
            if "每日" not in raw and "期" not in raw:
                topic = raw

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
        topic = filepath.stem

    # 清理零宽空格和不可见字符
    topic = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad\u2060\ufe0f]", "", topic).strip()

    # 分类（新格式优先，旧格式兜底）
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

    # 提取关键词（加粗词）
    keywords = re.findall(r"\*\*(.+?)\*\*", content)
    keywords = [k for k in keywords if len(k) <= 10 and not k.startswith("Q")
                and k not in ("本期话题", "今日话题", "话题")]

    return {
        "topic": topic,
        "category": category or "未分类",
        "keywords": keywords[:5],
    }


def is_duplicate(memory_content: str, date_str: str, topic: str) -> bool:
    """检查是否已存在同日记录（精确匹配日期 + 话题）"""
    # 先找该日期的所有记录块
    date_pattern = rf"## {re.escape(date_str)}\b"
    date_matches = list(re.finditer(date_pattern, memory_content))
    if not date_matches:
        return False
    # 在该日期的记录中检查话题是否重复
    topic_escaped = re.escape(topic[:12])  # 取话题前12字符匹配
    for m in date_matches:
        # 从该日期标题开始到下一个日期标题（或文件结尾）的范围内搜索
        start = m.start()
        next_date = re.search(r"## \d{4}-\d{2}-\d{2}", memory_content[start + len(m.group()):])
        end = start + len(m.group()) + next_date.start() if next_date else len(memory_content)
        block = memory_content[start:end]
        if re.search(topic_escaped, block):
            return True
    return False


def build_record(date_str: str, info: dict, filename: str) -> str:
    """构建一条 memory 记录"""
    lines = [
        f"## {date_str}",
        f"- 话题：{info['topic']}（{info['category']}）",
        f"- 文件：{filename}",
        f"- 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    if info["keywords"]:
        lines.append(f"- 关键词：{', '.join(info['keywords'])}")
    return "\n".join(lines) + "\n"


def find_insert_position(content: str, date_str: str) -> int:
    """找到正确的插入位置（按日期倒序，新记录在前）"""
    # 找所有 ## YYYY-MM-DD 标题
    existing_dates = re.findall(r"## (\d{4}-\d{2}-\d{2})", content)

    if not existing_dates:
        # 没有现有记录，追加到末尾
        return len(content)

    # 找第一个比目标日期小的记录位置
    for existing_date in existing_dates:
        if existing_date < date_str:
            # 在这个记录前插入
            pos = content.find(f"## {existing_date}")
            return pos

    # 所有现有日期都 >= 目标日期，追加到末尾
    return len(content)


def update_memory(filepath: Path, dry_run: bool = False) -> dict:
    """主函数：从文章更新 memory.md"""
    filename = filepath.name
    date_str = extract_date_from_filename(filename)

    print(f"[update_history] 处理文件: {filename}")
    print(f"[update_history] 提取日期: {date_str}")

    # 提取话题
    info = extract_topic_from_article(filepath)
    print(f"[update_history] 话题: {info['topic']}")
    print(f"[update_history] 分类: {info['category']}")
    if info["keywords"]:
        print(f"[update_history] 关键词: {', '.join(info['keywords'])}")

    # 读取 memory.md
    memory_path = find_memory_file()
    print(f"[update_history] Memory 文件: {memory_path}")

    memory_content = memory_path.read_text(encoding="utf-8")

    # 检查重复
    if is_duplicate(memory_content, date_str, info["topic"]):
        print(f"[update_history] ⚠️  该日期/话题已存在，跳过")
        return {"status": "skipped", "reason": "duplicate"}

    # 构建新记录
    new_record = build_record(date_str, info, filename)

    if dry_run:
        print(f"\n--- 预览（dry-run）---\n{new_record}")
        return {"status": "dry_run", "record": new_record}

    # 插入到正确位置
    insert_pos = find_insert_position(memory_content, date_str)

    # 确保前后有换行
    if insert_pos < len(memory_content) and memory_content[insert_pos] != "\n":
        new_record += "\n"

    updated = memory_content[:insert_pos] + new_record + memory_content[insert_pos:]

    # 写入
    memory_path.write_text(updated, encoding="utf-8")
    print(f"[update_history] ✅ 已更新 memory.md")

    return {
        "status": "updated",
        "date": date_str,
        "topic": info["topic"],
        "category": info["category"],
        "memory_path": str(memory_path),
    }


def find_latest_article(workspace: Path) -> Path:
    """找最新的文章文件"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_file = workspace / f"{today}-每日冷知识.md"
    if today_file.exists():
        return today_file

    md_files = sorted(workspace.glob("*-每日冷知识.md"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if md_files:
        return md_files[0]

    raise FileNotFoundError("未找到任何每日冷知识 md 文件")


def main():
    parser = argparse.ArgumentParser(description="从文章提取话题并更新 memory.md")
    parser.add_argument("file", nargs="?", help="文章文件路径（可选，默认最新）")
    parser.add_argument("--workspace", default=r"F:\WorkBuddy\daily-why",
                        help="工作目录")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览模式，不实际写入")
    args = parser.parse_args()

    workspace = Path(args.workspace)

    if args.file:
        filepath = Path(args.file)
        if not filepath.is_absolute():
            filepath = workspace / filepath
    else:
        filepath = find_latest_article(workspace)

    result = update_memory(filepath, dry_run=args.dry_run)
    print(f"\n[update_history] 结果: {result['status']}")


if __name__ == "__main__":
    main()

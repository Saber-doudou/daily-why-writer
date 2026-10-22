#!/usr/bin/env python3
"""
format_checker.py — 格式检查模块
从 validate_article.py 分离出来的格式检查功能。

功能：
- 标题 emoji 检测
- 分隔线数量检测
- 引用块检测
- 加粗检测
- Q 格式检测（h3 vs 加粗）
- 反转标签检测
- 风格表格检测
- 字数检测
"""

import re
from dataclasses import dataclass
from typing import Optional

# 从 writing_rules.json 加载规则
from pathlib import Path
import json

RULES_PATH = Path(__file__).parent / "writing_rules.json"
RULES = {}
if RULES_PATH.exists():
    try:
        RULES = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass


def _r(path: str, default=None):
    """安全地从 RULES 取嵌套值"""
    keys = path.split(".")
    val = RULES
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    return val if val is not None else default


# 格式规则常量
SEPARATOR_EXACT = _r("formatting.separator_exact", 2)
SEPARATOR_MAX = _r("formatting.separator_max", 2)
QUOTE_MIN = _r("formatting.quote_blocks_min", 2)
BOLD_MIN = _r("formatting.bold_min", 2)
Q_FORMAT = _r("formatting.q_format", "**Q1：xxx？**")
TWIST_LABEL = _r("formatting.twist_label", "冷知识反转")

# 字数规则
WC_MIN = _r("word_count.min", 300)
WC_MAX = _r("word_count.max", 600)
WC_P1_THRESHOLD = _r("word_count.p1_threshold", 600)


def count_chinese_chars(text: str) -> int:
    """统计中文字符数"""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def strip_markdown(text: str) -> str:
    """去掉 markdown 格式，返回纯文本"""
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"---+", "", text)
    text = re.sub(r"\|.+\|", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def check_title_emoji(content: str, result):
    """检查标题是否有 emoji 装饰"""
    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    if title_match:
        title = title_match.group(1)
        has_emoji = bool(
            re.search(r"[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]",
                      title))
        if not has_emoji:
            result.p1_error("标题缺少 emoji 装饰")
        else:
            result.ok("标题 emoji 装饰 ✓")


def check_separators(content: str, result):
    """检查分隔线数量（恰好 2 处）"""
    sep_count = len(re.findall(r"^\s*---\s*$", content, re.MULTILINE))
    if sep_count < SEPARATOR_EXACT:
        result.p0_error(
            f"分隔线不足（仅 {sep_count} 处），"
            f"需要恰好 {SEPARATOR_EXACT} 处：A段后 + F段前")
    elif sep_count > SEPARATOR_MAX + 1:
        result.p0_error(
            f"分隔线过多（{sep_count} 处），"
            f"应恰好 {SEPARATOR_MAX} 处，C段内部Q之间不加 ---")
    elif sep_count > SEPARATOR_MAX:
        result.p1_error(
            f"分隔线过多（{sep_count} 处），"
            f"应恰好 {SEPARATOR_MAX} 处，C段内部Q之间不加 ---")
    else:
        result.ok(f"分隔线使用 ✓ ({sep_count} 处)")


def check_quote_blocks(content: str, result):
    """检查引用块数量"""
    quote_lines = re.findall(r"^>\s+.+", content, re.MULTILINE)
    if len(quote_lines) < QUOTE_MIN:
        result.p1_error("缺少引用块「>」，应用来承载故事场景和反转金句")
    else:
        result.ok(f"引用块 ✓ ({len(quote_lines)} 行)")


def check_bold(content: str, result):
    """检查加粗关键词数量"""
    bold_count = len(re.findall(r"\*\*.+?\*\*", content))
    if bold_count < BOLD_MIN:
        result.p1_error(
            f"加粗偏少（仅 {bold_count} 处），"
            f"建议突出 2-3 个关键概念")
    else:
        result.ok(f"加粗关键词 ✓ ({bold_count} 处)")


def check_q_format(content: str, result):
    """检查 Q 格式（禁止 h3 格式）"""
    h3_questions = re.findall(r"^###\s+.*[？?]", content, re.MULTILINE)
    if h3_questions:
        result.p0_error(
            f"Q 标记使用了 h3 格式（{len(h3_questions)} 处），"
            f"应统一用加粗格式 **Q1：xxx？**")
    else:
        result.ok("Q 格式 ✓（加粗格式）")


def check_twist_label(content: str, result):
    """检查反转标签（必须用"冷知识反转"）"""
    if "冷知识彩蛋" in content:
        result.p1_error("反转标签使用了「冷知识彩蛋」，应统一用「冷知识反转」")
    elif "冷知识反转" in content:
        result.ok("反转标签 ✓（冷知识反转）")
    else:
        result.p1_error("缺少「冷知识反转」标签")


def check_style_table(content: str, result):
    """检查风格表格"""
    # 检查分类行
    if not re.search(r"分类\s*\|", content):
        result.p1_error("风格表格缺少「分类」行")
    else:
        result.ok("风格表格分类 ✓")

    # 检查行标题完整性
    table_row_headers = ["话题", "分类", "核心机制", "冷知识反转"]
    found_headers = [h for h in table_row_headers if re.search(rf"\|\s*{h}\s*\|", content)]
    missing_headers = [h for h in table_row_headers if h not in found_headers]
    if missing_headers:
        result.p2_error(
            f"风格表格行标题不完整，缺少：{'、'.join(missing_headers)}，"
            f"标准格式为 话题/分类/核心机制/冷知识反转")
    else:
        result.ok("风格表格行标题完整性 ✓")

    # 检查表格是否存在
    if not re.search(r"\|.+\|.+\|", content):
        result.p2_error("建议结尾附风格说明表格")
    else:
        result.ok("风格说明表格 ✓")


def check_word_count(content: str, result):
    """检查字数"""
    plain = strip_markdown(content)
    char_count = count_chinese_chars(plain)
    result.info["char_count"] = char_count
    if char_count < WC_MIN:
        result.p2_error(f"字数偏少（{char_count} 字），建议 {WC_MIN}-{WC_MAX} 字")
    elif char_count > WC_MAX:
        result.p1_error(f"字数过多（{char_count} 字），上限 {WC_MAX} 字，需精简")
    else:
        result.ok(f"字数 ✓ ({char_count} 字)")


def check_all_formats(content: str, result):
    """执行所有格式检查"""
    check_title_emoji(content, result)
    check_separators(content, result)
    check_quote_blocks(content, result)
    check_bold(content, result)
    check_q_format(content, result)
    check_twist_label(content, result)
    check_style_table(content, result)
    check_word_count(content, result)
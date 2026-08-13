#!/usr/bin/env python3
"""
check_topic.py — 话题去重校验脚本（机械性防护网）

用法：
    python check_topic.py "为什么xxx？"
    python check_topic.py --topic "为什么xxx？"
    python check_topic.py --file 2026-06-08-每日冷知识.md
    python check_topic.py --angle "为什么xxx？"              # 角度模式：相似度 0.50 到 0.70 之间放行并提示
    python check_topic.py --threshold 0.60 "为什么xxx？"      # 自定义重复阈值（默认 0.70）
    python check_topic.py --angle --threshold 0.60 "为什么xxx？"

退出码：
    0 = 通过（话题未使用过；角度模式下相似度 0.50 到阈值之间的"角度相关"话题放行，
        但输出含"⚠️ 角度相关（相似度 X%）"提示，需人工确认写作角度与已有话题不同）
    1 = 重复（话题已存在，精确匹配或语义相似；相似度 ≥ 阈值无论是否 --angle 均判重复）
    2 = 参数错误

设计原则：
    - 纯机械比对，不依赖 AI 判断力
    - 两层检测：精确匹配 + 关键词交集
    - 同时检查 topics_context.json 和已有文章文件
    - 角度模式（--angle）：相似度落在 [0.50, 阈值) 区间的候选属于"同一现象的不同角度"，
      放行并提示；未开启时该区间仍判重复，保持原严格行为
"""

import re
import sys
import json
import argparse
from pathlib import Path

# 疑问前缀，提取关键词前先去掉
QUESTION_PREFIXES = ["为什么", "怎么", "什么", "为何", "为啥"]

# 停用词：无区分度的虚词、助词、泛化主体
STOP_WORDS = frozenset([
    "的", "了", "会", "是", "在", "都", "就", "也", "还",
    "和", "与", "或", "有", "没", "不", "能", "可以",
    "总是", "竟然", "居然", "到底", "究竟",
    "人", "我们", "自己", "一个",
])

# 交集比例阈值（核心字符包含率 ≥70% → 判重复）
# 60% 会误杀"海水蓝 vs 海水咸"（通用字"海""水"拉高比例）
OVERLAP_THRESHOLD = 0.70

# 角度相关下限：相似度落在 [ANGLE_THRESHOLD, OVERLAP_THRESHOLD) 区间的话题
# 属于"同一现象的不同角度"（如"猫头鹰飞起来没声音"vs"猫头鹰晚上能看清猎物"）。
# 开启 --angle 时该区间放行（退出码 0）并输出提示，未开启时仍判重复（退出码 1）。
ANGLE_THRESHOLD = 0.50


def normalize_topic(text: str) -> str:
    """标准化话题文本：去 emoji、去首尾空白、统一全角半角"""
    text = re.sub(
        r'[\U0001F000-\U0001FFFF\U00002700-\U000027BF\U0000FE00-\U0000FE0F'
        r'\U0000200D\U00002600-\U000026FF\U00002300-\U000023FF\U00002B50'
        r'\U0000231A-\U0000231B\U00002934-\U00002935\U000025AA-\U000025FE'
        r'\U00002B05-\U00002B07\U00002B1B-\U00002B1C\U00003030\U0000303D'
        r'\U00003297\U00003299\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
        r'\U00002702-\U000027B0]+',
        '', text
    )
    text = text.strip().replace('\u3000', '')
    return text


def extract_core_chars(text: str) -> str:
    """
    提取话题的核心字符（去前缀、去标点、去停用字）。

    用于字符级语义相似度检测。
    """
    normalized = normalize_topic(text)

    # 去掉疑问前缀
    for prefix in QUESTION_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    # 去标点和空白
    normalized = re.sub(
        r'[？?！!。，,、；;：\u201c\u201d\u2018\u2019\u3000\s]+',
        '', normalized
    )

    # 去停用单字（的/了/会/是/在/都/就/也/还/和/与/或/有/没/不/能/人）
    stop_chars = set("的了会是在都就也还和与或有没能人可以")
    chars = [c for c in normalized if c not in stop_chars]

    return ''.join(chars)


def check_semantic_similarity(new_topic: str, existing_topic: str,
                              threshold: float = OVERLAP_THRESHOLD) -> tuple[bool, float, str]:
    """
    字符级包含率检测：短文本的字是否都在长文本中出现。

    原理：去掉"为什么"前缀和停用字后，如果新话题的大部分字
    都在已有话题中出现过，说明它们在说同一件事。

    参数:
        threshold: 判重复的相似度阈值（默认 OVERLAP_THRESHOLD，可被 --threshold 覆盖）

    返回: (is_similar: bool, score: float, detail: str)
        is_similar=True 表示相似度 ≥ threshold（判重复）；
        score 落在 [ANGLE_THRESHOLD, threshold) 区间时由调用方决定是否角度放行。
    """
    core_new = extract_core_chars(new_topic)
    core_existing = extract_core_chars(existing_topic)

    if len(core_new) < 3 or len(core_existing) < 3:
        return False, 0.0, "核心字符不足"

    set_new = set(core_new)
    set_existing = set(core_existing)

    # 短的一方做分母
    if len(set_new) <= len(set_existing):
        smaller, larger = set_new, set_existing
        smaller_text = core_new
    else:
        smaller, larger = set_existing, set_new
        smaller_text = core_existing

    if not smaller:
        return False, 0.0, "无有效字符"

    common = smaller & larger
    ratio = len(common) / len(smaller)

    if ratio >= threshold:
        return True, ratio, (
            f"字符包含率 {ratio:.0%}: "
            f"「{core_new}」vs「{core_existing}」交集 {common}"
        )

    return False, ratio, f"字符包含率 {ratio:.0%} < {threshold:.0%}"


def extract_topic_from_article(filepath: Path) -> str | None:
    """从文章文件提取标题（第一行 # 开头的行）"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#'):
                    topic = line.lstrip('#').strip()
                    return topic
    except Exception:
        pass
    return None


def check_topic(topic: str, workspace: Path, threshold: float = OVERLAP_THRESHOLD,
                angle_mode: bool = False) -> tuple[bool, str]:
    """
    检查话题是否已使用过（两层检测：精确匹配 + 语义相似）。

    参数:
        topic: 待校验话题
        workspace: 工作目录（含 config/topics_context.json 与 articles/）
        threshold: 判重复的相似度阈值（默认 0.70，可被 --threshold 覆盖）
        angle_mode: 角度模式；开启后相似度落在 [ANGLE_THRESHOLD, threshold) 区间的话题放行，
                    返回 False 且 detail 含"⚠️ 角度相关（相似度 X%）"提示

    返回: (is_duplicate: bool, detail: str)
    """
    normalized = normalize_topic(topic)
    if not normalized:
        return False, "话题为空"

    all_existing = []  # 收集所有已有话题用于语义检测

    # === 检查 1: topics_context.json ===
    context_file = workspace / "config" / "topics_context.json"
    if context_file.exists():
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                context = json.load(f)

            # 精确匹配 + 收集话题
            for existing in context.get("topic_summaries", []):
                norm_existing = normalize_topic(existing)
                if norm_existing == normalized:
                    return True, f"精确匹配 topic_summaries: \"{existing}\""
                all_existing.append(("topic_summaries", existing, None))

            for entry in context.get("topics", []):
                entry_topic = entry.get("topic", "")
                norm_entry = normalize_topic(entry_topic)
                if norm_entry == normalized:
                    return True, (
                        f"精确匹配 topics 数组: \"{entry_topic}\""
                        f"（{entry.get('date', '?')}，{entry.get('file', '?')}）"
                    )
                all_existing.append(("topics", entry_topic, entry.get("date")))

        except Exception as e:
            print(f"[check_topic] ⚠️ 读取 topics_context.json 失败: {e}", file=sys.stderr)

    # === 检查 2: 扫描已有文章文件 ===
    for md_file in sorted(workspace.glob("articles/**/*-每日冷知识*.md")):
        file_topic = extract_topic_from_article(md_file)
        if file_topic:
            if normalize_topic(file_topic) == normalized:
                return True, f"精确匹配文章文件: {md_file.name}"
            all_existing.append(("file", file_topic, md_file.name))

    # === 检查 3: 语义相似度检测 ===
    angle_matches = []  # 角度相关候选（相似度落在 [ANGLE_THRESHOLD, threshold) 区间）
    for source, existing_topic, meta in all_existing:
        is_sim, score, detail = check_semantic_similarity(topic, existing_topic, threshold)
        if is_sim:
            meta_str = f"（{meta}）" if meta else ""
            return True, (
                f"语义相似 [{source}]{meta_str}: \"{existing_topic}\" — {detail}"
            )
        if score >= ANGLE_THRESHOLD:
            angle_matches.append((source, existing_topic, meta, score))

    # 角度相关候选：相似度落在 [ANGLE_THRESHOLD, threshold) 区间
    # --angle 开启 → 放行并输出提示（由上层确认角度不同）
    # --angle 未开启 → 仍判重复（严格模式）
    if angle_matches:
        angle_matches.sort(key=lambda x: x[3], reverse=True)
        source, existing_topic, meta, score = angle_matches[0]
        meta_str = f"（{meta}）" if meta else ""
        if angle_mode:
            return False, (
                f"⚠️ 角度相关（相似度 {score:.0%}），请确认写作角度与已有话题不同 "
                f"[{source}]{meta_str}: \"{existing_topic}\""
            )
        return True, (
            f"语义相似 [角度相关区间] [{source}]{meta_str}: \"{existing_topic}\" "
            f"— 相似度 {score:.0%}（≥{ANGLE_THRESHOLD:.0%} 且 <{threshold:.0%}），"
            f"若确认写作角度不同请用 --angle 模式放行"
        )

    return False, "话题未使用过，可以写作"


def main():
    parser = argparse.ArgumentParser(description="话题去重校验")
    parser.add_argument("topic_positional", nargs='?', help="要校验的话题（位置参数）")
    parser.add_argument("--topic", "-t", help="要校验的话题")
    parser.add_argument("--file", "-f", help="从文章文件提取话题并校验")
    parser.add_argument("--threshold", type=float, default=OVERLAP_THRESHOLD,
                        help=f"语义相似重复阈值（默认 {OVERLAP_THRESHOLD}）")
    parser.add_argument("--angle", action="store_true",
                        help="角度模式：相似度 0.50 到阈值之间的角度相关话题放行并输出提示")
    parser.add_argument("--workspace", "-w", default=r"F:\WorkBuddy\daily-why",
                        help="工作目录路径")
    args = parser.parse_args()

    if args.threshold <= 0 or args.threshold > 1:
        print("[check_topic] ❌ 阈值必须在 0 到 1 之间", file=sys.stderr)
        sys.exit(2)
    if args.angle and args.threshold <= ANGLE_THRESHOLD:
        print(f"[check_topic] ⚠️ 阈值 {args.threshold} 不大于角度下限 {ANGLE_THRESHOLD}，"
              f"角度模式将不会放行任何话题", file=sys.stderr)

    # 确定话题来源
    topic = args.topic or args.topic_positional
    if args.file:
        filepath = Path(args.workspace) / args.file
        topic = extract_topic_from_article(filepath)
        if not topic:
            print(f"[check_topic] ❌ 无法从文件提取话题: {args.file}", file=sys.stderr)
            sys.exit(2)

    if not topic:
        print("[check_topic] ❌ 未提供话题。用法: check_topic.py \"为什么xxx？\"", file=sys.stderr)
        sys.exit(2)

    workspace = Path(args.workspace)
    is_dup, detail = check_topic(topic, workspace,
                                 threshold=args.threshold, angle_mode=args.angle)

    if is_dup:
        print(f"[check_topic] ❌ 重复: {detail}")
        sys.exit(1)
    else:
        print(f"[check_topic] ✅ 通过: {detail}")
        sys.exit(0)


if __name__ == "__main__":
    main()

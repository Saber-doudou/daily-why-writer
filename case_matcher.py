#!/usr/bin/env python3
"""
case_matcher.py — 智能判例匹配工具
根据问题关键词自动匹配相关判例，提高判例检索准确率。

用法：
    python case_matcher.py "因果链错误"
    python case_matcher.py "机构名虚构" --top 3
    python case_matcher.py --list
"""

import re
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional


# 判例库路径
CASE_STUDIES_PATH = Path(__file__).parent.parent / "review" / "CASE_STUDIES.md"


def load_case_studies() -> List[Dict]:
    """加载判例库，返回判例列表"""
    if not CASE_STUDIES_PATH.exists():
        return []

    content = CASE_STUDIES_PATH.read_text(encoding="utf-8")
    cases = []

    # 解析判例索引表
    index_pattern = r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(CS-\d+)\s*\|"
    for m in re.finditer(index_pattern, content):
        cases.append({
            "id": m.group(5),
            "date": m.group(1),
            "topic": m.group(2).strip(),
            "problem_type": m.group(3).strip(),
            "related_rule": m.group(4).strip(),
        })

    # 解析详细判例
    detail_pattern = (
        r"### (CS-\d+): (.+?)（(\d{4}-\d{2}-\d{2})）\s*\n\n"
        r"\*\*话题\*\*：(.+?)\s*\n\n"
        r"\*\*问题描述\*\*：\s*\n(.*?)\n\n"
        r"\*\*错误表现\*\*：\s*\n```\s*\n(.*?)\n```\s*\n\n"
        r"\*\*根因分析\*\*：\s*\n(.*?)\n\n"
        r"\*\*修正方案\*\*：\s*\n(.*?)\n\n"
        r"\*\*关联规则\*\*：(.+?)$"
    )

    for m in re.finditer(detail_pattern, content, re.MULTILINE | re.DOTALL):
        case_id = m.group(1)
        # 找到对应的索引记录并更新
        for case in cases:
            if case["id"] == case_id:
                case["title"] = m.group(2).strip()
                case["detailed_topic"] = m.group(4).strip()
                case["problem_description"] = m.group(5).strip()
                case["error_manifestation"] = m.group(6).strip()
                case["root_cause"] = m.group(7).strip()
                case["solution"] = m.group(8).strip()
                case["related_rule"] = m.group(9).strip()
                break

    return cases


def search_cases(query: str, cases: List[Dict], top_k: int = 3) -> List[Dict]:
    """根据查询关键词搜索相关判例

    Args:
        query: 查询关键词
        cases: 判例列表
        top_k: 返回前 k 个最相关的判例

    Returns:
        相关判例列表
    """
    if not query or not cases:
        return []

    # 计算每个判例的相关性分数
    scored_cases = []
    for case in cases:
        score = 0

        # 问题类型匹配（权重最高）
        if query in case.get("problem_type", ""):
            score += 10

        # 关联规则匹配
        if query in case.get("related_rule", ""):
            score += 8

        # 话题匹配
        if query in case.get("topic", ""):
            score += 5

        # 问题描述匹配
        if query in case.get("problem_description", ""):
            score += 3

        # 错误表现匹配
        if query in case.get("error_manifestation", ""):
            score += 2

        # 根因分析匹配
        if query in case.get("root_cause", ""):
            score += 2

        # 修正方案匹配
        if query in case.get("solution", ""):
            score += 2

        if score > 0:
            scored_cases.append((score, case))

    # 按分数排序，返回前 k 个
    scored_cases.sort(key=lambda x: -x[0])
    return [case for _, case in scored_cases[:top_k]]


def format_case_report(cases: List[Dict]) -> str:
    """格式化判例报告"""
    if not cases:
        return "未找到相关判例"

    report = []
    for i, case in enumerate(cases, 1):
        report.append(f"## 判例 {i}: {case.get('id', '未知')}")
        report.append(f"- **问题类型**: {case.get('problem_type', '未知')}")
        report.append(f"- **关联规则**: {case.get('related_rule', '未知')}")

        if case.get("error_manifestation"):
            report.append(f"- **错误表现**:")
            report.append(f"  ```")
            report.append(f"  {case['error_manifestation']}")
            report.append(f"  ```")

        if case.get("solution"):
            report.append(f"- **修正方案**:")
            for line in case["solution"].split("\n"):
                if line.strip():
                    report.append(f"  {line.strip()}")

        report.append("")

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="智能判例匹配工具")
    parser.add_argument("query", nargs="?", help="查询关键词")
    parser.add_argument("--top", type=int, default=3, help="返回前 k 个最相关的判例")
    parser.add_argument("--list", action="store_true", help="列出所有判例")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    # 加载判例库
    cases = load_case_studies()

    if args.list:
        # 列出所有判例
        print(f"判例库共 {len(cases)} 个判例：")
        for case in cases:
            print(f"  {case['id']}: {case.get('problem_type', '未知')} - {case.get('topic', '未知')}")
        return

    if not args.query:
        parser.print_help()
        return

    # 搜索相关判例
    matched_cases = search_cases(args.query, cases, args.top)

    if args.json:
        # JSON 格式输出
        print(json.dumps(matched_cases, ensure_ascii=False, indent=2))
    else:
        # 格式化输出
        print(f"查询: {args.query}")
        print(f"找到 {len(matched_cases)} 个相关判例：\n")
        print(format_case_report(matched_cases))


if __name__ == "__main__":
    main()

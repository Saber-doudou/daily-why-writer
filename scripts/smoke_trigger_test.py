#!/usr/bin/env python3
"""
smoke_trigger_test.py — daily-why 三技能触发冒烟测试

三层校验：
1. 路由表 JSON 合法性 + 结构与三 skill SKILL.md description 触发词一致性
2. 前缀冲突复检（委托 check_trigger_conflict 同款逻辑，独立实现）
3. 生成触发测试用例清单（每个触发词 → 预期路由 → 预期行为断言），供在对话中实测
   （当前环境无法自动模拟模型路由，实测由 AI/人工在对话中输入触发词完成）

用法：
    python smoke_trigger_test.py                # 输出测试报告到 stdout
    python smoke_trigger_test.py --write-report  # 同时写入 deliverables/触发冒烟测试-YYYYMMDD.md
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Windows GBK 兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

WORKSPACE = Path(r"F:\WorkBuddy\daily-why")
MAP_PATH = WORKSPACE / "config" / "skill-trigger-map.json"
DELIVERABLES = WORKSPACE / "deliverables"

# 三 skill 的 SKILL.md 路径（description 权威源）
SKILL_PATHS = {
    "daily-why-feed-learning": Path(r"C:\Users\admin\.workbuddy\skills\daily-why-feed-learning\SKILL.md"),
    "daily-why-publish": Path(r"C:\Users\admin\.workbuddy\skills\daily-why-publish\SKILL.md"),
    "daily-why-writer": Path(r"C:\Users\admin\.workbuddy\skills\daily-why-writer\SKILL.md"),
}

# 预期行为断言（每技能）
EXPECTED_BEHAVIOR = {
    "daily-why-feed-learning": [
        "加载技能后必须输出「✅ L2 SOP已加载」",
        "进入 Phase 0 输入验证（素材不足则显式提示缺哪几个 AI，不得静默终止）",
        "禁止仅确认收到后等待（ack 即失败）",
        "禁止把『学习总结』解读为『生成总结报告』（名词义误读）",
    ],
    "daily-why-publish": [
        "加载技能后必须输出「✅ L3 SOP已加载」",
        "进入 Step 1 脚本预检（l3_publish.py --dry-run）",
        "禁止仅确认收到后等待",
    ],
    "daily-why-writer": [
        "加载技能后输出「✅ SOP已加载：daily-why-writer SKILL.md」",
        "进入 Phase 0 选题流程",
        "输入含动作词（学习/投喂/总结/发布/推送/审计/备份）时不触发本技能",
    ],
}


def extract_trigger_words(skill_md: str) -> list:
    """从 SKILL.md description 的『触发词：』段提取触发词。
    允许跨行（description 为 folded scalar），截断到句号（触发词段以句号结尾，
    『路由排除』等说明在句号之后，不会被卷入）。"""
    m = re.search(r"触发词[：:]\s*([^。]+)", skill_md)
    if not m:
        return []
    text = m.group(1)
    parts = re.split(r"[、,，;；\s]+", text)
    return [p for p in parts if p]


def find_substring_conflicts(words_by_skill: dict, action_words_by_skill: dict) -> list:
    """两两检查子串冲突，仅报告【跨技能】冲突；被包含方有动作词优先规则则标已覆盖。"""
    entries = []
    for skill, words in words_by_skill.items():
        for w in words:
            entries.append((skill, w))
    conflicts = []
    n = len(entries)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            s1, a = entries[i]
            s2, b = entries[j]
            if s1 == s2:
                continue  # 同技能包含 = 设计合法
            if a == b or a not in b:
                continue
            covered = bool(action_words_by_skill.get(s2))
            conflicts.append({
                "prefix": a, "prefix_skill": s1,
                "contained_in": b, "contained_in_skill": s2,
                "covered": covered,
            })
    return conflicts


def main():
    write_report = "--write-report" in sys.argv
    today = datetime.now().strftime("%Y%m%d")
    issues = []

    # 1. 路由表加载与结构校验
    try:
        data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ 路由表 JSON 解析失败: {e}")
        return 1
    routes = {r["skill"]: r for r in data.get("routes", [])}
    missing = [s for s in SKILL_PATHS if s not in routes]
    if missing:
        print(f"❌ 路由表缺失技能: {missing}")
        return 1

    # 2. 与 SKILL.md description 一致性校验
    for skill, path in SKILL_PATHS.items():
        if not path.exists():
            issues.append(f"⚠️ SKILL.md 不存在: {path}")
            continue
        md = path.read_text(encoding="utf-8")
        desc_words = extract_trigger_words(md)
        map_words = routes[skill].get("trigger_words", [])
        only_desc = sorted(set(desc_words) - set(map_words))
        only_map = sorted(set(map_words) - set(desc_words))
        if only_desc:
            issues.append(f"⚠️ [{skill}] 仅存在于 SKILL.md description、路由表缺失: {only_desc}")
        if only_map:
            issues.append(f"⚠️ [{skill}] 仅存在于路由表、SKILL.md description 缺失: {only_map}")

    # 3. 子串冲突复检（跨技能，覆盖判定）
    words_by_skill = {}
    action_words_by_skill = {r["skill"]: r.get("action_words", []) for r in data["routes"]}
    for skill, path in SKILL_PATHS.items():
        md = path.read_text(encoding="utf-8") if path.exists() else ""
        words_by_skill[skill] = extract_trigger_words(md)
    conflicts = find_substring_conflicts(words_by_skill, action_words_by_skill)
    uncovered = [c for c in conflicts if not c["covered"]]

    # 4. 生成测试用例
    cases = []
    for skill in ["daily-why-feed-learning", "daily-why-publish", "daily-why-writer"]:
        r = routes[skill]
        for w in r.get("trigger_words", []):
            cases.append({
                "trigger": w,
                "expected_skill": skill,
                "expected_level": r.get("level", "?"),
                "behavior": EXPECTED_BEHAVIOR.get(skill, [])[:1],
            })
    # 附加歧义输入专项用例（验证动作词优先）
    ambiguity_cases = [
        {"trigger": "dailywhy学习总结", "expected": "L2（动作词优先，即使含 dailywhy 前缀）"},
        {"trigger": "dailywhy发布", "expected": "L3（动作词优先）"},
        {"trigger": "dailywhy", "expected": "不触发 L1 裸词（2026-08-28 起不再是触发词）；按语义可能走 L1 写作或询问"},
        {"trigger": "每日一个为什么学习", "expected": "L2"},
    ]

    total_words = sum(len(r.get("trigger_words", [])) for r in data["routes"])
    passed = len(issues) == 0 and len(uncovered) == 0

    lines = []
    lines.append(f"# 触发冒烟测试报告 - {today}")
    lines.append("")
    lines.append("> 由 scripts/smoke_trigger_test.py 生成。模型路由行为需在对话中实测，本报告为静态校验 + 测试用例清单。")
    lines.append("")
    lines.append(f"## 检查结果：{'✅ 通过' if passed else '⚠️ 存在问题'}")
    lines.append("")
    lines.append(f"- 路由表 JSON：{'✅ 合法' if routes else '❌ 非法'}")
    lines.append(f"- 触发词总数：{total_words}（L2={len(routes['daily-why-feed-learning']['trigger_words'])}，L3={len(routes['daily-why-publish']['trigger_words'])}，L1={len(routes['daily-why-writer']['trigger_words'])}）")
    lines.append(f"- 跨技能子串冲突：{len(conflicts)} 处（已覆盖 {len(conflicts) - len(uncovered)}，未覆盖 {len(uncovered)}）")
    for c in conflicts:
        mark = "✅已覆盖" if c["covered"] else "❌未覆盖"
        lines.append(f"  - [{mark}] '{c['prefix']}'({c['prefix_skill']}) 是 '{c['contained_in']}'({c['contained_in_skill']}) 的子串")
    lines.append(f"- 一致性告警：{len(issues)} 条")
    for i in issues:
        lines.append(f"  - {i}")
    lines.append("")
    lines.append("## 测试用例（对话实测用）")
    lines.append("")
    lines.append("| 触发输入 | 预期路由 | 预期行为断言 |")
    lines.append("|----------|----------|--------------|")
    for c in cases:
        lines.append(f"| `{c['trigger']}` | {c['expected_skill']}（{c['expected_level']}） | {c['behavior'][0]} |")
    lines.append("")
    lines.append("## 歧义输入专项用例")
    lines.append("")
    lines.append("| 触发输入 | 预期结果 |")
    lines.append("|----------|----------|")
    for c in ambiguity_cases:
        lines.append(f"| `{c['trigger']}` | {c['expected']} |")
    lines.append("")
    lines.append("## 实测记录模板（切模型后必跑）")
    lines.append("")
    lines.append("| 日期 | 模型 | 触发输入 | 实际路由 | 是否输出SOP确认 | 是否进入Phase/Step | 结论 |")
    lines.append("|------|------|----------|----------|------------------|---------------------|------|")
    lines.append("|      | hy3  | `dailywhy学习总结` |          |                  |                     |      |")
    lines.append("|      | deepseek | `dailywhy学习总结` |   |                  |                     |      |")
    lines.append("")
    report = "\n".join(lines)

    print(report)
    if write_report:
        DELIVERABLES.mkdir(exist_ok=True)
        out = DELIVERABLES / f"触发冒烟测试-{today}.md"
        out.write_text(report, encoding="utf-8")
        print(f"\n[smoke_trigger_test] 报告已写入: {out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

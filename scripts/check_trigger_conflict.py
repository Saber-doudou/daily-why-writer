#!/usr/bin/env python3
"""
check_trigger_conflict.py — daily-why 三技能触发词前缀/子串冲突静态检查

读取 config/skill-trigger-map.json（唯一权威源），对全部触发词做两两子串检查：
- 若 A 是 B 的子串（A != B），报告冲突（例如 L1 裸词 dailywhy 曾是 L2 dailywhy学习 的前缀）。
- 输出冲突列表；退出码 0 = 无冲突，1 = 存在冲突，2 = 参数/文件错误。

用法：
    python check_trigger_conflict.py            # 检查并输出结果
    python check_trigger_conflict.py --json     # 以 JSON 输出（供 CI/自动化解析）
"""
import json
import sys
from pathlib import Path

# Windows GBK 兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

MAP_PATH = Path(r"F:\WorkBuddy\daily-why\config\skill-trigger-map.json")


def load_map(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"路由表不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def find_conflicts(routes: list) -> dict:
    """两两检查触发词子串冲突，仅报告【跨技能】冲突（同技能内短词为长词前缀是设计合法）。

    覆盖判定：若被包含词所在技能声明了 action_words（非空，动作词优先），
    则该冲突已由「动作词优先」裁决规则覆盖（如 L1 的『每日一个为什么』
    是 L2 触发词前缀，但 L2 声明了 学习/投喂/总结 动作词优先 → covered）。
    """
    entries = []  # (skill, level, word, has_action_words)
    for r in routes:
        has_action = bool(r.get("action_words"))
        for w in r.get("trigger_words", []):
            entries.append((r["skill"], r.get("level", "?"), w, has_action))
    conflicts = []
    n = len(entries)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            a_skill, a_level, a, a_has_action = entries[i]
            b_skill, b_level, b, b_has_action = entries[j]
            if a_skill == b_skill:
                continue  # 同技能包含 = 设计合法（短词是长词前缀）
            if a == b or a not in b:
                continue
            # 跨技能：a 是 b 的子串。b 所属技能若有动作词优先规则 → 已覆盖
            covered = b_has_action
            conflicts.append({
                "prefix": a,
                "contained_in": b,
                "prefix_skill": f"{a_skill}({a_level})",
                "contained_in_skill": f"{b_skill}({b_level})",
                "covered_by_action_word_rule": covered,
                "risk": f"输入 '{b}' 会同时命中 '{a}'；{'已由被包含方动作词优先规则覆盖' if covered else '未被覆盖，需人工裁决'}",
            })
    return conflicts


def main():
    as_json = "--json" in sys.argv
    try:
        data = load_map(MAP_PATH)
    except Exception as e:
        print(f"❌ 路由表加载失败: {e}", file=sys.stderr)
        return 2

    routes = data.get("routes", [])
    if not routes:
        print("❌ 路由表无 routes 段", file=sys.stderr)
        return 2

    total_words = sum(len(r.get("trigger_words", [])) for r in routes)
    conflicts = find_conflicts(routes)
    covered = [c for c in conflicts if c["covered_by_action_word_rule"]]
    uncovered = [c for c in conflicts if not c["covered_by_action_word_rule"]]

    result = {
        "check": "trigger_substring_conflict",
        "map_path": str(MAP_PATH),
        "routes": len(routes),
        "total_trigger_words": total_words,
        "cross_skill_conflicts": len(conflicts),
        "covered_by_action_word_rule": len(covered),
        "uncovered_conflicts": len(uncovered),
        "conflicts": conflicts,
        "pass": len(uncovered) == 0,
    }

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("🔍 daily-why 触发词冲突静态检查（跨技能）")
        print(f"   路由表: {MAP_PATH.name}")
        print(f"   技能数: {len(routes)}，触发词总数: {total_words}")
        print("=" * 60)
        for r in routes:
            print(f"  [{r.get('level')}] {r['skill']}: {len(r.get('trigger_words', []))} 词"
                  + (f"，动作词 {r.get('action_words')}" if r.get("action_words") else ""))
        print("-" * 60)
        if conflicts:
            print(f"⚠️ 跨技能子串冲突 {len(conflicts)} 处（其中 {len(covered)} 处已由动作词优先规则覆盖）:")
            for c in conflicts:
                mark = "✅已覆盖" if c["covered_by_action_word_rule"] else "❌未覆盖"
                print(f"   [{mark}] '{c['prefix']}' ({c['prefix_skill']}) 是 '{c['contained_in']}' ({c['contained_in_skill']}) 的子串")
            if uncovered:
                print(f"\n❌ {len(uncovered)} 处冲突未被动作词优先覆盖，需人工裁决")
            else:
                print("\n✅ 所有跨技能冲突均已由动作词优先规则覆盖（A/B 方案生效）")
        else:
            print("✅ 无跨技能子串冲突（前缀冲突已消除）")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""review.json schema 机械校验器 —— 补上「强制输出物」缺失的执行校验（v1.0, 2026-09-07）

背景（常驻缺陷 40 / SOP Step 8.5「09-04 头号结论」）：
    reviewer_prompt v2.6 把 Step 5/5.5/5.6/5.7 的「自查法」软指令改成了强制输出物
    （fact_checks.detail_verified / quote_checks.verbatim_match /
     mechanism_checks.direction_ok+elements_complete / attribution_checks.is_primary_cause），
    但 **脚本侧零校验** —— 09-07 实证：v1 review.json 的 quote_checks 是空数组照样通过。
    「填了字段 ≠ 填对内容」，而「没填字段」至今无人发现。

    橙皮书 EXP-004「约束优于指令」：prompt 写得再准，Reviewer 不执行也无人知晓。
    本脚本把「是否执行」变成可机械判定的事实。

用法：
    python validate_review.py review/2026-09-07_review.json
    python validate_review.py review/2026-09-07_review.json --json     # 机器可读
    python validate_review.py review/2026-09-07_review.json --strict   # 警告也判失败

退出码：0=通过  1=校验失败  2=文件/参数错误

设计原则：
    - 只校验「结构完整性」，不评判「判断是否正确」——后者是 prompt 层的责任，
      本脚本解决的是「Reviewer 根本没做」这种最基础也最高发的失效。
    - 新增文件，不侵入 l3_publish.py 现有流程；接入与否由 Master 决定。
"""

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = "v1.0"

# v2.8（09-07 A 方案）新增：历史差距对照清单
GAP_PATTERNS_FILE = Path(
    r"C:\Users\admin\.workbuddy\skills\daily-why-writer\references\GAP_PATTERNS.md")
# 该清单自 2026-09-08 起强制；更早的 review.json 缺 gap_checks 属历史遗留，仅警告
GAP_ENFORCE_SINCE = "2026-09-08"

# v2.6 起要求的强制留痕数组
REQUIRED_ARRAYS = {
    "fact_checks": ["detail_verified"],
    "mechanism_checks": ["direction_ok", "elements_complete"],
    "attribution_checks": ["is_primary_cause"],
    "quote_checks": ["verbatim_match"],
    "term_checks": [],          # v2.7：无医学术语时允许空数组
}

# 顶层必需字段（两种 schema 至少命中其一：v1 用 p0_count，v2 两者都有）
REQUIRED_TOP_ANY = {
    "p0_count": ("p0",),
    "p1_count": ("p1",),
    "p2_count": ("p2",),
}

# 命中这些特征说明文中含「具体研究引用」，按 reviewer_prompt 自检清单第 5 项
# 要求 quote_checks ≥ 1 条
CITATION_HINT = re.compile(
    r"(19|20)\d{2}\s*年|《[^》]+》|期刊|论文|研究团队|大学|样本|受试者|"
    r"et al\.|Journal|University|研究显示|实验表明|数据来自",
    re.I,
)


def validate(path: Path) -> dict:
    """返回 {ok, errors, warnings, stats}"""
    errors, warnings = [], []
    stats = {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "errors": [f"读取/解析失败: {e}"],
                "warnings": [], "stats": {}}

    # 1. 顶层计数字段
    for key, alt in REQUIRED_TOP_ANY.items():
        if key not in data and not any(a in data for a in alt):
            errors.append(f"缺少计数字段 `{key}`（也未找到兼容字段 {'/'.join(alt)}）")

    # 2. script_result.char_count（maker-checker 闭环复核锚点 H2）
    sr = data.get("script_result")
    if not isinstance(sr, dict):
        errors.append("缺少 `script_result` 对象（H2 闭环复核将失效）")
    elif "char_count" not in sr:
        errors.append("`script_result` 缺少 `char_count`（无法做 maker-checker 闭环复核）")
    else:
        stats["char_count"] = sr["char_count"]

    # 3. 强制留痕数组：键必须存在
    for arr, fields in REQUIRED_ARRAYS.items():
        if arr not in data:
            errors.append(f"缺少强制输出物 `{arr}`（键名不得省略）")
            continue
        val = data[arr]
        if not isinstance(val, list):
            errors.append(f"`{arr}` 应为数组，实际为 {type(val).__name__}")
            continue
        stats[arr] = len(val)
        # 4. 数组内每条的必填字段
        for i, item in enumerate(val):
            if not isinstance(item, dict):
                errors.append(f"`{arr}[{i}]` 应为对象")
                continue
            for f in fields:
                if f not in item:
                    errors.append(f"`{arr}[{i}]` 缺少必填字段 `{f}`")

    # 5. 条件非空：文中含具体研究引用时 quote_checks 至少 1 条
    #    （reviewer_prompt v2.6 落盘前自检清单第 5 项）
    blob = json.dumps(data, ensure_ascii=False)
    has_citation = bool(CITATION_HINT.search(blob))
    qc = data.get("quote_checks", [])
    if has_citation and isinstance(qc, list) and len(qc) == 0:
        warnings.append(
            "文中疑似含具体研究引用（期刊/年份/样本/机构），但 `quote_checks` 为空 —— "
            "按 reviewer_prompt 自检清单第 5 项应 ≥1 条；若确认无逐字引用可忽略"
        )

    # 6. 全字段判 true 的可疑信号（EXP-004 反例：填了字段≠填对）
    #    若 mechanism/attribution 全部为 true 且条数 ≥2，提示人工复核而非判错
    for arr in ("mechanism_checks", "attribution_checks"):
        val = data.get(arr)
        if isinstance(val, list) and len(val) >= 2:
            flags = []
            for item in val:
                if isinstance(item, dict):
                    flags += [v for k, v in item.items()
                              if k.endswith("_ok") or k in ("elements_complete",
                                                            "is_primary_cause")]
            if flags and all(f is True for f in flags):
                warnings.append(
                    f"`{arr}` 共 {len(val)} 条全部判定为 true —— "
                    "属正常结果，但结合历史漏判率 100%（09-02 至 09-07 连续四天），"
                    "建议人工复核是否放松了标准"
                )

    # 7. gap_checks：A 方案（换判定主体）的核心校验
    #    把「开放判断」换成「对照检查」，并机械校验是否逐条过过
    gap = data.get("gap_checks")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    enforce = bool(m and m.group(1) >= GAP_ENFORCE_SINCE)
    if gap is None:
        msg = "缺少对照检查输出物 `gap_checks`（Step 5.9 未执行）"
        (errors if enforce else warnings).append(msg)
    elif not isinstance(gap, list):
        errors.append("`gap_checks` 应为数组")
    else:
        stats["gap_checks"] = len(gap)
        # 条数必须与类型库一致（防止只填前几条就交差）
        total = count_gap_patterns()
        if total and len(gap) < total:
            msg = (f"`gap_checks` 仅 {len(gap)} 条，少于 `GAP_PATTERNS.md` 的 {total} 条 "
                   "—— 必须逐条对照，一条都不能少")
            (errors if enforce else warnings).append(msg)
        ids = set()
        for i, item in enumerate(gap):
            if not isinstance(item, dict):
                errors.append(f"`gap_checks[{i}]` 应为对象")
                continue
            for f in ("pattern_id", "triggered", "checked"):
                if f not in item:
                    errors.append(f"`gap_checks[{i}]` 缺少必填字段 `{f}`")
            pid = item.get("pattern_id")
            if pid:
                if pid in ids:
                    errors.append(f"`gap_checks` 中 `pattern_id={pid}` 重复")
                ids.add(pid)
            # checked=false 即承认「没核过」—— 这正是漏判的成因
            if item.get("checked") is not True:
                msg = f"`gap_checks[{i}]`（{pid}）的 `checked` 不为 true —— 未逐条核对"
                (errors if enforce else warnings).append(msg)

    ok = not errors and not warnings
    return {"ok": ok, "errors": errors, "warnings": warnings, "stats": stats}


def count_gap_patterns() -> int:
    """从 GAP_PATTERNS.md 统计类型总数（锚定 '## G-NN' 标题行）"""
    try:
        text = GAP_PATTERNS_FILE.read_text(encoding="utf-8")
    except OSError:
        return 0
    return len(re.findall(r"^##\s+G-\d{2}", text, re.M))


def main() -> int:
    p = argparse.ArgumentParser(
        description=f"review.json schema 校验器 {VERSION} —— 补上强制输出物的执行校验")
    p.add_argument("review_json", help="review.json 路径")
    p.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p.add_argument("--strict", action="store_true", help="有警告也判失败")
    args = p.parse_args()

    path = Path(args.review_json)
    if not path.exists():
        print(f"❌ 文件不存在: {path}", file=sys.stderr)
        return 2

    r = validate(path)

    if args.json:
        print(json.dumps({"file": str(path), **r}, ensure_ascii=False, indent=2))
    else:
        print(f"{'=' * 60}\nreview.json 校验 {VERSION}: {path.name}\n{'=' * 60}")
        if r["stats"]:
            print("统计:", "  ".join(f"{k}={v}" for k, v in r["stats"].items()))
        if r["errors"]:
            print(f"\n🔴 错误 {len(r['errors'])} 项（必须修复）:")
            for e in r["errors"]:
                print(f"  - {e}")
        if r["warnings"]:
            print(f"\n🟡 警告 {len(r['warnings'])} 项（建议复核）:")
            for w in r["warnings"]:
                print(f"  - {w}")
        if not r["errors"] and not r["warnings"]:
            print("\n✅ 全部校验通过")

    if r["errors"]:
        return 1
    if r["warnings"] and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""validate_contract.py — dailywhy 机器交接契约校验器（R2 / P0-4）

为什么不用 jsonschema 库：09:40 的自动化跑在托管解释器里，该环境没有 jsonschema /
pydantic；装依赖会引入「装完才能跑」的部署风险。这里实现 JSON Schema 的**受控子集**，
只支持 contracts/*.schema.json 实际用到的关键字，行为可测、无外部依赖。

版本分流（裁决书 A1）：
  - 有 schema_version == "v1" → 按 v1 schema 严格校验，失败即 exit 1
  - 无 schema_version          → legacy，只校验 7 个核心字段；缺口记入 gaps，不算失败
  - 有 schema_version 但不是 v1 → 直接失败，不猜

用法：
  python scripts/validate_contract.py --kind review --file review/2026-10-22_review.json
  python scripts/validate_contract.py --kind review --all --gaps-out deliverables/.../legacy_gaps.tsv
  python scripts/validate_contract.py --kind learning_summary --file 投喂素材/20261022/学习总结.md
  python scripts/validate_contract.py --kind publish_manifest --file deliverables/.../publish_manifest.json
  python scripts/validate_contract.py --kind evidence_card --file evidence/xxx.json

退出码：0 通过｜1 契约违规｜2 用法或 IO 错误｜3 仅 legacy 缺口（非失败，供台账）
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "contracts"

KINDS = {
    "review": "review.schema.json",
    "learning_summary": "learning_summary.schema.json",
    "publish_manifest": "publish_manifest.schema.json",
    "evidence_card": "evidence_card.schema.json",
}

# 裁决书 A1：legacy 只校验 7 个核心字段，score / pass 二者取一
LEGACY_REVIEW_REQUIRED = [
    "article_id", "review_timestamp", "p0_count", "p1_count", "p2_count", "issues",
]
LEGACY_REVIEW_ONE_OF = [("score", "pass")]

LEGACY_LEARNING_REQUIRED = ["improvements"]


# ────────────────────────── 受控 JSON Schema 子集 ──────────────────────────

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value, expected):
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    py = TYPE_MAP.get(expected)
    return isinstance(value, py) if py else True


def validate_node(value, schema, path, errors):
    """递归校验。errors 收集 (路径, 原因)。"""
    if schema is True or schema is None:
        return

    expected = schema.get("type")
    if expected:
        candidates = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(value, c) for c in candidates):
            errors.append((path, f"类型应为 {'/'.join(candidates)}，实际 {type(value).__name__}"))
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append((path, f"取值应为 {schema['enum']} 之一，实际 {value!r}"))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append((path, f"长度 < {schema['minLength']}（实际 {len(value)}）"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append((path, f"长度 > {schema['maxLength']}（实际 {len(value)}）"))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append((path, f"不匹配模式 {schema['pattern']!r}"))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append((path, f"小于最小值 {schema['minimum']}"))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append((path, f"大于最大值 {schema['maximum']}"))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append((path, f"条目数 < {schema['minItems']}（实际 {len(value)}）"))
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                validate_node(item, item_schema, f"{path}[{i}]", errors)

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append((path, f"缺少必填字段 {key}"))
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                validate_node(value[key], sub, f"{path}.{key}", errors)
        if schema.get("additionalProperties") is False:
            extra = [k for k in value if k not in props]
            if extra:
                errors.append((path, f"出现未定义字段 {extra}"))


def load_schema(kind):
    path = CONTRACTS_DIR / KINDS[kind]
    if not path.exists():
        raise FileNotFoundError(f"schema 不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ────────────────────────── 版本分流 ──────────────────────────

def classify(doc):
    """返回 (version, error)。version ∈ {'v1','legacy'}。"""
    if not isinstance(doc, dict):
        return None, "顶层不是 JSON 对象"
    if "schema_version" in doc:
        ver = doc["schema_version"]
        if ver == "v1":
            return "v1", None
        return None, f"未知 schema_version={ver!r}，只接受 'v1'（不接受猜测）"
    return "legacy", None


def legacy_gaps(kind, doc):
    """legacy 文件的字段缺口，只记录不修复（裁决书 A1）。"""
    missing = []
    if kind == "review":
        missing += [k for k in LEGACY_REVIEW_REQUIRED if k not in doc]
        if not any(k in doc for k in LEGACY_REVIEW_ONE_OF[0]):
            missing.append("score|pass")
    elif kind == "learning_summary":
        missing += [k for k in LEGACY_LEARNING_REQUIRED if k not in doc]
        if not doc.get("improvements"):
            missing.append("## 改进点 锚点或条目")
    return missing


# ────────────────────────── 学习总结 Markdown → JSON ──────────────────────────

SECTION_KEYS = {
    "改进点": "improvements",
    "新提炼规则": "new_rules",
    "被拒绝的建议": "rejected_suggestions",
}


def md_to_learning_summary(path: Path) -> dict:
    """把学习总结 Markdown 规范化为 JSON。

    契约锚点：`## 改进点` 必须是逐字二级标题（L2 SKILL v3.4 已强制）。
    只抽三段列表项；其余章节保持自由文本，不进契约。
    """
    text = path.read_text(encoding="utf-8")
    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else ""

    sections = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current and re.match(r"^-\s+", line):
            sections[current].append(re.sub(r"^-\s+", "", line).strip())

    date = ""
    dir_m = re.search(r"(\d{8})", path.parent.name)
    if dir_m:
        d = dir_m.group(1)
        date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    else:
        dm = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", title + str(path))
        if dm:
            date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

    doc = {
        "date": date,
        "article_id": date,
        "title": title,
        # 与 contracts/learning_summary.schema.json 的必填字段名严格一致（审校 R2-1）
        "source_files": [str(path).replace("\\", "/")],
    }
    for zh, key in SECTION_KEYS.items():
        doc[key] = [{"text": t} for t in sections.get(zh, [])]
    return doc


# ────────────────────────── 单文件校验 ──────────────────────────

def check_file(kind, path: Path, require_v1=False, md_as_v1=False):
    """返回 (status, version, errors, gaps)。status ∈ ok/violation/legacy_gap"""
    if path.suffix.lower() == ".md":
        if kind != "learning_summary":
            return "violation", None, [("-", f"{kind} 不接受 Markdown 输入")], []
        doc = md_to_learning_summary(path)
        if md_as_v1:
            # 仅在显式声明时注入，用于验证「L2 产出 JSON 后」的 v1 通路；
            # 历史回放默认不注入，保证版本分类是真的（审校 R2-1）
            doc["schema_version"] = "v1"
    else:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            return "violation", None, [("-", f"JSON 解析失败: {e}")], []

    version, err = classify(doc)
    if err:
        return "violation", None, [("-", err)], []

    if require_v1 and version == "legacy":
        return "violation", version, [("-", "要求 v1：缺少 schema_version（新产出必须带）")], []

    if version == "v1":
        schema = load_schema(kind)
        errors = []
        validate_node(doc, schema, "$", errors)
        return ("ok" if not errors else "violation"), version, errors, []

    gaps = legacy_gaps(kind, doc)
    return ("legacy_gap" if gaps else "ok"), version, [], gaps


# ────────────────────────── CLI ──────────────────────────

def iter_targets(kind, args):
    if args.file:
        yield Path(args.file)
        return
    if kind == "review":
        base = ROOT / "review"
        for p in sorted(base.glob("*.json")):
            yield p
    elif kind == "learning_summary":
        base = ROOT / "投喂素材"
        # 2026-10-29：L2 v3.7 起机器交接件为 learning_summary.json（v1 契约）。
        # 批量扫描优先取 JSON（权威），无 JSON 的日期目录才回退 Markdown（legacy）。
        # 保持「每个日期目录至多一条」，避免同一天被重复计数。
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            js = d / "learning_summary.json"
            if js.exists():
                # 有机器契约件时，Markdown 只是渲染视图，不再重复计入
                yield js
                continue
            # 无 JSON：保留原有「一个目录多份 md 各计一份」的语义
            # （20260623 的 学习总结_v2.md、20260811 的第二份均属此类，取首份会丢覆盖）
            for p in sorted(d.glob("学习总结*.md")):
                yield p
    else:
        raise SystemExit(f"{kind} 必须显式给 --file")


def main():
    ap = argparse.ArgumentParser(description="dailywhy 契约校验（v1/legacy 版本分流）")
    ap.add_argument("--kind", required=True, choices=sorted(KINDS))
    ap.add_argument("--file", help="单个文件")
    ap.add_argument("--all", action="store_true", help="批量：review 扫 review/*.json，learning_summary 扫 投喂素材/*/学习总结*.md")
    ap.add_argument("--require-v1", action="store_true", help="要求带 schema_version=v1（新产出闸门）")
    ap.add_argument("--md-as-v1", action="store_true",
                    help="学习总结 Markdown 按 v1 校验（模拟 L2 已产出 JSON 的通路，仅测试用）")
    ap.add_argument("--gaps-out", help="把 legacy 缺口写成 TSV")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出汇总")
    args = ap.parse_args()

    if not args.file and not args.all:
        ap.error("需要 --file 或 --all")

    rows = []
    counts = {"ok": 0, "violation": 0, "legacy_gap": 0}
    v1 = 0
    legacy = 0

    for path in iter_targets(args.kind, args):
        status, version, errors, gaps = check_file(args.kind, path, args.require_v1, args.md_as_v1)
        counts[status] += 1
        if version == "v1":
            v1 += 1
        elif version == "legacy":
            legacy += 1
        rel = str(path).replace("\\", "/")
        root_str = str(ROOT).replace("\\", "/").rstrip("/")
        if rel.startswith(root_str + "/"):
            rel = rel[len(root_str) + 1:]
        rows.append({
            "file": rel,
            "kind": args.kind,
            "status": status,
            "version": version or "unknown",
            "errors": errors,
            "gaps": gaps,
        })

    if args.gaps_out:
        out = Path(args.gaps_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = ["timestamp\tkind\tschema_version\tfile\tmissing_fields"]
        from datetime import datetime
        ts = datetime.now().isoformat(timespec="seconds")
        for r in rows:
            if r["gaps"]:
                lines.append(f"{ts}\t{r['kind']}\tlegacy\t{r['file']}\t{','.join(r['gaps'])}")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({
            "kind": args.kind,
            "total": len(rows),
            "ok": counts["ok"],
            "violation": counts["violation"],
            "legacy_gap": counts["legacy_gap"],
            "v1": v1,
            "legacy": legacy,
            "rows": [r for r in rows if r["status"] != "ok"],
        }, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            if r["status"] == "ok":
                continue
            tag = "FAIL" if r["status"] == "violation" else "GAP "
            detail = "; ".join(f"{p}: {m}" for p, m in r["errors"]) if r["errors"] else "缺 " + ",".join(r["gaps"])
            print(f"[{tag}] {r['file']}  ({r['version']})  {detail}")
        print(f"\n合计 {len(rows)} 份｜ok {counts['ok']}｜violation {counts['violation']}｜legacy_gap {counts['legacy_gap']}｜v1 {v1}｜legacy {legacy}")

    if counts["violation"]:
        return 1
    if counts["legacy_gap"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

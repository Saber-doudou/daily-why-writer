#!/usr/bin/env python3
"""素材池维护工具（2026-10-27 新增，R3 补丁）。

【为什么有这个脚本】
L1 提示词步骤 5 原文是「用 Bash 追加/更新到 config/topic_candidates.json，
保持 JSON 合法」——纯手工、无脚本、无校验。10-27 生产实跑整步漏做，
而且从外部完全看不出来（正是项目自己立的 EXP-004「约束优于指令」的反面）。

【做法：不靠模型记，靠既有副作用派生】
每个候选在 L1 步骤 3 都必须过 check_topic.py，而 check_topic 本来就会把
每次判定写进 logs/check_topic_decisions.jsonl。所以「今天探测过哪些候选」
这件事早就被记录下来了，不需要模型再记一遍。

回捞规则：
  数据源 = logs/check_topic_decisions.jsonl
  筛选   = ts 属于当日 + mode == "angle"（步骤3/降级①②都走 --angle）
           + exclude_date 为空（排除步骤9 的成稿标题复查）
           + verdict == "pass"（判重复的说明议题已写过，回池没意义）
  减去   = evidence/{date}.json 的 topic（当日成稿主题）
  去重   = 与池内已有 topic 归一化比对

这样改完：L1 提示词一个字都不用动，模型也不用记住任何事。

【契约：field_spec 内嵌在数据里】
池内每类 source 的必填字段写在 topic_candidates.json 的 field_spec 里，
本脚本与 full_selfcheck.py 共读同一份规则，避免「代码一套、文档一套」。

用法：
  python scripts/topic_candidates.py --harvest                    # 回捞今天
  python scripts/topic_candidates.py --harvest --date 2026-10-27
  python scripts/topic_candidates.py --harvest --dry-run          # 只看会加什么
  python scripts/topic_candidates.py --validate                   # 按 field_spec 校验
  python scripts/topic_candidates.py --status                     # 池子概况
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "config" / "topic_candidates.json"
LOG = ROOT / "logs" / "check_topic_decisions.jsonl"
EVIDENCE_DIR = ROOT / "evidence"
ARTICLES_DIR = ROOT / "articles"

VALID_SOURCES = ("initial", "external", "l2", "rejected")

# field_spec 缺失时的兜底（旧文件兼容）；新规则以数据文件为准
DEFAULT_FIELD_SPEC = {
    "common": ["topic", "source"],
    "by_source": {
        "initial": ["category", "why_hot"],
        "external": ["category", "why_hot"],
        "l2": ["category", "why_hot"],
        "rejected": ["angle|why_hot|provenance"],
    },
}

_EMOJI = re.compile(
    "[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF\u2600-\u27BF\u200b\ufe0f\u200d]")
_PUNCT = re.compile(r"[？?。.！!，,、\s]+$")


def norm(text: str) -> str:
    """归一化用于去重：去 emoji、去尾部标点、压空白。"""
    s = _EMOJI.sub("", str(text or ""))
    s = re.sub(r"\s+", "", s)
    s = _PUNCT.sub("", s)
    return s.strip().lower()


def load_pool(path=POOL):
    return json.loads(path.read_text(encoding="utf-8"))


def save_pool(data, path=POOL):
    """原子写 + 回读校验：手改 JSON 写坏是这套流程的老问题。"""
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    json.loads(tmp.read_text(encoding="utf-8"))  # 写后回读，不合法直接抛错
    os.replace(tmp, path)
    return path


def field_spec_of(data):
    spec = data.get("field_spec")
    return spec if isinstance(spec, dict) else DEFAULT_FIELD_SPEC


def validate_pool(data):
    """按 field_spec 校验；返回 [(index, 原因)]。"""
    spec = field_spec_of(data)
    common = spec.get("common", ["topic", "source"])
    by_source = spec.get("by_source", {})
    problems = []
    for i, c in enumerate(data.get("candidates", [])):
        missing_common = [k for k in common if k not in c]
        if missing_common:
            problems.append((i, f"缺公共字段 {missing_common}"))
            continue
        src = c.get("source")
        if src not in VALID_SOURCES:
            problems.append((i, f"source 非法: {src!r}"))
            continue
        need = by_source.get(src) or []
        for rule in need:
            # "a|b|c" 表示至少其一
            alts = [x.strip() for x in rule.split("|")]
            if not any(a in c for a in alts):
                problems.append((i, f"source={src} 需 {rule}"))
                break
    return problems


def _read_jsonl(path):
    """读 JSONL，跳过 [truncated] 标记行与坏行（日志会按字节预算截断）。"""
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _selected_topic(date_str, evidence_dir=None, articles_dir=None):
    """当日成稿主题：优先证据卡，回落 articles 目录标题。"""
    evidence_dir = Path(evidence_dir or EVIDENCE_DIR)
    articles_dir = Path(articles_dir or ARTICLES_DIR)
    card = evidence_dir / f"{date_str}.json"
    if card.exists():
        try:
            t = json.loads(card.read_text(encoding="utf-8")).get("topic")
            if t:
                return t, "evidence_card"
        except Exception:
            pass
    month = date_str[:7]
    for p in sorted((articles_dir / month).glob(f"{date_str}-每日冷知识*.md")):
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    return line.lstrip("#").strip(), "article_title"
        except Exception:
            continue
    return None, None


def harvest(date_str, dry_run=False, pool_path=None, log_path=None,
            evidence_dir=None, articles_dir=None):
    """回捞当日探测过但未采用的候选，追加为 rejected。"""
    pool_path = Path(pool_path or POOL)
    log_path = Path(log_path or LOG)
    evidence_dir = Path(evidence_dir or EVIDENCE_DIR)
    articles_dir = Path(articles_dir or ARTICLES_DIR)

    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    cands = pool.setdefault("candidates", [])
    existing = {norm(c.get("topic")) for c in cands}

    rows = _read_jsonl(log_path)
    probes = [
        r for r in rows
        if str(r.get("ts", "")).startswith(date_str)
        and r.get("mode") == "angle"
        and not r.get("exclude_date")
        and r.get("verdict") == "pass"
    ]
    seen, ordered = set(), []
    for r in probes:
        key = norm(r.get("topic"))
        if key and key not in seen:
            seen.add(key)
            ordered.append(r["topic"])

    sel, sel_src = _selected_topic(date_str, evidence_dir, articles_dir)
    sel_key = norm(sel) if sel else None

    added, skipped_self, skipped_dup = [], [], []
    for topic in ordered:
        k = norm(topic)
        if sel_key and k == sel_key:
            skipped_self.append(topic)
            continue
        if k in existing:
            skipped_dup.append(topic)
            continue
        added.append({
            "topic": topic,
            "source": "rejected",
            "provenance": {
                "kind": "l1_probe",
                "date": date_str,
                "verdict": "pass",
                "note": "L1 步骤3 探测通过但当日未采用，由决策日志自动回捞",
            },
        })

    print(f"[topic_candidates] 日期 {date_str}｜日志探测通过 {len(ordered)} 条"
          f"｜成稿主题={sel or '未找到'}（来源 {sel_src or '-'}）")
    print(f"[topic_candidates] 待添加 {len(added)}｜跳过(成稿主题) {len(skipped_self)}"
          f"｜跳过(池内已有) {len(skipped_dup)}")
    for t in added:
        print(f"  + {t['topic']}")
    for t in skipped_self:
        print(f"  = 成稿: {t}")

    if dry_run:
        print("[topic_candidates] --dry-run，未写文件")
        return 0
    if not added:
        print("[topic_candidates] 无新增，文件未改动")
        return 0

    cands.extend(added)
    pool["updated"] = date_str
    problems = validate_pool(pool)
    if problems:
        print(f"[topic_candidates] ❌ 写入前校验失败：{problems[:5]}", file=sys.stderr)
        return 1
    save_pool(pool, pool_path)
    back = json.loads(pool_path.read_text(encoding="utf-8"))
    if len(back.get("candidates", [])) != len(cands):
        print(f"[topic_candidates] ❌ 回读条数不符 "
              f"{len(back.get('candidates', []))} != {len(cands)}", file=sys.stderr)
        return 1
    print(f"[topic_candidates] ✅ 已追加 {len(added)} 条，池内共 {len(cands)} 条")
    return 0


def cmd_validate():
    data = load_pool()
    problems = validate_pool(data)
    n = len(data.get("candidates", []))
    if problems:
        print(f"[topic_candidates] ❌ {n} 条中 {len(problems)} 条不合规")
        for i, why in problems[:20]:
            print(f"  [{i}] {why}")
        return 1
    print(f"[topic_candidates] ✅ {n} 条全部合规（按 field_spec）")
    return 0


def cmd_status():
    data = load_pool()
    cands = data.get("candidates", [])
    print(f"素材池：{len(cands)} 条｜updated={data.get('updated')}")
    print("source 分布:", dict(Counter(c.get("source") for c in cands)))
    spec = field_spec_of(data)
    no_ev = [i for i, c in enumerate(cands)
             if c.get("source") != "rejected" and "evidence" not in c]
    print(f"缺 evidence（质量字段，非结构）：{len(no_ev)} 条 {no_ev}")
    print("field_spec:", "内置默认" if spec is DEFAULT_FIELD_SPEC else "数据文件自带")
    return 0


def selftest():
    """临时目录端到端自测：验证 4 个过滤条件 + 成稿排除 + 去重 + field_spec 校验。

    为什么要有：回捞的数据源是「日志」，而日志里混着标题复查、严格模式判定、
    判重复记录、往日期记录和 [truncated] 标记行。过滤条件写错的后果是
    把成稿主题或已写过的重复话题回灌进池子，下游兜底取到就是废票。
    """
    import tempfile

    ok = 0
    total = 0

    def case(name, cond, detail=""):
        nonlocal ok, total
        total += 1
        ok += bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name}{'' if cond else '  ' + detail}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "config").mkdir()
        (root / "logs").mkdir()
        (root / "evidence").mkdir()
        pool_path = root / "config" / "topic_candidates.json"
        log_path = root / "logs" / "check_topic_decisions.jsonl"

        pool = {
            "updated": "2025-12-31",
            "field_spec": DEFAULT_FIELD_SPEC,
            "candidates": [{"topic": "为什么冰面那么滑？", "source": "rejected",
                            "angle": "冰面融化水膜"}],
        }
        pool_path.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
        (root / "evidence" / "2026-01-01.json").write_text(
            json.dumps({"topic": "为什么朝纸中间吹气纸会贴紧？"}, ensure_ascii=False),
            encoding="utf-8")

        entries = [
            # 期望新增
            {"ts": "2026-01-01T09:00:01", "mode": "angle", "exclude_date": None,
             "topic": "为什么纯水不导电？", "verdict": "pass"},
            # 成稿主题：须排除
            {"ts": "2026-01-01T09:00:00", "mode": "angle", "exclude_date": None,
             "topic": "为什么朝纸中间吹气纸会贴紧？", "verdict": "pass"},
            # 池内已有：须去重
            {"ts": "2026-01-01T09:00:02", "mode": "angle", "exclude_date": None,
             "topic": "为什么冰面那么滑？", "verdict": "pass"},
            # 步骤9 标题复查（带 exclude_date）：须排除
            {"ts": "2026-01-01T09:00:03", "mode": "angle", "exclude_date": "2026-01-01",
             "topic": "复查用的标题", "verdict": "pass"},
            # 严格模式判定：须排除
            {"ts": "2026-01-01T09:00:04", "mode": "strict", "exclude_date": None,
             "topic": "严格模式话题", "verdict": "pass"},
            # 判重复：议题已写过，回池无意义
            {"ts": "2026-01-01T09:00:05", "mode": "angle", "exclude_date": None,
             "topic": "已写过的重复话题", "verdict": "duplicate"},
            # 往日期：须排除
            {"ts": "2025-12-31T09:00:00", "mode": "angle", "exclude_date": None,
             "topic": "昨天的候选", "verdict": "pass"},
        ]
        lines = ["[truncated] 超过 5MB 自动截断"] + [
            json.dumps(e, ensure_ascii=False) for e in entries]
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        rc = harvest("2026-01-01", pool_path=pool_path, log_path=log_path,
                     evidence_dir=root / "evidence", articles_dir=root / "articles")
        after = json.loads(pool_path.read_text(encoding="utf-8"))
        topics = [c["topic"] for c in after["candidates"]]

        case("harvest 退出码 0", rc == 0, f"rc={rc}")
        case("只新增 1 条", len(topics) == 2, f"实际 {len(topics)}: {topics}")
        case("新增的是纯水条", "为什么纯水不导电？" in topics, str(topics))
        case("成稿主题未被回灌", "为什么朝纸中间吹气纸会贴紧？" not in topics)
        case("带 exclude_date 的复查被排除", "复查用的标题" not in topics)
        case("严格模式被排除", "严格模式话题" not in topics)
        case("判重复的不回池", "已写过的重复话题" not in topics)
        case("往日期不混入", "昨天的候选" not in topics)
        case("池内已有未被重复添加", topics.count("为什么冰面那么滑？") == 1)
        case("updated 已刷新", after.get("updated") == "2026-01-01", str(after.get("updated")))
        added = [c for c in after["candidates"] if c["topic"] == "为什么纯水不导电？"][0]
        case("新增条目带 provenance", isinstance(added.get("provenance"), dict))
        case("新增后 field_spec 校验通过", validate_pool(after) == [], str(validate_pool(after)))

        # 负向：把 topic 删掉，校验必须抓到
        broken = json.loads(json.dumps(after))
        del broken["candidates"][0]["topic"]
        case("缺 topic 能被校验抓到", len(validate_pool(broken)) == 1,
             str(validate_pool(broken)))
        # 负向：rejected 三选一全缺，必须抓到
        broken2 = json.loads(json.dumps(after))
        broken2["candidates"].append({"topic": "裸条目", "source": "rejected"})
        case("rejected 三选一全缺能被抓到",
             any("rejected" in why for _, why in validate_pool(broken2)))

    print(f"\n自检 {ok}/{total} 通过")
    return 0 if ok == total else 1


def main():
    ap = argparse.ArgumentParser(description="dailywhy 素材池维护（10-27）")
    ap.add_argument("--harvest", action="store_true", help="从决策日志回捞当日落选候选")
    ap.add_argument("--date", default=None, help="目标日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--dry-run", action="store_true", help="只看会加什么，不写文件")
    ap.add_argument("--validate", action="store_true", help="按 field_spec 校验池子")
    ap.add_argument("--status", action="store_true", help="池子概况")
    ap.add_argument("--selftest", action="store_true", help="临时目录端到端自测")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.validate:
        return cmd_validate()
    if args.status:
        return cmd_status()
    if args.harvest:
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
            print(f"[topic_candidates] ❌ 日期格式应为 YYYY-MM-DD，实际 {date_str}", file=sys.stderr)
            return 2
        return harvest(date_str, dry_run=args.dry_run)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

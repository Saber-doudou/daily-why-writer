#!/usr/bin/env python3
"""evidence_gate.py — 证据门禁（R3 / P0-1）

作用：写作前卡住「没有来源的机制/数字/归因 claim」，写作后卡住「正文事实句没有证据映射」。
只做机械判定，不判断事实真假（真假要靠证据卡里的 url + 逐字引文 + 审校）。

四类检查（对应方案书 P0-1）：
  1. 每条高风险 claim 必须有 url 与不少于 15 字的逐字引文；
  2. tertiary 来源不得单独支撑 mechanism / number / attribution；
  3. 正文中每个高风险事实句必须能映射到 claim id（句末 `<!-- claim:C3 -->` 或卡内 fragments 映射）；
  4. 未映射的事实句、或映射到 unverified claim 的句子，判 P0。

用法：
  python scripts/evidence_gate.py --card evidence/2026-10-27.json --article articles/2026-10/xxx.md
  python scripts/evidence_gate.py --card ... --article ... --mode warn     # 只告警不阻断
  python scripts/evidence_gate.py --selftest                               # 内置夹具自检

退出码：0 通过（或 warn 模式）｜1 存在 P0｜2 用法或读取错误
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIGH_RISK = {"mechanism", "number", "attribution"}
MIN_QUOTE = 15

# 高风险事实句特征：数字类表达。
# 阿拉伯数字 + 倍数/百分比/分数，外加带计量单位的中文数字（「五十年代」「三倍」这类
# 同样是可核事实，不能被漏掉——模拟运行 S1 就漏了「上世纪五十年代」）。
# 不带单位的中文数字（三张表、两步走）不触发，避免误杀。
FACT_PAT = re.compile(
    r"\d|倍|百分之|[一二三四五六七八九十百千万]+分之[一二三四五六七八九十]+"
    r"|[一二三四五六七八九十百千万]+(?:年|倍|米|毫米|厘米|吨|公斤|克|摄氏度|度|分钟|小时)"
)


# ───────────────────────── 卡片检查 ─────────────────────────

def check_card(card):
    """返回 findings 列表：[(severity, code, where, message)]"""
    out = []
    claims = card.get("claims") or []
    seen = set()
    for i, c in enumerate(claims):
        cid = c.get("id") or f"#{i}"
        where = f"claim {cid}"
        if cid in seen:
            out.append(("P0", "duplicate_id", where, f"claim id 重复: {cid}"))
        seen.add(cid)

        ctype = c.get("type")
        src = c.get("source") or {}
        url = (src.get("url") or "").strip()
        quote = (c.get("quote") or "").strip()
        level = (src.get("source_level") or "").strip()
        verified = c.get("verified_by")
        conf = c.get("confidence")

        if ctype in HIGH_RISK:
            if not url:
                out.append(("P0", "missing_url", where, f"{ctype} claim 没有 url"))
            if len(quote) < MIN_QUOTE:
                out.append(("P0", "short_quote", where,
                            f"{ctype} claim 引文不足 {MIN_QUOTE} 字（实际 {len(quote)}）"))
            if level == "tertiary":
                out.append(("P0", "tertiary_only", where,
                            f"{ctype} claim 仅由 tertiary 来源支撑"))
            if verified == "none":
                out.append(("P0", "unverified", where, "verified_by=none，未核实不许写"))
            if conf == "unverified":
                out.append(("P0", "unverified", where, "confidence=unverified，未核实不许写"))
            if verified == "snippet":
                out.append(("P1", "snippet_only", where,
                            "仅 snippet 级核实，高风险 claim 建议 fetch 原文"))
    return out


# ───────────────────────── 正文检查 ─────────────────────────

def resolve_mapping(card):
    """两种映射：句末 HTML 注释，或卡内 fragments 列表。"""
    frags = []
    for m in (card.get("mapping") or []):
        cid, frag = m.get("claim_id"), (m.get("text") or "").strip()
        if cid and len(frag) >= 4:
            frags.append((cid, frag))
    return frags


def check_article(text, card):
    out = []
    claims = {c.get("id"): c for c in (card.get("claims") or [])}

    # 4.0 banned_claims：已证伪断言出现在正文即为 P0
    for banned in (card.get("banned_claims") or []):
        b = (banned or "").strip()
        if b and b in text:
            out.append(("P0", "banned_claim_hit", "正文", f"命中已证伪断言「{b}」"))

    frags = resolve_mapping(card)
    inline = re.compile(r"<!--\s*claim:\s*([A-Za-z0-9,\s]+?)\s*-->")

    for lineno, line in enumerate(text.splitlines(), 1):
        body = re.sub(r"^\s*(>\s*)?([-*+]\s+|\d+\.\s+)?", "", line).strip()
        # 2026-10-27 审校 R3 抓到的必然误判：F 段结尾的标准四行表格，
        # 「核心机制」行常含数字（TRPV1、占壳约 1/3），但表格是渲染层、无句末可分，
        # 事实本身来自正文 claim。表格行不参与事实句判定，改由审校 fact_checks 覆盖。
        if body.startswith("|"):
            continue
        # 同期误杀回归：SKILL 强制的 `**Q1：...**` 标题，序号 1/2/3 被 FACT_PAT
        # 当成数字，整句被判「事实句无映射」。Q 标签是格式，不是事实断言，判前先剥离。
        body = re.sub(r"^\*{0,2}\s*Q\d+\s*[：:]\s*", "", body)
        if not body:
            continue
        markers = []
        for m in inline.finditer(body):
            ids = [x.strip() for x in m.group(1).split(",") if x.strip()]
            markers.append((m.start(), m.end(), ids))

        # 按中文句末切句，保留位置用于就近绑定注释
        bounds = [(m.start(), m.end()) for m in re.finditer(r"[。！？；]", body)]
        sents, start = [], 0
        for s, e in bounds:
            sents.append((start, e))
            start = e
        if start < len(body):
            sents.append((start, len(body)))

        for s, e in sents:
            raw = body[s:e]
            sent = inline.sub("", raw).strip()
            if not sent:
                continue
            ids = []
            for ms, me, mids in markers:
                if s <= ms < e:
                    ids += mids
            if not ids:
                for ms, me, mids in markers:
                    if ms >= e and not body[e:ms].strip():
                        ids += mids
                        break
            if not ids:
                for cid, frag in frags:
                    if frag in sent:
                        ids.append(cid)

            # ── 两道独立检查，刻意不串成一个门（10-28 修复 #68）──
            # ①「事实句必须有映射」：只对含数字特征的句子生效。不能要求每句叙述都
            #   挂映射，那会把整篇文变成注释灾难，所以这条受 FACT_PAT 限制是对的。
            # ②「映射本身必须有效」：与句子有没有数字**无关**。悬空引用（指向不存在的
            #   claim）和挂到未核实 claim 上，在任何句子上都是错的。
            # 原实现把 ② 也放在 `if not FACT_PAT: continue` 之后，于是无数字的句子
            # 挂错 claim 时完全静默：标记指向空处，门禁却以为「已映射」放行。
            # 证据：eval/sim-artifacts/S4/article.md 与 article-with-fact.md 只差一句
            # 带中文数字的插入语，P0 就从 2 变 3，差额正是 unverified_mapping。
            if not ids:
                if FACT_PAT.search(sent):
                    out.append(("P0", "unmapped_fact", f"L{lineno}",
                                f"事实句无证据映射: {sent[:40]}"))
                continue
            for cid in ids:
                c = claims.get(cid)
                if c is None:
                    out.append(("P0", "unknown_claim", f"L{lineno}",
                                f"映射到不存在的 claim {cid}"))
                    continue
                if c.get("verified_by") == "none" or c.get("confidence") == "unverified":
                    out.append(("P0", "unverified_mapping", f"L{lineno}",
                                f"映射到未核实的 claim {cid}"))
    return out


# ───────────────────────── 夹具自检 ─────────────────────────

SELFTEST = {
    "good": {
        "card": {
            "schema_version": "v1",
            "topic": "测试话题",
            "claims": [{
                "id": "C1", "text": "某机制", "type": "mechanism",
                "source": {"title": "原始论文", "url": "https://example.org/paper",
                           "source_level": "primary"},
                "quote": "这是一段不少于十五个字的原文逐字引文示例",
                "verified_by": "fetch", "confidence": "high",
            }],
            "banned_claims": ["已证伪说法"],
        },
        "article": "这项研究覆盖了 93 个物种。<!-- claim:C1 -->\n普通叙述句，没有数字。",
        "expect_p0": 0, "expect_codes": [],
    },
    "short_quote": {
        "card": {
            "schema_version": "v1", "topic": "测试",
            "claims": [{"id": "C1", "text": "x", "type": "mechanism",
                        "source": {"title": "t", "url": "https://a.b", "source_level": "primary"},
                        "quote": "太短", "verified_by": "fetch", "confidence": "high"}],
            "banned_claims": [],
        },
        "article": "无事实句。",
        "expect_p0": 1, "expect_codes": ["short_quote"],
    },
    "tertiary": {
        "card": {
            "schema_version": "v1", "topic": "测试",
            "claims": [{"id": "C1", "text": "x", "type": "attribution",
                        "source": {"title": "t", "url": "https://a.b", "source_level": "tertiary"},
                        "quote": "这是一段不少于十五个字的第三方转述引文示例",
                        "verified_by": "fetch", "confidence": "high"}],
            "banned_claims": [],
        },
        "article": "无事实句。",
        "expect_p0": 1, "expect_codes": ["tertiary_only"],
    },
    "unmapped": {
        "card": {
            "schema_version": "v1", "topic": "测试",
            "claims": [{"id": "C1", "text": "x", "type": "number",
                        "source": {"title": "t", "url": "https://a.b", "source_level": "primary"},
                        "quote": "这是一段不少于十五个字的原始数据引文示例",
                        "verified_by": "fetch", "confidence": "high"}],
            "banned_claims": [],
        },
        "article": "这项研究覆盖了 93 个物种、6000 多枚标本。",
        "expect_p0": 1, "expect_codes": ["unmapped_fact"],
    },
    "banned": {        "card": {
            "schema_version": "v1", "topic": "测试",
            "claims": [{"id": "C1", "text": "x", "type": "mechanism",
                        "source": {"title": "t", "url": "https://a.b", "source_level": "primary"},
                        "quote": "这是一段不少于十五个字的原文引文示例文字",
                        "verified_by": "fetch", "confidence": "high"}],
            "banned_claims": ["白蚁分泌蚁酸"],
        },
        "article": "据说白蚁分泌蚁酸，能腐蚀白银。",
        "expect_p0": 1, "expect_codes": ["banned_claim_hit"],
    },
    # 2026-10-27 模拟运行 S1 的误杀回归：SKILL 强制的 `**Q1：...**` 标题，
    # 序号被当成数字导致整句判「事实句无映射」。剥离 Q 标签后应为 0。
    "q_label_false_positive": {
        "card": {"schema_version": "v1", "topic": "测试", "claims": [], "banned_claims": []},
        "article": "**Q1：这东西为什么这么重？** → 因为它很密。\n**Q2：真的吗？** → 真的。",
        "expect_p0": 0, "expect_codes": [],
    },
    # 中文数字带计量单位属于可核事实，必须要求映射（S1 漏过「上世纪五十年代」）
    "cn_numeral_fact": {
        "card": {"schema_version": "v1", "topic": "测试", "claims": [], "banned_claims": []},
        "article": "上世纪五十年代，喷气客机接连出事。",
        "expect_p0": 1, "expect_codes": ["unmapped_fact"],
    },
    # 审校 R3 抓到的必然误判：F 段表格行含数字（TRPV1、1/3），但表格是渲染层无句末，
    # 事实来自正文 claim，不应判无映射。
    "table_row_no_false_positive": {
        "card": {"schema_version": "v1", "topic": "测试", "claims": [], "banned_claims": []},
        "article": "| 话题 | 猫钻纸箱 | 分类 | 动物世界 |\n| 核心机制 | TRPV1 与热中性区 30 到 38 摄氏度 | 冷知识反转 | 纸箱是减压舱 |",
        "expect_p0": 0,
        "expect_codes": [],
    },

    # ── 10-27 新增：3 个针对已知弱点的压力夹具 ──
    # 用途：11-01 把门禁从 warn 切 block 之前，需要「误杀率」样本。真实文章偏「顺手」，
    # 撞不到边角，所以用夹具专门顶三类已知失效模式，且固化为回归，不像一次性模拟会烂掉。
    "stress_cn_numeral_dense": {
        # 弱点：中文数字带单位。10-27 前 FACT_PAT 漏掉「上世纪五十年代」，
        # 修完后仍须防回归；这条同时断言「必须是 unmapped_fact 抓到的」而非别的规则凑数。
        "card": {"schema_version": "v1", "topic": "测试", "claims": [], "banned_claims": []},
        "article": "上世纪五十年代，喷气客机接连出事。三十倍的压力差把人推向车边。",
        "expect_p0": 2,
        "expect_codes": ["unmapped_fact"],
    },
    "stress_table_and_qlabel_clean": {
        # 弱点：两类必然误杀同时出现——表格行里的数字、Q 标签里的数字。
        # 两者都不是事实句，必须 0 命中；与上一条互为反向，防「一修就松」。
        "card": {"schema_version": "v1", "topic": "测试", "claims": [], "banned_claims": []},
        "article": ("**Q1：为什么会往里贴？** → 因为压差。\n"
                    "| 话题 | 测试 | 分类 | 物理化学 |\n"
                    "| 核心机制 | 约 1/3 的水，三倍差距 | 冷知识反转 | 五十年代 |"),
        "expect_p0": 0,
        "expect_codes": [],
    },
    "stress_tertiary_and_banned": {
        # 弱点：两条最重的 P0 家族（tertiary 单独支撑 / 命中已证伪断言）从未在
        # 贴近真实文章的输入上被触发过，只在最小样例上验过。这条同时打两枪。
        "card": {
            "schema_version": "v1", "topic": "测试",
            "claims": [{"id": "C1", "text": "某归因", "type": "attribution",
                        "source": {"title": "转述源", "url": "https://a.b",
                                   "source_level": "tertiary"},
                        "quote": "这是一段不少于十五个字的第三方转述引文示例",
                        "verified_by": "fetch", "confidence": "high"}],
            "banned_claims": ["风总把东西吹散"],
        },
        "article": "风总把东西吹散。",
        "expect_p0": 2,
        "expect_codes": ["banned_claim_hit", "tertiary_only"],
    },

    # ── 10-28 新增：守住 #68 的修复 ──
    # 两条都刻意用「没有数字特征的句子 + 一个映射标记」。修复前这两条全静默，
    # 修复后必须报出来。用它们锁住「映射有效性检查不受 FACT_PAT 限制」这个不变量，
    # 防止将来有人图省事又把检查串回数字判断后面。
    "stress_unknown_claim_plain_sentence": {
        "card": {"schema_version": "v1", "topic": "测试", "claims": [], "banned_claims": []},
        "article": "这是一句完全没有数字的叙述。<!-- claim:C99 -->",
        "expect_p0": 1,
        "expect_codes": ["unknown_claim"],
    },
    "stress_unverified_mapping_plain_sentence": {
        "card": {
            "schema_version": "v1", "topic": "测试",
            "claims": [{"id": "C1", "text": "某机制", "type": "mechanism",
                        "source": {"title": "某来源", "url": "https://a.b",
                                   "source_level": "secondary"},
                        "quote": "这是一段不少于十五个字的引文占位用于长度校验",
                        "verified_by": "none", "confidence": "medium"}],
            "banned_claims": [],
        },
        "article": "这是一句完全没有数字的机制叙述。<!-- claim:C1 -->",
        "expect_p0": 2,
        "expect_codes": ["unverified", "unverified_mapping"],
    },
}


def run_selftest():
    """夹具自测。

    10-27 强化：除 P0 数量外，可选断言 expect_codes（命中的代码集合）。
    只比数量有个盲区——「因为别的原因误打正着凑够条数」也会 PASS。
    例如某夹具期望 1 条 P0，实际因 short_quote 命中而不是预期的 tertary_only，
    数量对上了但被测的规则根本没被触发。
    """
    ok = 0
    for name, case in SELFTEST.items():
        findings = check_card(case["card"]) + check_article(case["article"], case["card"])
        p0 = [f for f in findings if f[0] == "P0"]
        codes = {f[1] for f in p0}
        good = len(p0) == case["expect_p0"]
        want = case.get("expect_codes")
        if want is not None:
            good = good and codes == set(want)
        ok += good
        line = f"[{'PASS' if good else 'FAIL'}] {name}: P0={len(p0)} 期望={case['expect_p0']}"
        if want is not None:
            line += f"｜codes={sorted(codes)} 期望={sorted(want)}"
        print(line)
        for f in p0:
            print(f"        {f[1]}: {f[3]}")
    print(f"\n自检 {ok}/{len(SELFTEST)} 通过")
    return 0 if ok == len(SELFTEST) else 1


# ───────────────────────── CLI ─────────────────────────

def run_replay(tsv_path):
    """历史错误 claim 回放：每条错误断言必须被 banned_claims 拦住，正确写法必须放行。"""
    path = Path(tsv_path)
    if not path.exists():
        print(f"[evidence_gate] 回放集不存在: {path}", file=sys.stderr)
        return 2
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header = lines[0].split("\t")
    rows = [dict(zip(header, ln.split("\t"))) for ln in lines[1:] if ln.strip()]
    hit = miss = fp = 0
    for r in rows:
        card = {"schema_version": "v1", "topic": r["topic"],
                "claims": [], "banned_claims": [r["wrong_claim"]]}
        wrong_findings = check_article(f"据说{r['wrong_claim']}。", card)
        right_findings = check_article(f"{r['right_claim']}。", card)
        caught = any(f[1] == "banned_claim_hit" for f in wrong_findings)
        clean = not any(f[1] == "banned_claim_hit" for f in right_findings)
        if caught and clean:
            hit += 1
            print(f"[PASS] {r['case_id']} {r['topic']}：错误写法被拦，正确写法放行")
        elif caught and not clean:
            fp += 1
            print(f"[FAIL] {r['case_id']} {r['topic']}：正确写法也被拦（误杀）")
        else:
            miss += 1
            print(f"[FAIL] {r['case_id']} {r['topic']}：错误写法未被拦住")
    total = len(rows)
    print(f"\n回放 {total} 例：命中 {hit}｜漏判 {miss}｜误杀 {fp}")
    return 0 if hit == total else 1


def _resolve(p):
    """--card / --article 路径解析：先按 cwd，再按仓库根。"""
    path = Path(p)
    if path.exists():
        return path
    alt = ROOT / p
    return alt if alt.exists() else path


def _schema_findings(card_path):
    """用 validate_contract 做 schema 校验，避免「字段写错也能 0 分通过」。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import validate_contract
        status, _ver, errors, _gaps = validate_contract.check_file(
            "evidence_card", card_path, require_v1=True)
        if status == "ok":
            return []
        detail = "; ".join(f"{p}: {m}" for p, m in errors[:3]) or status
        return [("P0", "schema_invalid", "证据卡", detail)]
    except Exception as e:
        return [("P1", "schema_unchecked", "证据卡", f"schema 校验未能执行: {e}")]


def write_report(card_path, article, findings, mode):
    """warn 模式下退出码恒为 0，P0 必须落盘，否则会静默丢失（模拟 S2 指出的硬伤）。"""
    p0 = [f for f in findings if f[0] == "P0"]
    p1 = [f for f in findings if f[0] == "P1"]
    out = Path(card_path).with_suffix(".gate.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "card": str(card_path).replace("\\", "/"),
        "article": str(article).replace("\\", "/") if article else None,
        "p0_count": len(p0),
        "p1_count": len(p1),
        "blocked": bool(p0) and mode == "block",
        "findings": [{"severity": s, "code": c, "where": w, "message": m}
                     for s, c, w, m in findings],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description="dailywhy 证据门禁（R3/P0-1）")
    ap.add_argument("--card", help="证据卡 JSON")
    ap.add_argument("--article", help="文章 Markdown（可选，缺省只查卡）")
    ap.add_argument("--mode", choices=["block", "warn"], default="block")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--replay", help="历史错误 claim 回放集（TSV）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-report", action="store_true", help="不写 .gate.json 报告")
    args = ap.parse_args()

    if args.selftest:
        return run_selftest()
    if args.replay:
        return run_replay(args.replay)
    if not args.card:
        ap.error("需要 --card（或用 --selftest）")

    card_path = _resolve(args.card)
    try:
        card = json.loads(card_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[evidence_gate] 读取证据卡失败: {e}", file=sys.stderr)
        return 2

    findings = _schema_findings(card_path) + check_card(card)
    if args.article:
        article_path = _resolve(args.article)
        try:
            text = article_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[evidence_gate] 读取文章失败: {e}", file=sys.stderr)
            return 2
        findings += check_article(text, card)

    p0 = [f for f in findings if f[0] == "P0"]
    p1 = [f for f in findings if f[0] == "P1"]

    if args.json:
        print(json.dumps({
            "card": str(card_path).replace("\\", "/"),
            "article": args.article,
            "p0_count": len(p0),
            "p1_count": len(p1),
            "findings": [{"severity": s, "code": c, "where": w, "message": m}
                         for s, c, w, m in findings],
        }, ensure_ascii=False, indent=2))
    else:
        for s, c, w, m in findings:
            print(f"[{s}] {c} @ {w}: {m}")
        print(f"\n证据门禁：P0={len(p0)} P1={len(p1)}（模式={args.mode}）")

    if not args.no_report:
        rp = write_report(card_path, args.article, findings, args.mode)
        print(f"[evidence_gate] 报告已落盘: {rp.name}（warn 模式下 P0 不会静默丢失）")

    if p0 and args.mode == "block":
        print("[evidence_gate] ❌ 阻断：存在 P0 未核实 claim", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

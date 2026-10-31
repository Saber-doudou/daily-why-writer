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
import os
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
    # 10-31 收窄（审查报告 P1-4，经实测修正）：
    # 删掉裸「倍」。原写法 `倍` 无前置要求，导致「倍感亲切」「事半功倍」被判成事实句。
    # 「倍」现在必须前置中文数字（走下面的「三倍」分支）或阿拉伯数字（走 \d，如「3倍」）。
    # 注：报告称「度」也是裸字符会误杀「态度/角度/程度」——**实测不成立**，
    #     「度」早已要求前置中文数字，那些词本就不命中，故本次不改动「度」。
    r"\d|百分之|[一二三四五六七八九十百千万]+分之[一二三四五六七八九十]+"
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

    # ── 第五类检查：机制覆盖（10-29 新增，审校意见 2.4）──
    out += check_mechanism_coverage(text, card)
    return out


def check_mechanism_coverage(text, card):
    """机制覆盖：卡片声明的机制证据，正文必须至少用上一次（P1 warn，不阻断）。

    为什么需要这一类：
    既有四类检查管的是「卡片里不能有未核实的机制 claim」（卡片层），
    但「正文那套机制说法是不是照着卡片写的」（正文层）门禁完全不管，全靠 Reviewer。
    10-27 的 Q1 就是纯机制句、无数字、无映射，门禁 P0=0，
    靠 Reviewer 的 elements_complete=False 才抓出来 —— Reviewer 一漏，机制错误就能发。

    判据（刻意选 claim 级而不是 Q 段级）：
    卡片里每条 type=mechanism 的 claim，正文必须至少引用一次。
    - 10-27 实证：C1（伯努利/压强，正是 Q1 讲的机制）全文一次未引用，只引了 C2/C3 → 命中
    - S5 鸽子文实证：C1 在 Q2、Q3 各引用一次 → 干净，不误报
    段级语义匹配（关键词/句向量）评估后未采用：10-27 Q1 与 S5 Q1 的内容与各自
    mechanism claim 的重合度大致相当，无法把两者分开，只会引入噪声（见交付说明）。
    """
    out = []
    mech = [c for c in (card.get("claims") or []) if c.get("type") == "mechanism"]
    if not mech:
        return out

    used = set()
    for m in re.finditer(r"<!--\s*claim:\s*([A-Za-z0-9,\s]+?)\s*-->", text):
        used |= {x.strip() for x in m.group(1).split(",") if x.strip()}
    for cid, frag in resolve_mapping(card):
        if frag and frag in text:
            used.add(cid)

    for c in mech:
        cid = c.get("id")
        if cid in used:
            continue
        snippet = (c.get("text") or "").strip()[:40]
        out.append(("P1", "mechanism_uncovered", f"claim {cid}",
                    f"卡片声明了这条机制证据，正文一次都没引用"
                    f"（正文的机制说法无法回溯到证据，只能靠审校兜）: {snippet}"))
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

    # ── 10-29 新增：第五类检查「机制覆盖」的正反夹具 ──
    # 全部断言 expect_p1_codes（代码集合）而非条数：条数对上但规则没被触发，
    # 是 #68 已经栽过一次的坑（「因为别的原因误打正着凑够条数」也会 PASS）。
    # 三条互为反向：① 未引用须命中 ② 行内注释引用须干净 ③ mapping.fragments 引用须干净。
    "stress_mechanism_uncovered": {
        # 正例，复刻 10-27 的现场：卡片声明了机制 claim，正文通篇没引用。
        # 卡片侧刻意做到 P0/P1 全清（fetch + secondary + 引文够长），
        # 确保唯一命中的就是 mechanism_uncovered，不被别的规则污染。
        "card": {
            "schema_version": "v1", "topic": "测试",
            "claims": [{"id": "C1", "text": "压强差把两张纸推向中间", "type": "mechanism",
                        "source": {"title": "某来源", "url": "https://a.b",
                                   "source_level": "secondary"},
                        "quote": "这是一段不少于十五个字的引文占位用于长度校验",
                        "verified_by": "fetch", "confidence": "high"}],
            "banned_claims": [],
        },
        "article": "**Q1：纸怎么会往里贴？** → 中间空气被吹快，压强就降下来了。",
        "expect_p0": 0, "expect_codes": [],
        "expect_p1_codes": ["mechanism_uncovered"],
    },
    "stress_mechanism_covered_inline": {
        # 反例一：同一张卡，正文用行内注释引用了 C1 → 必须干净。
        # 复刻 S5 鸽子文的形态（C1 在正文中被引用）。
        "card": {
            "schema_version": "v1", "topic": "测试",
            "claims": [{"id": "C1", "text": "压强差把两张纸推向中间", "type": "mechanism",
                        "source": {"title": "某来源", "url": "https://a.b",
                                   "source_level": "secondary"},
                        "quote": "这是一段不少于十五个字的引文占位用于长度校验",
                        "verified_by": "fetch", "confidence": "high"}],
            "banned_claims": [],
        },
        "article": "**Q1：纸怎么会往里贴？** → 压强差把两张纸推向中间。<!-- claim:C1 -->",
        "expect_p0": 0, "expect_codes": [],
        "expect_p1_codes": [],
    },
    "stress_mechanism_covered_via_fragments": {
        # 反例二：走 mapping.fragments 文本命中路径（无行内注释）也必须算已引用，
        # 否则只认注释标记会对「用片段映射的老卡片」全量误报。
        "card": {
            "schema_version": "v1", "topic": "测试",
            "claims": [{"id": "C1", "text": "压强差把两张纸推向中间", "type": "mechanism",
                        "source": {"title": "某来源", "url": "https://a.b",
                                   "source_level": "secondary"},
                        "quote": "这是一段不少于十五个字的引文占位用于长度校验",
                        "verified_by": "fetch", "confidence": "high"}],
            "mapping": [{"claim_id": "C1", "text": "压强差把纸推向中间"}],
            "banned_claims": [],
        },
        "article": "**Q1：纸怎么会往里贴？** → 压强差把纸推向中间。",
        "expect_p0": 0, "expect_codes": [],
        "expect_p1_codes": [],
    },
    # ── 10-31 新增：FACT_PAT「倍」收窄的正反夹具（审查报告 P1-4，经实测修正）──
    # 互为反向，锁死「裸倍不再命中、真倍数仍命中」，防一修就松。
    "stress_bei_bare_word_not_fact": {
        # 正例（修复前会误杀）：裸「倍」——倍感亲切，不得被判为事实句。
        "card": {"schema_version": "v1", "topic": "测试", "claims": [], "banned_claims": []},
        "article": "他倍感亲切地打着招呼，态度也很认真，这个角度很刁钻。",
        "expect_p0": 0, "expect_codes": [],
    },
    "stress_bei_real_multiple_still_fact": {
        # 反例（防一修就松）：「三倍」是真倍数，仍必须被 unmapped_fact 抓到。
        "card": {"schema_version": "v1", "topic": "测试", "claims": [], "banned_claims": []},
        "article": "这个数量是去年的三倍。",
        "expect_p0": 1, "expect_codes": ["unmapped_fact"],
    },
    "stress_bei_arabic_multiple_still_fact": {
        # 反例二：阿拉伯数字+倍（3倍）走 \d 分支，也必须仍命中。
        "card": {"schema_version": "v1", "topic": "测试", "claims": [], "banned_claims": []},
        "article": "产量提高了 3 倍。",
        "expect_p0": 1, "expect_codes": ["unmapped_fact"],
    },
}


def _cli_exit_code(card, mode, relax=None, article=None):
    """用真实 CLI 跑一遍门禁，返回退出码。

    测的是 main() 的退出码分支（run_selftest 内部的 check_* 调用覆盖不到）。
    卡片/正文写入临时目录，自包含，不依赖任何当日产物或外部文件。
    article 非空时才传 --article（否则只查卡片，正文层判据不会触发）。
    """
    import subprocess
    import tempfile
    env = None
    if relax is not None:
        env = dict(os.environ, DAILY_WHY_GATE_RELAX=relax)
    with tempfile.TemporaryDirectory() as td:
        cp = Path(td) / "card.json"
        cp.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
        cmd = [sys.executable, str(Path(__file__).resolve()),
               "--card", str(cp), "--mode", mode, "--no-report"]
        if article is not None:
            ap = Path(td) / "article.md"
            ap.write_text(article, encoding="utf-8")
            cmd += ["--article", str(ap)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
        return r.returncode


def run_selftest():
    """夹具自测。

    10-27 强化：除 P0 数量外，可选断言 expect_codes（命中的代码集合）。
    只比数量有个盲区——「因为别的原因误打正着凑够条数」也会 PASS。
    例如某夹具期望 1 条 P0，实际因 short_quote 命中而不是预期的 tertary_only，
    数量对上了但被测的规则根本没被触发。

    10-31 强化：末尾追加 block 模式退出码夹具（审查报告 P1-2）。
    此前 run_selftest 从不调用 main()，切 block 后真正生效的退出码路径零覆盖。
    """
    ok = 0
    total = len(SELFTEST)
    for name, case in SELFTEST.items():
        findings = check_card(case["card"]) + check_article(case["article"], case["card"])
        p0 = [f for f in findings if f[0] == "P0"]
        codes = {f[1] for f in p0}
        good = len(p0) == case["expect_p0"]
        want = case.get("expect_codes")
        if want is not None:
            good = good and codes == set(want)
        # 10-29：P1 代码集合断言（第五类机制覆盖是 warn 级，只能靠 P1 断言防空转）。
        # 仅在夹具显式声明 expect_p1_codes 时校验，历史夹具不受影响。
        p1 = [f for f in findings if f[0] == "P1"]
        want_p1 = case.get("expect_p1_codes")
        if want_p1 is not None:
            good = good and {f[1] for f in p1} == set(want_p1)
        ok += good
        line = f"[{'PASS' if good else 'FAIL'}] {name}: P0={len(p0)} 期望={case['expect_p0']}"
        if want is not None:
            line += f"｜codes={sorted(codes)} 期望={sorted(want)}"
        if want_p1 is not None:
            line += f"｜P1={sorted({f[1] for f in p1})} 期望={sorted(want_p1)}"
        print(line)
        for f in p0:
            print(f"        {f[1]}: {f[3]}")
    # ── block 模式退出码夹具（10-31 补，审查报告 P1-2）──
    # run_selftest 只测 findings（check_card/check_article），**从不调用 main()**，
    # 因此 main() 里 `if p0 and mode == "block": return 1` 这条真正会阻断的路径
    # 此前零测试覆盖。切 block 后生效的正是退出码，必须用真实 CLI 断言。
    # 四条互为反向：阻断 / 放行 / warn 恒放行 / kill switch 降级。
    _block_cases = [
        # (标签, 夹具名, mode, relax, 期望退出码, 是否带正文)
        ("block+卡片层P0 → 阻断", "short_quote", "block", None, 1, False),
        ("block+无P0 → 放行", "good", "block", None, 0, False),
        ("warn+有P0 → 恒放行", "short_quote", "warn", None, 0, False),
        ("block+有P0+kill switch → 降级放行", "short_quote", "block", "1", 0, False),
        # 分级阻断（10-31）：unmapped_fact 属正文层 WARN_ONLY_P0_CODES，
        # 卡片合规时不得阻断——这是「先切高置信子集」的核心不变量。
        ("block+仅正文层P0 → 分级不阻断", "unmapped", "block", None, 0, True),
        # 反向：正文层 P0 在 kill switch 关闭 + 卡片层无 P0 时也不阻断，
        # 但 kill switch 打开时更不能阻断（幂等，防分级逻辑被开关绕过）。
        ("block+仅正文层P0+kill switch → 仍不阻断", "unmapped", "block", "1", 0, True),
    ]
    for _label, _case, _mode, _relax, _want, _use_art in _block_cases:
        _art = SELFTEST[_case]["article"] if _use_art else None
        _rc = _cli_exit_code(SELFTEST[_case]["card"], _mode, _relax, _art)
        _good = _rc == _want
        ok += _good
        total += 1
        print(f"[{'PASS' if _good else 'FAIL'}] 退出码 {_label}: 实际={_rc} 期望={_want}")

    print(f"\n自检 {ok}/{total} 通过")
    return 0 if ok == total else 1


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


# 10-31 分级阻断（审查报告决策 1「先切高置信子集」）：
# block 模式下，**正文层**判据降级为 warn 不阻断——它们依赖 FACT_PAT 与句末映射，
# 误杀面宽（4 天样本 P0=0 只说明样本没触发，不等于判据安全）；
# **卡片层**判据（url/引文长度/tertiary/未核实/schema/命中已证伪/悬空引用）
# 是确定性检查，误杀面窄，才真正阻断。
# 命名从「阻断什么」改为「不阻断什么」，新增 P0 code 默认阻断，避免漏放。
WARN_ONLY_P0_CODES = {"unmapped_fact", "unverified_mapping"}


def gate_relaxed():
    """kill switch：DAILY_WHY_GATE_RELAX=1 时把 block 降级为 warn（不阻断、退出码 0）。

    为什么必须是环境变量而不是改 --mode：
    现行 `--mode` 写在 automation prompt 里，改它要 改 prompt → --update-automation
    → 写库 → **次日才生效**。按 Fowler 的 toggle 分类，这等于「关掉它需要一次发布」
    = 开关失职。环境变量开关出事时当次即可降级，且可从**不依赖门禁服务**的本地读取。
    与项目既有 `DAILY_WHY_DEDUP_RELAX=1` 同型，零学习成本。
    """
    v = (os.environ.get("DAILY_WHY_GATE_RELAX") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def write_report(card_path, article, findings, mode, relaxed=False):
    """warn 模式下退出码恒为 0，P0 必须落盘，否则会静默丢失（模拟 S2 指出的硬伤）。

    relaxed=True 时把 block 降级记录进报告（EXP-014 可观测性：降级不能静默，
    否则「今天没阻断」会被误读成「今天没有 P0」）。
    """
    p0 = [f for f in findings if f[0] == "P0"]
    p1 = [f for f in findings if f[0] == "P1"]
    out = Path(card_path).with_suffix(".gate.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "relaxed": relaxed,
        "card": str(card_path).replace("\\", "/"),
        "article": str(article).replace("\\", "/") if article else None,
        "p0_count": len(p0),
        "p1_count": len(p1),
        "blocked": bool(p0) and mode == "block" and not relaxed,
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

    relaxed = gate_relaxed()
    # 分级阻断：只有「会阻断的 P0」参与判定，正文层两类（WARN_ONLY_P0_CODES）降为 warn
    blocking = [f for f in p0 if f[1] not in WARN_ONLY_P0_CODES]
    soft = [f for f in p0 if f[1] in WARN_ONLY_P0_CODES]
    if soft:
        print(f"[evidence_gate] ⚠️ {len(soft)} 条正文层 P0 按分级策略降级为 warn（不阻断）: "
              f"{sorted({f[1] for f in soft})}", file=sys.stderr)

    if not args.no_report:
        rp = write_report(card_path, args.article, findings, args.mode, relaxed)
        print(f"[evidence_gate] 报告已落盘: {rp.name}（warn 模式下 P0 不会静默丢失）")

    if blocking and args.mode == "block" and relaxed:
        # kill switch 生效：阻断被显式降级，必须留下痕迹，不能被读成「今天没有 P0」
        print(f"[evidence_gate] ⚠️ kill switch 生效（DAILY_WHY_GATE_RELAX）："
              f"会阻断的 P0={len(blocking)} 但降级为 warn，不阻断（请尽快修复后关闭开关）",
              file=sys.stderr)
        return 0
    if blocking and args.mode == "block":
        print(f"[evidence_gate] ❌ 阻断：{len(blocking)} 条高置信 P0"
              f"（{', '.join(sorted({f[1] for f in blocking}))}）"
              "（如需紧急放行：设置 DAILY_WHY_GATE_RELAX=1 降级为 warn）", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

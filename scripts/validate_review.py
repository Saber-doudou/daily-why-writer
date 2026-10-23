#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""review.json schema 机械校验器 —— 补上「强制输出物」缺失的执行校验（v1.2, 2026-10-23）

背景（常驻缺陷 40 / SOP Step 8.5「09-04 头号结论」）：
    reviewer_prompt v2.6 把 Step 5/5.5/5.6/5.7 的「自查法」软指令改成了强制输出物
    （fact_checks.detail_verified / quote_checks.verbatim_match /
     mechanism_checks.direction_ok+elements_complete / attribution_checks.is_primary_cause），
    但 **脚本侧零校验** —— 09-07 实证：v1 review.json 的 quote_checks 是空数组照样通过。
    「填了字段 ≠ 填对内容」，而「没填字段」至今无人发现。

    橙皮书 EXP-004「约束优于指令」：prompt 写得再准，Reviewer 不执行也无人知晓。
    本脚本把「是否执行」变成可机械判定的事实。

v1.2 2026-10-23  新增第 9 项校验「标题主体口径核对」（缺陷 #66，Master 人工终审抓出的 P0）：
     ① `title_checks` 键必须存在（10-23 起强制，历史 review 仅警告），每条必填
     subject_scoped/unit_matches_source/scope_consistent_with_body/verdict 四字段；
     ② 条件非空——文章 H1 或结尾表格「话题」字段含消亡类断言（灭绝/绝迹/消失/消亡/
     绝了后/灭亡/绝种）时，`title_checks` 至少 1 条，空数组即 FAIL；
     ③ verdict 枚举 pass/fail。根因：10-23 介形虫稿件标题「为什么有的生物……反而
     灭绝了？」被读成类群灭绝（正文「现生约1.3万种」），v1/v2/四家AI/三轮审校全链
     漏判——6 维度审校核「数字与来源」，无一项核「标题主体与正文事实范围」。
     配套：reviewer_prompt v3.0 Step 5.11 + validate_article.py 标题 tripwire。
     标题来源：优先 --article 文章正文（H1 + 话题行），缺失时退回 review json 的
     title_checks[].title；两者皆无 → fail-open 仅警告不阻断。

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

VERSION = "v1.2"

# v1.2（10-23）新增：标题主体口径核对（title_checks）强制起始日
TITLE_CHECK_ENFORCE_SINCE = "2026-10-23"

# 消亡类断言关键词（命中即要求 title_checks 非空）——与 validate_article.py tripwire 同口径
TITLE_EXT_KWS = ("灭绝", "绝迹", "消失", "绝了后", "消亡", "灭亡", "绝种")

# title_checks 每条必填字段（reviewer_prompt v3.0 Step 5.11 强制留痕）
TITLE_CHECK_FIELDS = ("subject_scoped", "unit_matches_source",
                      "scope_consistent_with_body", "verdict")

# title_checks.verdict 合法枚举
TITLE_VERDICT_ENUM = ("pass", "fail")

# v2.8（09-07 A 方案）新增：历史差距对照清单
GAP_PATTERNS_FILE = Path(
    r"C:\Users\admin\.workbuddy\skills\daily-why-writer\references\GAP_PATTERNS.md")
# 该清单自 2026-09-08 起强制；更早的 review.json 缺 gap_checks 属历史遗留，仅警告
GAP_ENFORCE_SINCE = "2026-09-08"

# v1.1（09-18）新增：二轮 issue 闭环回应（issue_responses）强制起始日
ISSUE_RESPONSE_ENFORCE_SINCE = "2026-09-18"

# issue_responses.status 合法枚举（wontfix 归 unresolved + evidence 说明）
ISSUE_STATUS_ENUM = ("resolved", "partial", "unresolved")

# v2.6 起要求的强制留痕数组：键 -> (必填字段列表, 强制起始日)
# 起始日之前的 review 缺失该键仅警告（历史文件不回改、不误杀）：
# fact/mechanism/attribution/quote 自 v2.6（09-04）起、term_checks 自 v2.7（09-05）起、
# title_checks 自 v1.2（10-23，缺陷 #66）起强制。
REQUIRED_ARRAYS = {
    "fact_checks": (["detail_verified"], "2026-09-04"),
    "mechanism_checks": (["direction_ok", "elements_complete"], "2026-09-04"),
    "attribution_checks": (["is_primary_cause"], "2026-09-04"),
    "quote_checks": (["verbatim_match"], "2026-09-04"),
    "term_checks": ([], "2026-09-05"),
    "title_checks": (list(TITLE_CHECK_FIELDS), "2026-10-23"),
}

# 顶层必需字段（两种 schema 至少命中其一：v1 用 p0_count，v2 两者都有）
REQUIRED_TOP_ANY = {
    "p0_count": ("p0",),
    "p1_count": ("p1",),
    "p2_count": ("p2",),
}

# 命中这些特征说明文中含「具体研究引用」，按 reviewer_prompt 自检清单第 5 项
# 要求 quote_checks ≥ 1 条。
# 09-09 改造：收窄为精确信号，避免泛词（研究显示/实验表明/大学/期刊/论文）误杀正常科普文。
#   可靠信号：① 书名号包裹且含年份的文献；② 明确期刊名（《自然》《Science》等）；
#            ③ 年份+机构+研究动词；④ et al. / DOI 等文献标识。
CITATION_HINT = re.compile(
    r"(?:"
    r"《[^》]{2,}》.*?(?:19|20)\d{2}"                                  # 《XX》+年份（引用文献通常带年份）
    r"|《(?:自然|科学|细胞|物理|化学|Nature|Science|Cell)[^》]*》"        # 明确期刊名
    r"|(?:19|20)\d{2}\s*年[^。，]{0,20}?(?:大学|研究院|学院|团队|实验室|机构)"
      r"[^。，]{0,10}?(?:研究|发表|发现|实验|报告)"                       # 年份+机构+研究动词
    r"|\bet al\.|DOI:|doi:"                                            # 文献标识
    r")",
    re.I,
)


def _has_quote_verification(data: dict) -> bool:
    """文中含具体引用时，是否已存在逐字核验留痕。

    留痕可能位于 quote_checks（理想位置）或 fact_checks（Reviewer 实际常把引用核验
    放入 fact_checks，含 DOI/期刊/作者年份逐项 match）。两者任一存在即视为已核验，
    避免门禁误杀真实已做核验的文章（EXP-004：约束要对准真问题，而非字段僵化）。
    """
    qc = data.get("quote_checks")
    if isinstance(qc, list) and len(qc) > 0:
        return True
    fc = data.get("fact_checks")
    if isinstance(fc, list):
        for item in fc:
            if not isinstance(item, dict):
                continue
            src = item.get("source", "") or ""
            # 只查 source（引用留痕指向原始论文/期刊），不查 claim（claim 提到期刊名只是断言内容）
            if re.search(
                r"doi\.org|arxiv|10\.\d{4,9}/|《[^》]{2,}》|"
                r"(?:nature|science|cell)\b|(?:\.edu|\.ac\.|\.gov)",
                src, re.I,
            ):
                return True
    return False


def validate(path: Path, article_path: Path | None = None) -> dict:
    """返回 {ok, errors, warnings, stats, blocking}"""
    errors, warnings = [], []
    blocking = []   # 会触发 L3 发布中断的错误（引用门禁）
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

    # 3. 强制留痕数组：键必须存在（各数组有强制起始日，之前缺失仅警告，历史不回改）
    m_arr = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    date_in_name = m_arr.group(1) if m_arr else ""
    for arr, (fields, since) in REQUIRED_ARRAYS.items():
        if arr not in data:
            msg = f"缺少强制输出物 `{arr}`（键名不得省略）"
            if date_in_name and date_in_name >= since:
                errors.append(msg)
            else:
                warnings.append(f"{msg}（{arr} 强制起始日 {since}，本文件日期 {date_in_name or '未知'} 之前，仅警告）")
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
    #    09-09 改造：优先用「文章正文」检测引用（article_path），避免只查 review json 漏检正文引用；
    #    article_path 缺失时 fail-open 退回 review blob（不误杀，但可能漏检——仅 warn 不阻断）。
    _search_text = ""
    if article_path and Path(article_path).exists():
        try:
            _search_text = Path(article_path).read_text(encoding="utf-8")
        except OSError:
            _search_text = ""
    if not _search_text:
        _search_text = json.dumps(data, ensure_ascii=False)
    has_citation = bool(CITATION_HINT.search(_search_text))
    if has_citation and not _has_quote_verification(data):
        _msg = (
            "引用门禁未过：文中含具体研究引用（期刊/年份/机构），但 `quote_checks` 与 `fact_checks` "
            "均未发现逐字引用核验留痕 —— 按 reviewer_prompt 自检清单第 5 项必须 ≥1 条逐字引用核验；"
            "请回到 Reviewer 补 `quote_checks`（或确保 fact_checks 含 DOI/期刊/作者年份的逐项核验）后重试"
            "（机械门禁，EXP-004 约束优于指令）"
        )
        errors.append(_msg)
        blocking.append(_msg)

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

    # 8. 二轮 issue 闭环回应（v1.1，缺陷 P2-a：二轮审校未回应一轮 issues）
    #    触发条件：文件名为 {date}_v2_review.json 且同日 {date}_review.json 存在
    m_v2 = re.search(r"(\d{4}-\d{2}-\d{2})_v2_review\.json$", path.name)
    if m_v2:
        date_str = m_v2.group(1)
        enforce_ir = date_str >= ISSUE_RESPONSE_ENFORCE_SINCE
        v1_path = path.with_name(f"{date_str}_review.json")
        if not v1_path.exists():
            # fail-open：一轮审校缺失（如熔断降级），二轮无回应对象，不阻断
            warnings.append(
                f"同日一轮审校 `{v1_path.name}` 不存在，跳过 issue_responses 校验（fail-open）")
        else:
            try:
                v1_data = json.loads(v1_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                v1_data = None
                warnings.append(
                    f"一轮审校 `{v1_path.name}` 解析失败（{e}），跳过 issue_responses 校验")
            v1_issues = v1_data.get("issues") if isinstance(v1_data, dict) else None
            if not isinstance(v1_issues, list) or not v1_issues:
                warnings.append(
                    "一轮审校无 issues 数组（可能 P0/P1 全无），跳过 issue_responses 覆盖校验")
            else:
                ir = data.get("issue_responses")
                if ir is None:
                    msg = (f"缺少 `issue_responses`（二轮审校必须逐条回应一轮 issues 共 "
                           f"{len(v1_issues)} 条，见 reviewer_prompt Step 5.10）")
                    (errors if enforce_ir else warnings).append(msg)
                elif not isinstance(ir, list):
                    errors.append("`issue_responses` 应为数组")
                else:
                    stats["issue_responses"] = len(ir)
                    covered = set()
                    for i, item in enumerate(ir):
                        if not isinstance(item, dict):
                            errors.append(f"`issue_responses[{i}]` 应为对象")
                            continue
                        idx = item.get("issue_index")
                        st = item.get("status")
                        ev = item.get("evidence")
                        if not isinstance(idx, int) or isinstance(idx, bool):
                            errors.append(
                                f"`issue_responses[{i}]` 缺少合法 `issue_index`（整数下标）")
                        elif idx < 0 or idx >= len(v1_issues):
                            errors.append(
                                f"`issue_responses[{i}]` 的 `issue_index={idx}` 越界"
                                f"（一轮 issues 共 {len(v1_issues)} 条，下标 0 至 {len(v1_issues) - 1}）")
                        else:
                            covered.add(idx)
                        if st not in ISSUE_STATUS_ENUM:
                            errors.append(
                                f"`issue_responses[{i}]` 的 `status` 非法（{st!r}），"
                                f"须为 {'/'.join(ISSUE_STATUS_ENUM)}")
                        if not (isinstance(ev, str) and ev.strip()):
                            errors.append(
                                f"`issue_responses[{i}]` 缺少 `evidence`"
                                "（闭环证据：v2 文章位置或未处理理由）")
                    missed = sorted(set(range(len(v1_issues))) - covered)
                    if missed:
                        msg = (f"`issue_responses` 未覆盖一轮 issues 下标 {missed}"
                               f"（共 {len(v1_issues)} 条，必须逐条回应，一条不能少）")
                        (errors if enforce_ir else warnings).append(msg)

    # 9. 标题主体口径核对（v1.2，缺陷 #66）
    #    键存在性已由 REQUIRED_ARRAYS 覆盖；此处补两项：
    #    ① 条件非空——标题含消亡类断言时 title_checks 至少 1 条（空数组=没核对=FAIL）
    #    ② verdict 枚举 pass/fail + 与顶层计数的矛盾提示
    m_tc = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    enforce_tc = bool(m_tc and m_tc.group(1) >= TITLE_CHECK_ENFORCE_SINCE)
    title_blob, title_src = _extract_title_blob(article_path, data)
    has_ext_claim = bool(title_blob) and any(k in title_blob for k in TITLE_EXT_KWS)
    tc = data.get("title_checks")
    if isinstance(tc, list):
        stats["title_checks"] = len(tc)
        for i, item in enumerate(tc):
            if not isinstance(item, dict):
                continue
            v = item.get("verdict")
            if v not in TITLE_VERDICT_ENUM:
                errors.append(
                    f"`title_checks[{i}]` 的 `verdict` 非法（{v!r}），"
                    f"须为 {'/'.join(TITLE_VERDICT_ENUM)}")
        if has_ext_claim and not tc:
            msg = (
                f"标题含消亡类断言（{title_src}：{title_blob[:60]}…）但 `title_checks` 为空数组 "
                "—— 按 reviewer_prompt v3.0 Step 5.11 必须逐项核对主体圈定/单位与信源一致/"
                "断言强度≤正文可支撑范围并留痕（机械门禁，EXP-004 约束优于指令）"
            )
            (errors if enforce_tc else warnings).append(msg)
            if enforce_tc:
                blocking.append(msg)
        if tc and any(
            isinstance(it, dict) and it.get("verdict") == "fail" for it in tc
        ) and data.get("p0_count", 0) == 0 and data.get("p1_count", 0) == 0:
            warnings.append(
                "`title_checks` 存在 verdict=fail 的条目，但顶层 p0_count/p1_count 均为 0 "
                "—— 标题主体口径问题应计入 issues（方向一 P0 / 方向二 P1），请核对计数一致性"
            )
    elif has_ext_claim:
        msg = (f"标题含消亡类断言（{title_src}）但 `title_checks` 缺失或非数组 "
               "—— 按 reviewer_prompt v3.0 Step 5.11 必须留痕")
        (errors if enforce_tc else warnings).append(msg)

    ok = not errors and not warnings
    return {"ok": ok, "errors": errors, "warnings": warnings, "stats": stats, "blocking": blocking}


def _extract_title_blob(article_path: Path | None, data: dict) -> tuple[str, str]:
    """提取标题文本用于消亡类断言检测。

    来源优先级：① --article 文章正文的 H1（首个 # 开头的行）+ 结尾表格「话题」行；
    ② review json 的 title_checks[].title。两者皆无返回 ("", "无")。
    只取标题与话题字段，不扫正文——正文讲灭绝研究必然含「灭绝」二字，会误杀。
    """
    blob_parts = []
    if article_path and Path(article_path).exists():
        try:
            for line in Path(article_path).read_text(encoding="utf-8").split("\n"):
                s = line.strip()
                if s.startswith("#") and not blob_parts:
                    blob_parts.append(s.lstrip("#").strip())
                elif s.startswith("|") and "话题" in s:
                    blob_parts.append(s)
        except OSError:
            pass
        if blob_parts:
            return " ".join(blob_parts), "文章标题/话题字段"
    tc = data.get("title_checks")
    if isinstance(tc, list):
        titles = [it.get("title", "") for it in tc
                  if isinstance(it, dict) and it.get("title")]
        if titles:
            return " ".join(titles), "review title_checks[].title"
    return "", "无"


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
    p.add_argument("--article", help="文章正文路径（引用门禁检测源，优先于 review blob）")
    args = p.parse_args()

    path = Path(args.review_json)
    if not path.exists():
        print(f"❌ 文件不存在: {path}", file=sys.stderr)
        return 2

    r = validate(path, article_path=Path(args.article) if args.article else None)

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

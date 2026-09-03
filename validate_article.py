#!/usr/bin/env python3
"""
validate_article.py — P0/P1/P2 内容质量审核 + A+C+F 结构 + 排版格式验证
规则来源：writing_rules.json（唯一来源，与 daily-why-writer skill 同源）

用法：
    python validate_article.py 2026-05-09-每日冷知识.md
    python validate_article.py --strict 2026-05-09-每日冷知识.md
    python validate_article.py --json article.md
    python validate_article.py --latest
    python validate_article.py --verbose article.md   # 输出详细修复建议
"""

import re
import sys
import json
import argparse
import subprocess

# Windows GBK 终端兼容：强制 stdout 使用 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# 导入格式检查模块
from format_checker import (
    check_all_formats,
    count_chinese_chars,
    strip_markdown,
)

# ── 从 writing_rules.json 加载规则（唯一来源） ──
RULES_PATH = Path(__file__).parent.parent / "config" / "writing_rules.json"
RULES = {}
if RULES_PATH.exists():
    try:
        RULES = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass  # 降级为硬编码默认值


def _r(path: str, default=None):
    """安全地从 RULES 取嵌套值"""
    keys = path.split(".")
    val = RULES
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    return val if val is not None else default


# ── P0/P1 通过阈值（读规则文件，支持退出码） ──
P0_MUST_BE_ZERO = _r("quality.p0_must_be_zero", True)
P1_MAX_ALLOWED = _r("quality.p1_max_allowed", 2)
EXIT_ON_FAIL = _r("exit_on_fail", True)

# 字数（fallback 为 writing_rules.json 缺失时的兜底值；09-02 由 600 对齐至 690，
# 与 rules 的全文口径一致。正常路径始终读 rules，改此值不影响正常行为）
WC_MIN = _r("word_count.min", 300)
WC_MAX = _r("word_count.max", 690)
WC_P1_THRESHOLD = _r("word_count.p1_threshold", 690)

# 结构
QUESTIONS_P0_THRESHOLD = _r("structure.questions_p0_threshold", 2)

# 格式
SEPARATOR_EXACT = _r("formatting.separator_exact", 2)
SEPARATOR_MAX = _r("formatting.separator_max", 2)
QUOTE_MIN = _r("formatting.quote_blocks_min", 2)
BOLD_MIN = _r("formatting.bold_min", 2)
Q_FORMAT = _r("formatting.q_format", "**Q1：xxx？**")
TWIST_LABEL = _r("formatting.twist_label", "冷知识反转")

# 质量检测
CLICHE_OPENERS = _r("quality.cliche_openers", [
    "今天我们来", "今天我们要", "你知道吗？", "我们都知道",
    "随着", "在当今", "在如今", "在现在"
])
ANECDOTE_CHARS = _r("quality.anecdote_check_chars", 80)
CONNECTOR_KWS = _r("quality.connector_keywords",
                    ["首先", "其次", "然后", "最后", "此外", "另外"])
CONNECTOR_P1_THRESHOLD = _r("quality.connector_p1_threshold", 3)
PARA_MIN_LEN = _r("quality.paragraph_min_len", 50)
PARA_DEV_MAX = _r("quality.paragraph_deviation_max", 20)
TWIST_KWS = _r("quality.twist_keywords", [
    "反转", "恰恰", "其实", "没想到", "出乎意料", "真相是",
    "你以为", "别以为", "反直觉", "竟然", "居然", "万万没想到"
])
TWIST_HEADING_KWS = _r("quality.twist_heading_keywords",
                        ["反转", "彩蛋", "冷知识", "没想到", "趣味"])
QUESTION_PATTERNS = _r("quality.question_patterns", [
    r"Q\d+[：:]",
    r"\*\*\d+\.\s*.+\？",
    r"\*\*Q\d+",
    r"^\d+\.\s*.+\？",
    r"^###?\s*.*\？",
])

# 场景检测关键词
ANECDOTE_KWS = ["发现", "看到", "想象", "一天", "早晨", "深夜", "海底", "太空",
                "突然", "有一次", "你知道", "当你", "如果", "其实", "你以为"]


@dataclass
class ValidationResult:
    """验证结果"""
    file: str
    passed: bool = True
    score: int = 100
    p0: list = field(default_factory=list)
    p1: list = field(default_factory=list)
    p2: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    info: dict = field(default_factory=dict)
    fix_suggestions: list = field(default_factory=list)  # 可执行的修复建议
    related_cases: list = field(default_factory=list)    # 匹配的判例

    def error(self, msg: str, points: int = 10):
        self.errors.append(msg)
        self.score -= points
        self.passed = False

    def warn(self, msg: str, points: int = 3):
        self.warnings.append(msg)
        self.score -= points

    def ok(self, msg: str):
        self.info["checks_passed"] = self.info.get("checks_passed", 0) + 1

    def p0_error(self, msg: str):
        self.p0.append(msg)
        self.error(f"[P0] {msg}", 15)

    def p1_error(self, msg: str):
        self.p1.append(msg)
        self.warn(f"[P1] {msg}", 5)

    def p2_error(self, msg: str):
        self.p2.append(msg)
        self.warn(f"[P2] {msg}", 2)

    def add_fix(self, level: str, issue: str, suggestion: str, location: str = ""):
        """添加可执行的修复建议"""
        self.fix_suggestions.append({
            "level": level,
            "issue": issue,
            "suggestion": suggestion,
            "location": location,
        })

    def has_passed_p0p1(self) -> bool:
        return len(self.p0) == 0 and len(self.p1) <= P1_MAX_ALLOWED

    @property
    def p0p1_passed(self) -> bool:
        return self.has_passed_p0p1()


def validate_content_quality(content: str, result: ValidationResult):
    """P0/P1/P2 内容质量审核"""
    plain = strip_markdown(content)

    # ── 格式检查（调用 format_checker 模块） ──
    check_all_formats(content, result)

    # ── P0：事实 / 逻辑 / 结构 ──

    # P0: 缺少故事化开头（A段）
    sections = re.split(r"---\s*\n", content)
    has_anecdote = False
    for sec in sections[:3]:
        sec_clean = sec.strip()
        if not sec_clean:
            continue
        if ">" in sec_clean or any(kw in sec_clean for kw in ANECDOTE_KWS):
            has_anecdote = True
            break
    if not has_anecdote:
        result.p0_error("缺少故事化开头（A段）—— 应以场景或小故事切入")
        result.add_fix("P0", "缺少故事化开头（A段）",
            '在标题下方插入引用块场景段落，如：\n'
            '> 晚上十点，你窝在沙发里刷手机。不知不觉一小时过去了...',
            '第5行（标题后的空行位置）')

    # P0: 缺少疑问驱动结构（C段）
    q_count = 0
    for pat in QUESTION_PATTERNS:
        matches = re.findall(pat, content, re.MULTILINE)
        q_count = max(q_count, len(matches))
    if q_count < QUESTIONS_P0_THRESHOLD:
        result.p0_error(
            f"缺少疑问驱动结构（C段）—— 仅发现 {q_count} 个问题标记，"
            f"需要 {QUESTIONS_P0_THRESHOLD}+ 个递进式问题")
        result.add_fix("P0", "缺少疑问驱动结构（C段）",
            f'当前仅 {q_count} 个问题，需至少 {QUESTIONS_P0_THRESHOLD} 个。'
            f'使用格式：**Q1：xxx？** / **Q2：xxx？** / **Q3：xxx？**',
            '分隔线---之后为C段区域')
    else:
        result.ok(f"C段（疑问驱动）✓ — 发现 {q_count} 个问题")

    # P0: 缺少反转结尾（F段）
    last_third = content[len(content) // 3 * 2:]
    has_twist = any(kw in last_third for kw in TWIST_KWS)
    twist_headings = re.findall(
        f"({'|'.join(TWIST_HEADING_KWS)}).*", content)
    if twist_headings:
        has_twist = True
    if not has_twist:
        result.p0_error("缺少反转结尾（F段）—— 结尾应有意外反转或彩蛋")
        result.add_fix("P0", "缺少反转结尾（F段）",
            '在第二个分隔线---之后添加引用块反转，格式：\n'
            '> 🤝 **冷知识反转**：反转内容...\n'
            '并在末尾附风格表格（| 话题 | ... | 分类 | ... | 核心机制 | ... | 冷知识反转 | ... |）',
            '文章末尾区域')
    else:
        result.ok("F段（趣味反转）✓")

    # ── P1：AI 味 / 格式 ──

    # P1: 套话开头检测
    opening = plain[:ANECDOTE_CHARS]
    for c in CLICHE_OPENERS:
        if c in opening:
            result.p1_error(f"开头有套话嫌疑：「{c}」—— 建议直接切入场景")
            break

    # P1: AI 味排比检测（连续 3 行以数字/序号开头）
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    numbered_streak = 0
    for line in lines:
        if re.match(r"^\d+[.、]", line):
            numbered_streak += 1
        else:
            numbered_streak = 0
        if numbered_streak >= 3:
            result.p1_error("连续的序号式铺排（1.2.3.列表），AI 味较重，建议用叙述串联")
            break

    # P1: "首先/其次/最后/此外" 堆砌
    connector_count = sum(1 for kw in CONNECTOR_KWS if kw in plain)
    if connector_count >= CONNECTOR_P1_THRESHOLD:
        result.p1_error(
            f"连接词堆砌（{connector_count} 处「首先/其次/此外」），"
            f"建议减少过渡词依赖")

    # P1: 段落过于整齐（每段字数几乎相同）
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()
                  and not p.strip().startswith("|")
                  and not p.strip().startswith("---")]
    para_lens = [len(p) for p in paragraphs if len(p) > PARA_MIN_LEN]
    if len(para_lens) >= 3:
        avg = sum(para_lens) / len(para_lens)
        max_dev = max(abs(l - avg) for l in para_lens)
        if max_dev < PARA_DEV_MAX:
            result.p2_error(
                f"段落长度过于均匀（偏差 < {int(max_dev)} 字），"
                f"AI 排版的典型特征")

    # ── P1：表达润色检测（来自 proofreading skill 借鉴） ──

    # P1: 隐蔽冗余检测
    redundancy_patterns = [
        # "在...中发现/表明/显示" → 冗余介词
        (r"在[^。，]{2,20}中(?:发现|表明|显示|指出|认为)", "冗余介词「在...中」，可直接说「XX发现/表明」"),
        # "所+动词+的" 中 "所" 多余（覆盖高频动词）
        (r"所(?:培养|建立|产生|形成|带来|具有|提供|使用|采用|导致|引起|造成|积累|影响|决定|涉及|包含|经历|获得)的",
         "冗余助词「所」，可删去使表达更简洁"),
        # "通过...使/让" 双重介词
        (r"通过[^。，]{2,30}(?:使|让)", "冗余介词「通过...使」结构，删掉「通过」或「使」之一"),
        # "有效" + 能愿动词重复
        (r"能[^。，]{1,15}有效", "「能」和「有效」语义重叠，删掉「有效」"),
        # "进行" 万能动词
        (r"进行(?:了?\s*)(?:研究|分析|检查|测试|实验|观察|调查)", "万能动词「进行」，可直接用动词本身（如「研究了」）"),
    ]
    for pattern, desc in redundancy_patterns:
        matches = re.findall(pattern, plain)
        if matches:
            sample = matches[0][:20] + "..." if len(matches[0]) > 20 else matches[0]
            result.p1_error(f"隐蔽冗余：「{sample}」— {desc}")
            break  # 只报第一个，避免刷屏

    # P1: 近距离重复检测（同段同词 / 连续举例标记）
    # 先按段落拆分（排除表格行和分隔线）
    article_paragraphs = [p.strip() for p in re.split(r"\n{2,}", content)
                          if p.strip()
                          and not p.strip().startswith("|")
                          and not p.strip().startswith("---")
                          and not p.strip().startswith("#")]

    repetition_found = False
    for para in article_paragraphs:
        if repetition_found:
            break
        # 去掉 markdown 格式后统计
        para_plain = strip_markdown(para)
        if len(para_plain) < 30:
            continue

        # 1) 同段内同一实词（≥2字）出现 ≥3 次（高频虚词排除）
        words = re.findall(r"[\u4e00-\u9fff]{2,4}", para_plain)
        word_freq = {}
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1
        STOPWORDS = {"我们", "他们", "一个", "这个", "那个", "可以", "已经",
                     "不是", "没有", "就是", "如果", "但是", "因为", "所以",
                     "虽然", "这些", "那些", "什么", "怎么", "为什么", "时候",
                     "其实", "可能", "需要", "通过", "而且", "或者", "以及",
                     "不过", "而是", "然后", "之后", "之前", "出来", "起来",
                     "一些", "一定", "不会", "不能", "也会", "还是", "只是",
                     "对于", "其中", "这样", "那样", "比较", "非常", "应该",
                     "一种", "这种", "那种", "人体", "身体"}
        for w, cnt in sorted(word_freq.items(), key=lambda x: -x[1]):
            if cnt >= 3 and w not in STOPWORDS:
                result.p1_error(
                    f"近距离重复：「{w}」在同一段落中出现 {cnt} 次，"
                    f"考虑用近义词替换或合并表述")
                repetition_found = True
                break

    # 2) 连续"例如"检测
    example_marks = list(re.finditer(r"(?:例如|比如|譬如)", plain))
    for i in range(len(example_marks) - 1):
        gap = example_marks[i + 1].start() - example_marks[i].end()
        if gap < 50:  # 两个举例标记间距 < 50 字
            result.p1_error(
                f"连续举例标记：「{example_marks[i].group()}」和"
                f"「{example_marks[i+1].group()}」间距过近，"
                f"第二个可改为「又如」「再如」或删除")
            break


def validate_file(filepath: Path, strict: bool = False) -> ValidationResult:
    """验证单篇文章"""
    result = ValidationResult(file=filepath.name)

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        result.error(f"文件不存在: {filepath}", 50)
        return result
    except Exception as e:
        result.error(f"读取文件失败: {e}", 50)
        return result

    if not content.strip():
        result.error("文件内容为空", 50)
        return result

    validate_content_quality(content, result)

    result.score = max(0, result.score)
    result.info["max_score"] = 100
    result.info["final_score"] = result.score

    p0p1_ok = result.has_passed_p0p1()
    if strict and not p0p1_ok:
        result.passed = False

    result.info["p0_count"] = len(result.p0)
    result.info["p1_count"] = len(result.p1)
    result.info["p2_count"] = len(result.p2)
    result.info["p0p1_passed"] = p0p1_ok

    return result


def print_report(result: ValidationResult, use_json: bool = False, verbose: bool = False):
    """打印验证报告（P0/P1/P2 新版）
    verbose=True 时输出详细修复建议 + 自动匹配判例
    """
    if use_json:
        output = asdict(result)
        # 精简 JSON 输出：移除 info 中的内部字段
        output["related_cases"] = result.related_cases
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    print(f"\n{'='*60}")
    print(f"📋 审核报告: {result.file}")
    print(f"{'='*60}")

    p0p1_ok = result.has_passed_p0p1()
    overall_pass = result.passed and p0p1_ok
    status_icon = "✅ PASS" if overall_pass else "❌ FAIL"
    print(f"状态: {status_icon}")
    print(f"P0(致命)={len(result.p0)}  P1(重要)={len(result.p1)}  P2(一般)={len(result.p2)}")
    print(f"通过条件: P0=0 ? {'✅' if len(result.p0)==0 else '❌'}  |  "
          f"P1≤{P1_MAX_ALLOWED} ? {'✅' if len(result.p1)<=P1_MAX_ALLOWED else '❌'}")
    print()

    if result.info:
        print("--- 基本信息 ---")
        for k, v in result.info.items():
            if k not in ("max_score",):
                print(f"  {k}: {v}")
        print()

    if result.errors:
        print("--- ⚠️ 错误 ---")
        for e in result.errors:
            print(f"  ✗ {e}")
        print()

    if result.warnings:
        print("--- ⚡ 警告 ---")
        for w in result.warnings:
            print(f"  ! {w}")
        print()

    if result.p0:
        print("--- 🔴 P0 致命问题（必须清零） ---")
        for p in result.p0:
            print(f"  ✗ {p}")
        print()

    if result.p1:
        print("--- 🟡 P1 重要问题（≤2 可放行） ---")
        for p in result.p1:
            print(f"  ! {p}")
        print()

    if result.p2:
        print("--- 🔵 P2 一般问题（不设限） ---")
        for p in result.p2:
            print(f"  · {p}")
        print()

    # ── verbose: 输出详细修复建议 ──
    if verbose and result.fix_suggestions:
        print("--- 🛠️ 修复建议 ---")
        for i, fix in enumerate(result.fix_suggestions, 1):
            print(f"  [{fix['level']}] {fix['issue']}")
            if fix.get("location"):
                print(f"    位置: {fix['location']}")
            print(f"    建议: {fix['suggestion']}")
            print()

    # ── 自动匹配判例（有P0/P1问题时） ──
    if result.p0 or result.p1:
        cases = _fetch_related_cases(result)
        if cases:
            result.related_cases = cases
            print("--- 📚 相关判例 ---")
            for case in cases:
                print(f"  {case.get('id', '?')}: {case.get('problem_type', '?')} ({case.get('date', '?')})")
                if case.get('solution'):
                    for line in case['solution'].split('\n')[:2]:
                        line = line.strip()
                        if line:
                            print(f"    {line}")
            print()

    print(f"{'='*60}\n")


def _fetch_related_cases(result: ValidationResult) -> list:
    """自动调用 case_matcher.py 匹配相关判例"""
    try:
        # 从 P0/P1 问题中提取关键词
        all_issues = " ".join(result.p0 + result.p1)
        # 简化关键词：取前50个字符
        query = all_issues[:50]
        case_matcher = Path(__file__).parent / "case_matcher.py"
        if not case_matcher.exists():
            return []
        proc = subprocess.run(
            [sys.executable, str(case_matcher), query, "--json", "--top", "3"],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
            cwd=str(Path(__file__).parent),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception:
        pass  # 静默失败，不阻塞主流程
    return []


def main():
    parser = argparse.ArgumentParser(
        description="P0/P1/P2 内容质量审核（规则源: writing_rules.json）")
    parser.add_argument("files", nargs="*", help="要审核的 md 文件路径")
    parser.add_argument("--workspace", default=r"F:\WorkBuddy\daily-why",
                        help="工作目录")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--latest", action="store_true",
                        help="审核工作目录中最新的文章")
    parser.add_argument("--verbose", action="store_true",
                        help="输出详细修复建议和关联判例")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    files_to_check = []

    if args.files:
        for f in args.files:
            files_to_check.append(Path(f))
    elif args.latest:
        md_files = sorted(workspace.glob("articles/**/*-每日冷知识*.md"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        if md_files:
            files_to_check.append(md_files[0])
        else:
            print("[validate_article] 未找到任何文章文件")
            return
    else:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        # 支持新旧两种文件名格式：{日期}-每日冷知识.md / {日期}-每日冷知识-{关键词}.md
        today_files = sorted(
            [f for f in workspace.glob(f"articles/**/{today}-每日冷知识*.md")],
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        if today_files:
            files_to_check.append(today_files[0])
        else:
            md_files = sorted(workspace.glob("articles/**/*-每日冷知识*.md"),
                              key=lambda p: p.stat().st_mtime, reverse=True)
            if md_files:
                files_to_check.append(md_files[0])
            else:
                print("[validate_article] 未找到任何文章文件")
                return

    all_results = []
    for fp in files_to_check:
        result = validate_file(fp, strict=args.strict)
        print_report(result, use_json=args.json, verbose=args.verbose)
        all_results.append(result)

    if len(all_results) > 1:
        passed = sum(1 for r in all_results if r.has_passed_p0p1())
        print(f"\n汇总: {passed}/{len(all_results)} 篇通过 P0/P1 审核")

    # ── 退出码：失败处理 ──
    if EXIT_ON_FAIL:
        # 同时检查 result.passed（文件缺失等致命错误）和 p0p1 通过条件
        any_fail = any(not r.passed or not r.has_passed_p0p1() for r in all_results)
        if any_fail:
            sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
validate_article.py — P0/P1/P2 内容质量审核 + A+C+F 结构 + 排版格式验证
规则来源：writing_rules.json（唯一来源，与 daily-why-writer skill 同源）

用法：
    python validate_article.py 2026-05-09-每日冷知识.md
    python validate_article.py --strict 2026-05-09-每日冷知识.md
    python validate_article.py --json article.md
    python validate_article.py --latest
"""

import re
import sys
import json
import argparse

# Windows GBK 终端兼容：强制 stdout 使用 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── 从 writing_rules.json 加载规则（唯一来源） ──
RULES_PATH = Path(__file__).parent / "writing_rules.json"
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

# 字数
WC_MIN = _r("word_count.min", 300)
WC_MAX = _r("word_count.max", 600)
WC_P1_THRESHOLD = _r("word_count.p1_threshold", 600)

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

    def has_passed_p0p1(self) -> bool:
        return len(self.p0) == 0 and len(self.p1) <= P1_MAX_ALLOWED

    @property
    def p0p1_passed(self) -> bool:
        return self.has_passed_p0p1()


def count_chinese_chars(text: str) -> int:
    """统计中文字符数"""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def strip_markdown(text: str) -> str:
    """去掉 markdown 格式，返回纯文本"""
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"---+", "", text)
    text = re.sub(r"\|.+\|", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def validate_content_quality(content: str, result: ValidationResult):
    """P0/P1/P2 内容质量审核"""
    plain = strip_markdown(content)

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

    # P0: 缺少疑问驱动结构（C段）
    q_count = 0
    for pat in QUESTION_PATTERNS:
        matches = re.findall(pat, content, re.MULTILINE)
        q_count = max(q_count, len(matches))
    if q_count < QUESTIONS_P0_THRESHOLD:
        result.p0_error(
            f"缺少疑问驱动结构（C段）—— 仅发现 {q_count} 个问题标记，"
            f"需要 {QUESTIONS_P0_THRESHOLD}+ 个递进式问题")
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

    # P1: 标题缺少 emoji
    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    if title_match:
        title = title_match.group(1)
        has_emoji = bool(
            re.search(r"[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]",
                      title))
        if not has_emoji:
            result.p1_error("标题缺少 emoji 装饰")
        else:
            result.ok("标题 emoji 装饰 ✓")

    # P0: 分隔线数量（恰好 2 处，结构硬性要求）
    # 只匹配行首独立的 ---，排除表格分隔符 |---|
    sep_count = len(re.findall(r"^\s*---\s*$", content, re.MULTILINE))
    if sep_count < SEPARATOR_EXACT:
        result.p0_error(
            f"分隔线不足（仅 {sep_count} 处），"
            f"需要恰好 {SEPARATOR_EXACT} 处：A段后 + F段前")
    elif sep_count > SEPARATOR_MAX + 1:
        # 超过 3 处才报 P0（容忍 1 处偏差），恰好 3 处给 P1
        result.p0_error(
            f"分隔线过多（{sep_count} 处），"
            f"应恰好 {SEPARATOR_MAX} 处，C段内部Q之间不加 ---")
    elif sep_count > SEPARATOR_MAX:
        result.p1_error(
            f"分隔线过多（{sep_count} 处），"
            f"应恰好 {SEPARATOR_MAX} 处，C段内部Q之间不加 ---")
    else:
        result.ok(f"分隔线使用 ✓ ({sep_count} 处)")

    # P1: 引用块缺失
    quote_lines = re.findall(r"^>\s+.+", content, re.MULTILINE)
    if len(quote_lines) < QUOTE_MIN:
        result.p1_error("缺少引用块「>」，应用来承载故事场景和反转金句")
    else:
        result.ok(f"引用块 ✓ ({len(quote_lines)} 行)")

    # P1: 加粗不足
    bold_count = len(re.findall(r"\*\*.+?\*\*", content))
    if bold_count < BOLD_MIN:
        result.p1_error(
            f"加粗偏少（仅 {bold_count} 处），"
            f"建议突出 2-3 个关键概念")
    else:
        result.ok(f"加粗关键词 ✓ ({bold_count} 处)")

    # P0: Q 格式检测（禁止 h3 格式，结构硬性要求）
    h3_questions = re.findall(r"^###\s+.*[？?]", content, re.MULTILINE)
    if h3_questions:
        result.p0_error(
            f"Q 标记使用了 h3 格式（{len(h3_questions)} 处），"
            f"应统一用加粗格式 **Q1：xxx？**")
    else:
        result.ok("Q 格式 ✓（加粗格式）")

    # P1: 反转标签检测（必须用"冷知识反转"，禁止"冷知识彩蛋"）
    if "冷知识彩蛋" in content:
        result.p1_error("反转标签使用了「冷知识彩蛋」，应统一用「冷知识反转」")
    elif "冷知识反转" in content:
        result.ok("反转标签 ✓（冷知识反转）")
    else:
        result.p1_error("缺少「冷知识反转」标签")

    # P1: 风格表格分类行检测
    if not re.search(r"分类\s*\|", content):
        result.p1_error("风格表格缺少「分类」行")
    else:
        result.ok("风格表格分类 ✓")

    # P2: 风格表格行标题完整性检测（话题/分类/核心机制/冷知识反转）
    table_row_headers = ["话题", "分类", "核心机制", "冷知识反转"]
    found_headers = [h for h in table_row_headers if re.search(rf"\|\s*{h}\s*\|", content)]
    missing_headers = [h for h in table_row_headers if h not in found_headers]
    if missing_headers:
        result.p2_error(
            f"风格表格行标题不完整，缺少：{'、'.join(missing_headers)}，"
            f"标准格式为 话题/分类/核心机制/冷知识反转")
    else:
        result.ok("风格表格行标题完整性 ✓")

    # ── P2：细节优化 ──

    # 字数检测：< min 打 P2，> max 打 P1，中间正常
    char_count = count_chinese_chars(plain)
    result.info["char_count"] = char_count
    if char_count < WC_MIN:
        result.p2_error(f"字数偏少（{char_count} 字），建议 {WC_MIN}-{WC_MAX} 字")
    elif char_count > WC_MAX:
        result.p1_error(f"字数过多（{char_count} 字），上限 {WC_MAX} 字，需精简")
    else:
        result.ok(f"字数 ✓ ({char_count} 字)")

    # P2: 风格说明表格
    if not re.search(r"\|.+\|.+\|", content):
        result.p2_error("建议结尾附风格说明表格")
    else:
        result.ok("风格说明表格 ✓")


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


def print_report(result: ValidationResult, use_json: bool = False):
    """打印验证报告（P0/P1/P2 新版）"""
    if use_json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return

    print(f"\n{'='*60}")
    print(f"📋 审核报告: {result.file}")
    print(f"{'='*60}")

    p0p1_ok = result.has_passed_p0p1()
    status_icon = "✅ PASS" if p0p1_ok else "❌ FAIL"
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

    print(f"{'='*60}\n")


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
    args = parser.parse_args()

    workspace = Path(args.workspace)
    files_to_check = []

    if args.files:
        for f in args.files:
            files_to_check.append(Path(f))
    elif args.latest:
        md_files = sorted(workspace.glob("*-每日冷知识.md"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        if md_files:
            files_to_check.append(md_files[0])
        else:
            print("[validate_article] 未找到任何文章文件")
            return
    else:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        today_file = workspace / f"{today}-每日冷知识.md"
        if today_file.exists():
            files_to_check.append(today_file)
        else:
            md_files = sorted(workspace.glob("*-每日冷知识.md"),
                              key=lambda p: p.stat().st_mtime, reverse=True)
            if md_files:
                files_to_check.append(md_files[0])
            else:
                print("[validate_article] 未找到任何文章文件")
                return

    all_results = []
    for fp in files_to_check:
        result = validate_file(fp, strict=args.strict)
        print_report(result, use_json=args.json)
        all_results.append(result)

    if len(all_results) > 1:
        passed = sum(1 for r in all_results if r.has_passed_p0p1())
        print(f"\n汇总: {passed}/{len(all_results)} 篇通过 P0/P1 审核")

    # ── 退出码：失败处理 ──
    if EXIT_ON_FAIL:
        any_fail = any(not r.has_passed_p0p1() for r in all_results)
        if any_fail:
            import sys
            sys.exit(1)


if __name__ == "__main__":
    main()

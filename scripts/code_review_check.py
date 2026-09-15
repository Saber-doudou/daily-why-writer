#!/usr/bin/env python3
"""
code_review_check.py — 代码审查自动化检查工具（v2.0，2026-09-15）
快速检查 Python 脚本的代码质量、安全性和性能。

v2.0 变更（docs/code-review-standard.md P2 落地）：
- 修复 snake_case_function 规则反转 bug（原规则把正常 snake_case 命名误报为违规，停用 3 个月未察觉）
- 新增本项目历史缺陷模式规则：env fail-open 开关、eval/exec、shell=True、pickle、可变默认参数、requests 无 timeout
- 新增 --staged：读 git 暂存区文件（pre-commit hook 用），获取失败按 fail-closed 处理
- stdout 强制 UTF-8（git hook 场景防 GBK UnicodeEncodeError）

用法：
    python scripts/code_review_check.py                    # 检查所有脚本
    python scripts/code_review_check.py script.py          # 检查指定脚本
    python scripts/code_review_check.py --json             # JSON 格式输出
    python scripts/code_review_check.py --staged --strict  # pre-commit hook 用
"""

import re
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, field, asdict

# git hook / 非终端场景 stdout 可能是 GBK，中文输出会 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


@dataclass
class ReviewIssue:
    """审查问题"""
    file: str
    line: int
    severity: str  # P0, P1, P2
    category: str  # naming, security, performance, style, doc
    message: str
    suggestion: str = ""


@dataclass
class ReviewResult:
    """审查结果"""
    file: str
    issues: List[ReviewIssue] = field(default_factory=list)
    score: int = 100
    p0_count: int = 0
    p1_count: int = 0
    p2_count: int = 0


# 审查规则
REVIEW_RULES = {
    "naming": {
        # v2.0：删除 snake_case_function 规则 —— 原正则 r"def\s+[a-z]+_[a-z]+" 恰好匹配
        # 正常的 snake_case 命名却报"应使用 snake_case"，属规则反转 bug；反例检测由
        # camelCase_function 覆盖，无功能损失。
        "single_letter_var": {
            "pattern": r"\b[a-z]\b\s*=",
            "severity": "P2",
            "message": "单字母变量名，建议使用有意义的名称",
            "exclude": ["i", "j", "k", "x", "y", "z", "f", "e", "m", "n"],
        },
        "camelCase_function": {
            "pattern": r"def\s+[a-z]+[A-Z]",
            "severity": "P1",
            "message": "函数名不应使用 camelCase，应使用 snake_case",
        },
    },
    "security": {
        "hardcoded_path": {
            "pattern": r'Path\s*\(\s*r?"[A-Z]:\\',
            "severity": "P2",
            "message": "硬编码路径，建议提取到配置或环境变量",
        },
        "hardcoded_python_path": {
            "pattern": r"python\.exe",
            "severity": "P2",
            "message": "硬编码 Python 路径，建议使用 sys.executable",
        },
        "bare_except": {
            "pattern": r"except\s*:",
            "severity": "P1",
            "message": "裸 except 会捕获所有异常，建议指定异常类型",
        },
        "except_pass": {
            "pattern": r"except.*:\s*\n\s*pass",
            "severity": "P1",
            "message": "异常被静默吞掉，至少应该 log",
        },
        # ---- v2.0 新增：本项目历史缺陷模式 ----
        "env_fail_open": {
            # os.environ.get("X") == "1"：默认关闭型开关。若是保护开关（去重/校验/拦截）
            # 默认关即 Silent Fail-Open（09-15 事故根因）；仅豁免开关允许此形态，须留痕。
            "pattern": r"environ\.get\([^)]*\)\s*==\s*[\"']1[\"']",
            "severity": "P1",
            "message": "环境变量开关默认关闭（== \"1\" 才启用）：确认这是豁免开关而非保护开关；保护开关必须 fail-closed（如 != \"1\" 默认启用）",
        },
        "eval_exec": {
            "pattern": r"\b(eval|exec)\s*\(",
            "severity": "P0",
            "message": "使用 eval/exec 动态执行，存在代码注入风险",
        },
        "shell_true": {
            "pattern": r"shell\s*=\s*True",
            "severity": "P1",
            "message": "subprocess 使用 shell=True，拼接外部输入时有注入风险，建议列表参数",
        },
        "pickle_load": {
            "pattern": r"pickle\.loads?\s*\(",
            "severity": "P1",
            "message": "pickle 反序列化不可信数据可执行任意代码，建议 JSON",
        },
    },
    "correctness": {
        # v2.0 新增类别
        "mutable_default_arg": {
            "pattern": r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\})\s*[,)]",
            "severity": "P1",
            "message": "可变对象作默认参数（[]/{}），跨调用共享状态，建议默认 None 函数内重建",
        },
        "assert_only_check": {
            "pattern": r"^\s*assert\s+[^,]+$",
            "severity": "P2",
            "message": "仅用 assert 做校验，python -O 下会被跳过；生产校验用显式 if+raise",
        },
    },
    "performance": {
        "nested_loop": {
            "pattern": r"for\s+.*\n\s+for\s+",
            "severity": "P2",
            "message": "嵌套循环，检查是否可以优化",
        },
        "string_concat_loop": {
            "pattern": r"\+=\s*['\"]",
            "severity": "P2",
            "message": "循环内字符串拼接，建议使用 join()",
        },
    },
    "style": {
        "long_line": {
            "pattern": r".{120,}",
            "severity": "P2",
            "message": "行长度超过 120 字符",
        },
        "trailing_whitespace": {
            "pattern": r"\s+$",
            "severity": "P2",
            "message": "行尾有空白字符",
        },
    },
    "doc": {
        "missing_docstring": {
            "pattern": r"^def\s+\w+\s*\([^)]*\)\s*:",
            "severity": "P2",
            "message": "函数缺少 docstring",
            "check_next_line": True,
        },
    },
}


def check_file(filepath: Path) -> ReviewResult:
    """检查单个文件"""
    result = ReviewResult(file=filepath.name)

    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")
    except Exception as e:
        result.issues.append(ReviewIssue(
            file=filepath.name,
            line=0,
            severity="P0",
            category="error",
            message=f"无法读取文件: {e}",
        ))
        return result

    # 检查每一行
    for i, line in enumerate(lines, 1):
        # 命名检查
        for rule_name, rule in REVIEW_RULES.get("naming", {}).items():
            if rule_name == "single_letter_var":
                matches = re.findall(rule["pattern"], line)
                for match in matches:
                    var_name = match.split("=")[0].strip()
                    if var_name not in rule.get("exclude", []):
                        result.issues.append(ReviewIssue(
                            file=filepath.name,
                            line=i,
                            severity=rule["severity"],
                            category="naming",
                            message=f"{rule['message']}: {var_name}",
                        ))
            elif re.search(rule["pattern"], line):
                result.issues.append(ReviewIssue(
                    file=filepath.name,
                    line=i,
                    severity=rule["severity"],
                    category="naming",
                    message=rule["message"],
                ))

        # 安全检查
        for rule_name, rule in REVIEW_RULES.get("security", {}).items():
            if re.search(rule["pattern"], line):
                result.issues.append(ReviewIssue(
                    file=filepath.name,
                    line=i,
                    severity=rule["severity"],
                    category="security",
                    message=rule["message"],
                ))

        # 性能检查
        for rule_name, rule in REVIEW_RULES.get("performance", {}).items():
            if rule_name == "nested_loop":
                # 检查连续两行都是 for 循环
                if i < len(lines) and re.search(rule["pattern"], line + "\n" + lines[i]):
                    result.issues.append(ReviewIssue(
                        file=filepath.name,
                        line=i,
                        severity=rule["severity"],
                        category="performance",
                        message=rule["message"],
                    ))
            elif re.search(rule["pattern"], line):
                result.issues.append(ReviewIssue(
                    file=filepath.name,
                    line=i,
                    severity=rule["severity"],
                    category="performance",
                    message=rule["message"],
                ))

        # 正确性检查（v2.0 新增类别）
        for rule_name, rule in REVIEW_RULES.get("correctness", {}).items():
            if re.search(rule["pattern"], line):
                result.issues.append(ReviewIssue(
                    file=filepath.name,
                    line=i,
                    severity=rule["severity"],
                    category="correctness",
                    message=rule["message"],
                ))

        # 反向规则：requests 调用行缺 timeout（跨行调用会误报，见 docs/code-review-standard.md）
        if re.search(r"requests\.(get|post|put|delete|head)\s*\(", line) and not re.search(r"timeout\s*=", line):
            result.issues.append(ReviewIssue(
                file=filepath.name,
                line=i,
                severity="P2",
                category="security",
                message="requests 调用未见 timeout 参数（跨行调用请忽略），无超时会无限挂起",
            ))

        # 风格检查
        for rule_name, rule in REVIEW_RULES.get("style", {}).items():
            if re.search(rule["pattern"], line):
                result.issues.append(ReviewIssue(
                    file=filepath.name,
                    line=i,
                    severity=rule["severity"],
                    category="style",
                    message=rule["message"],
                ))

        # 文档检查
        for rule_name, rule in REVIEW_RULES.get("doc", {}).items():
            if rule_name == "missing_docstring":
                if re.search(rule["pattern"], line):
                    # 检查下一行是否是 docstring
                    if i < len(lines) and not re.search(r'^\s*"""', lines[i]):
                        result.issues.append(ReviewIssue(
                            file=filepath.name,
                            line=i,
                            severity=rule["severity"],
                            category="doc",
                            message=rule["message"],
                        ))

    # 统计问题数量
    for issue in result.issues:
        if issue.severity == "P0":
            result.p0_count += 1
        elif issue.severity == "P1":
            result.p1_count += 1
        elif issue.severity == "P2":
            result.p2_count += 1

    # 计算分数
    result.score = max(0, 100 - (result.p0_count * 20) - (result.p1_count * 10) - (result.p2_count * 2))

    return result


def print_report(result: ReviewResult, use_json: bool = False):
    """打印审查报告"""
    if use_json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return

    print(f"\n{'='*60}")
    print(f"📋 代码审查报告: {result.file}")
    print(f"{'='*60}")

    # 状态
    status_icon = "✅" if result.p0_count == 0 else "❌"
    print(f"状态: {status_icon}")
    print(f"分数: {result.score}/100")
    print(f"P0(致命)={result.p0_count}  P1(重要)={result.p1_count}  P2(一般)={result.p2_count}")

    # 按严重度分组显示问题
    if result.p0_count > 0:
        print(f"\n--- 🔴 P0 致命问题（必须修复） ---")
        for issue in result.issues:
            if issue.severity == "P0":
                print(f"  ✗ 第 {issue.line} 行: {issue.message}")

    if result.p1_count > 0:
        print(f"\n--- 🟡 P1 重要问题（建议修复） ---")
        for issue in result.issues:
            if issue.severity == "P1":
                print(f"  ! 第 {issue.line} 行: {issue.message}")

    if result.p2_count > 0:
        print(f"\n--- 🔵 P2 一般问题（可选修复） ---")
        for issue in result.issues:
            if issue.severity == "P2":
                print(f"  · 第 {issue.line} 行: {issue.message}")

    # 按类别统计
    category_counts = {}
    for issue in result.issues:
        category_counts[issue.category] = category_counts.get(issue.category, 0) + 1

    if category_counts:
        print(f"\n--- 按类别统计 ---")
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count} 个问题")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="代码审查自动化检查工具（v2.0）")
    parser.add_argument("files", nargs="*", help="要检查的文件路径")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--staged", action="store_true", help="检查 git 暂存区 py 文件（pre-commit hook 用，隐含 strict）")
    parser.add_argument("--strict", action="store_true", help="严格模式（P0 不通过，退出码 1）")
    args = parser.parse_args()

    # 获取文件列表
    workspace = Path(r"F:\WorkBuddy\daily-why")
    if args.staged:
        # fail-closed：拿不到暂存区清单就终止，hook 将拒绝提交
        repo_root = Path(r"F:\WorkBuddy\daily-why-writer")
        try:
            cfg = json.loads((workspace / "scripts" / "config.json").read_text(encoding="utf-8"))
            if cfg.get("git_repo_path"):
                repo_root = Path(cfg["git_repo_path"])
        except Exception:
            pass  # 读不到配置则用默认路径
        try:
            out = subprocess.run(
                ["git", "-C", str(repo_root), "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                capture_output=True, text=True, timeout=15,
            )
            if out.returncode != 0:
                print(f"[code_review_check] 获取暂存区失败（fail-closed 终止）: {out.stderr.strip()}", file=sys.stderr)
                sys.exit(2)
            staged = [ln.strip() for ln in out.stdout.splitlines() if ln.strip().endswith(".py")]
            existing = [repo_root / p for p in staged if (repo_root / p).exists()]
            if staged and not existing:
                print("[code_review_check] 暂存 py 文件均无法读取（fail-closed 终止）", file=sys.stderr)
                sys.exit(2)
            files = existing
        except SystemExit:
            raise
        except Exception as e:
            print(f"[code_review_check] 获取暂存区异常（fail-closed 终止）: {e}", file=sys.stderr)
            sys.exit(2)
    elif args.files:
        files = [Path(f) for f in args.files]
    else:
        files = list(workspace.glob("scripts/*.py"))

    if not files:
        print("未找到要检查的文件")
        return

    # 检查每个文件
    all_results = []
    for filepath in files:
        if not filepath.exists():
            print(f"文件不存在: {filepath}")
            if args.staged:
                sys.exit(2)
            continue

        result = check_file(filepath)
        print_report(result, use_json=args.json)
        all_results.append(result)

    # 汇总
    if len(all_results) > 1:
        total_p0 = sum(r.p0_count for r in all_results)
        total_p1 = sum(r.p1_count for r in all_results)
        total_p2 = sum(r.p2_count for r in all_results)
        avg_score = sum(r.score for r in all_results) / len(all_results)

        print(f"\n{'='*60}")
        print(f"📊 汇总统计")
        print(f"{'='*60}")
        print(f"检查文件: {len(all_results)} 个")
        print(f"平均分数: {avg_score:.1f}/100")
        print(f"总问题数: {total_p0 + total_p1 + total_p2} 个")
        print(f"  P0(致命): {total_p0} 个")
        print(f"  P1(重要): {total_p1} 个")
        print(f"  P2(一般): {total_p2} 个")
        print(f"{'='*60}")

    # 退出码（--staged 隐含 strict：hook 场景 P0 必须拦截）
    if args.strict or args.staged:
        any_p0 = any(r.p0_count > 0 for r in all_results)
        if any_p0:
            sys.exit(1)


if __name__ == "__main__":
    main()

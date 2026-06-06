#!/usr/bin/env python3
"""
auto_fix.py — 自动化格式修复工具
修复 validate_article.py 检测到的可自动修复的格式问题。

修复项：
  1. h3 Q 格式 → **Q1：xxx？** 加粗格式
  2. 分隔线数量 → 恰好 2 处 ---
  3. 反转标签 "冷知识彩蛋" → "冷知识反转"
  4. 风格表格行数 → 补全至 4 行（含表头）

流程：
  python auto_fix.py article.md           # 修复所有可自动修复的问题
  python auto_fix.py article.md --dry-run # 仅预览修复，不实际修改
  python auto_fix.py article.md --verify  # 修复后验证

安全：
  - 修复前自动备份为 .bak 文件
  - --dry-run 模式不修改文件
"""

import re
import sys
import json
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

# 从 writing_rules.json 加载规则
RULES_PATH = Path(__file__).parent / "writing_rules.json"
RULES = {}
if RULES_PATH.exists():
    try:
        RULES = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass


def _r(path: str, default=None):
    keys = path.split(".")
    val = RULES
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    return val if val is not None else default


TWIST_LABEL = _r("formatting.twist_label", "冷知识反转")
SEPARATOR_EXACT = _r("formatting.separator_exact", 2)
Q_FORMAT = _r("formatting.q_format", "**Q1：xxx？**")


@dataclass
class FixReport:
    """修复报告"""
    file: str
    fixed: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    backup_path: str = ""
    changes: int = 0


def backup_file(filepath: Path) -> Path:
    """创建备份文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = filepath.with_suffix(f".bak.{timestamp}")
    shutil.copy2(filepath, backup)
    return backup


# ── Fix 1: h3 Q格式 → **Q1：xxx？** 加粗格式 ──

def fix_q_format(content: str, report: FixReport) -> str:
    """将 ### Q1：xxx？ 格式改为 **Q1：xxx？** 加粗格式"""
    patterns = [
        # ### Q1：xxx？ / ### Q1: xxx？
        (r'^###\s+(Q\d+[：:]?\s*.+)$', r'**\1**'),
        # 纯数字格式 ### 1. xxx？
        (r'^###\s+(\d+)\.\s*(.+[？?].+)$', r'**Q\1：\2**'),
    ]
    changed = False
    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        if new_content != content:
            changed = True
            content = new_content

    if changed:
        report.fixed.append({
            "type": "Q格式",
            "detail": "h3 → **Qx：xxx？** 加粗格式",
            "fixes": len(re.findall(r"\*\*Q\d+", content)) - len(re.findall(r"^###\s+Q", content, flags=re.MULTILINE)),
        })
    else:
        report.skipped.append("Q格式：未发现 h3 格式的 Q 标题")

    return content


# ── Fix 2: 分隔线数量 → 恰好 2 处 --- ──

def fix_separators(content: str, report: FixReport) -> str:
    """确保分隔线恰好 2 处（A/C段之间 和 C/F段之间）"""
    # 检测现有分隔线
    sep_pattern = re.compile(r'^---\s*$', re.MULTILINE)
    separators = list(sep_pattern.finditer(content))

    count = len(separators)
    if count == SEPARATOR_EXACT:
        report.skipped.append(f"分隔线：已恰好 {count} 处，无需修复")
        return content

    if count == 0:
        report.skipped.append("分隔线：未找到任何分隔线，无法自动判断插入位置")
        return content

    if count > SEPARATOR_EXACT:
        # 多于 2 处，保留前 2 处，删除其余
        lines = content.split('\n')
        sep_indices = [m.start() for m in separators]
        # 转换为行号
        line_positions = []
        pos = 0
        for i, line in enumerate(lines):
            line_positions.append(pos)
            pos += len(line) + 1  # +1 for newline

        # 找到分隔线所在行
        sep_line_nums = []
        for m in separators:
            idx = m.start()
            for i, lp in enumerate(line_positions):
                if lp == idx:
                    sep_line_nums.append(i)
                    break

        # 保留第 1 和第 2 处分隔线，删除其余（从后往前删）
        if len(sep_line_nums) > 2:
            keep_indices = sorted(sep_line_nums)[:2]
            for line_num in sorted(sep_line_nums)[2:][::-1]:
                # 删除该行，并清理其前后的空行
                # 只删除分隔线行本身，保留上下文空行
                if line_num < len(lines):
                    del lines[line_num]
            content = '\n'.join(lines)
            report.fixed.append({
                "type": "分隔线",
                "detail": f"超出：{len(sep_line_nums)} 处 → 保留前 2 处",
            })
            return content

    # count < 2: 不足 2 处
    if count == 1:
        # 只有 1 处，需在合适位置插入第 2 处
        # 策略：如果在 F 段前没有分隔线，在"🤝"或"反转"关键词前插入
        lines = content.split('\n')
        inserted = False
        twist_markers = ['> 🤝', '> **冷知识', '冷知识', '反转']
        for i, line in enumerate(lines):
            if any(marker in line for marker in twist_markers):
                # 在这行之前插入分隔线
                lines.insert(i, '---')
                lines.insert(i + 1, '')  # 加空行
                inserted = True
                break

        if inserted:
            content = '\n'.join(lines)
            report.fixed.append({
                "type": "分隔线",
                "detail": "不足：1 处 → 在反转段落前自动插入第 2 处",
            })
        else:
            report.skipped.append("分隔线：仅 1 处，且无法定位反转段落，需手动插入")
        return content

    return content


# ── Fix 3: 反转标签 "冷知识彩蛋" → "冷知识反转" ──

def fix_twist_label(content: str, report: FixReport) -> str:
    """将错误的反转标签替换为规范标签"""
    replacements = [
        ("冷知识彩蛋", TWIST_LABEL),
        ("**冷知识彩蛋**", f"**{TWIST_LABEL}**"),
        ("冷知识彩蛋：", f"{TWIST_LABEL}："),
        ("**冷知识彩蛋：**", f"**{TWIST_LABEL}：**"),
    ]

    changed = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            changed = True

    if changed:
        report.fixed.append({
            "type": "反转标签",
            "detail": f'"冷知识彩蛋" → "{TWIST_LABEL}"',
        })
    else:
        report.skipped.append("反转标签：未发现需要修复的标签")

    return content


# ── Fix 4: 风格表格行数 → 补全至 4 行 ──

def fix_style_table(content: str, report: FixReport) -> str:
    """确保风格表格有 4 行（表头 + 话题 + 分类 + 核心机制 + 反转）"""
    lines = content.split('\n')

    # 找到表格区域（以 | 开头的连续行）
    table_ranges = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('|') and line.endswith('|'):
            start = i
            while i < len(lines) and lines[i].strip().startswith('|'):
                i += 1
            end = i
            table_ranges.append((start, end))
        else:
            i += 1

    for start, end in table_ranges:
        table_lines = lines[start:end]
        # 过滤掉分隔行 |---|
        data_lines = [l for l in table_lines if not re.match(r'^\|[\s\-:]+\|', l)]
        data_count = len(data_lines)

        if data_count >= 4:
            continue  # 已满足 4 行（含表头）

        if data_count < 1:
            continue  # 无法判断

        # 取表头判断列数
        header = data_lines[0]
        cols = len([c for c in header.split('|') if c.strip()])

        # 从已有行推断内容
        if data_count < 4:
            missing = 4 - data_count
            # 定义标准表头顺序
            standard_rows = ["话题", "分类", "核心机制", "冷知识反转"]

            # 找到分隔行
            sep_line_idx = None
            for j, l in enumerate(table_lines):
                if re.match(r'^\|[\s\-:]+\|', l.strip()):
                    sep_line_idx = j
                    break

            # 找到已存在的行关键词
            existing_kw = set()
            for dl in data_lines[1:]:  # 跳过表头
                plain = dl.strip().lower()
                for kw in ["话题", "分类", "核心机制", "冷知识反转", "反转", "核心"]:
                    if kw in plain:
                        existing_kw.add(kw)
                        break

            # 构建缺失行
            missing_rows = []
            for row_name in standard_rows:
                # 检查是否已存在
                already = False
                for ek in existing_kw:
                    if row_name[:2] in ek or ek in row_name:
                        already = True
                        break
                if not already and len(missing_rows) < missing:
                    # 生成占位行
                    missing_rows.append(f"| {row_name} | （待填充） |")

            if missing_rows:
                # 插入位置：在分隔行之后
                insert_idx = start + (sep_line_idx if sep_line_idx else 1)
                for row in missing_rows:
                    lines.insert(insert_idx + 1, row)

                report.fixed.append({
                    "type": "风格表格",
                    "detail": f"补全 {len(missing_rows)} 行 → 达到 4 行标准",
                })
                content = '\n'.join(lines)
                break

    if not any("风格表格" in str(f) for f in report.fixed):
        report.skipped.append("风格表格：已满足 4 行或未找到表格，无需修复")

    return content


# ── 主修复流程 ──

def auto_fix(filepath: Path, dry_run: bool = False) -> FixReport:
    """对文章执行所有自动修复"""
    report = FixReport(file=str(filepath))

    if not filepath.exists():
        report.errors.append(f"文件不存在: {filepath}")
        return report

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        report.errors.append(f"读取失败: {e}")
        return report

    original = content

    # 依次应用修复
    content = fix_q_format(content, report)
    content = fix_separators(content, report)
    content = fix_twist_label(content, report)
    content = fix_style_table(content, report)

    # 统计变更
    if content != original:
        report.changes = len(content) - len(original)

        if not dry_run:
            # 创建备份
            backup = backup_file(filepath)
            report.backup_path = str(backup)
            # 写入修复后的内容
            filepath.write_text(content, encoding="utf-8")
        else:
            report.skipped.append("--dry-run：未实际写入文件")
    else:
        report.skipped.append("内容无变化，无需修复")

    return report


def verify_fix(filepath: Path):
    """修复后验证：运行 validate_article.py"""
    import subprocess
    validator = Path(__file__).parent / "validate_article.py"
    if not validator.exists():
        print("[auto_fix] 验证工具不可用")
        return

    result = subprocess.run(
        [sys.executable, str(validator), str(filepath), "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        cwd=str(Path(__file__).parent),
    )

    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            p0 = len(data.get("p0", []))
            p1 = len(data.get("p1", []))
            p0p1_ok = data.get("p0p1_passed", False)
            print(f"\n✅ 验证通过：P0={p0}, P1={p1}, 得分={data.get('score', '?')}")
        except json.JSONDecodeError:
            print(f"\n[auto_fix] 验证输出解析失败")
            print(result.stdout[:500])
    else:
        print(f"\n❌ 验证失败（仍有 P0/P1 问题）")
        print(result.stdout[:500] if result.stdout else result.stderr[:500])


def print_report(report: FixReport):
    """打印修复报告"""
    print(f"\n{'='*60}")
    print(f"🛠️  自动修复报告: {report.file}")
    print(f"{'='*60}")

    if report.backup_path:
        print(f"📦 备份: {report.backup_path}")

    print(f"📊 修复项: {len(report.fixed)}  跳过项: {len(report.skipped)}  错误: {len(report.errors)}")
    print()

    if report.fixed:
        print("--- ✅ 已修复 ---")
        for f in report.fixed:
            if isinstance(f, dict):
                print(f"  [{f['type']}] {f['detail']}")
            else:
                print(f"  {f}")
        print()

    if report.skipped:
        print("--- ⏭️ 跳过 ---")
        for s in report.skipped:
            print(f"  {s}")
        print()

    if report.errors:
        print("--- ❌ 错误 ---")
        for e in report.errors:
            print(f"  {e}")
        print()

    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Daily Why 文章自动格式修复工具")
    parser.add_argument("file", help="要修复的文章路径")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅预览修复，不实际修改")
    parser.add_argument("--verify", action="store_true",
                        help="修复后运行 validate_article.py 验证")
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.is_absolute():
        # 相对于工作目录
        workspace = Path(r"F:\WorkBuddy\daily-why")
        filepath = workspace / args.file

    report = auto_fix(filepath, dry_run=args.dry_run)
    print_report(report)

    if args.verify and not args.dry_run and report.fixed:
        verify_fix(filepath)


if __name__ == "__main__":
    main()

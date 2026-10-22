#!/usr/bin/env python3
"""
archive_lessons.py — FEEDBACK_LOG 休眠教训归档 + 再犯激活检测

双模式：
  1. archive   → 检查 FEEDBACK_LOG 中超30天+已转化规则的教训，归档到 FEEDBACK_ARCHIVE
  2. check     → 将新 AI 反馈与休眠库匹配，检测是否有再犯需激活

Usage:
  # 归档模式（干跑预览）
  python archive_lessons.py --mode archive --dry-run

  # 归档模式（实际执行）
  python archive_lessons.py --mode archive

  # 激活检测模式
  python archive_lessons.py --mode check --feedback "新的AI审校反馈文本..."
"""

import argparse
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────────
SKILL_REFERENCES = Path.home() / ".workbuddy" / "skills" / "daily-why-writer" / "references"
FEEDBACK_LOG = SKILL_REFERENCES / "FEEDBACK_LOG.md"
FEEDBACK_ARCHIVE = SKILL_REFERENCES / "FEEDBACK_ARCHIVE.md"

DORMANT_DAYS = 30  # 超过多少天未再犯视为可归档


def parse_log_table(filepath: Path):
    """解析 FEEDBACK_LOG.md / FEEDBACK_ARCHIVE.md 的表格，返回 (header_section, rows, footer_section)"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 定位表格主体（从 | 日期 | 开头到下一个 ## 或文件结束）
    # 使用更可靠的策略：找到 "| 日期 " 表格头，找到其后的数据行
    lines = content.split("\n")

    # 找表格头行索引（包含 "| 日期" 的行）
    table_start = None
    table_end = None
    for i, line in enumerate(lines):
        if line.strip().startswith("| 日期") or line.strip().startswith("| 原日期"):
            table_start = i
            break

    if table_start is None:
        return content, [], ""

    # 找表格结束（下一个 ## 标题或文件末尾）
    for i in range(table_start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("## ") and i > table_start + 1:
            table_end = i
            break

    if table_end is None:
        table_end = len(lines)

    # 表头部分 = table_start 之前的行 + 表格头 + 分隔符行
    header_lines = lines[:table_start]
    
    # 找到表格头到数据之间的行（表格头 + 分隔符 + 可能的空行）
    data_start = None
    for i in range(table_start, min(table_end, len(lines))):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("| -") and not stripped.startswith("| 日") and not stripped.startswith("| 原"):
            data_start = i
            break

    if data_start is None:
        data_start = table_start + 3  # fallback

    # 实际的 header（包含表格头行和分隔符行）
    table_header_lines = lines[table_start:data_start]

    # 数据行
    raw_rows = lines[data_start:table_end]

    # 解析每一行
    rows = []
    for line in raw_rows:
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("| -") or stripped.startswith("|—"):
            continue
        # 去除首尾 |
        parts = [p.strip() for p in stripped.strip("|").split("|")]
        if len(parts) >= 4:
            rows.append({
                "line": line,
                "date": parts[0].strip(),
                "topic": parts[1].strip(),
                "lesson": parts[2].strip(),
                "rule": parts[3].strip(),
            })

    # 尾部部分
    footer_lines = lines[table_end:] if table_end < len(lines) else []

    # 重新构建 header（包含表格头之前 + 表格头行 + 分隔符行）
    all_header = header_lines + lines[table_start:data_start]

    return all_header, rows, footer_lines


def is_date_eligible(date_str: str, reference_date: datetime) -> bool:
    """检查日期是否超过 DORMANT_DAYS 天"""
    if not date_str:
        return False
    
    # 处理 YYYY-MM-DD 格式
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # 处理 YYYY-MM 格式（只有年月，默认当月1日）
    except ValueError:
        try:
            dt = datetime.strptime(date_str, "%Y-%m")
        except ValueError:
            return False

    dt = dt.replace(tzinfo=timezone.utc)
    return (reference_date - dt) > timedelta(days=DORMANT_DAYS)


def has_converted_rule(rule_str: str) -> bool:
    """检查是否已转化为规则"""
    rule_str = rule_str.strip()
    if not rule_str or rule_str in ("—", "-", "—"):
        return False
    return True


def build_log_content(header_lines, rows, footer_lines):
    """重建 FEEDBACK_LOG.md"""
    lines = list(header_lines)
    
    if rows:
        lines.append("")  # 空行
        for row in rows:
            lines.append(row["line"])
    
    # 尾部
    if footer_lines:
        lines.extend(footer_lines)
    
    return "\n".join(lines)


def build_archive_content(header_lines, rows, footer_lines):
    """重建 FEEDBACK_ARCHIVE.md，包含归档的教训"""
    lines = list(header_lines)
    
    if rows:
        lines.append("")
        for row in rows:
            lines.append(row["line"])
    
    if footer_lines:
        lines.extend(footer_lines)
    
    return "\n".join(lines)


def update_archive_summary_line(header_lines, rows: list):
    """更新 FEEDBACK_ARCHIVE 中的 '当前无休眠教训' 提示行"""
    count = len(rows)
    if count > 0:
        new_line = f"> **当前 {count} 条休眠教训**"
    else:
        new_line = "> 当前无休眠教训。"

    for i, line in enumerate(header_lines):
        stripped = line.strip()
        if stripped.startswith("> **当前") or stripped.startswith("> 当前无"):
            header_lines[i] = new_line
            return new_line
    
    # 没找到，在第一个 > 行后面插入
    for i, line in enumerate(header_lines):
        stripped = line.strip()
        if stripped.startswith(">"):
            header_lines.insert(i + 1, new_line)
            return new_line
    
    return None


# ── 归档模式 ──────────────────────────────────────────────────────

def cmd_archive(dry_run: bool):
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")

    print(f"📦 FEEDBACK 归档 | 参考日期: {today_str}")
    print(f"   来源: {FEEDBACK_LOG}")
    print(f"   目标: {FEEDBACK_ARCHIVE}")
    print()

    # 读取 active log
    if not FEEDBACK_LOG.exists():
        print(f"❌ 未找到 {FEEDBACK_LOG}")
        return 1

    log_header, log_rows, log_footer = parse_log_table(FEEDBACK_LOG)
    print(f"   FEEDBACK_LOG: {len(log_rows)} 条教训")

    # 读取 archive
    if FEEDBACK_ARCHIVE.exists():
        arch_header, arch_rows, arch_footer = parse_log_table(FEEDBACK_ARCHIVE)
    else:
        arch_header, arch_rows, arch_footer = [], [], []

    print(f"   FEEDBACK_ARCHIVE: {len(arch_rows)} 条休眠教训")
    print()

    # 筛选可归档条目
    eligible = []
    remaining = []
    for row in log_rows:
        if is_date_eligible(row["date"], today) and has_converted_rule(row["rule"]):
            eligible.append(row)
        else:
            remaining.append(row)

    if not eligible:
        print("✅ 无可归档条目")
        return 0

    print(f"🔍 发现 {len(eligible)} 条可归档教训：")
    print()
    for row in eligible:
        age = (today - datetime.strptime(row["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)).days
        print(f"  [{row['date']}] ({age}天前) {row['topic']} → {row['rule']}")
    print()

    if dry_run:
        print("⚠️  干跑模式 — 未执行实际写入")
        print(f"   移除后 FEEDBACK_LOG: {len(remaining)} 条")
        print(f"   归档到 ARCHIVE: {len(eligible)} 条")
        return 0

    # 实际执行写入
    # 1. 更新 FEEDBACK_LOG
    new_log = build_log_content(log_header, remaining, log_footer)
    with open(FEEDBACK_LOG, "w", encoding="utf-8") as f:
        f.write(new_log)

    # 2. 构建归档行（追加归档日期列）
    archive_data_rows = list(arch_rows)
    for row in eligible:
        # 构建归档格式：原日期 | 话题 | 教训 | 转化规则 | 归档日期
        archive_row = f"| {row['date']} | {row['topic']} | {row['lesson']} | {row['rule']} | {today_str} |"
        archive_data_rows.append({"line": archive_row, "date": row["date"], "topic": row["topic"], "lesson": row["lesson"], "rule": row["rule"], "archived": today_str})

    # 3. 如果 archive 文件不存在，创建基础结构
    if not FEEDBACK_ARCHIVE.exists():
        arch_header = [
            "# Feedback Archive（休眠教训库）",
            "",
            "> **用途**：存放超过30天未再犯的教训，保持活跃日志精简",
            "> **加载时机**：不主动加载，仅在审校需要回溯历史时手动查阅",
            "> **关联**：FEEDBACK_LOG.md（活跃教训）",
            "",
            "---",
            "",
            "## 休眠策略",
            "",
            "| 状态 | 定义 | 位置 |",
            "|------|------|------|",
            "| **活跃** | 最近30天内的教训 + 已转化为规则但仍在30天窗口内的 | FEEDBACK_LOG.md |",
            "| **休眠** | 超过30天未再犯 + 已转化为规则的教训 | 本文件 |",
            "| **再犯** | 休眠教训被新的AI反馈再次指出 | 激活回 FEEDBACK_LOG.md，标记 `[再犯]` |",
            "",
            "### 归档条件（必须同时满足）",
            "1. 距今超过30天",
            "2. 已转化为规则（写入 FP/CHECKLIST/SKILL.md）",
            "",
            "### 再犯激活流程",
            "1. 新的AI反馈指出某个问题",
            "2. 检查是否匹配本文件中的休眠教训",
            "3. 如匹配 → 将该教训移回 FEEDBACK_LOG.md，追加 `[再犯]` 标记",
            "4. 分析再犯原因：是规则遗忘还是规则执行不到位？",
            "",
            "---",
            "",
            "## 休眠教训",
            "",
        ]
        arch_footer = []

    # 更新摘要行
    update_archive_summary_line(arch_header, archive_data_rows)

    # 构建 archive table header（如果为空）
    has_table_header = any("| 原日期" in line or "| 日期" in line for line in arch_header)
    if not has_table_header:
        arch_header.append("| 原日期 | 话题 | 教训 | 转化规则 | 归档日期 |")
        arch_header.append("|--------|------|------|---------|-----------|")

    new_archive = build_archive_content(arch_header, archive_data_rows, arch_footer)
    with open(FEEDBACK_ARCHIVE, "w", encoding="utf-8") as f:
        f.write(new_archive)

    print(f"✅ 归档完成：")
    print(f"   FEEDBACK_LOG: {len(remaining)} 条（移除 {len(eligible)} 条）")
    print(f"   FEEDBACK_ARCHIVE: {len(archive_data_rows)} 条（新增 {len(eligible)} 条）")
    return 0


# ── 激活检测模式 ──────────────────────────────────────────────────

def cmd_check(feedback_text: str, dry_run: bool):
    if not FEEDBACK_ARCHIVE.exists():
        print("📭 FEEDBACK_ARCHIVE 不存在，跳过激活检测")
        return 0

    _, arch_rows, _ = parse_log_table(FEEDBACK_ARCHIVE)
    if not arch_rows:
        print("📭 休眠库为空，无需检测")
        return 0

    print(f"🔍 激活检测 | 休眠教训: {len(arch_rows)} 条")
    print()

    # 将反馈文本分词，用于匹配
    feedback_lower = feedback_text.lower()
    
    # 创建每个休眠教训的关键词（从教训列提取）
    matches = []
    for row in arch_rows:
        lesson = row["lesson"]
        topic = row["topic"]
        # 用话题 + 教训前50个字符作为匹配范围
        search_text = f"{topic} {lesson[:100]}".lower()
        
        # 计算反馈文本和教训文本的重叠度
        # 使用简单的关键词匹配：检查是否有足够多的关键词重叠
        keywords = set(re.findall(r'[\u4e00-\u9fff\w]+', search_text))
        feedback_keywords = set(re.findall(r'[\u4e00-\u9fff\w]+', feedback_lower))
        
        common = keywords & feedback_keywords
        
        # 如果共同关键词占比超过一定比例，视为匹配
        if len(keywords) > 0 and len(common) / len(keywords) >= 0.4:
            matches.append({
                "row": row,
                "overlap": len(common),
                "ratio": len(common) / len(keywords),
            })

    if not matches:
        print("✅ 未发现匹配的休眠教训，无再犯激活")
        return 0

    # 按匹配度排序
    matches.sort(key=lambda x: x["ratio"], reverse=True)

    print(f"⚠️  发现 {len(matches)} 个可能匹配的休眠教训：")
    print()
    for m in matches:
        print(f"  [{m['row']['date']}] {m['row']['topic']}")
        print(f"    教训: {m['row']['lesson'][:80]}...")
        print(f"    规则: {m['row']['rule']}")
        print(f"    匹配度: {m['ratio']:.0%} (共同 {m['overlap']} 词)")
        print()

    if not dry_run:
        print("⚠️  激活操作需要人工确认，请审阅后手动执行。")
        print("   确认后运行: python archive_lessons.py --mode activate --match-id <索引>")
        print()
        print("   或使用以下命令一次性激活全部匹配项：")
        print("   python archive_lessons.py --mode activate --match-all")

    return 0


def cmd_activate(match_id: int = None, match_all: bool = False):
    """激活匹配的休眠教训：从 ARCHIVE 移回 FEEDBACK_LOG"""
    if not FEEDBACK_ARCHIVE.exists():
        print("❌ FEEDBACK_ARCHIVE 不存在")
        return 1

    _, arch_rows, arch_footer = parse_log_table(FEEDBACK_ARCHIVE)
    if not arch_rows:
        print("📭 休眠库为空")
        return 0

    # 读取 active log
    log_header, log_rows, log_footer = parse_log_table(FEEDBACK_LOG)

    if match_id is not None:
        if match_id < 0 or match_id >= len(arch_rows):
            print(f"❌ match_id {match_id} 超出范围 (0-{len(arch_rows)-1})")
            return 1
        to_activate = [arch_rows[match_id]]
        remaining = [r for i, r in enumerate(arch_rows) if i != match_id]
    elif match_all:
        # 让用户通过 --confirm 确认
        to_activate = list(arch_rows)
        remaining = []
    else:
        print("❌ 请指定 --match-id <索引> 或 --match-all")
        return 1

    # 构造激活行
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for row in to_activate:
        # 在原始教训行上加 [再犯] 标记
        original_line = row["line"]
        if "[再犯]" not in original_line:
            row["line"] = original_line.rstrip() + f" `[再犯 {today_str}]`"
        log_rows.append(row)

    # 按日期排序
    log_rows.sort(key=lambda r: r.get("date", ""))

    # 写入更新后的 FEEDBACK_LOG
    new_log = build_log_content(log_header, log_rows, log_footer)
    with open(FEEDBACK_LOG, "w", encoding="utf-8") as f:
        f.write(new_log)

    # 写入更新后的 FEEDBACK_ARCHIVE
    arch_header, _, _ = parse_log_table(FEEDBACK_ARCHIVE) if FEEDBACK_ARCHIVE.exists() else ([], [], [])
    # 重建 arch_header（从文件中读取原始 header 部分）
    arch_header_result = []
    with open(FEEDBACK_ARCHIVE, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")
    table_start = None
    for i, line in enumerate(lines):
        if "| 原日期" in line or "| 日期" in line:
            table_start = i
            break
    if table_start is not None:
        arch_header_result = lines[:table_start]
    else:
        arch_header_result = lines  # fallback

    update_archive_summary_line(arch_header_result, remaining)

    new_archive = build_archive_content(arch_header_result, remaining, arch_footer)
    with open(FEEDBACK_ARCHIVE, "w", encoding="utf-8") as f:
        f.write(new_archive)

    print(f"✅ 激活完成：")
    print(f"   FEEDBACK_LOG: {len(log_rows)} 条（新增 {len(to_activate)} 条 [再犯]）")
    print(f"   FEEDBACK_ARCHIVE: {len(remaining)} 条（移除 {len(to_activate)} 条）")
    return 0


# ── 主入口 ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FEEDBACK_LOG 休眠教训归档 + 再犯激活检测",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["archive", "check", "activate"],
        default="archive",
        help="操作模式：archive=归档, check=激活检测, activate=执行激活",
    )
    parser.add_argument("--feedback", "-f", help="激活检测模式：AI审校反馈文本")
    parser.add_argument("--dry-run", "-n", action="store_true", help="干跑模式，不实际写入")
    parser.add_argument("--match-id", type=int, help="激活模式：按索引激活单个教训")
    parser.add_argument("--match-all", action="store_true", help="激活模式：激活全部匹配项")
    parser.add_argument(
        "--confirm", 
        action="store_true", 
        help="激活模式：确认 --match-all（防止误操作）"
    )

    args = parser.parse_args()

    if args.mode == "archive":
        return cmd_archive(dry_run=args.dry_run)

    elif args.mode == "check":
        if not args.feedback:
            print("❌ 激活检测模式需要 --feedback '反馈文本'")
            return 1
        return cmd_check(args.feedback, dry_run=args.dry_run)

    elif args.mode == "activate":
        if args.match_all and not args.confirm:
            print("⚠️  批量激活需要 --confirm 确认")
            print("   请先运行 --mode check 查看匹配结果，确认无误后加 --confirm")
            return 0
        return cmd_activate(match_id=args.match_id, match_all=args.match_all)

    return 0


if __name__ == "__main__":
    sys.exit(main())

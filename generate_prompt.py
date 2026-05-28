#!/usr/bin/env python3
"""
generate_prompt.py — 从 writing_rules.json + SKILL.md 自动生成 automation prompt
解决 "prompt 与脚本/技能不一致" 的系统性问题。

设计原则：
  - writing_rules.json = 数值规则唯一来源（字数、阈值等）
  - SKILL.md = 写作规范唯一来源（结构、排版、风格）
  - 本脚本 = prompt 唯一生成器（不再手动编辑 prompt）

用法：
    python generate_prompt.py                    # 输出到 stdout
    python generate_prompt.py --backup           # 同时备份到 automation-2-prompt-backup.md
    python generate_prompt.py --check            # 检查规则一致性，不输出 prompt
"""

import json
import re
import argparse
from pathlib import Path
from datetime import datetime


WORKSPACE = Path(r"F:\WorkBuddy\daily-why")
RULES_PATH = WORKSPACE / "writing_rules.json"
SKILL_PATH = Path(r"C:\Users\admin\.workbuddy\skills\daily-why-writer\SKILL.md")
PYTHON_PATH = r"C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe"
TOPICS_CONTEXT = WORKSPACE / "topics_context.json"
BACKUP_PATH = WORKSPACE / "automation-2-prompt-backup.md"


def load_rules() -> dict:
    """加载 writing_rules.json"""
    if not RULES_PATH.exists():
        raise FileNotFoundError(f"规则文件不存在: {RULES_PATH}")
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def load_skill() -> str:
    """加载 SKILL.md"""
    if not SKILL_PATH.exists():
        raise FileNotFoundError(f"Skill 文件不存在: {SKILL_PATH}")
    return SKILL_PATH.read_text(encoding="utf-8")


def load_recent_topics(limit: int = 10) -> list:
    """从 topics_context.json 加载最近话题（用于去重提示）"""
    if not TOPICS_CONTEXT.exists():
        return []
    try:
        data = json.loads(TOPICS_CONTEXT.read_text(encoding="utf-8"))
        return data.get("topic_summaries", [])[:limit]
    except Exception:
        return []


def check_consistency(rules: dict, skill: str) -> list:
    """检查 writing_rules.json、SKILL.md、prompt 之间的一致性"""
    issues = []

    # 1. 字数：rules vs skill
    wc_min = rules["word_count"]["min"]
    wc_max = rules["word_count"]["max"]
    wc_pattern = r"(\d+)[-~](\d+)\s*字"
    skill_wc = re.findall(wc_pattern, skill)
    if skill_wc:
        s_min, s_max = int(skill_wc[-1][0]), int(skill_wc[-1][1])
        if s_min != wc_min or s_max != wc_max:
            issues.append(
                f"字数不一致: writing_rules.json={wc_min}-{wc_max}, "
                f"SKILL.md={s_min}-{s_max}")

    # 2. 分隔线数量
    sep_exact = rules["formatting"]["separator_exact"]
    if f"{sep_exact} 处" not in skill and f"{sep_exact}处" not in skill:
        issues.append(f"分隔线数量: rules={sep_exact}, SKILL.md 中未明确提到")

    # 3. Q 格式
    q_format = rules["formatting"]["q_format"]
    if q_format not in skill:
        issues.append(f"Q 格式: rules 要求 '{q_format}', SKILL.md 中未找到完全匹配")

    # 4. 风格表格行数
    table_rows = rules["formatting"]["style_table_rows"]
    if f"{table_rows} 行" not in skill and f"统一 {table_rows}" not in skill:
        issues.append(f"风格表格行数: rules={table_rows}, SKILL.md 中未明确")

    # 5. 反转标签
    twist_label = rules["formatting"]["twist_label"]
    if twist_label not in skill:
        issues.append(f"反转标签: rules='{twist_label}', SKILL.md 中未找到")

    # 6. 分类选项一致性
    skill_cats = re.findall(r"\*\*(人体奥秘|自然科学|生活常识|宇宙探索|动物世界|物理化学)\*\*", skill)
    # 只要能找到就行
    if not skill_cats:
        issues.append("SKILL.md 中未找到标准分类选项列表")

    return issues


def generate_prompt(rules: dict, recent_topics: list = None) -> str:
    """生成完整的 automation prompt（排版规则由 SKILL.md 提供，prompt 不重复）"""
    wc_min = rules["word_count"]["min"]
    wc_max = rules["word_count"]["max"]

    # 构建去重话题列表
    dedup_section = ""
    if recent_topics:
        dedup_section = "\n## 最近话题（绝对不要重复）\n"
        for t in recent_topics:
            dedup_section += f"- {t}\n"

    PYTHON = "C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe"

    prompt = f"""《每日一个为什么》
生成一篇"每日一个为什么"冷知识文章。

前置检查：先检查 `F:/WorkBuddy/daily-why/{{今天日期}}-每日冷知识.md` 是否已存在，存在则跳过。

失败处理：如果任意步骤出错或结果不符合要求，立即停止，不再继续后续步骤，并报告问题原因。

## 步骤
1. 加载 **daily-why-writer** skill，按其中 A+C+F 结构、排版格式、语言风格和黑名单写文章
2. 运行 `{PYTHON} F:/WorkBuddy/daily-why/prepare_topics.py` 刷新话题库（确保 topics_context.json 包含最新文章记录）
3. 读取 `F:/WorkBuddy/daily-why/topics_context.json`，从 `topics` 数组的 `topic` 字段选一个**未曾使用**的话题。优先选自然科学 / 生活常识 / 人体奥秘类，避免高度重复的话题领域
{dedup_section}4. **写前快速查证**：用 WebSearch 搜 1-2 个该话题的关键词（中文），目的是：
   - 查证文章中的关键数字是否准确（距离、倍数、温度等），有争议的表述要修正
   - 看看同类科普是否写了辟谣/误区内容，如有则参考融入
   - 确认你的反转是否够独特（别人没写才保留）
   - **注意**：搜 1-2 个结果即可，不用深入阅读超过 2 篇。纯常识类话题（如海水咸、天蓝）可跳过此步
5. 综合查证结果，按 A+C+F 结构写文章，字数 {wc_min}-{wc_max} 字。最后一个问题（Q3）建议定位为辟谣或冷门延伸
6. **写后自检**：按 daily-why-writer skill 中的「写作自检清单」逐项检查，重点关注：
   - 用词精准度（身体部位术语、解剖位置是否准确、量词是否有依据）
   - 机制描述准确性（通俗比喻是否牺牲了准确性，"懂行的人会不会皱眉？"）
   - 避免绝对化表述（"不是A而是B"→"A为主、B为辅"更安全）
   - 数据与引用（关键数字有出处、区间优于精确值、使用标准科学单位）
   - 猜测与事实边界（推测性内容是否标注了"科学家猜测""可能是因为"）
   - 比喻一致性（全文比喻是否统一、经得起推敲）
   - 冷知识反转是否加了闭环收尾句（增强记忆点）
   如发现问题，修正后再保存
7. 保存到 `F:/WorkBuddy/daily-why/{{今天日期}}-每日冷知识.md`
8. 运行 `{PYTHON} F:/WorkBuddy/daily-why/validate_article.py` 审核
   - 如果审核不通过（审核脚本在 P0>0 或 P1>2 时 exit code 为 1），停止流水线，不要继续
9. 运行 `{PYTHON} F:/WorkBuddy/daily-why/update_history.py` 更新记忆
"""
    return prompt


def write_backup(prompt: str, rules: dict):
    """将 prompt 和变更记录写入备份文件"""
    version = rules.get("_version", "unknown")
    today = datetime.now().strftime("%Y-%m-%d")

    # 读取现有备份保留历史记录
    existing = ""
    if BACKUP_PATH.exists():
        existing = BACKUP_PATH.read_text(encoding="utf-8")

    # 提取历史变更记录部分
    history_section = ""
    if "## Phase B 版本变更记录" in existing:
        idx = existing.index("## Phase B 版本变更记录")
        history_section = existing[idx:]

    backup = f"""# daily-why Prompt 备份

> 维护时间：{today} {datetime.now().strftime('%H:%M')}
> 用途：automation prompt 恢复基线，由 generate_prompt.py 自动生成
> 规则版本：writing_rules.json v{version}
> 自动化 ID：`automation-1778312519754`

---

## 自动生成的 Prompt（当前使用）

```
{prompt}
```

---

## 生成方式

此 prompt 由 `generate_prompt.py` 从以下源自动生成：
- `writing_rules.json` — 数值规则（字数、阈值等）
- `SKILL.md` — 写作规范（结构、排版、风格）
- `topics_context.json` — 已用话题（去重）

**修改规则后运行以下命令同步 prompt：**
```bash
python generate_prompt.py --backup
```

---

{history_section}""" if history_section else f"""# daily-why Prompt 备份

> 维护时间：{today} {datetime.now().strftime('%H:%M')}
> 用途：automation prompt 恢复基线，由 generate_prompt.py 自动生成
> 规则版本：writing_rules.json v{version}
> 自动化 ID：`automation-1778312519754`

---

## 自动生成的 Prompt（当前使用）

```
{prompt}
```

---

## 生成方式

此 prompt 由 `generate_prompt.py` 从以下源自动生成：
- `writing_rules.json` — 数值规则（字数、阈值等）
- `SKILL.md` — 写作规范（结构、排版、风格）
- `topics_context.json` — 已用话题（去重）

**修改规则后运行以下命令同步 prompt：**
```bash
python generate_prompt.py --backup
```
"""

    BACKUP_PATH.write_text(backup, encoding="utf-8")
    print(f"[generate_prompt] 备份已写入: {BACKUP_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="从 writing_rules.json + SKILL.md 自动生成 automation prompt")
    parser.add_argument("--backup", action="store_true",
                        help="同时备份到 automation-2-prompt-backup.md")
    parser.add_argument("--check", action="store_true",
                        help="只检查规则一致性，不输出 prompt")
    args = parser.parse_args()

    # 加载规则
    rules = load_rules()
    skill = load_skill()

    # 一致性检查
    issues = check_consistency(rules, skill)
    if issues:
        print("⚠️  规则一致性问题:")
        for issue in issues:
            print(f"  - {issue}")
        print()
    else:
        print("✅ 规则一致性检查通过\n")

    if args.check:
        return

    # 加载最近话题
    recent = load_recent_topics(10)

    # 生成 prompt
    prompt = generate_prompt(rules, recent)

    print("=" * 60)
    print("📋 生成的 Automation Prompt")
    print(f"   规则版本: writing_rules.json v{rules['_version']}")
    print(f"   字数范围: {rules['word_count']['min']}-{rules['word_count']['max']}")
    print(f"   最近话题: {len(recent)} 个（用于去重）")
    print("=" * 60)
    print()
    print(prompt)
    print()

    if args.backup:
        write_backup(prompt, rules)


if __name__ == "__main__":
    main()

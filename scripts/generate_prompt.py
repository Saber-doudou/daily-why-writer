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
    python generate_prompt.py --update-automation # 生成 prompt 并更新到 automation 数据库
"""

import json
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Windows GBK 兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")


WORKSPACE = Path(r"F:\WorkBuddy\daily-why")
RULES_PATH = WORKSPACE / "config" / "writing_rules.json"
SKILL_PATH = Path(r"C:\Users\admin\.workbuddy\skills\daily-why-writer\SKILL.md")
SKILL_COMPACT_PATH = Path(r"C:\Users\admin\.workbuddy\skills\daily-why-writer\SKILL_COMPACT.md")
PYTHON_PATH = r"C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe"
TOPICS_CONTEXT = WORKSPACE / "config" / "topics_context.json"
TOPICS_CONTEXT_COMPACT = WORKSPACE / "config" / "topics_context_compact.json"
BACKUP_PATH = WORKSPACE / "archive" / "automation-prompt-backup.md"


def load_rules() -> dict:
    """加载 writing_rules.json"""
    if not RULES_PATH.exists():
        raise FileNotFoundError(f"规则文件不存在: {RULES_PATH}")
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def load_skill(compact: bool = False) -> str:
    """加载 SKILL.md（精简版或完整版）
    compact=True 时若 SKILL_COMPACT.md 不存在，自动降级为完整版 SKILL.md"""
    if compact and not SKILL_COMPACT_PATH.exists():
        compact = False  # 降级：回退到完整版
    path = SKILL_COMPACT_PATH if compact else SKILL_PATH
    if not path.exists():
        raise FileNotFoundError(f"Skill 文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def load_recent_topics(limit: int = 0, compact: bool = False) -> list:
    """从 topics_context.json 加载最近话题（用于去重提示）
    limit=0 表示加载全部标准话题（topic_summaries 已在 prepare_topics.py 中过滤为标准格式）
    compact=True 时使用精简版 topics_context_compact.json"""
    path = TOPICS_CONTEXT_COMPACT if compact else TOPICS_CONTEXT
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        summaries = data.get("topic_summaries", [])
        if limit > 0:
            return summaries[:limit]
        return summaries
    except Exception:
        return []


def get_fp_range() -> str:
    """从 FORBIDDEN.md 读取当前 FP 编号上限，避免 prompt 漏扫新规则"""
    fp_path = Path(r"C:\Users\admin\.workbuddy\skills\daily-why-writer\references\FORBIDDEN.md")
    if fp_path.exists():
        nums = re.findall(r"FP-(\d+):", fp_path.read_text(encoding="utf-8"))
        if nums:
            return f"FP-01到{max(int(n) for n in nums)}"
    return "FP-01到45"


def check_consistency(rules: dict, skill: str) -> list:
    """检查 writing_rules.json、SKILL.md、prompt 之间的一致性"""
    issues = []

    # 1. 字数：rules vs skill
    # 注意：只匹配真正的字数区间（如 300-600 字/中文字符），
    # 避免误匹配 SKILL.md 中"关键词2-6字"这类非字数区间（单数字 → \d{3,} 排除）
    wc_min = rules["word_count"]["min"]
    wc_max = rules["word_count"]["max"]
    wc_pattern = r"(\d{3,})[-~](\d{3,})\s*中?文?字"
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

    # 4. 风格表格行数（支持阿拉伯数字与中文数字，如"4 行"与"四行"）
    cn_num_map = {"一": "1", "二": "2", "三": "3", "四": "4",
                  "五": "5", "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}
    table_rows = rules["formatting"]["style_table_rows"]
    table_reprs = {str(table_rows)}
    for cn, arabic in cn_num_map.items():
        if str(table_rows) == arabic:
            table_reprs.add(cn)
    if not any(f"{r}行" in skill or f"{r} 行" in skill or f"统一 {r}" in skill
               for r in table_reprs):
        issues.append(f"风格表格行数: rules={table_rows}, SKILL.md 中未明确")

    # 5. 反转标签
    twist_label = rules["formatting"]["twist_label"]
    if twist_label not in skill:
        issues.append(f"反转标签: rules='{twist_label}', SKILL.md 中未找到")

    # 6. 分类选项一致性
    # 分类名可能在加粗、表格、或纯文本中，只要出现即可
    category_options = ["人体奥秘", "自然科学", "生活常识", "宇宙探索", "动物世界", "物理化学"]
    found_cats = [c for c in category_options if c in skill]
    if len(found_cats) < 3:  # 至少找到 3 个才算有效
        issues.append("SKILL.md 中未找到标准分类选项列表")

    return issues


def generate_prompt(rules: dict, recent_topics: list = None) -> str:
    """生成精简版 automation prompt（核心流程 + 增量规则，不重复 SKILL.md 已有内容）"""
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

前置检查：先检查 `F:/WorkBuddy/daily-why/articles/{{年月}}/{{今天日期}}-每日冷知识.md` 是否已存在，存在则跳过。
`{{今天日期}}` 取自系统注入的 `current_time`（ISO 格式），直接截取 YYYY-MM-DD 部分，**不要自行推算**。`{{年月}}` 为 YYYY-MM 格式。

失败处理：如果任意步骤出错或结果不符合要求，立即停止，不再继续后续步骤，并报告问题原因。

## 步骤
1. 加载 **daily-why-writer** skill，按其中 A+C+F 结构、排版格式、语言风格和黑名单写文章
2. 运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/prepare_topics.py` 刷新话题库（确保 topics_context.json 包含最新文章记录）
3. **外部源拉取优先**：用 WebSearch 检索 1 到 2 个关键词（如"冷知识 有趣""你知道吗 科学现象"），筛选 3 个候选话题（要求：现象具体、有科学反转点），逐个运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/check_topic.py --angle "候选"` 去重（退出码 0 → 选中；含"⚠️ 角度相关"提示 → 确认角度不同后采用；1 → 换下一个候选，最多 3 个；2 → 参数错误）。外部源失败 → 降级脑洞选题：读 `topics_context.json` 的 topic_summaries 选一个未曾使用的话题（优先选自然科学 / 生活常识 / 人体奥秘类）；仍失败 → 素材池兜底：从 `F:/WorkBuddy/daily-why/config/topic_candidates.json` 的 candidates 数组取候选；再失败 → 输出"⚠️ 今日选题失败"上报。落选候选用 Bash 回写素材池（source=external/rejected，已有则跳过，保持 JSON 合法）
{dedup_section}4. **写前快速查证**：用 WebSearch 搜 1-2 个该话题的关键词（中文），查证关键数字、研究者引用完整性（机构+年份+发表期刊）和引用准确性
5. **边写边自检**：按 A+C+F 结构写文章，字数 {wc_min}-{wc_max} 字。每写完一段（A/C/F），立即检查：
   - A段：是否以场景或小故事切入，避免套话开头
   - C段：Q格式是否正确（加粗，非h3）、逻辑是否自洽、F段是否与Q3重复、开头是否避免学术化句式
   - F段：长度是否与Q段均衡、是否用了「冷知识反转」标签
   - 最后一个问题（Q3）建议定位为辟谣或冷门延伸
6. **写后总检**：按 daily-why-writer skill 中的「写作自检清单」逐项检查，重点关注机制描述准确性
7. 保存到 `F:/WorkBuddy/daily-why/articles/{{年月}}/{{今天日期}}-每日冷知识.md`
8. 运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/validate_article.py` 审核
   - 如果审核不通过（审核脚本在 P0>0 或 P1>2 时 exit code 为 1），**先检索判例库再修正**：
     - 运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/case_matcher.py "问题关键词"` 智能匹配相关判例
     - 参考判例中的「修正方案」进行修正
     - 修正后重新运行 validate_article.py 验证
   - 如果审核通过，继续下一步
9. 运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/update_history.py` 更新记忆
"""
    return prompt


def generate_multi_agent_prompt(rules: dict, recent_topics: list = None) -> str:
    """生成多Agent版本的 automation prompt（Orchestrator 写作 + spawn 独立 Reviewer 审校，v2.0 熔断链）"""
    wc_min = rules["word_count"]["min"]
    wc_max = rules["word_count"]["max"]

    PYTHON = "C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe"
    SKILL_DIR = "C:/Users/admin/.workbuddy/skills/daily-why-writer"
    fp_range = get_fp_range()

    prompt = f"""每日冷知识自动化：Orchestrator 写作 + 独立 Reviewer 审校模式（v2.0，spawn 独立审校子 agent，自审仅作熔断降级）。

前置：用 glob `F:/WorkBuddy/daily-why/articles/**/{{今天日期}}-每日冷知识*.md` 检查，已存在则跳过。{{今天日期}}截取自系统 current_time。失败处理：任意步骤出错立即停止并报告。

## 阶段0：强制加载写作SOP（必须在写任何字之前完成）

**优先执行①，若失败则执行②；未完成 SOP 加载不得进入阶段1。**

① 调用 Skill 工具，参数 skill=`daily-why-writer`。将返回的 SKILL.md 完整内容作为本轮写作的唯一权威 SOP；
② 若上述调用失败（当前环境无 Skill 工具或调用报错），则用 Read 工具读取文件全文：
   `{SKILL_DIR}/SKILL.md`
   将读取到的完整内容作为本轮写作 SOP。

加载完成后，写作、自查、精修三个阶段严格以 SKILL.md 的最新内容为准。

加载成功后，必须在对话中显式输出确认："✅ SOP已加载：daily-why-writer SKILL.md，含A+C+F结构、排版格式、黑名单等全部写作规范。"未输出此确认不得进入阶段1。

## 阶段1：选题+写作（Orchestrator 亲自执行）

前置：阶段0的 SOP 已加载。所有写作规范以 SOP 为准。

1. 运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/prepare_topics.py --compact` 刷新话题库
2. **外部源拉取（选题主源，优先执行）**：用 WebSearch 检索 1 到 2 个关键词（如"冷知识 有趣""你知道吗 科学现象"，或指定源：维基百科/百度百科你知道吗、果壳、知乎科普），从搜索结果中筛选 3 个候选话题（要求：现象具体、有科学反转点、与已有话题不重复）
3. **去重校验**：按顺序对每个候选运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/check_topic.py --angle "候选话题"`：
   - 退出码 0 且输出无"⚠️ 角度相关"提示 → 选中该候选，进入步骤 4
   - 退出码 0 但输出含"⚠️ 角度相关（相似度 X%）"提示 → 角度放宽：确认写作角度与已有话题确实不同后允许采用
   - 退出码 1 → 换下一个候选（最多试 3 个候选）
   - 退出码 2 → 参数错误，修正话题文本后重试
4. **选中后查证**：用 WebSearch 查证 1 到 2 个关键词：关键数字、研究者引用完整性（机构+年份+期刊）、引用准确性
5. **落选话题回写素材池**：本轮拉取/筛选过程中未采用的候选（含查证后放弃的），用 Bash 追加/更新到 `F:/WorkBuddy/daily-why/config/topic_candidates.json` 的 candidates 数组（source 字段标记 `external` 或 `rejected`；已有则跳过），保持 JSON 合法
6. **降级链**（外部源拉取失败或无可用候选时按序降级）：
   - 降级① 脑洞选题：读 `F:/WorkBuddy/daily-why/config/topics_context_compact.json` 的 topic_summaries，自己想一个新话题，运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/check_topic.py --angle "话题"` 校验（退出码 0 → 继续；1 → 重选，最多 3 轮；2 → 参数错误）
   - 降级② 素材池兜底：从 `F:/WorkBuddy/daily-why/config/topic_candidates.json` 的 candidates 数组取候选，同样运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/check_topic.py --angle "话题"` 校验
   - 降级③ 仍失败 → 触发下方选题失败上报，不得静默终止
7. 按阶段0加载的 SOP（SKILL.md）写文章，字数{wc_min}-{wc_max}
8. 保存到 `F:/WorkBuddy/daily-why/articles/{{年月}}/{{今天日期}}-每日冷知识-{{关键词}}.md`（关键词2-6字，{{年月}}为YYYY-MM格式）

【硬约束】选题失败上报：若外部源拉取、脑洞选题、素材池兜底全部失败（候选均被 check_topic.py 判重复），必须输出"⚠️ 今日选题失败：失败候选列表 + 3 个建议新方向"，不得静默终止。

## 阶段2：独立 Reviewer 审校（spawn 子 agent 为主路径，v2.0）

初稿写入文件后，使用 Agent 工具 **spawn 独立审校子 agent**（禁止 Orchestrator 自己审，maker-checker）。**禁止传 name 参数**（name 依赖 team 上下文，本地 automation 环境必失败；08-13 实证去掉 name 后 spawn 成功，08-20 本项目实证成功）。

**spawn 参数**：
- subagent_type: "general-purpose"
- model: "reasoning"
- 任务内容（原样传入子 agent）：
  1. Read 读取 `{{初稿文件完整路径}}`
  2. 运行脚本审核：`{PYTHON} F:/WorkBuddy/daily-why/scripts/validate_article.py --json "{{初稿文件完整路径}}"`，记录 P0/P1/P2 与得分
  3. Read 加载 `{SKILL_DIR}/references/CHECKLIST.md` 逐项人工对照扫描
  4. Read 加载 `{SKILL_DIR}/references/FORBIDDEN.md`，逐条扫描文件中【全部】FP 规则（数量以文件实际内容为准，不要写死编号）
  5. Read 加载 `{SKILL_DIR}/reviewer_prompt.md`，**严格执行其中的 P0/P1/P2 分级标准**：P0=事实错误/逻辑矛盾/结构缺失；P1=AI味/连接词≥3、字数>600、类比失准、**绝对化**；P2=措辞微调。凡命中「绝对化/类比失准/字数>600」至少标 P1，**禁止降为 P2**
  6. **事实断言独立核验**：对文中人物/机构/亲缘关系/年份/数据类断言，用 WebSearch 独立核实至少 2 处关键断言，发现事实错误标记 P0
  7. 最小结构验证（不依赖 SKILL.md 写作规则）：A段引用块（>开头）、C段Q格式（**Q1/Q2/Q3：**）、F段引用块含"冷知识反转"标签、结尾风格表格（四行）。任一缺失即 P0 结构缺失
  8. 输出审核报告**写入文件** `F:/WorkBuddy/daily-why/review/{{今天日期}}_review.json`（含 pass/p0_count/p1_count/p2_count/score/review_timestamp/issues 数组，每项含 level/category/description/suggestion）。**`review_timestamp` 必须先用 Bash 执行 `date +%Y-%m-%dT%H:%M:%S%z` 取系统真实时间写入，禁止自行推断或编造时间**。并在最终回复文本中回报审校结论（SendMessage 在本地 automation 环境不可用，以文本回报兜底）
  9. 通过条件：P0=0 且 P1≤2

**等待策略（文件检测优先）**：
1. spawn 成功后每 1 分钟轮询检查 `F:/WorkBuddy/daily-why/review/{{今天日期}}_review.json` 是否已生成
2. reviewer 显式上限 15 分钟（spawn 成功起算），超时 → 按熔断降级
3. 检测到 review.json 已生成（或收到 reviewer 文本回报）→ 继续；**不等待 SendMessage**

**熔断链（兜底路径）**：spawn 报 team 上下文错误 → 去掉 name 参数重试 1 次 → 仍失败 → **熔断**（本次不再尝试 spawn）→ Orchestrator 自审（加载 CHECKLIST.md + FORBIDDEN.md 执行审校）→ 输出标注「⚠️ 未独立审校」。自审仅为降级路径，独立 reviewer 是主路径。

【硬约束】审校由 spawn 的独立 reviewer 完成，Orchestrator 不得自己审。若降级为自审，必须标注「⚠️ 未独立审校」。输出 JSON / Markdown 时，禁止使用 `~` 作为区间/范围连接符；一律用中文"到"或"至"。例如：400到700纳米，不得写 400~700。

【硬约束】审校降级标记：若熔断链触发（spawn 失败/超时/空返回），输出带「⚠️ 未独立审校」标记并继续，不得阻塞。

## 阶段3：修复+输出（Orchestrator 根据审校报告）

- 通过（P0=0且P1≤2）→ 直接进入输出
- 不通过 → 根据报告中的 issues 修复文章 → 写入文件 → 重新 spawn Reviewer 审校（最多2轮）
- 2轮后仍不通过 → 标记"⚠️ 需人工审核"，输出当前最佳版本
- **防死循环**：连续 2 轮审校指向同一 P 级问题且修复无实质改进 → 停止迭代，标记"⚠️ 需人工审核"并输出当前最佳版本
- 输出：文件路径、审核得分、P0/P1/P2 数、审校方式（独立 reviewer / ⚠️未独立审校）
- 运行 `{PYTHON} F:/WorkBuddy/daily-why/scripts/update_history.py` 更新记忆

## 阶段4：创建投喂素材文件夹

所有阶段完成后，创建当天的投喂素材文件夹：

1. 提取日期：从系统 current_time 截取 YYYYMMDD 格式（如 20260623）
2. 使用 Bash 工具执行：
   ```bash
   mkdir -p "F:/WorkBuddy/daily-why/投喂素材/{{YYYYMMDD}}" && touch "F:/WorkBuddy/daily-why/投喂素材/{{YYYYMMDD}}/ds.txt" "F:/WorkBuddy/daily-why/投喂素材/{{YYYYMMDD}}/ima.txt" "F:/WorkBuddy/daily-why/投喂素材/{{YYYYMMDD}}/千问.txt" "F:/WorkBuddy/daily-why/投喂素材/{{YYYYMMDD}}/豆包.txt"
   ```
3. 输出：✅ 已创建投喂素材文件夹 `F:/WorkBuddy/daily-why/投喂素材/{{YYYYMMDD}}/`，含4个空txt文件（ds.txt、ima.txt、千问.txt、豆包.txt）"""

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
    parser.add_argument("--update-automation", action="store_true",
                        help="生成 prompt 并更新到 automation 数据库")
    parser.add_argument("--compact", action="store_true",
                        help="使用精简版 SKILL.md 和 topics_context.json，减少 Token 消耗")
    parser.add_argument("--multi-agent", action="store_true", default=True,
                        help="生成多Agent版本的 prompt（默认开启）")
    parser.add_argument("--single-agent", action="store_true",
                        help="强制单Agent模式（覆盖 --multi-agent）")
    args = parser.parse_args()

    # 加载规则
    rules = load_rules()
    skill = load_skill(compact=args.compact)

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
    recent = load_recent_topics(0, compact=args.compact)  # 精简版加载全部话题

    # 生成 prompt（--single-agent 覆盖 --multi-agent）
    if args.single_agent:
        prompt = generate_prompt(rules, recent)
        mode = "精简版" if args.compact else "完整版（单Agent）"
    else:
        prompt = generate_multi_agent_prompt(rules, recent)
        mode = "多Agent版（默认）"

    print("=" * 60)
    print("📋 生成的 Automation Prompt")
    print(f"   规则版本: writing_rules.json v{rules['_version']}")
    print(f"   字数范围: {rules['word_count']['min']}-{rules['word_count']['max']}")
    print(f"   最近话题: {len(recent)} 个（用于去重）")
    print(f"   模式: {mode}")
    print("=" * 60)
    print()
    print(prompt)
    print()

    if args.backup:
        write_backup(prompt, rules)

    if args.update_automation:
        # 写入到固定文件，供外部脚本读取
        latest_path = WORKSPACE / "config" / "automation-prompt-latest.txt"
        latest_path.write_text(prompt, encoding="utf-8")
        print(f"[generate_prompt] Prompt 已写入: {latest_path}")
        print(f"[generate_prompt] 请运行以下命令更新 automation:")
        print(f"  automation_update mode=update id=automation-1778312519754 prompt=< {latest_path}")


if __name__ == "__main__":
    main()

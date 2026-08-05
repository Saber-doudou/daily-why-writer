---
name: daily-why-writer
description: >
  每日冷知识科普文章写作助手。按 A+C+F 结构（故事开头→疑问驱动→反转收尾）
  撰写 300-600 字趣味科普。含排版规范、科学准确性自检（CHECKLIST.md）、
  标点纠错（GB/T 15834）。触发词：每日一个为什么、每日一个为什么写作、
  dailywhy、dailywhy写作、每日冷知识。
agent_created: true
last_updated: 2026-08-04
---

# daily-why-writer

每日冷知识（"每日一个为什么"）文章的写作 skill。

## 元规则

1. **教训没有不可泛化的** — 每次出错分析根因，提炼为可复用规则，记录到 FEEDBACK_LOG
2. **三层分离，按需加载**：本文件 = 核心法典（Always Load）；`references/CHECKLIST.md` = 科学准确性自检（写后加载）；`references/FORBIDDEN.md` = 黑名单 FP-01~65（写后加载）；`references/FEEDBACK_LOG.md` = 活跃教训（30天内，审校时按需检索）；`references/FEEDBACK_ARCHIVE.md` = 休眠教训（30天未再犯，手动查阅）；`references/EXAMPLES.md` = 好/坏案例（写作时按需查阅）
3. **数值规则内联**：本文已内联所有关键阈值，`writing_rules.json` 仅供 `validate_article.py` 程序化验证

---

## 工作流总览

```
选题 → 去重校验(check_topic.py) → 写前查证(WebSearch) → 写作(A+C+F) → 写后自检(CHECKLIST+FORBIDDEN) → 审核(validate_article.py) → 记录(update_history.py)
```

**决策树**：选题完成→[check_topic.py 退出码1?]→YES:重选话题(最多3轮) / NO:继续。用户确认→[自动模式?]→YES:跳过 / NO:🟡等"OK"。初稿→[字数>600?]→YES:删C段冗余 / NO:继续。自检→[P0>0?]→YES:修复重检(最多3轮) / NO→[P1>2?]→YES:🟡问用户 / NO:✅。审核→[validate失败?]→YES:修复(最多2轮) / NO:✅发布。

---

## Phase 0：选题与去重

1. **读取已有话题**：读 `F:\WorkBuddy\daily-why\config\topics_context.json` 的 `topic_summaries` 数组，了解所有已用话题
2. **选题**：自己想一个新话题（不在 topic_summaries 中），分类从 6 个标准中选一：人体奥秘 / 自然科学 / 生活常识 / 宇宙探索 / 动物世界 / 物理化学
3. **检查点**（非自动模式）：展示已选话题，等待用户确认

### Phase 0.5：去重校验（强制，不可跳过）

选题后、写文章前，**必须**运行机械校验脚本：

```bash
C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe F:/WorkBuddy/daily-why/scripts/check_topic.py "你选的话题"
```

- **退出码 0** → 通过，进入 Phase 1
- **退出码 1** → 重复！回到 Phase 0 重选（最多 3 轮，仍失败则终止并报告）
- **退出码 2** → 参数错误，检查话题格式

> ⚠️ 此步骤是机械性防护网，不依赖 AI 判断力。即使你确信话题没写过，也必须跑这个脚本。
>
> 若 3 轮选题均被 check_topic.py 判定重复，终止并报告"⚠️ 今日选题失败，需人工介入"。

---

## Phase 1：写前查证

用 WebSearch 搜 1-2 个关键词：查证关键数字（距离、倍数、温度），争议表述要修正；**核实机构名和研究者姓名**（如"英格兰大学"不存在→应为"曼彻斯特大学"）；**搜索最新科学机制**（搜"XX 机制 最新研究"）；看看同类科普有无辟谣/误区内容；确认反转是否独特。纯常识类话题（海水咸、天蓝）可跳过。

> ⚠️ WebSearch 失败或无结果时：使用已有常识写作，标注"⚠️ 未查证"，在 F 段注明"建议读者自行确认"。不得因搜索失败而终止流程。

---

## Phase 2：写作（A+C+F 结构）

### 结构模板

```
# emoji 为什么xxx？
> A段：场景描写，引用块包裹...
---
**Q1：问题？** → 答案
**Q2：问题？** → 答案
**Q3：问题？** → 答案
---
> emoji **冷知识反转**：反转内容...
| 话题 | 为什么xxx？ | 分类 | 6选1 |
| 核心机制 | 一句话 | 冷知识反转 | 一句话 |
```

### 排版格式（硬性规则，违者 P0/P1）

| 项 | 要求 |
|---|---|
| **标题** | emoji + 疑问句 |
| **Q 格式** | 统一 `**Q1：xxx？**` 加粗，**禁止** h3 格式（P0） |
| **分隔线** | 恰好 2 处：A段后 + F段前。Q 之间**不加**（>2→P0） |
| **引用块** | A 段和 F 段必须 `>` 包裹，C 段不用 |
| **F 段标签** | 统一 `> emoji **冷知识反转**：`，禁止"冷知识彩蛋" |
| **加粗** | `**` 突出 2-3 个关键概念 |
| **风格表格** | 结尾必须附：话题/分类/核心机制/冷知识反转 四行 |

### 内容规则

- **A 段**：≥1 感官细节 + ≥1 具体动作；禁止套话开头（"今天我们来""随着""在当今"等黑名单词）
- **C 段**：3-4 个递进问题（基础→进阶→延伸/辟谣，<2→P0，<3→P1）；Q 段逻辑自洽（表面矛盾必须搭桥）；"研究表明"≤1 处
- **F 段**：提供 Q3 之外的新角度；长度与 Q 段相当；反转后可加闭环收尾；反转≤15 字可转述
- **字数**：300-600 中文字符（>600→P1）
- **语言**：轻松生动，大众读者；人称统一；连接词 ≤2 处（≥3→P1）

---

## Phase 3：写后自检

1. 加载 `references/CHECKLIST.md` 逐项检查科学准确性
2. 加载 `references/FORBIDDEN.md` 扫描 FP-01~65
3. **标点自查**（5 项高频陷阱，GB/T 15834-2011）：

| # | 陷阱 | 错误 → 正确 |
|---|------|-------------|
| 1 | 概数间加顿号 | 七、八月 → 七八月 |
| 2 | 省略号与"等"并用 | ……等 → 二选一 |
| 3 | 书名号并列加顿号 | 《A》、《B》 → 《A》《B》 |
| 4 | 非疑问句用问号 | 我不知道他是谁？ → 我不知道他是谁。 |
| 5 | 同一句两个冒号 | 研究表明：因素：X → 研究表明，因素：X |

> 问号依据：句子是否表示疑问语气，而非句中是否含疑问词（GB/T 15834-2011）

### 质量门禁

| 级别 | 判定 | 处理 |
|------|------|------|
| **P0 致命** | 事实错误、逻辑矛盾、结构缺失、Q用h3、分隔线>2 | 必须清零（最多3轮） |
| **P1 重要** | AI味/连接词≥3、字数>600 等 | 最多允许 2 个 |
| **P2 一般** | 措辞微调、风格表格不完整 | 不设限 |

通过条件：**P0=0 且 P1≤2**。常见修复：字数超→删 C 段冗余；Q 逻辑不自洽→搭桥；F 段短→补延伸知识；学术化→改主动。

---

## Phase 4：审核与发布

1. 保存文章到 `F:\WorkBuddy\daily-why\articles\{YYYY-MM}\{日期}-每日冷知识-{话题关键词}.md`
   - 文件名格式：`{YYYY-MM-DD}-每日冷知识-{关键词}.md`
   - 关键词从话题中提取，2-6 字，如"手指泡水起皱""打哈欠""海水是咸的"
   - 示例：`2026-06-08-每日冷知识-手指泡水起皱.md`（保存到 `articles/2026-06/` 目录）
2. 运行 `scripts/validate_article.py` 验证（最多 2 轮）
3. 运行 `scripts/update_history.py` 更新话题记录
4. 有新教训 → 记录到 `references/FEEDBACK_LOG.md`

**自动模式**：`--auto` 跳过所有确认检查点，用于 cron 定时任务。

---

## 三 Skill 架构

```
L1: daily-why-writer（本文件）— 每日09:40自动运行，产出v1
L2: daily-why-feed-learning — 四AI投喂学习，产出v2+新规则
L3: daily-why-publish — 匹配检查+IMA备份+GitHub推送+记忆归档
```

| Skill | 路径 | 触发词 |
|-------|------|--------|
| L1 写作 | `~/.workbuddy/skills/daily-why-writer/` | 写冷知识、每日冷知识 |
| L2 投喂 | `~/.workbuddy/skills/daily-why-feed-learning/` | 投喂学习、四AI学习 |
| L3 发布 | `~/.workbuddy/skills/daily-why-publish/` | 发布、推送、备份 |

---

## 🤖 多 Agent 执行模式（v1.0）

> **1 Agent spawn 模式**：Orchestrator 亲自选题+写作+自检+精修，只 spawn Reviewer 做独立审校。

| 角色 | 职责 | 阶段 | 加载模块 | 预估 Token |
|------|------|------|---------|:---:|
| **Orchestrator**（Automation 自身） | 选题 + 写作 + 自检 + 精修 + 输出 + 记忆更新 | Phase 0-2, 4-5 | 写作阶段: SKILL.md + topics_context.json；精修阶段: + CHECKLIST.md + FORBIDDEN.md | 峰值~20K |
| **reviewer**（spawn） | 独立审校 + 脚本审核 + 判例检索 | Phase 3 | reviewer_prompt.md + CHECKLIST.md + FORBIDDEN.md | ~12K |

### 模块化设计原则
- Orchestrator 写作阶段不加载 CHECKLIST.md/FORBIDDEN.md —— 避免"知道考纲做题"
- Orchestrator 精修阶段加载 CHECKLIST.md/FORBIDDEN.md —— 精准修复
- Reviewer 不加载 SKILL.md 写作规则 —— 纯粹的审核视角
- CASE_STUDIES.md 按需检索，不塞进上下文

### 执行流程

```
Phase 0: 防重跑检查（今日文章是否已存在）
    ↓
Phase 1: 【Orchestrator】选题 + check_topic.py 去重 + WebSearch 查证
    ↓
Phase 2: 【Orchestrator】A+C+F 写作 + 写后自检
    ↓
Phase 3: 【Orchestrator】初稿写入文件 → spawn reviewer
    ↓
Phase 3.5: 【reviewer 独立审校】
    - 读取初稿
    - 运行 validate_article.py
    - 按 CHECKLIST + FORBIDDEN 逐项检查
    - 按需 Grep CASE_STUDIES.md
    - 输出 review_report.json
    ↓
    若 P0=0 且 P1≤2 → Phase 4（通过）
    否则 → Phase 4（修复循环）
    ↓
Phase 4: 【Orchestrator】收到审核报告
    - 通过 → 直接输出 + 记忆更新
    - 不通过 → 按报告修复 → 写入文件 → re-spawn reviewer（最多 2 轮）
    - 2 轮后仍不通过 → 标记"⚠️ 需人工审核"，输出当前最佳版本
    ↓
Phase 5: 【Orchestrator】输出全文 + update_history.py + 记忆更新
```

**效率规范**：网络请求上限3次；记忆更新合并为1次。

### Agent 级异常处理

| 场景 | 处理策略 |
|------|---------|
| reviewer 超时（10分钟无响应） | Orchestrator 跳过审校，直接输出初稿 + 标注"⚠️ 未审校" |
| reviewer spawn 失败 | 重试 1 次 → 仍失败 → 跳过审校 |
| reviewer 返回空结果 | Orchestrator 重试 1 次，仍为空则跳过审校 |
| validate_article.py 脚本执行失败 | reviewer 降级为纯 AI 审校（不依赖脚本） |

### 迭代终结条件

- 审校通过（P0=0 且 P1≤2）→ 输出文章
- 审校不通过 → Orchestrator 直接修复 → reviewer 重新审校（最多 2 轮）
- 2 轮后仍不通过 → 标记"⚠️ 需人工审核"，输出当前最佳版本

### 消息协议

reviewer → orchestrator：
```json
{ "agent": "reviewer", "status": "done", "file": "{date}_review.json", "p0_count": 0, "p1_count": 1, "pass": true, "score": 95 }
```

---

## 相关文件索引

| 文件 | 用途 | 加载时机 |
|------|------|---------|
| `references/CHECKLIST.md` | 70 项科学准确性自检（含 FP 交叉引用） | Phase 3 |
| `references/FORBIDDEN.md` | 65 条禁止模式 FP-01~65 | Phase 3 |
| `references/FEEDBACK_LOG.md` | 教训→规则转化记录（30天内活跃） | 按需检索 |
| `references/FEEDBACK_ARCHIVE.md` | 休眠教训库（30天未再犯） | 手动查阅 |
| `references/EXAMPLES.md` | A段/F段/Q格式好/坏案例 | 写作时查阅 |
| `CODE_REVIEW_GUIDE.md` | Python 脚本代码审查标准 | 改脚本时查阅 |
| `writing_rules.json` | 程序化验证数据源 | validate_article.py |
| `validate_article.py` | 格式+质量自动审核 | Phase 4 |
| `update_history.py` | 话题去重记录更新 | Phase 4 |
| `reviewer_prompt.md` | Reviewer Agent 审校 prompt | Phase 3（spawn 时加载） |

## 风格样本

一篇合格文章：看标题想点 → 第一段被带入场景 → 3 个问题牵着走 → 结尾反转"打脸" → 记住一个冷知识。

**结构速查**：
```
# 🦷 为什么咬到舌头会特别疼？
> 你正啃着鸡腿，突然"咔嚓"一声——牙齿狠狠咬在舌头侧面。那种钻心的疼，比被针扎还让人跳起来...
---

**Q1：舌头不是全身最灵活的肌肉吗？怎么这么脆弱？** → 答案
**Q2：为什么咬到舌头比咬到嘴唇疼那么多？** → 答案
**Q3：有没有办法让咬伤好得快一点？** → 答案
---

> 🧠 **冷知识反转**：舌头的愈合速度是身体其他部位的3倍...
| 话题 | 舌头咬伤特别疼 | 分类 | 人体奥秘 |
| 核心机制 | 舌头密布痛觉感受器，神经末梢密度是皮肤的6倍 | 冷知识反转 | 舌头愈合速度是身体最快，约3天即可痊愈 |
```

---
*Version: v3.1 | 2026-07-08 | FP-46(模糊量词) + CHECKLIST §40(恒星能量来源术语)*
*Version: v3.1 | 2026-07-09 | + FP-47(化学感官类比因果倒置) + CHECKLIST §41(比例区分研究类型)/§42(感官差异感知属性)*
*Version: v3.1 | 2026-07-14 | + FP-49(辟谣一刀切否定中间态) + CHECKLIST §47(标题概念域一致性)*
*Version: v3.1 | 2026-07-15 | + FP-50(极限值须标理论极限前提) + FP-51(结构数值须WebSearch核实) + CHECKLIST §48(分级结构层级数量区分)*
*Version: v3.1 | 2026-07-17 | + FP-52(物理过程动词不精确) + CHECKLIST §49(天文坐标标注坐标系)/§50(A段→C段过渡衔接)*
*Version: v3.1 | 2026-07-17 | + FP-53(薄膜干涉黑膜成因遗漏半波损失) + FP-54(干涉类表述主动误导) + CHECKLIST §51(光学干涉覆盖半波损失)/§52(干涉因果表述避免主动误导)
*Version: v3.1 | 2026-07-23 | + FP-55(冷知识反转与前文逻辑断裂) + FP-56(结尾口号式说教) + CHECKLIST §53(反常现象开头须前置条件限定)/§54(科学新闻引用的论文归属核查)*
*Version: v3.1 | 2026-07-23 | + FP-57(湿表面现象区分光照条件) + CHECKLIST §55(湿表面现象须区分光照条件)*
*Version: v3.1 | 2026-07-23 | + CHECKLIST §56(防御/保护功能反转须展开具体机制)（投喂学习）*
*Version: v3.1 | 2026-07-23 | + FP-58(误区纠正只破坏不重建) + CHECKLIST §57(生化/机制叙事优先提供类比锚点)（喝酒脸红 投喂学习）*
*Version: v3.1 | 2026-07-24 | + FP-59(季节性变化"一直都在"静态绝对化表述) + CHECKLIST §58(相邻Q段内容边界不重叠)/§59(A段感官细节内部自洽)/§60(避免"一直都在"静态表述)（树叶变红 投喂学习）*
*Version: v3.1 | 2026-07-27 | + FP-60(光学反射性结构术语混淆) + CHECKLIST §61(明毯用词精度)/§62(F段表格内容差异化)（猫眼发亮 投喂学习）*
*Version: v3.1 | 2026-07-28 | + FP-61(食品加工动词与实物加工方式不符) + CHECKLIST §63(并列成分各因素权重准确性)（面包变硬 投喂学习）*
*Version: v3.1 | 2026-07-29 | + FP-62(密度变化误用"变轻/变重")（冰浮水面 投喂学习）*
*Version: v3.1 | 2026-07-30 | + FP-63(高压环境蛋白质变性类比喻混淆热变性) + CHECKLIST §64(高压/压强Topic蛋白质变性描述用压力专属动词)（深海鱼压不扁 投喂学习）*
*Version: v3.1 | 2026-07-31 | + FP-64(机制拟人化感知/躲避归属错误) + CHECKLIST §65(机制终止归因须指向物理过程停止)/§66(倍数数据须限定时段场景)/§67(机制断言须给实验证据)（向日葵转头 投喂学习）*
*Version: v3.1 | 2026-08-03 | + FP-65(用疾病/病理术语解释正常现象) + CHECKLIST §68(相关数值间须说明衔接逻辑)/§9细化(引用融入行文)/§66案例(五成为主观感受范围)（月亮错觉 投喂学习）*
*Version: v3.1 | 2026-08-04 | + CHECKLIST §69(概括动词须覆盖并列全部机制)/§70(历史考古断言须加证据强度与前提限定) + 修复§57内容错乱（蜂蜜不坏 投喂学习）*
*Version: v3.1 | 2026-08-05 | + CHECKLIST §71(同一现象/参数表述须前后一致)/§72(习惯化等基础学习形式勿简化为学会/学习)/§73(强因果关联知识点须点明因果链)（含羞草缩叶 投喂学习）*

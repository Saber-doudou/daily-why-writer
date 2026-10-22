---
name: daily-why-feed-learning
description: >
  四AI投喂学习技能 — 通过4个AI（DeepSeek/IMA/千问/豆包）的优化建议对比学习，
  自动重写优化版文章、提炼新规则、升级每日冷知识写作技能。
  触发词：每日一个为什么学习、每日一个为什么学习总结、每日一个为什么投喂、dailywhy学习、dailywhy学习总结。
  路由规则：凡输入含「学习/投喂/总结」动作词（如 dailywhy学习总结），本技能优先于
  其他 dailywhy 系列技能触发（动作词优先，最高优先级），触发即执行 L2 全流程。
agent_created: true
last_updated: 2026-09-01
version: v3.3
---

# daily-why-feed-learning

四AI投喂学习技能 — 通过4个AI（DeepSeek/IMA/千问/豆包）的优化建议对比学习，自动重写优化版文章、提炼新规则、升级每日冷知识写作技能。

---

## 触发裁决（先于一切执行，最高优先级，2026-08-28 新增）

收到以下任一触发词，**必须立即调用 Skill 工具加载本技能并显式输出「✅ L2 SOP已加载」**，随后进入 Phase 0：

- 每日一个为什么学习 / 每日一个为什么学习总结 / 每日一个为什么投喂
- dailywhy学习 / dailywhy学习总结

**硬约束（违反即流程失败）：**
1. 禁止仅确认收到后等待（违反「已知触发词直接执行不追问」全局铁律）。
2. 禁止把「学习总结」解读为「生成学习总结报告」（名词义误读）——`dailywhy学习总结` 是执行指令，不是报告请求。
3. **动作词优先**：当输入同时可匹配多个技能（如 L1 的 dailywhy 前缀冲突）时，凡含「学习/投喂/总结」动作词，一律路由到本技能，本技能优先级最高。
4. 触发后先执行 Phase 0 输入验证；若素材不足（有效 AI 少于 2），按 Phase 0 话术明确提示缺哪几个 AI 及投喂路径，不得静默终止。
5. 路由以 `F:\WorkBuddy\daily-why\config\skill-trigger-map.json` 为唯一权威源，触发前先读该表核对。

---

## 设计哲学

**核心理念**：通过"我写一版 → 4个AI各给建议 → 对比差距 → 吸收最优"的循环，持续进化写作能力。

**进化闭环**：
```
L1 自动化产出 v1（daily-why-writer，每日09:40自动运行）
     ↓
Master 手动投喂素材（4AI点评优化版）
     ↓
L2 Skill 自动学习 → v2 + 新规则
     ↓
新规则写入 skill → 下次 L1 自动化时生效
     ↓
L3 验证 + 发布（daily-why-publish）
     ↓
循环往复，能力持续提升
```

---

## 投喂素材规范

### 目录结构
```
投喂素材/{YYYYMMDD}/
├── ds.txt              ← DeepSeek 点评优化+版本
├── ima.txt             ← IMA 点评优化+版本
├── 千问.txt            ← 通义千问 点评优化+版本
├── 豆包.txt            ← 豆包 点评优化+版本
└── 学习总结.md         ← Phase 5 产出（学习完成后生成）
```

### 最低要求
- 至少有 2 个 AI 的完整素材
- 每个 AI 的文件必须包含对原文的点评+优化建议（非纯点赞）

---

## 执行流程

### Phase 0: 输入验证
1. 读取投喂素材文件夹路径：`F:\WorkBuddy\daily-why\投喂素材\{YYYYMMDD}\`
2. 验证文件夹存在且包含有效素材文件
3. 统计有效 AI 数量（至少 2 个）
4. 确认对应初版文章存在：`F:\WorkBuddy\daily-why\articles\{YYYY-MM}\{YYYY-MM-DD}-每日冷知识-*.md`
5. 若素材不足 → 提示用户补充，终止
6. 若无当日文章 → 提示先运行 L1 自动化

### Phase 1: 差额分析

**F1 素材完整性检查点（09-01 新增）**：开始差额分析前，先核对 4 个素材文件**非空壳**（`ls -la 投喂素材/{YYYYMMDD}/`，正常 4 到 6 KB 以上；接近 0 字节 = L2 未真执行），并向 Master 展示素材摘要（4 个文件大小 + 是否齐全），确认后进入差额分析。

**F3 字数口径核对（09-01 新增，Master 决策后统一全文口径）**：差额分析及学习总结记录字数时，以 `validate_article.py --json` 实测的 `char_count`（全文口径，含结尾表格，上限 690）为准；**禁止手写/估算字数**（历史多次实证 AI 自记字数系统性失真，09-01 差 84 字）。与 `l3_publish.py` 的 `chinese_chars` 应一致。

1. 读取初版文章全文
2. 逐家读取 4 个 AI 的优化建议：
   - `ds.txt` / `ima.txt` / `千问.txt` / `豆包.txt`
3. **差额分析矩阵**：

| 分析维度 | 我的版本 | 最佳AI版本 | 差距 |
|---------|---------|-----------|------|
| 事实覆盖 | [列出] | [列出] | [缺失事实] |
| 比喻质量 | [我的比喻] | [AI比喻] | [比喻差距] |
| 数据精确度 | [我的数据] | [AI数据] | [数据差距] |
| 结构完整度 | [A+C+F] | [AI结构] | [结构差距] |
| 记忆点强度 | [我的反转] | [AI反转] | [反转差距] |

4. **高频问题提取**：
   - 4 家都指出的问题 → P0 必须修正
   - 3 家指出的问题 → P1 优先修正
   - 2 家指出的问题 → P2 可选修正

5. **事实修正清单**：
   - 数据范围错误 → 标记需 WebSearch 二次核实
   - 术语错误（如"遗传病"）→ 标记
   - 格式外功能（互动/投票/预告）→ 标记拒绝
   - ⚠️ **信源甄别（08-25 教训，强制）**：AI 的"事实性指控"不能直接采信——4家AI可能引用同一错误信源（IMA 曾把今日头条"玻璃碗贴不住/绝缘体电荷扩散"当 P0 硬伤指控初版，与权威源 BBC Science Focus/How It Works/百度知道矛盾，实为错误信源复述）。**多数 AI 一致 ≠ 正确**；凡涉及物理机制/数据/人物等事实指控，必须回归权威源独立核实后再决定采纳或拒绝

6. **各AI独特贡献提取**：
   - DeepSeek：事实核查+比喻创意
   - IMA：前沿科学+量化数据
   - 千问：结构分析+表格扩展
   - 豆包：表达润色+口语化过渡

### Phase 1.5: 用户确认（⚠️ 暂停等待确认）

差额分析完成后，**暂停执行**，向用户展示分析摘要：

```
## 差额分析摘要

### 核心差距（3-5条）
1. [最重要的差距]
2. [第二重要的差距]
3. [第三重要的差距]

### P0 事实修正（必须修正）
- [事实1]
- [事实2]

### 各AI亮点采纳
- DeepSeek：[采纳项]
- IMA：[采纳项]
- 千问：[采纳项]
- 豆包：[采纳项]

### 拒绝项（格式外/数据错/不适用）
- [拒绝项1] — [原因]
- [拒绝项2] — [原因]

确认后继续重写？[确认/调整方向/跳过]
```

**等待用户确认**：
- 用户回复"确认" → 继续 Phase 2
- 用户回复"调整方向" → 根据用户反馈调整分析方向，重新展示
- 用户回复"跳过" → 终止本次学习

**⚠️ 调整方向后重新校验**：
若用户调整了采纳清单，Phase 2 第4点的 Grep 验证必须基于**更新后的采纳清单**，而非原始清单。

### Phase 2: v2 重写
1. 基于差额分析结果，重写文章：
   - 保留初版的核心叙事结构和 A+C+F 框架
   - 吸收 AI 建议中有价值的部分（比喻、数据、机制、实用建议）
   - 修正所有 P0/P1 级事实错误
   - 过滤掉格式外功能（互动/投票/预告/配图建议）

2. **重写原则**：
   - **吸收而非照搬**：AI 的素材是参考，不是模板
   - **保持 A+C+F 结构**：Q加粗禁h3、分隔线恰好2处、F段标签"冷知识反转"
   - **只改有差距的地方**：不要为了改而改
   - **字数目标**：300-600 字
   - **比喻自检**：方向性（FP-20）+ 情感色彩（FP-21）

3. **自检清单**：
   - □ 字数 300-600
   - □ 所有 P0 事实错误已修正
   - □ 所有 P1 事实错误已修正
   - □ A+C+F 结构完整
   - □ CHECKLIST.md 逐条检查
   - □ FORBIDDEN.md 逐条检查（以 FORBIDDEN.md 实际 FP 条目为准）
   - □ 标点自查（5项高频陷阱）
   - □ AI数据范围已WebSearch核实

4. **⚠️ 采纳项落地校验（强制，不可跳过）**：
   重写完成后，**必须用 Grep 工具逐条验证** Phase 1.5 确认的"各AI亮点采纳"清单：
   
   **执行方式（强制，禁止凭印象判断）**：
   - 事实类修正 → 用 Grep 搜索 v2 文件，确认错误已改（如原错误"锁孔"→搜索"锁孔"确认消失，搜索"旋转门"确认出现）
   - 表达类改进（比喻/措辞/结构）→ 用 Grep 搜索关键词或同义词，确认已采用
   - 机制补充 → 用 Grep 搜索关键术语，确认信息已加入
   - **禁止**：仅凭记忆或印象判断是否落地，必须用工具验证
   
   **状态标注**：
   - ✅已落地：Grep 找到匹配内容，确认已采用
   - ⚠️部分落地：Grep 找到但不完整（说明差什么）
   - ❌未落地：Grep 未找到 → 必须回退修改，不得跳过
   
   **兜底规则**：
   - 若 Grep 未找到但你认为已落地 → 必须人工审读 v2 全文确认
   - 若人工审读仍确认未落地 → ❌ 必须回退修改
   - **目的**：杜绝"分析时觉得好、重写时忘了用"的问题

5. 写入：`F:\WorkBuddy\daily-why\articles\{YYYY-MM}\{YYYY-MM-DD}-优化版-每日冷知识-{关键词}.md`

6. 运行 `scripts/validate_article.py` 审核（P0=0 且 P1≤2 = 通过）
   - 不通过 → 修复重试（最多 2 轮）
   - 2 轮后仍不通过 → 标记"⚠️ 需人工审核"，输出当前最佳版本

7. **v2 独立 Reviewer 审校（2026-08-31 起强制，最终发布版本也必须过独立视角）**：
   用 Agent 工具 spawn 独立审校子 agent（subagent_type="general-purpose"，model="reasoning"，**禁传 name**）：
   - **审校对象**：`F:\WorkBuddy\daily-why\articles\{YYYY-MM}\{YYYY-MM-DD}-优化版-每日冷知识-{关键词}.md`
   - **任务内容（原样传入子 agent）**：
     ① Read 读取优化版文件
     ② 运行 `C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe F:/WorkBuddy/daily-why/scripts/validate_article.py --json "{优化版路径}"` 记录 P0/P1/P2 与得分
     ③ Read 加载 `C:/Users/admin/.workbuddy/skills/daily-why-writer/references/CHECKLIST.md` 逐项扫描
     ④ Read 加载 `C:/Users/admin/.workbuddy/skills/daily-why-writer/references/FORBIDDEN.md` 逐条扫描（条数以文件实际为准）
     ⑤ Read 加载 `C:/Users/admin/.workbuddy/skills/daily-why-writer/reviewer_prompt.md`，严格执行 P0/P1/P2 分级（绝对化/类比失准/字数>600 至少 P1，禁降 P2）
     ⑥ 事实断言 WebSearch 独立核验至少 2 处，错误标 P0
     ⑦ 报告写入 `F:/WorkBuddy/daily-why/review/{YYYY-MM-DD}_v2_review.json`（**与 L1 的 `_review.json` 分离不覆盖**；`review_timestamp` 用 Bash `date +%Y-%m-%dT%H:%M:%S%z` 取系统时间）
     ⑧ 通过条件：P0=0 且 P1≤2
   - **等待**：每 1 分钟轮询 `review/{YYYY-MM-DD}_v2_review.json`，15 分钟上限
   - **熔断链**：spawn 失败/超时 → 降级为仅脚本审核（第 6 步结果），标注「⚠️ v2 未独立审校」，**不阻塞流程**
   - 不通过 → 修复优化版 → 重新 spawn 审校（最多 2 轮）→ 仍不通过 → 「⚠️ 需人工审核」
   - **v2 审校得分记入学习总结与质量仪表盘 v2 列**（替换纯脚本分）

### Phase 3: 规则提炼
1. **新规则识别标准**：
   - 4 家 AI 都能做对但我做错 → 新 CHECKLIST 条目
   - 4 家 AI 都避免但我犯了 → 新 FORBIDDEN Pattern (FP-XX)
   - 某家 AI 独特技法值得学习 → 记录到 AI能力特点.md

2. **规则优先级**：
   - P0：涉及事实准确性 → 直接加入 CHECKLIST.md
   - P1：涉及表达技法 → 加入 FORBIDDEN.md 或 CHECKLIST.md
   - P2：涉及风格偏好 → 记录到学习总结，不强制加入

3. **规则冲突处理**：
   - 若新规则与现有规则冲突 → 标记冲突，由 Master 决定
   - 若新规则是现有规则的细化 → 作为子规则加入
   
   **⚠️ 冲突检测方法**：
   - 用 Grep 搜索 FORBIDDEN.md 和 CHECKLIST.md，检查是否存在语义相近的规则
   - 若存在 → 标记冲突，展示给 Master 决定
   - 若不存在 → 正常加入

4. **规则格式**：
   ```markdown
   ## FP-XX: 问题类型（YYYY-MM-DD 教训）
   - ❌ 具体禁止内容
   - ✅ 正确做法
   ```

### Phase 4: 技能同步更新（⚠️ 强制，不可跳过）

1. **FORBIDDEN.md 更新**：
   - 将新禁止模式写入 `~/.workbuddy/skills/daily-why-writer/references/FORBIDDEN.md`
   - 更新 FP 总数

2. **CHECKLIST.md 更新**：
   - 将新自检项写入 `~/.workbuddy/skills/daily-why-writer/references/CHECKLIST.md`

3. **FEEDBACK_LOG.md 更新**：
   - 将新教训写入 `~/.workbuddy/skills/daily-why-writer/references/FEEDBACK_LOG.md`

4. **SKILL.md 元数据更新**：
   - 更新 `~/.workbuddy/skills/daily-why-writer/SKILL.md` 中的 FP 总数
   - 更新最后更新日期

5. **AI能力特点.md 更新**：
   - 追加本次投喂记录到 `F:\WorkBuddy\daily-why\投喂素材\AI能力特点.md` 历史投喂记录
   - 如有新发现的AI特点，更新注意事项列

6. **自动化 Prompt 重新生成**（⚠️ 强制，规则变更后必须执行）：
   - 当 FORBIDDEN.md、CHECKLIST.md 或 SKILL.md 有任何变更时，**必须**重新生成自动化 prompt
   - 命令：
     ```bash
     C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe F:/WorkBuddy/daily-why/scripts/generate_prompt.py --update-automation
     ```
   - 该命令从 `writing_rules.json` + SKILL.md 自动生成最新 prompt 到 `config/automation-prompt-latest.txt`
   - **数据库落地（不可省略）**：脚本只写文件，不会自动更新 automation 数据库。必须读取 `config/automation-prompt-latest.txt` 全文，用 automation_update 工具（mode=update, id=automation-1778312519754, prompt=文件内容）写入数据库，并确认返回 nextRunAt 正常
   - 若脚本执行失败 → 记录到学习总结标注"⚠️ prompt未更新"，不阻塞后续流程
   - **目的**：确保下次 L1 自动化运行时使用最新的规则，避免"规则改了但 prompt 没跟上"的问题

7. **同步检查清单**（⚠️ 强制逐条验证）：
   ```markdown
   ## Skill 同步检查清单
   - [ ] FORBIDDEN.md FP总数 = SKILL.md 元数据一致
   - [ ] CHECKLIST.md 条目数合理
   - [ ] FEEDBACK_LOG.md 已追加本次教训
   - [ ] AI能力特点.md 历史记录已更新
   - [ ] 自动化 prompt 已重新生成（generate_prompt.py --update-automation）
   - [ ] 所有文件路径引用可访问
   - [ ] 休眠教训激活检测已执行
   ```
   
8. **休眠教训激活检测**（新增，⚠️ 强制）：
   - 将本次全部新教训文本拼接，作为 `--feedback` 参数
   - 运行激活检测：
     ```bash
     C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe F:/WorkBuddy/daily-why/scripts/archive_lessons.py --mode check --feedback "【新教训1文本】; 【新教训2文本】"
     ```
   - 若有匹配 → 检查输出，判断是否真的再犯
   - 若确认再犯 → 运行 `--mode activate --match-id <索引>` 激活回 FEEDBACK_LOG
   - 将激活结果记录到学习总结的「⚠️ 休眠教训激活」小节

9. **CHECKLIST 规则升降级**（新增，⚠️ 强制）：每次投喂学习后，用规则触发数据重算 CHECKLIST 分区，让活跃区自动反映最新高发问题：
   ```bash
   C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe F:/WorkBuddy/daily-why/scripts/rule_lifecycle.py --update
   ```
   - 该命令自动重写 `references/CHECKLIST.md` 为 活跃区/预防区/待验证区 三区结构（编号不变，规则不删）
   - 运行后确认输出"已重写为三区结构"；若有 ⚠️ 警告（未分类条目）→ 人工检查

   **⚠️ 验证方法（强制）**：
   - 用 Read 工具读取各文件，确认内容已更新
   - 用 Grep 搜索确认新增规则已写入
   - 禁止凭印象勾选，必须用工具验证

### Phase 5: 学习总结
1. **相邻话题沉淀（素材池反哺，强制）**：回顾四 AI 讨论、差额分析与 v2 重写过程中出现的、尚未写过的相邻话题（例：投喂"辣椒为什么辣"时提到的"为什么有人怕辣有人不怕"），整理 1 到 3 个候选，写入 `F:\WorkBuddy\daily-why\config\topic_candidates.json`：
   - 追加到 candidates 数组，每项含 topic / category / why_hot / evidence / source 字段
   - source 字段标记为 `l2`（L2 投喂反哺）
   - 若话题与 topic_candidates.json 已有候选或 topics_context.json 已用话题重复 → 跳过
   - 用 Bash + python 读取/写入，保持 JSON 合法（写入后 json.loads 校验）
2. 生成学习总结报告：
   ```markdown
   # 学习总结 - {YYYYMMDD}

   ## 基本信息
   - 日期：{YYYY-MM-DD}
   - 话题：{话题标题}
   - 参与 AI：{AI列表}
   - v1 得分：{分数} | v2 得分：{分数}

   ## 差额分析摘要
   ### 核心差距
   - [差距1]
   - [差距2]

   ## v1 → v2 改进点
   1. [改进1]
   2. [改进2]
   3. [改进3]

   ## 新提炼规则
   - FP-XX: [禁止模式] — [简要说明]
   - CHECKLIST §N: [自检项] — [简要说明]

   ## 各AI贡献
   - DeepSeek：[贡献]
   - IMA：[贡献]
   - 千问：[贡献]
   - 豆包：[贡献]

   ## 被拒绝的建议
   - [建议] — [拒绝原因]

   ## 相邻话题沉淀（素材池反哺）
   - [候选话题1]（source=l2，已写入 topic_candidates.json）
   - [候选话题2]（source=l2，已写入 topic_candidates.json）

   ## 后续行动
   - [ ] 规则已同步到 FORBIDDEN.md
   - [ ] 规则已同步到 CHECKLIST.md
   - [ ] FEEDBACK_LOG.md 已更新
   - [ ] AI能力特点.md 已更新
   - [ ] 自动化 prompt 已重新生成
   - [ ] 相邻话题已沉淀到素材池（source=l2）
   - [ ] 同步检查清单已通过
   ```

3. 写入：`F:\WorkBuddy\daily-why\投喂素材\{YYYYMMDD}\学习总结.md`

### Phase 6: 记忆更新
1. 更新 `.workbuddy/automations/automation-1778312519754/memory.md`：
   - 在当日条目中追加投喂优化信息（优化版文件、审核得分、新规则）

2. 更新 `.workbuddy/memory/MEMORY.md`：
   - 如有重大教训，追加到"关键教训"章节

### F2 异常标注证据门槛（09-01 新增，防自记失真污染决策链）

写任何「⚠️ 老问题复现 / 异常 / 失败」标记（学习总结、工作区日志、memory.md）时，**必须附至少一条可核验证据**：
- 文件 mtime 序列（如 `ls -la --time-style=+"%Y-%m-%d %H:%M:%S"` 输出）
- 命令输出 / 数据库字段 / 脚本实测结果
- **无证据的异常标记禁止写入**（09-01 实证：日志与学习总结均记「v2 review_timestamp 自造（写 10:50 实 <10:38）」，但实测 mtime 序列自洽——优化版 10:45:43 → timestamp 10:50:42 → review 文件 10:52:01，**系误报**，且被两处文档重复记录，持续污染决策链）。

---

## 产出清单

| 产出物 | 路径 | 说明 |
|-------|------|------|
| v2 优化版文章 | `{YYYY-MM-DD}-优化版-每日冷知识-{关键词}.md` | 重写后的文章 |
| 学习总结 | `投喂素材/{YYYYMMDD}/学习总结.md` | 结构化学习报告 |
| 更新后的 FORBIDDEN | `references/FORBIDDEN.md` | 新禁止模式已加入 |
| 更新后的 CHECKLIST | `references/CHECKLIST.md` | 新自检项已加入 |
| 更新后的 FEEDBACK_LOG | `references/FEEDBACK_LOG.md` | 新教训已记录 |
| 更新后的 AI能力特点 | `投喂素材/AI能力特点.md` | 历史记录已更新 |
| 素材池候选 | `config/topic_candidates.json` | L2 反哺的相邻话题（source=l2）已沉淀 |
| 更新后的自动化 Prompt | automation 数据库 | generate_prompt.py --update-automation |

---

## 边界条件与异常处理

### 素材不足
- **触发**：投喂素材文件夹中有效 AI 数量 < 2
- **处理**：提示用户补充素材，终止执行
- **提示**：`"素材不足：当前仅有 {N} 个 AI 的素材，至少需要 2 个。请补充后重试。"`

### 素材格式异常
- **触发**：AI 文件内容过短（< 100 字）或为空
- **处理**：跳过该 AI，继续处理其他 AI
- **记录**：在学习总结中标记跳过的 AI 及原因

### 无当日文章
- **触发**：对应的初版文章不存在
- **处理**：提示用户先运行 L1 自动化生成文章

### 审核不通过
- **触发**：v2 文章 validate_article.py 审核 P0>0 或 P1>2，或 v2 独立 Reviewer 审校不通过
- **处理**：根据审核报告修复，重试最多 2 轮
- **兜底**：2 轮后仍不通过，输出当前最佳版本 + "⚠️ 需人工审核"

### v2 独立审校失败（2026-08-31 新增）
- **触发**：spawn 独立 Reviewer 失败/超时（15 分钟）
- **处理**：熔断降级为仅脚本审核（validate_article.py），标注「⚠️ v2 未独立审校」
- **原则**：v2 审校是增强项，**任何情况下不得阻塞 L2 流程**

### 规则冲突
- **触发**：新规则与现有规则语义冲突
- **处理**：标记冲突，展示给 Master 决定
- **输出**：在学习总结中标注冲突项

---

## 质量追踪

每次 L2 执行后更新 MEMORY.md 中的质量仪表盘：

```markdown
## 质量趋势（最近10次投喂）
| 日期 | 话题 | AI数 | 新FP | v1分→v2分 | 状态 |
|------|------|------|------|-----------|------|
| {date} | {topic} | {N} | {N} | {s1}→{s2} | ✅/⚠️ |
```

---

## 关键文件路径

| 文件 | 路径 | 用途 |
|------|------|------|
| 本文件 | `~/.workbuddy/skills/daily-why-feed-learning/SKILL.md` | 四AI投喂学习技能 |
| 写作技能 | `~/.workbuddy/skills/daily-why-writer/SKILL.md` | 主写作技能（规则来源） |
| 禁止模式 | `~/.workbuddy/skills/daily-why-writer/references/FORBIDDEN.md` | 禁止模式（FP条目见文件实际内容） |
| 自检清单 | `~/.workbuddy/skills/daily-why-writer/references/CHECKLIST.md` | 16大类自检 |
| 教训记录 | `~/.workbuddy/skills/daily-why-writer/references/FEEDBACK_LOG.md` | 教训→规则转化 |
| AI特点 | `F:\WorkBuddy\daily-why\投喂素材\AI能力特点.md` | 四家AI能力参考 |
| 投喂素材 | `F:\WorkBuddy\daily-why\投喂素材\{YYYYMMDD}\` | 素材文件夹 |
| Prompt生成 | `F:\WorkBuddy\daily-why\scripts\generate_prompt.py` | 规则变更后重新生成自动化 prompt |
| 自动化记忆 | `.workbuddy/automations/automation-1778312519754/memory.md` | 执行记录 |

---

## 使用示例

```
Master: 投喂学习 20260612
Skill: 自动执行 L2 全流程（Phase 0→1→1.5暂停→2→3→4→5→6）
```

```
Master: 学习 F:\WorkBuddy\daily-why\投喂素材\20260612
Skill: 同上
```

---

*Version: v1.0 | 2026-06-12 | 初始版本，参照 history-today-feed-learning 适配 daily-why A+C+F 格式*

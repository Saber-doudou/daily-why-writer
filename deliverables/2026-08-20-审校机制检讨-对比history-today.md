# 审校机制检讨：daily-why vs history-today（2026-08-20）

> 背景：Master 指令「学习一下隔壁历史上的今天如何避免自审的，你们都是一起做的优化，检讨一下」。
> 触发事件：2026-08-19 审计发现 daily-why 最近 4 个发布日（08-14/17/18/19）v1 全部 validate 100 分通过，
> 却 4 篇全被 L2 四 AI 揪出 P0 事实硬伤——「自写自审」的事实拦截率≈0。

---

## 一、隔壁 history-today 的审校机制（v9.8.2，主路径=独立 Reviewer）

### 1. 核心设计：独立 Reviewer 是主路径，自审只是降级

```
Phase 3: 【spawn 独立 Reviewer】→ 6 维度审校 → review_report.json
    ├─ spawn 成功 → 独立审校（主路径）
    └─ spawn 失败 → 熔断链降级 → Orchestrator 自审 + 标注「⚠️ 未独立审校」（兜底）
```

- **spawn 规范（写死在 SKILL.md P0-1）**：`Agent(subagent_type="general-purpose", model="reasoning")`
  **禁止传 name 参数**（name 依赖 team 上下文，本地 automation 环境必失败；08-13 实证去掉 name 后 spawn 成功）
- **文件检测等待（P0-2）**：spawn 成功后每 1 分钟轮询 `archive/daily/{date}_review.json` 是否生成；
  reviewer 显式上限 15 分钟；**不依赖 SendMessage 回传**（08-17/08-19 实证本地不可用，以文本回报兜底）
- **熔断链**：spawn 报 team 上下文错误 → 去掉 name 重试 1 次 → 仍失败 → 熔断（本次不再尝试）→
  Orchestrator 自审（加载 review_rules.md + review/prompts/ 6 个模板执行 6 维度审校）→ 输出标注「⚠️ 未独立审校」
- **Reviewer 不加载写作规则**：纯粹的审核视角（不知道考纲，避免"知道考纲做题"）
- **判例预检**：审校前按文章题材域从 CASE_STUDIES.md 提取同领域高频问题模式（Grep 命中，禁止整读 96K）

### 2. 落地证据（我实际核查的文件）

| 日期 | review.json 记录 | 审校方式 |
|------|-----------------|---------|
| 08-13 | P0=1（格弗罗伊年龄数字错误）被揪出 | 独立审校（去掉 name 后 spawn 成功） |
| 08-14 | "sub-agent spawn unavailable in sandbox, team-context missing" | ⚠️ 降级自审（标注明确） |
| 08-17 | "熔断降级：reviewer spawn 15min 超时" | ⚠️ 降级自审（标注明确） |
| 08-18 | **review_mode="orchestrator_self_review + independent_agent_review"**，agent-62de8983 抓到自审漏检的 P1（标题剧透） | ✅ 独立 agent 成功（Master 推动改用 Agent 工具） |
| 08-19 | domain_precheck + 8 issues 逐条带 rule_ref | 独立审校（主路径） |

**关键事实**：隔壁 08-18 由 Master 推动、改用 **Agent 工具**召唤独立审校 agent，**实际成功**，且抓到
自审（orchestrator_self_review，P0=0/P1=0）**漏检的 P1**（标题『一封家书，压住了天平』剧透最大悬念，Rule 38）。
这直接证明：**本环境独立审校 agent 是可行的**，且**确实能抓到自审抓不到的问题**。

---

## 二、daily-why 的现状（v3.1，主路径=同步自审）

### 1. 当前设计（写死在 SKILL.md + automation prompt）

```
Phase 3: 【Orchestrator】初稿写入文件 → 同步审校（主代理亲自执行）
    - validate_article.py --json
    - CHECKLIST + FORBIDDEN 人工对照
    - 最小结构验证
    - 就地输出审核报告
```

- SKILL.md 明文：**「同步审校模式：Orchestrator 选题+写作+自检+精修+审校全同步执行，不 spawn 子 agent
  （子 agent 回传通道在本环境不可靠，08-06/08-13 两次实证，spawn 阻塞调用无法被异常规则打断）」**
- automation prompt 阶段2 明文：**「禁止使用 Agent 工具 spawn 独立审校子 agent（该回传通道在本环境不可靠）」**

### 2. 实际效果（2026-08-19 审计结论）

| 日期 | 话题 | v1 自审 | L2 揪出的 P0 硬伤 |
|------|------|--------|-------------------|
| 08-14 | 飞蛾扑灯 | 100分 | 蚊子列入趋光举例（实际靠 CO₂/体温定位） |
| 08-17 | 鞋带松开 | 100分（P0/P1/P2=0） | 摆锤装置模拟写成"让人跺脚"（实验描述失真） |
| 08-18 | 喷嚏闭眼 | 100分 | 泪腺位置错误 + 速度类比失准 |
| 08-19 | 红酒挂杯 | 100分 | 汤姆森是开尔文勋爵哥哥，写"弟弟" |

---

## 三、检讨：同样的起点，相反的结论

### 1. 08-13 同一天，两边处理方式天壤之别

| 维度 | history-today | daily-why |
|------|--------------|-----------|
| 遇到问题 | spawn 报 team 上下文错误 | 子 agent 回传不可靠 |
| 反应 | 去掉 name 重试 → **成功** | 直接放弃，写死"禁止 spawn" |
| 主路径 | 独立 Reviewer（自审仅降级） | 同步自审（唯一路径） |
| 等待策略 | 文件检测轮询（绕开 SendMessage） | 阻塞调用等返回 |
| 降级标注 | 「⚠️ 未独立审校」显式标注 | 无（自审即常态） |
| 独立视角 | ✅ 保留（08-18 实证成功） | ❌ 永久放弃 |

### 2. 三个核心错误

1. **过度泛化的错误结论**：把"当前环境某次 spawn 阻塞调用失败"推广为"子 agent 通道在本环境永远不可靠"。
   隔壁在同一环境、同一天遇到同类问题，却通过「去掉 name 参数」和「文件检测替代 SendMessage」两条
   workaround 绕过了——说明我们当时**没有穷尽尝试就下了死结论**。

2. **放弃了最核心的防线——独立视角**：写作和审校是同一个模型实例，共享同一知识盲区和错误倾向。
   "主代理自审"本质是"自己批改自己的卷子"：能查出格式/结构问题（validate 脚本兜底），
   但查不出"写错的弟弟/哥哥"这种事实性错误。隔壁 08-18 的实证（独立 agent 抓到自审漏检的 P1）
   正是对独立视角价值的直接证明。

3. **把降级路径固化成唯一路径，还双重写死**：SKILL.md 和 automation prompt 两层都写了"禁止 spawn"，
   连每次运行"尝试一次、失败再降级"的机会都不给自己。隔壁是"每次先试独立 reviewer，失败才降级"，
   我们是一步到位放弃。

### 3. 我们其实有历史资产，只是被废弃了

- `skills/daily-why-writer/reviewer_prompt.md`（3.3KB，2026-06-21）：完整的独立 Reviewer prompt，
  含角色定位（不加载 SKILL.md、不参与选题、只审核）、审校流程、JSON 输出格式、异常处理——**保留至今，可复用**
- `agents/quality-reviewer.json`（2026-06-05）：早期双 Agent 架构的审校 Agent 配置
- 说明：我们不是"没有独立审校方案"，而是 08-06/08-13 之后**主动废弃了它**

---

## 四、修复建议（对齐隔壁 v9.8.2，待 Master 决策后落地）

### 方案 A：恢复独立 Reviewer 为主路径（推荐，直接对齐隔壁已验证方案）

1. **改 SKILL.md 多 Agent 执行模式**：
   - 主路径：spawn 独立 Reviewer（`Agent(subagent_type="general-purpose", model="reasoning")`，**禁止传 name**）
   - Reviewer 加载：CHECKLIST.md + FORBIDDEN.md + reviewer_prompt.md（不加载写作规则）
   - 输出：写入 `review/{date}_review.json`（文件落盘）
   - 等待：每 1 分钟轮询文件是否生成，上限 15 分钟，不依赖 SendMessage
   - 熔断链：spawn 失败 → 去掉 name 重试 1 次 → 仍失败 → 熔断 → Orchestrator 自审 + 标注「⚠️ 未独立审校」
2. **改 automation prompt**（generate_prompt.py 模板 + 数据库同步）：
   - 阶段2 从"同步式审校"改为"独立 Reviewer 审校 + 熔断降级"
3. **验证**：改后首个工作日观察 review.json 是否由独立 agent 生成

### 方案 B：自审保留，但增加"第二模型复核"折中（若 Master 不信任 spawn）

- 主代理自审后，用**不同模型的独立视角**复核事实断言（人物/机构/亲缘/数字类 WebSearch 二次核验）
- 实现成本低，但本质仍是"生成者+评判者同源"，独立视角打折

### 建议落地顺序

1. 先做一次 **spawn 可行性实验**（当前会话直接 spawn 一个独立 agent 审昨天的文章，验证去掉 name 后能否成功）
2. 成功 → 方案 A 全面落地（SKILL.md + automation prompt + generate_prompt.py）
3. 失败 → 回退方案 B，并在 SKILL 记录实证结论

---

## 五、结论

> **我们输的不是技术，是心态**：隔壁遇到 spawn 失败想的是"怎么绕过"，我们想的是"放弃这个功能"。
> 同一个 08-13，隔壁去掉 name 成功、08-18 用 Agent 工具成功并抓到自审漏检的 P1；
> 我们至今还写着"子 agent 通道不可靠，禁止 spawn"。
> **独立审校视角必须恢复为主路径**——这是"生成者与评判者分离"（EXP-005）的基本要求，
> 也是隔壁已经在本环境跑通、被 Master 亲自验证过的路。

*审计人：SeniorDeveloper | 2026-08-20 | 依据：两项目 SKILL.md、automation prompt、archive/daily/*_review.json 逐文件核对*

# maker-checker 与自动化运行细节

> 从 MEMORY.md §1「架构与自动化」下沉，2026-09-08（v3 记忆治理，架构区削减至配额内）
> 主文件只留指针行：`- maker-checker v2.0 熔断链 → topics/maker_checker.md；通过线 P0=0 且 P1≤2`

## 0. L1 / L2 / L3 链路定义

- **L1 `daily-why-writer`**：写作，工作日 09:40 计划（实测波动 09:45 至 10:11）
- **L2 `daily-why-feed-learning`**：四AI投喂，**手动触发**
- **L3 `daily-why-publish`**：IMA+GitHub 发布备份，**手动触发**
- ⚠️ 自动化只覆盖 L1（设计如此，**非缺陷**）；L2/L3 手动占比高不得列为缺陷

## 1. maker-checker v2.0 完整定义

- **分工**：Orchestrator 负责选题 + 写作 + 精修；**独立 Reviewer** 负责 6 维度 P0/P1/P2 审核
- **Reviewer 规格**：`subagent_type=general-purpose`，`model=reasoning`，**禁传 name 参数**
- **熔断链**（spawn 失败时的降级路径，顺序不可颠倒）：
  1. Reviewer spawn 报错
  2. → 去掉 `name` 参数重试一次
  3. → 仍失败 → Orchestrator 自审，并在产出中标「⚠️未独立审校」
- **通过线**：P0 = 0 且 P1 ≤ 2
- **产出**：`review/<日期>_review.json`，由 `validate_article.py` 校验后入库

> ⚠️ 按 EXP-006（记忆分层），本条属**程序性记忆**，理想归宿是 `~/.workbuddy/skills/daily-why-writer/SKILL.md`（L1 阶段0 本来就强制加载）。
> 本次为控制改动面先落 topics/，待四层归位时可迁入 SKILL.md，届时主文件连指针行都可省。

## 2. L1 触发时间实测（波动台账）

- 计划：工作日 09:40（rrule `FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=9;BYMINUTE=40`）
- 实测波动区间：09:45 至 10:11
- **2026-09-08 实际触发 10:11:08，延迟 +31 分 08 秒**（审计 P1-3 记录的极值）
- 该波动为调度器侧行为，非脚本逻辑问题；`next_run_at` 字段正常（09-09 09:40:00，未被污染）

> 逐日明细看 `topics/trends.md`。

## 3. 触发词（唯一权威源 config/skill-trigger-map.json）

> 下方清单 2026-09-08 从 json 复制，仅供离线检索；**冲突时一律以 json 为准**。

- **L1**（写作兜底）：`每日一个为什么` / `每日一个为什么写作` / `dailywhy写` / `dailywhy写作` / `每日冷知识`
- **L2** 动作词：`学习` `投喂` `总结`
- **L2** 触发词：`每日一个为什么学习` / `每日一个为什么学习总结` / `每日一个为什么投喂` /
  `dailywhy学习` / `dailywhy学习总结`
- **L3** 动作词：`发布` `推送` `审计` `备份`
- **L3** 触发词：`每日一个为什么发布` / `每日一个为什么推送` / `每日一个为什么审计` /
  `每日一个为什么备份` / `每日一个为什么推送备份` / `每日一个为什么发布备份` /
  `dailywhy发布` / `dailywhy推送` / `dailywhy审计` / `dailywhy备份` /
  `dailywhy推送备份` / `dailywhy发布备份`
- **裁决**：动作词优先；同时命中多技能按 L2 → L3 → L1 顺序
- ⚠️ 裸词 `dailywhy` 自 2026-08-28 起**不再**作为 L1 触发词（前缀冲突修复，C 方案）
- ⚠️ L1 触发词不得改动，约束问题通过机制层解决而非修改用户习惯（Master 定调）

## 4. 文章命名与副本策略

- 命名格式：`{YYYY-MM-DD}-每日冷知识-{2-6字}.md`
- L2 产出的优化版加前缀：`优化版-`
- **单一副本原则**：文章仅存本地 `articles/`，**不进 git、不进 IMA**（Master 2026-09-01 确认）
- 违反此条会造成副本分叉，属 P0 级错误

## 5. 运行环境固定项

- Python：`C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe`（managed，勿用 system 版本）
- 自动化 ID：`automation-1778312519754`
- 改 prompt 的唯一路径：`generate_prompt.py --update-automation`（**写库后必须回读比对**，09-01 有写库损坏先例）

# dailywhy 优化交接说明（接手人入口）

> 版本：v1.0（交接版）
> 日期：2026-10-22
> 交接对象：接手 dailywhy 优化实施的工程师
> 决策人：Master（内容口味、发布授权、决策变更）
> 执行人：接手工程师（按达尔文循环实施、验收、回滚）
> 执行裁决：`deliverables/2026-10-23-dailywhy优化执行-裁决书.md`（22 条问题与修订口径；与本文冲突时以裁决书为准）
> 先读本文，再按第 1 节「文档地图」顺序读

---

## 0. 一页纸摘要

**dailywhy 是什么**
每日冷知识自动化：L1 每天 09:40 写一篇 300 到 690 字的科普文章，L2 由人工投喂四家 AI 点评做优化版与规则学习，L3 做发布前校验、IMA 备份、GitHub 推送、记忆归档。

**现在什么状态**
能稳定日更，但四类问题反复出现：

1. **事实漏检**：脚本 100 分不等于事实正确。10-21 白蚁稿机制整链错误，靠 L2 才发现。
2. **选题语义盲区**：字符匹配查不出换术语的同主题，2 个月内 2 次暴雷。
3. **上下文过长**：Writer 峰值加载 82,552 字符规则，产出上限 690 字，比例约 120:1。
4. **内容不够生动**：负向规则过载，缺少正向示例与文风度量。

**要做什么**
13 条建议全量推进，30 到 42 人日，10 到 12 周。核心五件事：

- 证据卡 + 机制/数字/归因三类 claim 全阻断（但配 4 级日更兜底，不停更）。
- 评测金集 + 回归门禁（先有尺子，再改 prompt）。
- 规则分层 + 按需检索（把 82.5K 字符压到 20K 以内）。
- 结构化契约（JSON schema 替代自由文本与正则）。
- 可观测性（run_id、阶段耗时、成本、错误分类）。

**第一件事**
R1：修 `prepare_topics.py` 的 full/compact 双文件漂移，0.5 人日，可随时回滚。

**不要做的事**
不要直接改 main；不要动 09:40 的 L1 自动化 prompt；不要提交 `scripts/config.json`。

---

## 1. 文档地图（按顺序读）

| 顺序 | 文档 | 用途 | 建议用时 |
|---|---|---|---|
| 1 | 本文 | 交接入口、环境、第一周、坑位 | 10 分钟 |
| 2 | [`../2026-10-21-dailywhy优化方案书.md`](../2026-10-21-dailywhy优化方案书.md) 第 0、1、2 节 | 结论、路线图、现状基线 | 20 分钟 |
| 3 | 同上，第 3、4、5 节 | 13 条建议的现状、依据、方案、收益、成本、风险 | 60 分钟 |
| 4 | 同上，第 7、10 节 | 全量实施计划、达尔文循环 | 20 分钟 |
| 5 | 同上，第 9 节 + 附录 E | 已确认决策、三类 claim 例子与全阻断设计 | 15 分钟 |
| 6 | [`../2026-10-22-dailywhy达尔文执行清单.md`](../2026-10-22-dailywhy达尔文执行清单.md) | R1 到 R13 勾选、前三轮详细步骤、每日节奏、禁止事项 | 15 分钟 |
| 7 | 方案书附录 D | BGE-M3、影子/阻断、文风标签的白话解释 | 10 分钟 |
| 8 | [`../2026-10-23-dailywhy一次性全做提示词.md`](../2026-10-23-dailywhy一次性全做提示词.md) | 一次性全做 R1 到 R13 的总控提示词（可选） | 5 分钟 |

**只读这三份就够开工。** 其余历史文档（CHANGELOG、docs/ 旧计划、deliverables/ 旧报告）是背景资料，不需要先读。

---

## 2. 环境与关键路径

| 项 | 值 |
|---|---|
| 工作空间 | `F:/WorkBuddy/daily-why` |
| Python | `C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe` |
| 写作技能 | `C:/Users/admin/.workbuddy/skills/daily-why-writer/SKILL.md` |
| L2 技能 | `C:/Users/admin/.workbuddy/skills/daily-why-feed-learning/SKILL.md` |
| L3 技能 | `C:/Users/admin/.workbuddy/skills/daily-why-publish/SKILL.md` |
| L1 自动化 | `automation-1778312519754`，工作日 09:40 |
| 发布脚本 | `scripts/l3_publish.py` |
| 格式审核 | `scripts/validate_article.py` |
| 去重 | `scripts/check_topic.py` |
| 话题库刷新 | `scripts/prepare_topics.py` |
| 全盘自检 | `scripts/full_selfcheck.py` |
| 运行日志 | `l3_run.log`、`logs/check_topic_decisions.jsonl`、`review/*.json` |
| 配置 | `scripts/config.json`（含 IMA ID，**已 gitignore，不要提交**） |
| 文章归档 | `articles/{YYYY-MM}/` |
| 发布报告 | `deliverables/{date}-发布报告.md` |

**开工前先跑三条命令，确认环境正常：**

```bash
C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe scripts/full_selfcheck.py
C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe scripts/check_topic.py --angle "测试话题"
C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe scripts/validate_article.py --latest
```

预期：`full_selfcheck` 为 **20/24**（4 个已知失败项）；`check_topic` 返回 0/1/2 三态之一；`validate_article` 输出最近一篇的 P0/P1/P2 与得分。

> 若 `validate_article --latest` 因文件名含「每日冷知识」被沙箱拦截而失败，不要判环境损坏；按第 7 节坑位 1 处理（复制到临时名再跑）。

---

## 3. 已确认决策（D-01 到 D-05）

| 编号 | 决策 | 状态 |
|---|---|---|
| D-01 | 13 条建议**全量推进**，30 到 42 人日，10 到 12 周；不缩减为最小闭环 | 已确认 |
| D-02 | 六段是**主对话内顺序阶段** + **唯一 Reviewer 子 agent**；不做多 agent 编排、不并行 spawn | 已确认 |
| D-03 | 机制、数字、归因三类 claim **全阻断**；引文、措辞、来源锚点影子 2 周；配 4 级日更兜底 | 已确认 |
| D-04 | 本地 embedding **小模型先行**：`bge-small-zh-v1.5`（约 100MB）或 `text2vec-base-chinese`（约 400MB）；不够再升级 `BAAI/bge-m3`（约 2GB） | 已确认 |
| D-05 | 文风标签 10 组 A/B，季度换 5 组；若 Master 不参与日常，由接手人标注、Master 抽检 3 组 | 已确认 |

**变更规则**：任何决策变更，先改方案书第 9 节，再改执行清单，避免两处不一致。

---

## 4. 接手第一周（按顺序做，不要跳）

### Day 1：环境与基线（不写代码）

- [ ] 读本文与方案书第 0、2、10 节。
- [ ] 跑第 2 节三条命令，确认基线 20/24。
- [ ] 看 `l3_run.log` 最后 30 行，确认最近一次发布状态。
- [ ] 确认 09:40 的 L1 自动化仍在 main 上跑。
- [ ] 建优化分支：`git checkout -b auto-optimize/dailywhy-20261022`。
- [ ] 不要在第一天的任何时刻改自动化 prompt。

### Day 2 到 Day 3：R1 双文件 SSOT（0.5 人日）

按执行清单 R1 执行。核心是让 `prepare_topics.py --compact` 不再只写 compact；`check_topic.py` 与 L1 prompt 读同一份事实。

**验收**：`full_selfcheck` 该项转绿；`topics_context.json` 与 `topics_context_compact.json` 的 `topic_summaries` 完全一致。

**回滚**：`git revert` 本轮 commit；用备份 json 覆盖。

### Week 1 到 Week 2：R2 结构化契约（3 到 4 人日）

按执行清单 R2。先写 `review.schema.json` 与 `learning_summary.schema.json`，因为这两类历史事故最多。

**验收**：50 份历史文件通过率 ≥95%；L3 改进点、话题、字数读取零正则。

**回滚**：保留旧读取路径作为 feature flag。

### Week 2：R3 证据卡 + 全阻断 + 安全池（3 到 4 人日）

按执行清单 R3。**顺序不能反：先建安全池 → 再跑 5 天日更演练 → 最后把 gate 从 warn 切成 block。**

**验收**：3 条测试 prompt 全过；阻断正确率 100%；误杀 ≤10%；兜底成功率 100%；连续 5 天日更不中断。

**回滚**：gate 降回 warn，保留代码，不改 main。

---

## 5. 不能碰的东西

| 不能碰 | 原因 |
|---|---|
| `main` 分支 | 所有优化走 `auto-optimize/dailywhy-20261022`；未合并的改动不影响 09:40 的 L1 |
| 09:40 L1 自动化 prompt | 只在 Master 确认合并后替换；替换前先在分支跑 3 条测试 prompt + 金集 |
| `scripts/config.json` | 含 IMA KB ID，已被 gitignore；提交会泄露配置 |
| `articles/` 历史文章 | 只读参考，不修改、不移动、不删除 |
| `review/*.json` 历史审校 | 只读参考；新审校写新文件，不覆盖旧文件 |
| IMA / GitHub 凭据 | 不写入代码、不进日志；用环境变量或平台授权 |
| 已发布文章的 IMA 归档 | 不删除、不移动；IMA API 无移动/删除能力 |

---

## 6. 验收口径

| 指标 | 目标 | 数据来源 |
|---|---|---|
| 日更不中断 | 连续 20 个工作日零停更 | `l3_run.log`、发布报告 |
| 事实 P0 召回（金集） | 100% | `eval_runner` |
| 生产事实 P0 | ≤1 篇/20 篇 | L2 审校 + 发布报告 |
| 去重召回 / 误杀 | ≥90% / ≤5% | 100 对标注样本 |
| Writer 输入规则 | ≤20,000 字符 | `prompt_budget` |
| Reviewer 输入规则 | ≤25,000 字符 | `prompt_budget` |
| L1 延迟 | P95 ≤15 分钟 | `run_metrics.jsonl` |
| 全盘自检 | 24/24 | `full_selfcheck` |
| 单篇积分成本 | 先测，再降 30% 到 50% | 月度积分账单（无逐次 token 回传） |

---

## 7. 已知坑（按踩坑概率排序）

1. **Windows 沙箱可能拦截文件名含「每日冷知识」的子进程读取**。用 Read/Write 复制到临时名，或用包装脚本复用权威函数；不要以为是文件损坏。
2. **spawn 首次可能 429**。等待 30 到 60 秒重试；这不是 team 上下文错误，不要触发熔断链。
3. **IMA API 无笔记移动/删除**。落位配置改前先查存量；改错只能新建，不能搬家。
4. **git push 沙箱网络可能失败**。以 `ls-remote` 或 `api.github.com` 的 remote sha 为准，不信本地 `ahead N`。
5. **full/compact 双文件漂移**。R1 修完前，不要相信「话题库一致」；以 `topic_summaries` 逐项比对为准。
6. **版本号多口径漂移**。改版本号必须三处对齐：`config/version.json`、SKILL 标题/页脚、脚本 `VERSION`。
7. **文风标签不要用单一 AI 偏好当标准**。以人工 A/B 为准；AI 只做辅助，不做 ground truth。
8. **规则越加越多不等于越好**。新规则必须有历史反例 + 正确写法 + 可脚本判定的触发条件；否则不进规则库。
9. **主工作区就是生产**：09:40 直接读工作区，分支不隔离；R2 起用 `git worktree` 影子工作区 `F:/WorkBuddy/daily-why-opt`。
10. **技能目录 git 历史停在 08-04**：SKILL/references 回滚用文件级快照，不用 `git revert`。
11. **manifest 零存量、历史 review 字段有缺口**：按裁决书 A1/A2 版本分流处理，不改历史文件。

---

## 8. 交接前检查（Master 与接手人一起过一遍）

- [ ] 接手人能访问工作空间、Python、技能目录、自动化后台。
- [ ] 接手人知道 `automation-1778312519754` 的存在与 09:40 时间。
- [ ] 接手人知道 `scripts/config.json` 不进 git。
- [ ] 接手人能跑 `full_selfcheck` 并解释 4 个失败项。
- [ ] 接手人能跑 `check_topic` 三态。
- [ ] 接手人读过方案书第 0、2、9、10 节与附录 E。
- [ ] 优化分支已建，main 未动。
- [ ] 安全池建设已排进 R3，且知道「先建池、再演练、再切 block」。
- [ ] 决策人（Master）与执行人（接手工程师）的分工已确认。

---

## 9. 角色边界

| 事项 | 决策人 | 执行人 |
|---|---|---|
| 发什么、怎么改文风、选题偏好 | Master | 提供 A/B 样本与数据，不擅自定标准 |
| D-01 到 D-05 变更 | Master | 提案 + 影响分析 |
| 技术实现、回滚、分支操作 | — | 接手工程师 |
| 发布授权 | Master | 执行并留痕 |
| 金集标注 | Master 抽检 3 组 | 接手人标 10 组（D-05） |

---

## 10. 第一份产出

R1 完成后，交一份 **1 页验收记录**，只写四件事：

1. 改了什么文件、哪几行。
2. 跑了什么命令、输出是什么。
3. 两个话题库文件是否一致（`topic_summaries` 逐项比对结果）。
4. `full_selfcheck` 该项是否转绿。

不要一上来写大报告；先让 R1 可验证，再谈后续。

---

*本文是交接入口。方案细节以《dailywhy 优化方案书》v1.3 为准，执行步骤以《dailywhy 达尔文执行清单》v1.1 为准。*

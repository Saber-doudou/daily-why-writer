# check_topic 整改补充任务销账报告（F1-F5）

> 文档定位：`deliverables/2026-10-13-check_topic整改补充任务清单.md` 的执行结果销账，替代该清单各「验收」列为最终证据。
> 执行人：当值会话｜日期：2026-10-13｜Master 裁定：F1 选方案 B；F6 不打包。
> 纪律：本报告所有数字均来自脚本实跑（证据文件见第五节），无手写估算。

---

## 一、总结论

**F1 至 F5 全部完成，验收全过。** dedup_selftest **21/21 全绿**（原 19 项零回退 + I13/I14 新绿）；full_selfcheck **20/24**（第 12 项保持 PASS，余 4 项即 F6 范围外、按 Master 裁定未动）；prompt 写库回读 **DB==FILE 逐字一致**；记忆分片与 CHANGELOG 同步完毕。

---

## 二、逐项销账

### F1 单字 specific 误杀修复（🟡，方案 B）✅

**怎么改**：
1. `check_topic.py` `check_concept_overlap`：硬重复判定由「同 concept + 双方 specific 各 ≥1」收紧为「**+ 双方 generic 各 ≥1**」（同主体才拦）；仅 generic 命中仍不拦；输出消息升级为主词+现象词双侧明细。
2. `dedup_selftest.py`：新增 I13（汗水咸）/ I14（融雪盐）误杀回归，全量 19 → 21 项。
3. `topics/dedup_defense.md`：已知边界段更新（删除「单字 specific 误杀隐患」条，改为 F1 修复记录 + 精度优先取舍说明）。

**实测**（真实库，修复后）：

| 用例 | 期望 | 实测 |
|---|---|---|
| A1 牛排候选 | EXIT=1 | EXIT=1 概念[牛排血水]（主词 牛排 vs 牛排；现象词 红色汁液 vs 血水） |
| A3 大海里的盐 | EXIT=1 | EXIT=1 概念[海水咸]（主词 大海 vs 海水；现象词 盐 vs 咸） |
| A2 牛排废弃标题 | EXIT=1 | EXIT=1 概念[牛排血水]（字符串参数等价验证，见旁记） |
| 汗水为什么是咸的 | EXIT=0 | EXIT=0（角度提示列出海水是咸的 67% ×3，交由人工逐个确认） |
| 为什么盐能让雪融化 | EXIT=0 | EXIT=0（干净放行） |
| A4 牛排熟成 | EXIT=0 | EXIT=0 |

**已知取舍**：不含量化主词的措辞（如「海里的盐」）会漏拦，属精度优先的定向交换；generic 词表扩充候选（海里/大洋）留待月度复盘。已在代码注释与分片双处记录。

### F2 决策日志瘦身 + 截断机制修（🟡）✅

**怎么改**（`check_topic.py` 一处）：
1. `log_decision` 的 matches 只记 `score ≥ 0.3` 的候选（`DECISION_LOG_MIN_SCORE`）；
2. 截断改字节预算：超 5MB 时从尾部保留约 2MB（按行边界对齐）+ 标记行（`_truncate_decision_log`），修复「按行数截断（保留 2000 行 ≈26MB）永不压回 5MB 以下且每次全文件读写」缺陷；
3. 可选的 `context` 字段（l1/gate/selftest）**未加**：check_topic 层无可靠信号区分调用来源（selftest 走子进程 CLI），强行猜测等于制造脏数据；如需该维度建议后续由调用方经环境变量显式传入。

**实测**：人造 6,501,157 字节假日志 → 跑一次 check_topic → **2,087,564 字节**（<5MB ✅）、末条为新记录 ✅、截断标记行存在 ✅；瘦身后单条 **293 字节**（<2KB ✅）；dedup_selftest 21/21 不受影响（日志改动不影响退出码）✅。

### F3 T3 prompt 改 --file 模式（🟡）✅

**怎么改**（`generate_prompt.py` 三处 + 写库）：
1. 步骤 9 成稿标题复查：裸传标题字符串 → `--file "articles/{年月}/{今天日期}-每日冷知识-{关键词}.md"`（脚本自提首行标题并去 emoji，彻底消除引号/$/反引号的 shell 解释风险，顺带去掉人工抄写出错面）；
2. 步骤 3 与降级①/②：候选话题统一单引号包裹 + 新增「shell 传参纪律」条（含单引号例外的处理规则）；
3. 走 `--update-automation` 写库，回读 DB 与 `automation-prompt-latest.txt` 归一化逐行比对：**DB==FILE True，121 行全同**，新内容（--file / shell 传参纪律 / 单引号）均在库。

**实测**（写库前）：关节文 `--angle --exclude-date 2026-10-13 --file` → **EXIT=0** ✅；关节文 `--file` 不带 exclude → EXIT=1（自匹配，证明 exclude 参数必要且生效）；`generate_prompt.py --check` → 0 警告 ✅。

### F4 dedup_defense.md 版本号笔误（💭）✅

「CHANGELOG v4.16」→ **v5.0**（v4.16 本身是违规两位数 patch）。一行修正，已落。

### F5 「蛇」案例沉淀（💭）✅

`topics/defects.md` 新增 **#64**：硬编码测试话题随语料库腐化致自检基线误判（「蛇」75% 根因判定、R1 动态锚点为好模式、三条教训：测试锚点优先动态取自语料库/硬编码锚点须随库增长复核/基线 FAIL 先判测试数据腐化再判被测系统缺陷）。

### F6 范围外四项（可选打包）— 按 Master 裁定**不做**

full/compact 不一致（40 vs 42）、素材池 6 条缺字段、SKILL.md 区间 `~` 残留、memory 新格式提取 26 条：均为 T1-T6 之前存在的既有失败，本次未动，full_selfcheck 余 4 项失败即此四项，与基线完全一致。建议另立任务排期（其中 full/compact SSOT 是设计变更，需先查 09-15 调研建议至今未落地的原因）。

---

## 三、验收总表（对照补充清单各「验收」列）

| 清单验收项 | 要求 | 实测 | 结论 |
|---|---|---|---|
| F1 | 汗水咸 EXIT=0、融雪盐 EXIT=0、A1/A3 EXIT=1、A4-A8 不变、selftest 21/21、第 12 项不回退 | 全部满足（A4-A8 复跑不变；I13/I14 新绿；I7/I8 仍拦） | ✅ |
| F2 | 单条 <2KB；人造 >5MB 假日志跑一次后 <5MB 且末条为新记录；selftest 全绿 | 293B；6.5MB→2.1MB，末条为新记录，标记行在；21/21 | ✅ |
| F3 | prompt 与 DB 回读一致；关节文 --file EXIT=0；--check 0 警告 | DB==FILE 逐字一致（121 行）；EXIT=0；0 警告 | ✅（废弃文 --file 半例见旁记） |
| F4 | v4.16 → v5.0 | 已改 | ✅ |
| F5 | defects/lessons 补一两条 | defects.md #64 | ✅ |
| 收尾 1 | selftest 全绿 + selfcheck ≥20/24 且第 12 项 PASS | 21/21；20/24，第 12 项 PASS | ✅ |
| 收尾 2 | CHANGELOG 记 v5.1 | 已记（含版本号说明） | ✅ |
| 收尾 3 | dedup_defense.md 同步本批改动 | T1/T3 条目更新 + F1-F5 段新增 + 边界段更新 | ✅ |
| 收尾 4 | 改 prompt 走写库 + 回读逐字比对 | 已走，DB==FILE | ✅ |
| 收尾 5 | 简短销账报告 | 本文件 | ✅ |

---

## 四、偏差与旁记（如实披露）

1. **证据锚点流失（已闭环）**：任务书与审查报告引作证据的 `articles/2026-10/2026-10-13-每日冷知识-牛排血水_废弃.md` 于 14:25 前后被移除（articles/2026-10 目录 mtime 14:25 佐证；无脚本删痕：全脚本库 unlink 仅涉 message_handler 与临时校验脚本，均不碰 articles；备份目录无此文件）。**Master 15:08 确认系本人删除**（可从回收站恢复），经评估**无需恢复**：标题字符串与全部数字已文档化（任务书/审查报告/记忆分片/日志），字节级复核可由仍在库的 09-07 原文 + 已记录标题复现，R5 锚点为 topic_summaries 字符串不依赖该文件。影响与处置：① R5 回归不受影响（仍 EXIT=1）；② F3 验收中「牛排废弃文 --file EXIT=1」无法按字面复跑，实质覆盖由 R5 + F1-A2 字符串实测提供；③ 该文件是今日事件的关键证据，其消失系 Master 主动清理，非流程事故。
2. **终验证据与交付树差 1 个文件**：终验证据产生时存在 1 个临时 runner 脚本（`scripts/_tmp_f_final.py`，运行后已删，full_selfcheck 语法项计 32 个），最终交付树 31 个。无检查项依赖文件计数，结论不受影响；此为审查报告 💭2 建议的「证据状态=交付状态」的已知残余（runner 与证据本身不可兼得，择证据保真）。
3. **F2 可选 context 字段未做**：理由见 F2 条第 3 点（无可靠调用来源信号，不造脏数据）。

---

## 五、证据文件（deliverables/）

- `2026-10-13-check_topic整改-F轮验证.txt`：selftest 21/21 + full_selfcheck 20/24 + F1 六例 + F2 截断三断言 + 瘦身实测
- `2026-10-13-check_topic整改-F3写库前实测.txt`：--file 组合三例 + --check
- `2026-10-13-check_topic整改-F3写库回读.txt`：DB==FILE True，121 行
- `2026-10-13-check_topic整改-F轮终验.txt`：清理后干净状态终验 21/21 + 20/24

## 六、改动文件清单

| 文件 | 变更 | 任务 |
|---|---|---|
| `scripts/check_topic.py` | check_concept_overlap 加 generic 共现条件；log_decision score≥0.3 过滤 + 字节预算截断（_truncate_decision_log） | F1/F2 |
| `scripts/dedup_selftest.py` | 新增 I13/I14；docstring 同步 21 项 | F1 |
| `scripts/generate_prompt.py` | 步骤 9 改 --file；步骤 3/降级支路单引号 + shell 传参纪律条 | F3 |
| `config/automation-prompt-latest.txt` | 重新生成（15101 字节，121 行） | F3 |
| automation DB（automation-1778312519754） | prompt 写库并回读逐字一致 | F3 |
| `.workbuddy/memory/topics/dedup_defense.md` | F4 版本号修正 + T1/T3 条目同步 + F1-F5 段 + 边界段更新 + 旁记 | F4/收尾3 |
| `.workbuddy/memory/topics/defects.md` | 新增 #64 | F5 |
| `.workbuddy/memory/2026-10-13.md` | 追加 F1-F5 执行段 + 旁记 | 收尾 |
| `CHANGELOG.md` | 新增 v5.1 条目 | 收尾2 |

**未改动**：概念表词表（F1 走规则侧不动词表）、文章、review、技能 SKILL.md、l3_publish.py。

## 七、回退方式（各项独立）

- F1：`check_concept_overlap` 去掉 `nh["generic"] and eh["generic"]` 条件即回 T1 原行为（dedup_selftest I13/I14 会转 FAIL 告警）。
- F2：`log_decision` 去掉 score 过滤 + 恢复按行数截断（或删 `_truncate_decision_log` 调用）。
- F3：`generate_prompt.py` 删步骤 9 的 `--file` 改回字符串传参 → 重跑 `--update-automation` 写库回读。
- F4/F5：文档类，不回退。

---

*销账报告完。F1-F5 全部销账，F6 按 Master 裁定留待另立任务。*

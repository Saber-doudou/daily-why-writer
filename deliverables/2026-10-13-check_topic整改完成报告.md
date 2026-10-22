# check_topic 整改任务完成报告书

> 文档定位：`deliverables/2026-10-13-check_topic整改任务书.md`（下称「任务书」）的执行结果报告，供 Master 交办的审核人核查。
> 执行人：当值会话（高级开发工程师视角）｜执行日期：2026-10-13｜结论：**T1 至 T6 全部完成，dedup_selftest 19/19 全绿，验收 A1 至 A8 实测达标**。
> 纪律基线：本报告所有数字均来自脚本实跑输出（证据文件见第八节），无一手写估算。

---

## 一、执行摘要

任务书要求的六项整改（T1 概念重叠检测 / T2 全候选报告+标点规范化 / T3 L1 成稿标题复查 / T4 决策日志 / T5 回归扩展 / T6 记录纠正）已全部落地，核心验收指标：

| 指标 | 结果 |
|---|---|
| 事件复现（A1 牛排候选 50.0% 漏判、top-1 雪 67% 掩蔽） | 修复前逐字复现成功，与任务书一致 |
| A1/A2/A3（牛排候选、牛排废弃标题、海水同义改写） | 修复后均 **EXIT=1 概念硬重叠拦截**，`--angle` 不可覆盖 |
| A4 至 A8（熟成/绽色/解冻/肉色/关节） | 零误杀，全部放行 |
| `dedup_selftest.py` | 基线 10/10 → 修复后 **19/19 全绿**（无回退，新增 9 项） |
| `full_selfcheck.py` 第 12 项 | 基线 FAIL → **修复后 PASS** |
| automation prompt 写库 | DB 与 `automation-prompt-latest.txt` **逐字一致**（回读校验） |
| MEMORY.md 记忆门禁 | 下沉后零损失（0 丢失）、分区配额与单行长度**全部合规** |

**任务书自查结论（执行前已完成，无异议）**：任务书关键论断全部脚本复属实：50.0%/62.5%/66.7% 数字、top-1 掩蔽现象、hy3 数字错误根因（按未使用的 `STOP_WORDS` 手算）、来源标注有误（实为 articles 文件扫描而非 topic_summaries）均验证通过。执行中发现任务书两处待修正表述（A9 行字面期望、full_selfcheck 第 12 项基线状态），详见第六节，均已按实质意图处理并如实标注。

---

## 二、执行前自查（先查后做，防止把错误当依据）

| 核验项 | 方法 | 结论 |
|---|---|---|
| A1 候选角度模式输出 | 实跑 `check_topic.py --angle "生牛排渗出的红色汁液不是血是肌红蛋白"` | 逐字复现：top-1 雪 67%，来源为 articles 文件扫描（2026-08-10-优化版），hy3 标注 [topic_summaries] 有误属实 |
| A2 废弃标题 | 实跑 `--angle --exclude-date 2026-10-13` | top-1 即牛排 67%、雪不出现，T3 复验标准成立 |
| A3 至 A8 当前行为 | 实跑 8 组用例 | 与任务书验收表「修复前」列全部一致（A3 海水漏判、A5 夜空 50% 噪声、A4/A6/A7/A8 放行） |
| 基线自检 | `dedup_selftest.py` 10/10；`full_selfcheck.py` 19/24 | 取基线防「无对比宣称修复」；**发现第 12 项基线即 FAIL**（见第六节偏差 2） |
| hy3 方案书头部标注 | 读原文 | 「已被整改任务书取代」标注已存在且完整，T6 末项仅需核验 |
| 10-13 日志 / MEMORY.md | 读原文 | 日志已含复盘纠正追加段；MEMORY.md 索引行数字已是纠正后的 50.0%/62.5% |

---

## 三、逐项执行明细

### T1 概念重叠检测（P0，已完成）

- **新增 `config/topic_concepts.json`**：严格按任务书 schema，首批仅 3 个有实证依据的家族：牛排血水（generic 牛排/牛肉，specific 血水/红色汁液/渗出液/肉汁）、海水咸（generic 海水/大海/海洋，specific 咸/盐分/盐）、关节痛天气（generic 关节/膝盖，specific 预报天气/天气预报/阴雨天/变天）。generic 仅提示不拦截；机制词（肌红蛋白等）未入表。
- **`check_topic.py` 检查 3 后插入检查 4**：新增 `load_concepts()` / `extract_concept_hits()` / `check_concept_overlap()`。判定规则按任务书修正版：新话题与已有话题命中同一 concept 且双方 specific 各 ≥1 → 硬重复（exit 1，`--angle` 不可覆盖）；仅 generic 命中不提示不拦；概念表缺失/JSON 损坏/为空 → 降级现状行为 + stderr 醒目警告（防 Silent Fail-Open，实测警告文案含「概念重叠检测（检查4）降级关闭」）。
- **实测**（修复后，全文见证据文件）：
  - A1 候选 → `❌ 重复: 概念重叠 [topic_summaries]: "为什么牛排里的血水其实不是血？" — 概念[牛排血水] 双侧命中现象词（新话题: 红色汁液；已有: 血水）`
  - A3 海水 → `概念[海水咸] 双侧命中现象词（新话题: 盐；已有: 咸）`（hy3 自设用例按其原规则判不出，修正版规则可拦）
  - 两种模式（strict / --angle）均 EXIT=1，验证「--angle 不可覆盖」。

### T2 角度模式全候选报告 + 标点规范化（P0，已完成）

- **全候选报告**：`angle_matches` 排序后全部输出（≥0.50 分数降序，至少前 5 条并给出总数「共 N 个候选」），严格模式同样列全（便于人工判断）。修复前只报 top-1。
- **ASCII 引号规范化**：`extract_core_chars` 剥离集加入 `"` `'`（原 0x22/0x27 残留使含引号标题各虚增 1 公共字符）。
- **实测**：A5 真空绽色查询输出「共 2 个候选」全列表（修复前仅见 top-1 夜空 50%）；A2 废弃标题对文章分数由 66.7% 变为 62.5%（与对台账一致），引号虚增已消除。

### T3 L1 成稿标题复查（P0，已完成）

- **`generate_prompt.py` 阶段1 新增步骤 9**（保存文章后、阶段2 前）：跑 `check_topic --angle --exclude-date {今天日期} "文章首行标题"`；exit 1 不得进入审校（含「概念重叠」说明）；exit 0 含 ⚠️ → 逐个确认全部候选后才放行。步骤 3 的 ⚠️ 分支同步改为「逐个确认全部候选」并写入 10-13 实证教训（50.0% 被 66.7% 掩蔽）。
- **写库链路**：`generate_prompt.py --update-automation` 重新生成 `config/automation-prompt-latest.txt`（14712 字节）→ `automation_update` 写入 `automation-1778312519754` → **回读 DB 与文件归一化逐字比对**。
- **回读抓出一次转抄事故并已修正**：首次写库后比对发现第 65 行行尾 `**` 被丢（DB 8394 字符 vs 文件 8396），重写后复验 DB==FILE 逐字一致、120 行全同。这正是回读纪律的价值实证。

### T4 去重决策日志（P1，已完成）

- `check_topic.py` 每次判定追加 JSONL 到 `logs/check_topic_decisions.jsonl`，schema 严格按任务书：`{ts, mode, threshold, exclude_date, topic, verdict, matches[{source, topic, score}]}`。
- 超过 5MB 自动截断（保留最近 2000 条 + 标记行）；日志失败仅 stderr 警告，不影响退出码与输出格式。
- 实测：29 条记录落盘（586KB），末条 `{"ts": "2026-10-13T12:17:00", "mode": "angle", "threshold": 0.7, ..., "verdict": "pass", "matches": [...]}`，含全部候选得分（如关节查询 matches=300 条全量），漏判率/误杀率自此可度量。

### T5 回归测试扩展（P0，已完成）

- **`dedup_selftest.py` 由 10 项扩至 19 项**（沿用既有框架，未新建脚本）：
  - 隔离区 setup 同步放入 `topic_concepts.json` 副本 + 4 个受控话题（09-07 牛排血水 / 04-03 海水是咸的作概念锚点；青蛙夏天 / 刺猬冬眠作双候选锚点，与冬眠查询实测分别 50% 与 67% 落角度区间）；
  - I7 牛排换术语 → 概念拦截（--angle 不可覆盖）；I8 海水同义改写 → 概念拦截；I9 熟成 / I10 绽色 / I11 解冻+肉色 → 零误杀放行；I12 全候选报告双候选断言（stdout 须同时含「青蛙夏天」「刺猬冬天」）；
  - R5 真实库冒烟：10-13 废弃标题 `--angle --exclude-date 2026-10-13` → 拦截（修复前该场景 --angle 会放行，是 L1 缺口的活体回归）；
  - L1/L2 锁行为：「不」必须保留在 core（`牛排里血水其实不血` 实测含「不」）；ASCII 引号必须被剥离（`血水液体` 实测无引号）。
- `STOP_WORDS` 常量已标「废弃勿用」注释（含灵敏度理由：并入后 A1 50.0%→42.9%、A2 62.5%→57.1%）。
- **`full_selfcheck.py` 第 12 项修复**（详见第六节偏差 2）：基线话题「为什么蛇没有脚还能爬行？」随库增长与「蛇没有脚还能爬得飞快」包含率 75% ≥70% 误判，换零候选话题「为什么煮粥时火太大会溢锅？」（实测 EXIT=0 干净放行）。
- **实测：19/19 ALL PASS**；既有 10 项（I1-I6、R1-R4）无回退。

### T6 记录纠正（P1，已完成）

- **`2026-10-13.md` 日志**：追加「T1-T6 整改执行完毕」段（append-only，未改历史行）；含得分口径澄清（审校综合分 95 vs validate 脚本分 100，日志首段 score100 实为脚本分，经 review.json 实测确认）。
- **MEMORY.md 分片索引行**：数字同步为纠正值并下沉。原 L18（160 字符超长行、所在区超配额 82 字符）改为 64 字符索引行，全文下沉至新建 `topics/dedup_defense.md`（事件/勘误/T1-T6 执行/验收/已知边界全文，标注读时机）。下沉前后快照 `archive/MEMORY-pre-dedup-shard-2026-10-13.md`，`verify_memory_migration.py` 零损失校验 **0 丢失**；`check_memory_size.py --strict-sections` 由基线两项违规修复为 **EXIT=0 全部合规**。
- **CHANGELOG**：记 v5.0（版本号说明见第六节偏差 4）。
- **hy3 方案书标注**：核验头部「本文已被整改任务书取代……数字与规则勿引用」完整存在，无需补充。

---

## 四、验收实测总表（修复后，全部脚本实跑）

| # | 用例 | 期望 | 修复前 | 修复后 | 结论 |
|---|---|---|---|---|---|
| A1 | 生牛排渗出的红色汁液不是血是肌红蛋白 vs 09-07 | 硬重复 | 通过（50.0%，被雪 67% 掩蔽） | EXIT=1 概念[牛排血水] | ✅ |
| A2 | 为什么切牛排时流出的"血水"根本不是血？ | 硬重复 | 62.5% 至 66.7% 角度区间，L1 未查 | EXIT=1 概念[牛排血水] | ✅ |
| A3 | 为什么大海里的盐是从哪儿来的？ vs 04-03 | 硬重复 | 通过（33.3% 漏判） | EXIT=1 概念[海水咸] | ✅ |
| A4 | 为什么牛排要熟成？ | 放行 | 通过（40.0%） | EXIT=0 | ✅ |
| A5 | 真空包装牛排绽色 | 放行 | 通过（夜空 50% 噪声） | EXIT=0 + 全候选列表 | ✅ |
| A6 | 原切牛排解冻别用水冲 | 放行 | 通过（37.5%） | EXIT=0 | ✅ |
| A7 | 看肉色判断不了牛排熟不熟 | 放行 | 通过（37.5%） | EXIT=0 | ✅ |
| A8 | 关节比天气预报还准（排除当日） | 放行 | 通过 | EXIT=0 | ✅ |
| A9 | 为什么雪是白色的？ | 放行（任务书行字面） | — | EXIT=1 精确匹配（该话题已存在，拦截至正确行为） | ⚠️ 任务书该行表述有误，实质意图（无概念命中、不掩蔽）已达成 |

**自检对比**：

| 自检 | 基线 | 修复后 | 说明 |
|---|---|---|---|
| dedup_selftest | 10/10 | **19/19** | 新增 9 项全绿，既有 10 项无回退 |
| full_selfcheck | 19/24 | **20/24** | 第 12 项 FAIL → PASS；余 4 项失败与基线完全一致（话题库 full/compact 40 vs 42、素材池 6 条缺字段、SKILL.md 区间 `~` 写法、memory 新格式提取 26 条），均为先于本任务存在的既有问题，不在 T1-T6 范围，未处理 |

---

## 五、改动文件清单

| 文件 | 变更 | 对应任务 |
|---|---|---|
| `scripts/check_topic.py` | 检查 4 概念重叠（T1）；全候选报告 + ASCII 引号剥离（T2）；决策日志（T4）；STOP_WORDS 废弃标注 | T1/T2/T4 |
| `config/topic_concepts.json` | 新建，3 族概念表 | T1 |
| `scripts/generate_prompt.py` | 阶段1 步骤 9 成稿标题复查；步骤 3 全候选确认 | T3 |
| `config/automation-prompt-latest.txt` | 重新生成（14712 字节） | T3 |
| automation DB（automation-1778312519754） | prompt 写库并回读逐字一致 | T3 |
| `scripts/dedup_selftest.py` | 10 → 19 项（I7-I12/R5/L1-L2） | T5 |
| `scripts/full_selfcheck.py` | 第 12 项 rc1 话题修复（附根因注释） | T5 |
| `.workbuddy/memory/MEMORY.md` | 分片索引行下沉为 64 字符索引 | T6 |
| `.workbuddy/memory/topics/dedup_defense.md` | 新建分片（全文） | T6 |
| `.workbuddy/memory/2026-10-13.md` | 追加执行记录段 | T6 |
| `CHANGELOG.md` | 新增 v5.0 条目 | T6 |
| `archive/MEMORY-pre-dedup-shard-2026-10-13.md` | 下沉前快照 | T6 |
| `logs/check_topic_decisions.jsonl` | 新建运行日志（29 条） | T4 |
| `deliverables/2026-10-13-check_topic整改-{修复前实测,修复后实测,基线自检,修复后自检,终验自检}.txt` | 实证存档 5 份 | 全部 |
| `deliverables/2026-10-13-check_topic整改完成报告.md` | 本报告 | — |

**未改动**：hy3 方案书（标注已存在）、articles/、review/、技能 SKILL.md 系列、l3_publish.py、version.json（无技能版本变化，故不涉及）。

---

## 六、与任务书的偏差及理由（如实披露，供审核人判断）

1. **执行顺序微调**：任务书建议 T2 → T3 → T1+T5 → T4 → T6；实际为 T1+T2（含 T4 同文件顺带实现）→ T5 → T3 → T6。理由：让代码改动先过回归测试再动生产 prompt（T3 是唯一改线上自动化的一步），降低「未验证代码进生产」风险。各任务仍独立可回退，交付物集合不变。
2. **full_selfcheck 第 12 项基线即失败（任务书假设其通过）**：实测「为什么蛇没有脚还能爬行？」与库内「蛇没有脚还能爬得飞快」字符包含率 75% ≥70% 阈值，基线即误判重复。根因是测试话题未随话题库增长而更新（测试数据腐化），非检测器缺陷。为满足任务书「第 12 项须通过」的验收口径，做最小修复：rc1 换用实测零候选的「为什么煮粥时火太大会溢锅？」，并在代码注释中记录根因。若审核人认为应保持原话题另议，可回退此一处（full_selfcheck.py 单文件）。
3. **T2 复验标准的字面场景因 T1 优先而不可直接演示**：任务书 T2 要求「A1 查询须同时展示雪 66.7% 与牛排 50.0%」，但 T1 规则明确概念命中时 `--angle` 不可覆盖（概念检查位于角度报告之前），故 A1 查询修复后直接 EXIT=1 概念拦截，不再进入角度列表。这是任务书内部 T1/T2 规则的必然相互作用，非实现缺陷。全候选报告机制改由 I12（隔离区双候选断言）+ A5（真实库「共 2 个候选」全列表）实测验证，证据充分。
4. **CHANGELOG 版本号取 v5.0 而非 v4.16**：按 2026-09-28 版本号铁律「三段式每段永不超一位数、满十进位」，v4.15 的 patch 段为 15（历史两位数段不回改），下一新编版本 patch 15+1=16 超段 → minor 进位 4→5、patch 归 0 = v5.0。这是编号规范进位，不是语义上的大版本跳跃（本次主体是修复），已在 CHANGELOG 条目内注明理由。
5. **任务书 A9 行字面期望有误**：「为什么雪是白色的？」作为查询本身已存在于库（2026-08-10 文章），精确匹配拦截止正确行为；该行「放行」的表述不成立。其实质意图（雪无概念命中、不在候选列表中掩蔽牛排）已达成：A1 场景的概念拦截来自牛排家族，雪不出现在概念判定中。
6. **MEMORY.md 除「同步改数」外顺带修了两个既有违规**：数字在任务书发出后的复盘追加段已纠正，本次动因是写入纪律「放不下先砍再写」：原索引行所在区超配额 82 字符、该行 160 字符超长，不合规无法直接写入，遂将全文下沉 `topics/dedup_defense.md` 后主文件只留索引行，顺带使 `check_memory_size --strict-sections` 回归合规（EXIT=0）。

---

## 七、风险、回退与已知边界

**回退粒度（各项独立）**：
- T1：删除 `check_topic.py` 检查 4 调用即回现状；或删 `config/topic_concepts.json`（自动降级 + stderr 警告，行为等同现状）。
- T2：还原 `format_angle_candidates` 调用为 top-1 输出、还原 `extract_core_chars` 正则（剥离集去掉 ASCII 引号）。
- T3：`generate_prompt.py` 删除阶段1 步骤 9 → 重跑 `--update-automation` 写库（prompt 回退一版）。
- T4：删除 `_finish` 中的 `log_decision` 调用（或删 logs/ 目录）。
- T5：`dedup_selftest.py` 从 git 历史恢复 10 项版本。
- T6：记录类，不回退。

**已知边界（诚实声明，与任务书第八节一致并补充实测发现）**：
1. 概念表是高价值家族的针对性补丁，不是通用语义引擎；未收录家族的「换说法」重复仍可能漏判。Phase 2 候选（本次不做）：text2vec CoSENT 语义向量（数百 MB，与零依赖约束冲突）/ L2 四 AI 投喂兼做去重交叉验证（零新增依赖，推荐优先评估）。
2. 单字 specific 有误杀隐患：概念表按任务书 schema 收录了单字「盐」「咸」，「为什么盐能让雪融化」类话题 vs「海水是咸的」会误拦（双侧 specific 命中即拦）。建议月度复盘时收紧为多字词（盐分/海水盐）。A4-A7 实测均不误杀，首批风险可控。
3. topic_summaries 无 date 字段，概念检测的 exclude-date 依赖「topics_context 刷新先于当日文章写入」的时序假设（L1 步骤 1 刷新、步骤 9 复查与该假设兼容；代码注释已注明）。
4. `config/topic_concepts.json` 未列入 `scripts/config.json` 的 `git_add_files`（与 `topics_context.json` 一致，本地有效）；若需跨设备/仓库同步，须后续纳入 L3 同步清单，本次未动（任务书未要求）。
5. `logs/check_topic_decisions.jsonl` 为运行时产物，未入同步清单，符合预期。

---

## 八、附录

### 8.1 实证文件（deliverables/）
- `2026-10-13-check_topic整改-修复前实测.txt`：A1-A8 修复前逐字输出（复现任务书数字）
- `2026-10-13-check_topic整改-修复后实测.txt`：同组用例修复后输出 + 决策日志检查
- `2026-10-13-check_topic整改-基线自检.txt`：dedup_selftest 10/10 + full_selfcheck 19/24（含第 12 项基线 FAIL 原貌）
- `2026-10-13-check_topic整改-修复后自检.txt`：T1/T2/T4/T5 落地后自检
- `2026-10-13-check_topic整改-终验自检.txt`：全部改动（含 T3/T6）后终验 19/19 + 20/24

### 8.2 关键复现命令（managed python）
```bash
PY="C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe"
# A1 概念拦截（修复前为 exit 0 + 雪 67% 提示）
"$PY" scripts/check_topic.py --angle "生牛排渗出的红色汁液不是血是肌红蛋白"
# 全候选报告（A5）
"$PY" scripts/check_topic.py --angle "为什么真空包装牛排拆开是暗紫色，遇空气才变鲜红"
# 零误杀（A4）
"$PY" scripts/check_topic.py --angle "为什么牛排要熟成？"
# 回归全量
"$PY" scripts/dedup_selftest.py
# 概念表缺失时的降级警告（执行人已实测：临时改名后 stderr 输出
# 「⚠️ 概念表缺失: ...\config\topic_concepts.json — 概念重叠检测（检查4）降级关闭，仅字符级检测生效」，
# exit 0 按现状行为放行，概念表已还原）
mv config/topic_concepts.json config/topic_concepts.json.bak
"$PY" scripts/check_topic.py --angle "为什么牛排要熟成？"
mv config/topic_concepts.json.bak config/topic_concepts.json
```

### 8.3 审核人快速核查点
1. `scripts/check_topic.py` 检查 4（`check_concept_overlap`）与 `config/topic_concepts.json` 的 schema 一致性；
2. `deliverables/2026-10-13-check_topic整改-终验自检.txt` 的 19/19 与第 12 项 PASS；
3. automation prompt 步骤 9 与 DB 回读一致（可用 sqlite 只读查询 `automations` 表 id=automation-1778312519754 的 prompt，与 `config/automation-prompt-latest.txt` 归一化比对）；
4. `topics/dedup_defense.md` 与 `archive/MEMORY-pre-dedup-shard-2026-10-13.md` 的零损失关系（`verify_memory_migration.py --snapshot` 复跑）；
5. CHANGELOG v5.0 条目与版本号进位理由。

---

*报告完。所有判定均附脚本实测证据；未验证项已在第六节与第七节如实标注。*

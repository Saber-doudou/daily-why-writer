# Daily Why 变更日志

> 记录每次重大改造的详细变更。MEMORY.md 只存精简摘要，详细日志在此。

---

## v4.7 — 2026-09-10 沙箱网络隔离 push 失败处置固化（L3 发布线 v3.16→v3.17）

**背景（09-10 实踩）**：L3 发布时 Phase 3 报「❌ 网络失败（不可重试）：github.com 探活失败」，`--retry` 在沙箱内重试同样失败，发布报告判「⚠️ 部分成功 / 错误 1 个」。但 `git log -1` 显示本地 commit `9ee9882` 已正常生成——失败发生在 push 阶段，非 commit 阶段。沙箱内 `git ls-remote origin HEAD` 直接 `Recv failure: Connection was reset`，证实为沙箱网络隔离，与凭证损坏、rebase 冲突均无关。

**根因**：既有 SOP 已固化「`unverified` 是沙箱常态不代表推送失败」，但只覆盖「push 成功返回后核验不了」这一种；未覆盖「沙箱内根本连不上、push 直接失败」这种，导致 AI 易误判为发布失败并留下错误的报告状态。

**改造（v3.17，SOP 层，不改脚本）**：边界条件表新增该场景处置链——① 先 `git log -1` 确认 commit 已生成（区分 commit 失败与 push 失败）；② 沙箱外 `git -c credential.helper=wincred push origin main`；③ 权威核验走 `curl -s https://api.github.com/repos/{owner}/{repo}/commits/main` 取 remote sha 与本地 HEAD 比对（延续铁律「不信本地 ahead 数」，且 gh CLI 在当前环境不可用：node 22 下 `gh` 报 TypeError + 依赖被黑名单的 wmic.exe）；④ 发布报告脚本生成区属 checksum 保护区不可改写，补推结论写入「AI 语义验证补充区」并注明「修正脚本区首轮结论」，保证报告反映真实最终态（EXP-014 可观测性即诚实性）。

**顺带修复**：SKILL 变更日志表补记 v3.16 行（此前标题已升 v3.16 但表格漏行），内容据 l3_publish.py 注释还原——引用机械门禁（正文含引用且 quote_checks/fact_checks 均无逐字核验 → blocking 硬阻断）。

**验证**：本次实际执行该链路成功，remote main sha = `9ee9882e89b90f62810a375d345cf1863d146c8a`，与本地 HEAD 一致。

---

## v4.6 — 2026-09-09 v3.16 引用门禁落地修复（两处）

**修复1（门禁误杀）**：v3.16 引用门禁首跑即误杀当日已发布文章——检测逻辑只认 `quote_checks` 字段，而 Reviewer 实际把逐字引用核验放在 `fact_checks`（含 DOI `10.1038/s41586-020-2643-8`、Nature 585、作者与团队逐项 match）。修正 `validate_review.py`：新增 `_has_quote_verification()`，命中「正文含引用」时，只要 `quote_checks` 或 `fact_checks` 任一处存在逐字引用核验留痕（source 指向 DOI/期刊/学术域名）即视为已核验、放行；两者皆空才 `blocking` 硬拦。单测 4 例（真实今日+构造场景）全过。

**修复2（CHANGELOG 未进 GitHub）**：v3.15 把 `CHANGELOG.md` 加进 `git_add_files` 却漏加 `l3_publish.py` 的 `files_to_copy`/`extra_sync`，导致该文件自检报「无复制源」、从未进 repo。修正：在 `extra_sync` 补 `(project_dir / "CHANGELOG.md", "CHANGELOG.md")`，与 `git_add_files` 对齐。相关缺陷 #48。

---

## v4.5 — 2026-09-09 引用机械门禁（L3 发布线 v3.15→v3.16）

**背景（决策项2）**：09-09 回执报告显示，v2 review.json 的 `quote_checks` 为空，但正文明确含《自然》引用；且 09-02 至 09-07 连续四天同类「有引用却零逐字核验」漏判（历史命中率 100%）。`validate_review.py` 此前虽有检测，但为 `warnings`（不阻断）、`CITATION_HINT` 过宽（泛词「研究显示/实验表明/大学/期刊」会误杀正常科普文）、检测源是 review json blob 而非文章正文（正文引用漏检）。落实铁律 EXP-004「约束优于指令」：把「Reviewer 是否执行逐字引用核验」变成可机械判定、可硬阻断的事实。

**改造（v3.16）**：① `validate_review.py` 检测源从 review json blob 改为 `article_path` 文章正文（正文引用不再漏检）；② `CITATION_HINT` 收窄为精确信号——书名号+年份文献、明确期刊名（《自然》《Science》等）、年份+机构+研究动词、et al./DOI；③ 命中「正文含引用且 `quote_checks` 为空」→ 升为 `errors` 且记入 `blocking` 列表；④ `l3_publish.py` Phase 1 检测到 `blocking` 即 `res.fail` + `sys.exit(1)` 硬阻断发布，逼回 Reviewer 补 `quote_checks`（与 dedup_gate_check 同构）；⑤ `validate_review.py` 新增 `--article` CLI 参数供人工回归；⑥ 版本号三处对齐 v3.16。相关缺陷 #47。

**fail-open 兜底**：`article_path` 缺失时退回 review blob 且不阻断（`warn` 不 `blocking`），避免文件缺失导致误杀或卡死；校验器自身异常仍 `warn` 不阻断。

## v4.4 — 2026-09-09 选题去重硬卡点（L3 发布线 v3.13→v3.14）

**背景**：09-08 L1 产出《蜂蜜能放几千年都不坏》撞 08-04《蜂蜜放再久也不坏》（相似度 71%），根因是去重仅靠 AI 软约束——check_topic.py 仅以 prompt 要求 AI 调用，无代码级强制，且 `--angle` 在 50%-70% 相似度主动放行放大风险。落实铁律 EXP-004「约束优于指令」，将 `DAILY_WHY_DEDUP_ENFORCE=1` 注入 L3 自动化实际调用命令（非 AI 可跳过的提示词），l3_publish.py 新增 `dedup_gate_check` 做 Phase 0 话题去重硬卡点（三态：默认软 warn 不阻断 / ENFORCE=1 硬拦 exit 1 / OFF=1 紧急关）。相关缺陷 #43。

**事故与修复（v3.14）**：v3.13 首跑即 100% 误杀——`check_topic.py` 扫 `articles/**` 把当日初版与优化版互判「精确匹配」重复（对方就是自己），Phase 0 exit 1，L3 无法执行。v3.14 修复：check_topic 增 `exclude_date` 参数 + CLI `--exclude-date`（topics 数组按 date 剔除、文章文件按文件名前缀剔除当日自身），`dedup_gate_check(articles, res, date_str)` 必传当日日期。相关缺陷 #45。

**教训**：新增硬卡点必须配「不误杀已知正常样例」回归用例（EXP-004 延伸：约束过强=全面阻断，危害大于无约束）。

## v4.3 — 2026-09-08 记忆治理 v3（闸门 0 至 5）

**背景**：记忆体系治理第三轮，落地阶段5 门禁前置 L1 + 强制输出物接线 + 动态配额 + 衰减/零损失/写入准入脚本入 extra_sync。配套 L3 发布线升至 v3.12。

## v4.2 — 2026-09-07 记忆分片重构（8 分片 + 4 个新脚本）

**背景**：09-07 记忆分片压缩重构，原 MEMORY.md「常驻缺陷台账」「铁律」等区原文搬家到 topics/ 分片（defects.md / iron_rules.md / maker_checker.md 等 8 个分片），并新增 restructure_memory.py 等 4 个治理脚本。

> ⚠️ **本次压缩丢失了「重大改造→CHANGELOG.md」这条归档规则**（原见 `MEMORY.backup.20260827.md:59`，现行 MEMORY.md 与 topics/ 分片 grep 零命中），是后续 CHANGELOG 停更 20 天的根因之一（详见缺陷 #46）。本 v4.2/v4.3/v4.4 三条即为此欠账的补记。

## v4.1 — 2026-08-20 审校机制 v2.0：恢复独立 Reviewer（撤销 v4.0 的"同步式审校"决策）

**背景**：Master 指令排查发现 08-14/17/18/19 连续 4 个发布日 v1 全部 validate 100 分通过，却 4 篇全被 L2 四 AI 揪出 P0 事实硬伤（自写自审事实拦截率≈0）。对照 history-today v9.8.2（独立 Reviewer 主路径 + 熔断链 + 文件检测，08-18 实证抓到自审漏检 P1）＋橙皮书 EXP-005（maker-checker）＋达尔文 8 维度评估（42.6 vs 85.2）后，撤销 v4.0 的"同步式审校"决策，恢复独立 Reviewer 审校。

> ⚠️ 与 v4.0 的关系：v4.0（08-13）当时因 spawn 阻塞 90 分钟卡死而改同步自审，但**未穷尽 workaround**——08-13 同一天隔壁 history-today 实证"去掉 name 参数后 spawn 成功"，08-20 本项目 spawn agent-649f7e2c 复现成功。v4.0 是"放弃主义"，v4.1 是"绕过主义"。

### P0: 独立 Reviewer 审校主路径

1. **SKILL.md 多Agent段 v1.1 → v2.0**：审校改为 spawn 独立 Reviewer（`Agent(subagent_type="general-purpose", model="reasoning")`，禁止传 name）；Reviewer 不加载写作规则；新增熔断链（去 name 重试→熔断→自审+标注「⚠️ 未独立审校」）、文件检测等待（review/{date}_review.json 落盘轮询，15min 上限）、防死循环。
2. **generate_prompt.py 阶段2 改写**：同步式审校 → 独立 Reviewer spawn + 等待策略 + 熔断链；阶段3 去 re-spawn → 重新 spawn；版本号同步 v2.0。
3. **自动化数据库已更新**（automation_update 写入，nextRunAt 正常）。
4. **reviewer_prompt.md 复活升级 v2.0**：修正脚本路径、CHECKLIST 94 项/FP 66 条、新增 6 维度审校 + 事实断言独立核验 + 文件落盘输出。
5. **spawn 实证（关键）**：08-20 spawn agent-649f7e2c 审 08-19 红酒挂杯 v1，成功抓到 2 处 P0（汤姆森是开尔文勋爵**哥哥** + **1855 年任职贝尔法斯特女王学院而非格拉斯哥大学**——后者连 L2 四 AI 都没发现）+ 1 处 P1（Q2"缩成小球"命中 FP-66）。独立审校价值当场验证。

### 遗留事项
- 08-19 已发布文章（IMA v6.0 + GitHub e5fa2fb）含"格拉斯哥大学"机构错误，v2 优化版已修正"哥哥"但未修正机构归属——建议人工确认是否补发修正版。
- 下一个工作日（08-21）自动化首跑，观察 review/{date}_review.json 是否由独立 agent 生成。

**教训**：①技术失败先找 workaround 再下"不可行"结论（去 name / 文件检测两条路都没试就放弃了）；②生成者与评判者必须分离（EXP-005），自审查不出自己写错的事实；③格式分（validate 100）≠质量分，事实核验必须独立 WebSearch。

---

## v4.0 — 2026-08-13 自动化稳定性重构 + 选题机制三管齐下

**背景**：08-13 自动化三连故障——①选题 3 轮全判重（话题池 39 个近饱和）；②阶段2 spawn Reviewer 空返回卡 90 分钟超时；③Reviewer 再次空返回。Darwin 复评 78.9 分（执行链路口径）暴露三大结构性问题：边界黑洞（spawn 阻塞防不住）、检查点缺失（失败不上报）、双架构并存（文档与执行脱节）。

### P0: 阶段2 同步式审校（根治 spawn 卡死）

1. **generate_prompt.py 阶段2**：spawn Reviewer 改为"主代理同步审校"（validate_article.py --json → auto_fix 可选 → CHECKLIST/FORBIDDEN 人工对照 → 最小结构验证 → 就地输出报告）；阶段3 去 re-spawn。
2. **SKILL.md 多Agent段 v1.0 → v1.1**：删 reviewer（spawn）行、Phase 3.5 合并、异常表新口径、消息协议改就地输出。
3. **Darwin 复评 87.3 分达标**（≥85，较 78.9 提升 8.4）；TP2（spawn 空返回）从架构上消除不可复现。

### P0: 选题机制三管齐下（根治选题枯竭）

4. **A 外部源拉取（主源）**：阶段1 选题优先 WebSearch 拉取冷知识源筛 3 候选 → check_topic --angle 去重 → 查证 → 落选回写素材池 → 降级链（脑洞→素材池→失败上报）。
5. **B 角度模式**：check_topic.py 加 ANGLE_THRESHOLD=0.50、--angle（0.50 到 0.70 区间放行+强制提示）、--threshold 可配。
6. **C L2 反哺**：feed-learning Phase 5 加"相邻话题沉淀"（四 AI 讨论未写话题 → 素材池 source=l2）。
7. **D 素材池**：topic_candidates.json 角色转可再生素材池（source 枚举 initial/external/l2/rejected，20 条初始）。

### P1: 遗留问题清理（6 项）

8. **话题库对齐**：重跑 prepare_topics 使 full/compact 一致（40 条）。
9. **--check 0 警告**：字数正则 `\d{3,}` 排除"关键词2-6字" + 风格表格支持中文数字。
10. **存量 `~` 清理**：SKILL.md FP-01~65 → "FP-01 到 65"、get_fp_range 去 `~`。
11. **历史遗留标记**：message_handler.py / review_report_template.md 加"非默认执行路径"。
12. **双架构标注**：SKILL.md 多Agent段加"执行权威"声明。
13. **三方一致性**：源码生成 == latest.txt == 数据库 prompt（4285 字符精确一致）。

### P2: 专项修复与工具

14. **topic_utils 支持 memory 新格式**（`## 日期` + `- 话题：`）：话题集从 37 扩到 **84 条**（summaries 80），full/compact 一致无重复。
15. **send_daily_why.py 去 BOM**（U+FEFF）。
16. **投喂素材早期目录补空文件**（4 目录 15 个）。
17. **新增 scripts/full_selfcheck.py**：全盘自检工具（22 项：脚本语法/JSON/引用/话题库/素材池/文章结构/三方一致性/check_topic 三态等）。

**教训**：①纸面异常规则防不住阻塞工具调用，架构上消除依赖才有效；②有限候选池必然枯竭，外部供给+内部回流才可持续；③memory.md 格式变更导致话题提取静默失效——数据格式契约要进自检。

---

## v3.5 — 2026-08-04 自动化体系瘦身

**背景**：Darwin 评估发现 3 处代码/配置重复 + 1 处过时硬编码 + 3 个历史备份。

### P0: 删除冗余副本（3 项，零风险）

1. **删除 skill writer 内 10 个 .py 副本**：auto_fix / case_matcher / format_checker / generate_prompt / message_handler / orchestrator / prepare_topics / topic_utils / update_history / validate_article — 所有自动化链路指向 `scripts/`，这些是纯冗余。`message_handler.py` 和 `topic_utils.py` 与 scripts/ 下 byte-identical。
2. **删除 skill writer 内 `writing_rules.json`**：所有脚本（GP/VA/AF/FC）均读 `config/writing_rules.json`，副本 byte-identical 无引用。
3. **删除项目根 `CODE_REVIEW_GUIDE.md`**（旧版 10475B）：保留 skill 版（10883B），更新 `scripts/README.md` 引用路径。

### P1: 修复过时硬编码

4. **feed-learning SKILL.md** 两处 `FP-01~30` → 动态表述"以 FORBIDDEN.md 实际 FP 条目为准"（实际已达 FP-65）。

### P2: 清理历史备份

5. **删除 `config/` 3 个 7月8日备份**：`automation-backup-2026-07-08.json`、`automation-complete-backup-2026-07-08.md`、`automation-snapshot-2026-07-08.md`（改动3已稳定 27 天）。

**收益**：删除 15 个冗余文件（~130KB），消除代码/规则版本分裂风险，修正 2 处过期信息引用。

---

## v2.95 — 2026-06-04 四家AI投喂学习（第三轮）

基于 DeepSeek/IMA/千问/豆包 对"伤口愈合发痒"文章的优化建议：

1. **FP-08 神经纤维功能绝对化**：描述神经纤维时避免"专门传递XX"，应写"参与传递"——大多数神经纤维是多功能的
2. **FP-09 跨系统类比不当**：类比前检查信号通路是否一致；"同一套系统"→"同一类化学语言"
3. **FP-10 止痒建议单一化**：至少提供2-3种方案，让读者有选择
4. **FP-11 漏掉读者已有体验**：读者普遍有的体感变化（如"从疼变痒"）必须解释
5. **CHECKLIST §7 类比与跨系统准确性**：类比前检查通路、措辞区分、神经纤维多功能性
6. **CHECKLIST §8 读者体验优先**：体感变化必须解释、多方案、安全提示精简但必有
7. **教训**：遗漏痂皮干燥收缩致痒机制（物理因素）、冷知识反转时间线不准确、冷敷机制描述不准确
8. **生成优化版**：`2026-06-04-优化版-每日冷知识.md`（869字，审核90分）

---

## v2.95 — 2026-06-02 SKILL.md 拆分（三层分离）

1. **元规则引入**：SKILL.md 新增 3 条元规则（教训泛化、三层分离、判例按需检索）
2. **Feedback Log**：SKILL.md 新增教训→规则转化表，记录 7 条历史教训
3. **Forbidden Pattern 编号**：黑名单改为 FP-01~FP-07 格式，新增 FP-03/04/05
4. **判例库建立**：创建 `review/CASE_STUDIES.md`，包含 7 个详细判例（CS-001~CS-007）
5. **automation prompt 升级**：步骤 8 新增判例检索逻辑（审核不通过时 Grep 判例库参考修正）

---

## v2.95 — 2026-06-02 四家AI投喂学习（第二轮）

基于 DeepSeek/IMA/千问/豆包 对"指纹"文章的优化建议：

1. **SKILL.md C段新增**：Q段之间的逻辑必须自洽（不能有表面矛盾，需搭桥）
2. **SKILL.md F段新增**：冷知识反转不能与Q3内容重复，应提供新角度
3. **SKILL.md 机制准确性新增**：科学机制要跟踪最新研究，避免引用过时解释
4. **SKILL.md 数据引用新增**：机构名必须真实存在 + 数据不能过度量化
5. **SKILL.md 写前查证新增**：核实机构名 + 搜索最新机制两个检查项
6. **生成优化版**：`2026-06-02-优化版-每日冷知识.md`（修正事实错误+补充图灵机制+搭逻辑桥+F段换角度）

---

## v2.0 — 2026-05-29 表达润色检测

借鉴 `awesome_proofreading_auto` 审稿系统的表达润色框架：

1. **SKILL.md 新增第 6 项自检**：「表达润色检查」，覆盖 4 个子维度
2. **validate_article.py 新增 3 项自动化检测**（均为 P1）：
   - 隐蔽冗余：正则匹配「在...中」「所+动词+的」「通过...使」「能...有效」「进行+万能动词」
   - 近距离重复：同段同一实词（≥2字）出现 ≥3 次
   - 连续举例标记：「例如/比如/譬如」间距 < 50 字触发
3. **验证结果**：测试用例 3/3 命中，正常文章 0/3 误报

---

## v2.0 — 2026-05-28 全流程审阅 + prompt 自动生成

1. **generate_prompt.py 新增**：从 writing_rules.json + SKILL.md 自动生成 automation prompt，消除手动同步
2. **validate_article.py GBK 修复**：加 sys.stdout reconfigure，Windows 下不再崩溃
3. **update_history.py 分类修复**：新增 `| 分类 | xxx |` 匹配
4. **P0 升级**：Q用h3格式、分隔线>3处从 P1 升级为 P0
5. **风格表格行标题检测**：新增 P2 检测（话题/分类/核心机制/冷知识反转完整性）
6. **零宽空格清理**：prepare_topics.py + update_history.py 提取话题时清理 \u200b/\ufe0f
7. **废弃文件归档**：auto_generate.py、test_qwen.py、test_qwen_simple.py → archive/
8. **回测结果**：05-11~05-28 共 14 篇，7 通过 / 7 失败（旧文章不回修）
9. **writing_rules.json v1.4**：新增 q_format_level(P0)、separator_over_tolerance_level(P0)
10. **精简排版规范**：SKILL.md 删除 3 个重复子章节，排版格式表为唯一权威
11. **prompt 删除排版铁律**：automation prompt 从 1853→1601 字符
12. **话题去重列表前移**：从 prompt 末尾移到步骤 3 之后
13. **generate_prompt.py 对齐实际 prompt**：9 步 + 写后自检 + 去重列表位置
14. **三处同步验证**：数据库 = generate_prompt.py = 备份文件完全一致

---

## v1.3 — 2026-05-26 全面优化

基于 14 篇文章（05-11~05-26）的产出分析：

1. **排版规范统一**：Q格式统一加粗（禁h3）、分隔线恰好2处、引用块A+F段必须、F段标签统一"冷知识反转"、风格表格统一4行含分类
2. **topics_context.json 刷新**：prompt 新增步骤2运行 prepare_topics.py，防止话题库过期
3. **字数上限调整**：300-600 字（原 300-500），超 600 打 P1
4. **分隔线计数 bug 修复**：content.count("---") 误把表格 |---| 计入，改为正则 ^\s*---\s*$
5. **memory.md 去重**：清理 05-13 重复标题、05-11 重复日期
6. **prepare_topics.py 分类提取**：新增 `| 分类 | xxx |` 新格式匹配
7. **update_history.py 去重增强**：模糊前8字符匹配改为精确日期+话题12字符匹配

---

## Phase A+B — 2026-05-11 话题重复修复（v2.95）

基于打哈欠主题重复事故：

1. **话题提取新增方式5+6**：修复旧格式文章（`# 每日冷知识 | 日期` + `## 为什么xxx？`）无法提取话题的 bug
2. **统一记忆路径**：update_history.py 写入路径改为优先 automation-1778312519754/memory.md
3. **记忆合并**：automation-2/memory.md 全部历史 → automation-1778312519754/memory.md
4. **修复验证**：4 篇旧文章（04-09/04-20/04-21/04-22）话题从文件名→正确标题

---

## Phase B — 2026-05-09 全面改造

基于「三只虾」内容工厂方法论，引入以下改造：

1. **防重跑**：prompt 首步检查今日文件是否已存在，存在则跳过
2. **P0/P1/P2 审核**：validate_article.py 改为分级制（P0=0 且 P1≤2 通过），新增 AI味检测
3. **写作规范 Skill 化**：daily-why-writer skill 集中管理风格规范，prompt 精简 79%
4. **规则单源**：writing_rules.json 作为唯一数值规则源
5. **失败处理**：validate.py P0>0 或 P1>2 时 exit(1)，prompt 检测到后停止流水线
6. ~~Humanizer 集成~~ 已撤除（实测与文章亲切风格冲突）
7. ~~推送~~ 已撤除（无实际发送功能）

---

## Phase A — 2026-05-07 prompt 恢复 + 脚本增强

1. 从 automation-2 迁移到 automation-1778312519754（文件系统级）
2. Phase B 脚本系统建立：prepare_topics.py、validate_article.py、update_history.py、run_pipeline.py
3. prompt 从 ~4000 字符精简至 ~900（精简 78%）
4. 执行时间：从 14:00 改为 09:30（后于 05-09 改为 09:40）

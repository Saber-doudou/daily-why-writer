# Daily Why 变更日志

> 记录每次重大改造的详细变更。MEMORY.md 只存精简摘要，详细日志在此。

---

## v5.9 — 2026-11-01 切 block 上线 + 分级阻断 + FACT_PAT 收窄 + C 方案（Reviewer 形式门禁）（Reviewer v3.2 / L2 v3.8 / L3 v3.3.0）

v5.8 当时列的「未执行（需 Master 授权）」两项，本轮拿到授权后全部执行完毕；
另补记两项 10-31 已完成但 v5.8 漏记的事项。

### 1. 证据门禁切 block + 4 级兜底接线 + 写库回读（报告决策 4/A 方案收尾）

**问题**：观察期早就跑完（10-27 至 10-30 四个工作日真跑 P0 全 0），但 automation prompt 里
两处门禁仍是 `--mode warn`，且第 4 级兜底「安全池」只有一句说明文字、没有可执行命令，
等于**兜底链在纸上**。

**改动**（`scripts/generate_prompt.py` 三处）：
- 步骤 4.5、9.5 的 `--mode warn` 改 `--mode block`；
- 4 级兜底写成可执行步骤：① 改 claim ② 定向补证 ③ 换角度 ④
  `safe_pool.py --status` + `--consume S0X --date {今天日期} --reason l4`；
- 写入切换记录与回退开关：`DAILY_WHY_GATE_RELAX=1` 当次降级（无需改 prompt / 写库 / 等次日），
  并给出回退阈值（连续 2 个工作日卡片层 P0 阻断，或单日 ≥2 次阻断）。

**验收**：`generate_prompt.py --check` exit 0；`config/automation-prompt-latest.txt`
11588 字符 / 128 行 / sha256[:16] `1f71d85f63fa7335`；写库后从会话记录解析平台返回值
**逐字节比对 EXACT MATCH**（DB 与文件两侧字符数、行数、sha 三项全等），
而不是只看 `success: true`。**这是项目硬规矩：改 prompt 必须回读比对平台。**

**时点提醒**：11-01 是周日、10-31 是周六，L1 的 rrule 是周一到周五 09:40，两天都不触发，
**首次 block 真跑是 11-02 周一**。

### 2. 分级阻断 `WARN_ONLY_P0_CODES`（10-31 完成，v5.8 漏记，此处补入）

`evidence_gate.py` 新增 `WARN_ONLY_P0_CODES = {"unmapped_fact", "unverified_mapping"}`：
只有**卡片层高置信** P0 返回 exit 1 阻断；**正文层**这两类依赖数字判据与句末映射、
误杀面宽的，自动降为 warn 只记录进 `.gate.json`。

**理由**：block 一旦误杀，当天就出不了稿。卡片层问题是「引文太短 / 缺 url / tertiary 单独支撑」
这类确定性缺陷，判得准；正文层的映射判定依赖对句中数字的识别，误杀面明显更宽。
分级不是放水，是把「判得准的」和「判不太准的」分开对待。

### 3. `FACT_PAT` 收窄：删掉裸「倍」（报告决策 4，**经实测修正报告结论**）

报告 P1-4 称 `度` 与 `倍` 都是裸字符，会误杀「态度/角度/程度/过度/知名度」与「倍感亲切」。
**实测：`度` 那条不成立** —— 现行写法要求「度」前必须有中文数字，`FACT_PAT.search("态度")`
返回 False，不会误杀。真正误杀的只有裸 `倍`（`倍感亲切`、`事半功倍`）。

**所以只删 `倍`，没有按报告删 `度`。** 差一点就因为照抄报告而制造新的漏检
（删了 `度` 会让「三度」「零下五度」这类真事实句不再被要求挂映射）。
结论写进代码注释，避免下一个人重新踩。

### 4. C 方案落地：Reviewer 正式降级为形式门禁（报告决策 2，Master 09-07 预先裁定）

**定性**：这不是新决定，是**裁定未落地**。09-07 已定「连续 3 个工作日 gap_checks 执行完整
且漏判率仍 ≥ 1/2 → 自动转 C 方案」，实际从 09-08 跑到 10-30，漏判率仍是 6/6 = 100%，
A 方案却一直在打 prompt 补丁。

**改动四处，全部同步**：

| 位置 | 改动 |
|---|---|
| `reviewer_prompt.md` v3.1 → **v3.2** | 新增「本岗职责边界」+「分级口径对照表」；Step 5/5.5/5.6/5.7/5.8/5.9 六个判断类维度降为 `advisory_findings` 只留痕不定级；Step 8 的 P0 收窄为 6 类可机械复核项；落盘自检清单增第 11 项 |
| `scripts/validate_article.py` | 输出新增 `structure_score` / `score_scope=mechanical_only` / `score_excludes`；文本改「结构分: N/100（仅机械规则，不含事实与机制判断）」，不再裸打印 `final_score: 100` |
| `scripts/validate_review.py` v1.3 → **v1.4** | 新增第 10 项校验「分值口径」：`structure_score` 必填（11-01 起按文件名日期）、与 `score` 必须同值、越界报错 |
| `contracts/review.schema.json` | 新增 `structure_score` 属性并写明语义边界；`score` 标注为已降级的兼容别名。required 仍 19 项不变（契约引擎不支持 anyOf，日期分流交给 validate_review 做，与 title_checks 同款方案） |

**责任承接**：`daily-why-feed-learning` v3.7 → **v3.8**，新增「事实与机制责任（C 方案承接）」专章。
三条硬约束：事实机制问题不得因「没把握」被过滤；四 AI 均无输入的维度必须显式写
「本维度今日无输入」而**不得默认无问题**（默认无问题正是 Reviewer 过去 6 次的做法）；
确认的问题须进 `learning_summary.json` 的 improvements。

**代价**：失去一道名义上的独立复核。但 100% 漏判还主动发绿灯的复核会让下游降低警惕，
比没有更危险。事实这一层现在有 `evidence_gate.py` 做确定性阻断，比 LLM 判断硬。

**验收**：`full_selfcheck.py` **30/30**；版本一致性 5 技能全绿
（writer v4.5 / reviewer-prompt v3.2 / publish v3.3.0 / feed-learning v3.8 / health-audit v1.6）；
`validate_review.py` 四夹具按设计分流（新日期缺字段 exit 1、补齐 exit 0、两值不一致 exit 1、
历史日期不受新规影响）；`l3_publish` 解析正则加 `structure_score/结构分` 分支后
对真实输出实测命中 `结构分: 100`。

### 5. `delivery_check.py` 派生件归类

`config/automation-prompt-latest.txt` 被判「改了但不在同步清单」。它是
`generate_prompt.py --update-automation` 的确定性产物、只作写库步骤的一次性交接件，
归入 `AUTO_DERIVED` 派生类（与 topics_context 同性质）。理由写进代码注释，
**不是为了让自检变绿而消警**：真正该进镜像的是它的生产者 `generate_prompt.py`，那个在清单里。

---

## v5.8 — 2026-10-31 审查报告整改：kill switch + sim-runs 补录 + block 退出码夹具 + 版本 v3.3.0（L3 v3.3.0）

本轮依据 `deliverables/2026-10-30-最近优化代码与流程审查报告.md`，按其「建议的来」执行 4 项，
全部**不改 prompt、不碰线上行为**。

### 1. 装 `DAILY_WHY_GATE_RELAX=1` kill switch（报告决策 1，P0）

**问题**：切 block 后 `evidence_gate` 真会阻断（11-01 起），但现行 `--mode` 写在 automation
prompt 里——改它要 改 prompt → `--update-automation` → 写库 → **次日才生效**。
按 Fowler 的 toggle 分类，这等于「关掉它需要一次发布」= 开关失职。

**修复**：`evidence_gate.py` 新增 `gate_relaxed()`，读环境变量 `DAILY_WHY_GATE_RELAX`
（1/true/yes/on 命中）。命中即把 block 降级为 warn、退出码 0，**但当次在 stderr 打印告警并把
`relaxed=true` 写进 `.gate.json`**（EXP-014：降级不得静默，否则会被读成「今天没有 P0」）。
与项目既有 `DAILY_WHY_DEDUP_RELAX=1` 同型，零学习成本。

**实测四组合**：block+有P0+开关关 → **1（阻断）**｜block+有P0+开关开 → **0（降级）**｜
block+无P0+开关关 → **0（放行）**｜报告字段 `relaxed=true blocked=false p0=2`（留痕）。

### 2. 补录 `eval/sim-runs.tsv` 的 S6/S7（报告决策 5，P2 但优先级高于编号）

该文件 mtime 停在 10-28 00:44，10-29/10-30 真实跑未录入，而它是切 block 前必须看的依据。
字节级追加两行（混合行尾 CRLF/LF 混杂，用 Edit 会规范化行尾、篡改历史行）：
- **S6** 10-29 水果不是果肉：初版 617 字→优化版 555 字，P0=0/P1=5（全 snippet_only），
  D-09 首次真产出 learning_summary.json、transport 切 json
- **S7** 10-30 螺旋桨反转：初版 587 字→优化版 687 字，P0=0/P1=6（全 snippet_only），
  注记 v1 审校 score=100/issues=0、漏判率 6/6（报告 P0-2）

**验收**：`git diff --numstat` = `2  0`（纯追加、0 删除）；12 行；行尾原样保留
（前4行 CRLF / 5-7行 LF / 新增行 CRLF）。

### 3. 补 block 模式退出码夹具（报告 P1-2）

`run_selftest()` 只调 `check_card`+`check_article`，**从不调用 `main()`**，
因此 `main()` 第 598 行 `if p0 and mode == "block": return 1` 这条真正阻断的路径**零测试覆盖**。
新增 `_cli_exit_code()` 用真实 CLI 跑临时卡片（自包含、不依赖当日产物），断言 4 种组合：
阻断 / 放行 / warn 恒放行 / kill switch 降级。**门禁自检 16/16 → 20/20**。

### 4. 版本号 `v3.3` → `v3.3.0`（报告决策 3，P1-3）

**这是上一轮我的疏漏**：按 Master「直接 3.3」进位时没查 SKILL 变更日志表，
撞上 08-17 老条目 `| v3.3 |`（实为 v3.0.3）。字符串层面完全撞号，且 `"v3.3" < "v3.28"`，
任何大小比较都会误判新版本更旧（版本门禁是等值比较才侥幸通过）。

**修复**：写作完整三段式 **v3.3.0**，四处对齐（l3_publish VERSION / SKILL frontmatter+标题+末条 /
version.json）+ CHANGELOG + 交接单；并在 08-17 老条目加注「此条为老编号，实为 v3.0.3」。
同时把 `_updated` 从 2026-10-29 同步到 2026-10-31（报告 P2-4）。

**回归全绿**：版本门禁 5/5（publish 四处全 v3.3.0）、全盘自检 **30/30**、
门禁自检 **20/20**、回放 10/10 零误杀、delivery 四方一致无缺口。

### 未执行（需 Master 授权，涉及改 prompt / SOP）

- **决策 1 后半**：11-01 切 block（先切高置信子集 tertiary/banned/unknown_claim，
  unmapped_fact/unverified_mapping 继续 warn）+ 4 级兜底写成 L1 可执行步骤（报告 P0-1）
- **决策 2**：转 C 方案，Reviewer 降级形式门禁、`score` 改名（报告 P0-2）
- **决策 4**：FACT_PAT 收窄——实测修正：报告称「度」是裸字符会误杀「态度/角度/程度」，
  **实测不成立**（`度` 在正则里要求前置中文数字，态度/角度/温度/程度均不命中）；
  真正裸的只有 `倍`（「倍感亲切」命中）。故只需修 `倍` + `\d`，无需动「度」
- **safe_pool 接入 L1**（报告 P1-1）

---

## v5.7 — 2026-10-29 安全池升 fetch 级 + R3.8 推送门修正 + 交付自检防复发固化（L3 v3.3.0）

本轮续接交接单，完成待办第 4、7 项，并兑现第 5 项遗留（接入 full_selfcheck）。

### 1. 安全池 S02/S03/S05 升 fetch 级（R3 切 block 的最后硬前置）

**空白**：8 题 12 条 claim 实测 **100% `source_level=secondary` + `verified_by=snippet`**，一条 fetch 都没有。门禁对 snippet 只给 P1 不阻断——切 block 后走到 L4 兜底，用的是一张门禁不会拦、但也没核到位的卡。

**改动**：逐条打开 url 抓原文引文（≥15 字），S02 舷窗 / S03 冰面 / S05 微波炉共 **5 条 claim** 改 `verified_by=fetch`、`confidence=high`，quote 换成逐字原文。`source_level` 保持 `secondary` 不动——升 fetch 是「核实深度」维度，`secondary` 是「信源层级」维度（这些文章本身是二手转述科普，非一级论文），两者独立，不把转述源伪装成一级源。其余 5 题（S01/S04/S06/S07/S08）显式标注「P1 级兜底：仅 snippet 级，未 fetch 原文」。

**核实证据（WebFetch 逐字回源）**：
- S02 中国军网「是什么磨平了窗户的棱角」：原文「圆角设计能把应力散开，从而大幅降低产生裂纹的风险」✅
- S03 环球科学「冰为什么是滑的」：原文「随着温度升高至零下70摄氏度，冰面的摩擦系数开始降低，并在零下7摄氏度达到最小值」✅；⚠️ 同文另有「预融化起始温度零下153摄氏度、而非此前认为的零下70左右」——两个「零下70」不同含义，已在 note 里标注勿混
- S03 上海科协「冰为什么那么滑」：原文「并不存在所谓的液体水膜，哪怕是几十个纳米的液体水膜也是不存在的」✅
- S05 文摘报「金属真的不能进微波炉吗」：原文「金属内的电子在电磁波的作用下做振动，并辐射出同频电磁波」+「金属曲率较大或带有尖端…将空气分子电离成带电粒子…直至产生电火花」✅

**验收**：3 题 `check_card` 均 **P0=0 / P1=0**；未升级 5 题对照仍报 snippet_only P1（符合预期）；safe_pool 健康检查 8 题全可用。

### 2. R3.8 推送门修正（L3 v3.28 → 进位 v3.3.0）

**D1（探活误判）**：`git_pull_rebase_push` 重试循环里 `if not github_reachable(): return False "网络失败（不可重试）"`，而 `github_reachable()` 是单次 curl（实测每次 1.7 到 2.8 秒、会偶发失败）。一次抖动，整条重试链作废，还告诉你「不可重试」。10-29 晚 `ls-remote` 报 `Empty reply` 正是这种抖动（当天 14:03 的真实发布其实已成功 `91a8746`）。
   - 修复：探活自身重试 3 次（间隔 2s / 5s），全失败才判不可达；**且探活失败不再 early-return，仍照常尝试真实 pull/push**，让 git 的真实 stderr 当裁判——curl 不通 ≠ git 不通。探活从「裁判」降级为「省时间」。

**D2（错误归类）**：`classify_git_error` 只认 network / conflict，其余全归 other，落到 abort 分支后统一打印「rebase 冲突」。真实 stderr 是 `cannot pull with rebase: You have unstaged changes`——工作区脏，rebase 根本没开始，却白跑一次 `rebase --abort`。
   - 修复：新增 `dirty` 类（`unstaged changes` / `your local changes` / `cannot pull with rebase` / `please commit or stash` 等），判 dirty 放在 conflict 之前（否则「cannot rebase」会被 conflict 分支误抓），dirty 不执行 --abort、不谎报冲突；`other` 类同样不再谎报冲突。

**防复发**：新建 `scripts/git_push_selftest.py`，14 条纯 mock 夹具（无真实网络/git 副作用）覆盖四类分流、D1 探活失败仍尝试、探活自身重试、D2 不 abort 不谎报、真冲突仍 abort（防一修就松）、真实网络错耗尽重试后返回 network。接入 full_selfcheck 第 5c 项。

### 3. 交付自检防复发固化（兑现第 5 项遗留）

- `delivery_check.py` 缺口 4 `not_in_mirror` 原先把「本轮新增、有复制源、只是还没跑 L3 送达」的**在途**文件也判红。每新增一个清单项就红到下次 L3，混进高频自检会造成告警疲劳（10-28 已埋隐患）。
   - 修复：区分**在途**（缺项能反查到 src→rel 映射、且 src 落在本轮 changed 集里 → 不判红但显式列出，诚实不静默）与**历史遗漏**（反查不到本轮复制源 → #67 类真缺陷，判红）。
   - 加 `--selftest` 反向夹具锁死这个区分（防「一修就松」把 #67 检查放宽没了），接入 full_selfcheck 第 5e 项；四方一致接入第 5d 项。
- 新增 `git_push_selftest.py`、`delivery_check.py` 均已同步进 `git_add_files` 与 `extra_sync` 两份清单（自身也被送达检查覆盖）。

### 4. 版本号读法归正（Master 10-29 裁定）

publish 链此前被误读。`v3.9 → v3.10 → … → v3.28` 实为**省略第二个点的三段式**：v3.9=v3.0.9、v3.10=v3.1.0（patch 满十进 minor 的实证）…v3.28=v3.2.8，每段个位数，十进制进位一直正确；误读成「major=3、minor=28 两位数」才会纠结要不要跳 v4.0。
**Master 10-30 拍板：本次进位到 v3.3.0**（完整三段式；消除与 08-17 老 v3.3=v3.0.3 的字符串撞号），停止在 v3.2x 上继续累加（不再产出 v3.29 这类中间版本）。规则固化进 l3_publish.py 注释 / SKILL.md 末条 / version.json：**禁止今后写 v3.30 / v3.31 这类小数点后双位数的形式**。

**回归**：版本门禁 5/5（publish 四处全 v3.3.0）、R3.8 夹具 14/14、反向夹具 PASS、全盘自检 **30/30**（从 27 项扩到 30 项）、3 篇真实文章 block 模式实跑 P0=0 / 退出码 0。

### R3 切 block 状态（未执行，留 11-01）

前置条件已全部满足：3 篇真实文章 gate P0=0（10-27/10-28/10-29）+ 安全池 3 题升 fetch。但 generate_prompt.py 第 287 行明确约定「观察期 10-27 至 10-31 用 warn，11-01 起切 block」，10-30/10-31 两天真跑还可积累误杀样本。**按既定约定与稳定优先，不擅自提前**，留到 11-01 由两处 `--mode warn` → `--mode block`（改 prompt 走 generate_prompt.py --update-automation 并回读比对平台）。

---

## v5.6 — 2026-10-29 L2 机器交接契约 + 门禁机制覆盖 + R3.9 交付链路自检（L2 v3.7 / L3 v3.28）

本轮三项，均来自 10-28 交接单待办第 2、3、5 项。

### 1. L2 Phase 5 产出 `learning_summary.json`（v3.6 → v3.7，D-09 硬条件）

**空白**：`contracts/learning_summary.schema.json`（10-26）与 `l3_publish.py` 的「JSON 优先、缺失回退正则并 warn」分支（10-26）已双双就位，**唯独 L2 侧没有生产者**，半套契约空挂。v3.4 的「契约锚点」只锁了 Markdown 章节标题，L3 拿到后仍要靠正则**猜**标题、抽 bullet——本质是把自由文本当接口用，历史已 5 次分叉（#54/#58，v3.9/v3.21/v3.23 三次「已根治」均失准）。

**改动**：Phase 5 新增第 5 步，落盘 `投喂素材/{YYYYMMDD}/learning_summary.json`，字段按 schema；Markdown 降级为渲染视图。落盘后强制 `validate_contract.py --kind learning_summary --require-v1`，rc≠0 禁止进入 Phase 6。

**验收信号**：L3 发布报告的 `transport` 字段由 `regex` 变 `json`。这是「这一步到底做没做」的可观测证据（EXP-014）。

**配套**：`validate_contract.py` 的 `--all` 由只 glob `学习总结*.md` 改为「有 JSON 取 JSON，无 JSON 保留原 glob 语义」。修正过程中发现 20260623 的 `学习总结_v2.md` 与 20260811 的第二份 md 会被「每目录取首份」静默丢掉，已改回全量枚举；新旧逻辑份数比对 93=93，零回归。

### 2. 门禁第五类检查 `mechanism_uncovered`（evidence_gate）

**空白**（审校 2.4）：既有四类检查管的是「卡片里不能有未核实的机制 claim」（卡片层），但「正文那套机制说法是不是照着卡片写的」（正文层）门禁完全不管，全靠 Reviewer。10-27 的 Q1 就是纯机制句、无数字、无映射，门禁 P0=0，靠 Reviewer 的 `elements_complete=False` 才抓出来。

**判据**：卡片里每条 `type=mechanism` 的 claim，正文必须至少引用一次；未引用即 P1 点名（先 warn 不阻断）。

**实测区分度**：
- 10-27 吹纸实验：C1（伯努利/压强，正是 Q1 讲的机制）全文一次未引用，只引了 C2/C3 → 命中 ✅
- 10-28 空杯嗡嗡声：C1（亥姆霍兹共振）未引用 → 命中 ✅
- S5 鸽子文：C1 在 Q2、Q3 各引一次 → 干净，不误报 ✅

**段级语义匹配评估后未采用**：交接单原始要求是「三个 Q 段各自的机制句至少匹配一条机制 claim（关键词或句向量均可）」。实测 10-27 Q1 与 S5 Q1 的内容与各自 mechanism claim 的重合度大致相当，关键词重叠无法把两者分开——采用只会引入噪声，与它自己的验收条件「S5 不误报」冲突。claim 级判据已能抓到同样的缺陷且零误杀，故不引入句向量依赖。

**回归**：新增 3 条夹具（未引用须命中 / 行内注释引用须干净 / mapping.fragments 引用须干净），全部断言 `expect_p1_codes` 代码集合而非条数（#68 教训：条数对上但规则没被触发也会 PASS）；自测 13/13 → 16/16；历史回放仍 10/10 零误杀。

### 3. R3.9 交付链路四方一致自检 `scripts/delivery_check.py`（L3 v3.27 → v3.28）

**空白**（#67 根因）：现有三道检查全在「清单内部」打转——① 白名单每项有没有复制源 ② 已跟踪文件在不在白名单 ③ `full_selfcheck` 只扫本地不读镜像。**没有一道问「该进清单的有没有进」，也没有一道问「清单里的有没有真落到镜像里」。**

**四方**：① 本轮交付物（工作区改动 + 未跟踪 + 最近 N 次提交，按范围过滤）② `git_add_files` ③ `l3_publish` 同步清单 ④ 镜像仓库 HEAD 树实际存在。缺一 exit 1 并指名。

**设计要点**：
- 清单用 **AST 从 `l3_publish.py` 原样提取**，不 import（避免触发发布路径副作用）、不复制第二份（避免再次漂移，与 #58 回归验证同手法）。踩到两个坑：一是 `Path(CFG["scripts_dir"]) / "x"` 写法原求值器不支持，二是**同一源文件会被复制到镜像两个位置**（`generate_prompt.py` 同时落根目录与 `scripts/`），用 `{src: rel}` 字典会让后一条静默覆盖前一条，凭空造出「无复制源」假缺口——已改为 (src, rel) 列表。
- 远端校验**默认关闭**，需显式 `--remote`。网络不通不得判红，否则会变成新的假失败（10-28 D1 教训：单次探活失败被当成「不可重试」）。
- 每日刷新的派生数据（`topics_context*.json`）排除出交付范围，否则每天必红会诱发告警疲劳（EXP-014）。
- 脚本自身补入 `extra_sync` 与 `git_add_files`——检查别人的东西，自己先被检查。

**当前状态**：`delivery_check.py` 已进两份清单，但尚未送达镜像（今日新建，需下一次 L3 发布才会复制+提交）。自检因此报 1 条 `not_in_mirror`，属**预期内正确告警**，非缺陷。

**未接入 `full_selfcheck`**：同上原因，此刻接入会让 27/27 变红且红得让人困惑。待下一次 L3 发布确认该项转绿后立即接入，作为 R4 准入的常驻检查。

---

## v5.5 — 2026-10-28 门禁映射有效性检查脱离数字门（evidence_gate，缺陷 #68）

**来源**：C4 剩余 3 次模拟执行方在 S4 上发现——同一篇文，纯文字机制句 P0=2，只插入一句带「零下二十度」的插入语就变 P0=3，差额是 `unverified_mapping`。验收方复现确认。

**根因**：`check_article` 里 `if not FACT_PAT.search(sent): continue` 把整句跳过，连带跳过了两个与数字无关的检查。这道 early-continue 只该管「事实句必须有映射」（不能要求每句叙述都挂映射，那会把整篇文变成注释灾难），却顺手把「映射本身必须有效」也一起管了。

**严重度要分开看**（避免过度反应）：
- `unknown_claim`（映射到不存在的 claim）：**真漏洞**。正文挂 `<!-- claim:C99 -->` 而卡片无此条，句子没数字时完全静默——标记指向空处，门禁却以为「已映射」放行。
- `unverified_mapping`（映射到未核实 claim）：**不算绕过**。只要卡片里有未核实的 claim，卡片层 `unverified` 照样报 P0 拦下；损失的只是「定位不到是哪一句」。

**修复**：拆成两道独立检查，注释写明为何不能合并。①「事实句必须有映射」保留 `FACT_PAT` 限制；②「映射本身必须有效」对任何带标记的句子都生效。

**回归**：新增 2 条夹具 `stress_unknown_claim_plain_sentence` / `stress_unverified_mapping_plain_sentence` 锁住不变量，自测 11/11 → 13/13；历史回放 10/10 零误杀；10-27 真实文章 P0 仍为 0（无新误杀）。

**数值变化（两版对照，各自成立）**：S4 P0 由 2 → 3（多出 `unverified_mapping`，更准），S3 仍 2、S5 仍 0、真实文章仍 0。修复前原证另存 `eval/sim-artifacts/S4/S4.pre-fix.gate.json`；`eval/sim-runs.tsv` 历史行不改（记的是修复前那次运行的真值）。

**沉淀**：defects.md #68。教训——**一道门同时管两件事时，条件最严的那个会静默掉另一个**；凡「A 场景才需要、B 场景也必须」的组合，必须拆成两个独立判断。

---

## v5.4 — 2026-10-27 R2/R3 交付物首次真正进入 GitHub + 素材池自动回捞（L3 v3.27，缺陷 #67）

**来源**：Master 问「再补推一次 GitHub」。核验时发现远端 sha 本身已是最新（`3b62eed` 已在 `refs/heads/main`），但顺手对目录树时发现更严重的问题：**R2 的契约层与 R3 的全部产物，从来没有进过 GitHub 仓库**。

**实证（远端 `ls-tree` 与镜像 `scripts/` 逐项比对）**：`validate_contract.py`、`contracts/` 四份 schema、`evidence_gate.py`、`safe_pool.py`、`safe_topics.json`、`eval/historical_claims.tsv` 全部缺失。R3 曾宣告「合并到 main」，但那只是本地工作区仓库；镜像仓库的同步白名单里根本没有这些条目。

**根因（与 #59 同源，属同一类结构性盲区）**：Phase 3 的双向自检有两个方向——「`git_add_files` 的每一项有没有复制源」和「repo 里已跟踪的文件在不在白名单」。**两个方向都不检查「当期交付物有没有进清单」**。加之外层 `full_selfcheck` 只扫本地脚本与配置，从不读镜像内容，于是脚本自检、发布报告、manifest 三者同时报绿。**缺的是「交付物 → 发布物」这一跳的反向核对**，正是死文件判据的反面。

**修复（两份清单必须同改，只改一份会触发「无复制源」告警）**：
1. `l3_publish.py` 的 `extra_sync` 与 `config.json` 的 `git_add_files` 同步补 10 项：`validate_contract.py`、`evidence_gate.py`、`safe_pool.py`、`topic_candidates.py`、`contracts/` 四份 schema、`safe_topics.json`、`eval/historical_claims.tsv`。每一项都答得出「谁读、哪步读」——contracts 由 `validate_contract` 分流读取；`validate_contract` 由 `evidence_gate` 与 L3 读；`evidence_gate` 由 L1 步骤 4.5/9.5 读；`safe_topics` 由 `safe_pool` 读，是 11-01 切 block 后的降级兜底；`topic_candidates` 由 `update_history` 末尾调用；`historical_claims` 是门禁回放样本。
2. 镜像 `.gitignore` 补 `runtime 产物`（`.workbuddy/`、`__pycache__/`、`*.pyc`）——此前这两个未跟踪目录让 `git status` 永远非空，每次 Phase 3 都要走一遍空提交判断。

**顺带落地：素材池自动回捞（替代 L1 步骤 5 的人工手改）**。步骤 5 原文「用 Bash 追加/更新，保持 JSON 合法」是纯手工、无脚本、无校验，10-27 生产实跑整步漏做且外部不可见（EXP-004 反例）。改为从既有副作用派生：每个候选在步骤 3 都要过 `check_topic`，而它本来就会写决策日志，因此「今天探测过哪些候选」早已被记录。新增 `scripts/topic_candidates.py --harvest`：读日志 → 筛（当日 + `mode=angle` + 无 `exclude_date` + `verdict=pass`）→ 减去证据卡里的成稿主题 → 去重 → 追加为 `rejected`（带 `provenance` 追溯）。挂到 `update_history.py` 末尾（L1 阶段 3 既有硬步骤），**L1 提示词一个字不改**，失败只警告不阻断。配套 `check_topic --no-log`，`dedup_selftest` / `full_selfcheck` / `safe_pool` 三处测试调用全部传上，否则日志被 20 多条测试话题污染（实测 10-27 日志 30 条里只有 3 条真实候选）。自测 14/14。

**契约数据化**：素材池每类 source 的必填字段从自检代码搬进 `topic_candidates.json` 的 `field_spec`，`topic_candidates.py` 与 `full_selfcheck.py` 共读同一份，杜绝「代码一套、文档一套」。219 条全部合规；5 条缺 `evidence` 继续在自检里点名，不塞占位假数据。

**门禁自测强化**：`evidence_gate` 自测支持 `expect_codes`。原来只比 P0 数量，**别的原因凑够条数也会 PASS**，被测规则可能压根没被触发。已有 7 个夹具全部补上理由断言；新增 3 个压力夹具覆盖已知弱点——中文数字带单位（`stress_cn_numeral_dense`）、表格行与 Q 标签双误杀（`stress_table_and_qlabel_clean`）、tertiary 与 banned 双触发（`stress_tertiary_and_banned`）。自测 8/8 → 11/11。夹具记入 `eval/sim-runs.tsv` 的 F1/F2/F3，明确标注**不计入 C4 的 5 次模拟**。

**版本对齐**：`l3_publish.py` VERSION v3.26 → v3.27 + `daily-why-publish/SKILL.md` frontmatter/标题/末条 `*Version:` 三处 + `version.json`（daily-why-publish v3.26→v3.27 + `_note` + `_updated`）。fail-closed 版本门禁实测 5 个技能全部一致、0 FAIL。

**验收**：`full_selfcheck` 26/26 → 27/27；门禁自测 11/11；素材池自测 14/14；8 项验收批次全绿。推送后 `ls-remote` 权威核验远端 `f5e728e` 与本地一致，远端目录树确认上述 10 项均已落地。

**沉淀**：defects.md #67；教训——新增交付物必须同改两份清单，且**验收要看 repo 实际内容，不能只看脚本自检结论**（自检通过与交付完成是两件事）。

---

## v5.3 — 2026-10-23 标题主体口径核对全链防线落地（reviewer_prompt v3.0 + CHECKLIST §128 + validate_review v1.2，缺陷 #66）

**来源**：Master 人工终审抓出 P0——10-23 介形虫稿件标题「为什么有的生物，把繁衍技能点满，反而灭绝了？」被读成「介形虫类群灭绝了」，与正文「现生的只有约 1.3 万种」正面矛盾。v1、v2 两版稿件、四家 AI 投喂、三轮独立审校**全链漏判**（均盯着「因果软化」，无人核对「谁灭绝了」）。Master 二轮反馈「物种也不对吧 应该是某些分支吧」「标题一直都是一种痛 我想修无从下手」→ 授权系统性修复。

**根因（结构性盲区，非粗心）**：审校 6 维度（fact/mechanism/attribution/quote/term/gap）核的全是「数字与来源对不对」，**没有一项核「标题主体与正文事实范围是否一致」**——v2 审校甚至 verified 了「现存约 1.3 万种」，却没有检查项把这条知识与标题对照。**事实核对 ≠ 范围核对**。与 #59/#60/§124 同构：约束没接到审校输入链 = 没有防线。

**查证（论文原文，不停在二手转述）**：WebFetch Nature 2018 论文页（Martins et al., "High male sexual investment as a driver of extinction in fossil ostracods"）——摘要原文 "to test how sexual selection relates to **actual species extinction**. We show that **species** with more pronounced sexual dimorphism... had estimated **extinction rates** that were **ten times higher**..."，**分析单位确认为物种**（Master 猜的「分支」反而不是论文单位）；史密森尼通稿/科普中国/文汇网全部同口径。

**稿件修复（两轮，maker-checker 独立复验各一轮）**：① v2「有的物种，把繁衍技能点满，反而绝了后？」修掉方向一（类群灭绝误读）但踩方向二（无限定泛称=过度外推，论文只研究 93 种白垩纪介形虫、正文自书「别急着套到孔雀或海象头上」）；② 终版「**为什么有的介形虫**，把繁衍技能点满，反而绝了后？」主体圈定到介形虫 + 单位保持物种级 + 「绝了后」语义上不可能用于现存类群 + 符合房体风格（近期标题全部点名主体）。表格「话题」字段同步。两轮独立复验均判定修复成立、无新 P0/P1/P2，终稿 589 字/100 分。

**机制修复（EXP-004 约束优于指令，四处全配机械校验）**：

1. **`validate_article.py` 标题 tripwire**：H1 含消亡类断言（灭绝/绝迹/消失/绝了后/消亡/灭亡/绝种）且主体为无限定泛称（有的/某些/一些+物种/生物/动物/族群/类群）→ P2 提示三项核对（主体圈定/单位与论文一致/正文现状不矛盾）。三连测试：v1、v2 两个坏标题均被抓（98 分），终版干净放过（100 分）；**全量回归 231 篇历史文章仅命中当日 v1（真阳性），误报 0**。
2. **`reviewer_prompt.md` v2.10 → v3.0**（按「每段永不超一位数、满十进位」规范进 minor）：新增 **Step 5.11 标题主体口径核对**——方向一（主体被缩小：标题断言对象灭绝而正文表明其现存）判 P0；方向二（主体被放大：无限定泛称主体）判 P1；单位纪律（物种≠分支≠类群≠个体，以论文摘要原文为准）；三项核对（主体圈定/单位与信源一致/断言强度≤正文可支撑范围）。强制留痕 `title_checks`（subject_scoped/unit_matches_source/scope_consistent_with_body/verdict/note，字段不得省略）；输出模板补字段示例；落盘自检清单增第 9 项（无条件强制）；审校流程小节标题「6 维度」→「多维核对」（Step 5.11 后已远超 6 项）。
3. **`validate_review.py` v1.1 → v1.2**：① `title_checks` 键必须存在（10-23 起强制，历史仅警告——REQUIRED_ARRAYS 增加效日豁免机制，顺带修掉 term_checks 自 09-05 起无豁免的同类瑕疵）；② 条件非空——文章 H1 或表格「话题」字段含消亡类断言时 `title_checks` ≥1 条，空数组即 FAIL（标题来源优先 `--article` 正文，缺失退回 review JSON 内记录，两者皆无 fail-open 仅警告）；③ verdict 枚举 pass/fail + 与顶层 p0/p1 计数的矛盾警告。**8 个测试用例全过**：历史 10-22 仅警告、今日 review 缺键 FAIL、合规样本 PASS、verdict=fail 计数矛盾警告、字段缺失 FAIL、空数组+坏标题 FAIL、空数组无文章路径 fail-open、终版好标题 PASS。
4. **CHECKLIST.md 新增 §128**（活跃区）：标题主体口径须与正文事实范围一致——两类错判定级别、单位纪律、三项核对、机械防线索引、10-23 案例全文、自检问题。

**版本三口径对齐**：reviewer_prompt.md 头部 v3.0 + version.json（daily-why-reviewer-prompt v2.10→v3.0 + _note + _updated 2026-10-23）+ CHANGELOG 本条目。`deliverables/L2后检查-提示词.md` 版本表同步 v2.10→v3.0。deliverables 下 15 份历史发布报告按「历史不回改」保留 v2.10 记录。

**沉淀**：defects.md #66（全文）、lessons.md 10-23 条、MEMORY.md §6 索引行（精简两行腾预算，2980/3000）。网上经验已调研并吸收：科普中国「九题法则」之甩题（悬念须与核心内容有直接科学关联）、腾讯「先成文后定题、题文互应」、KSJ 手册「标题必须与正文能支撑的范围一致」（vagus nerve 案例：标题过度承诺而正文逐段拆台，正确做法是换标题）、Duke「pique interest without lying」。

---

## v5.2 — 2026-10-20 IMA 备份落位改造 + #60 知识库上传长期静默失败根治（L3 v3.25）

**来源**：Master 指定——「dailywhy 的备份到 IMA 上要放进《workbuddy自动化备份》这个知识库首页，并且还要放到《history-today》这个笔记本里」。勘察中顺带挖出隐藏缺陷 #60。

**根因（#60，EXP-014 可观测性缺陷）**：共享工具 `ima_archive.py`（C:/Users/admin/WorkBuddy/tools/）的 `_upload_to_knowledge_base` 使用两个**不存在**的 API 路径（`openapi/knowledge/v1/import`、`import_doc`，真实前缀为 `openapi/wiki/v1`），且把知识库**根目录 folder_id**（7457707061698771）当作 `kb_id` 传入；`backup-memory` 对知识库上传失败只 print 不返回错误，l3_publish 只解析 `note_id` 不看知识库结果 → **知识库上传自始从未成功**，09-30 起所有备份实际未进知识库而发布报告全绿。实证：知识库「20-daily-why/现行版」最新备份滞留 v6.4（09-30），v7.0 及之后全部缺失。

**改造（四处）**：

1. **ima_archive.py（共享工具，参数化不破坏其他调用方）**：`_upload_to_knowledge_base` 重写为官方 `openapi/wiki/v1/add_knowledge`（media_type=11 + note_info.content_id + knowledge_base_id + 可选 folder_id，省略=根目录=首页）；`backup_memory` 新增 `note_folder_id`/`kb_folder_id` 可选参数与 `--note-folder-id=`/`--kb-folder-id=` CLI；输出 `RESULT_NOTE_ID=`/`RESULT_KB=ok|fail` 结构化行；文件头 docstring 同步。
2. **config.json（敏感文件，gitignore 内不进版本同步）**：`ima_kb_id` 由 7457707061698771 修正为真实 kb_id `vVMri-Fu1XYI1Lj0HvhJoJNUryQr_47L7CW8ep9sInU=`（search_knowledge_base 权威返回）；新增 `ima_kb_root_folder_id`（7457707061698771，根目录=首页）与 `ima_note_folder_id`（folder8966fab4b0c096b3，IMA 笔记本《history-today》，list_notebook 实测 105 篇），均附实测注释。
3. **l3_publish.py v3.25**：Phase 2 传 `--note-folder-id`（笔记归《history-today》笔记本）、不传 kb-folder-id（知识库关联落首页）；解析 `RESULT_KB` 三态落 res 记录（ok / fail / 行缺失均可见，fail 与缺失出 ⚠️）；VERSION + docstring 同步升级。
4. **版本三处对齐**：config/version.json（publish v3.24→v3.25 + _note 补记）+ l3_publish.py + publish SKILL.md（frontmatter/标题/变更日志表/页脚，**顺带补录 09-24 遗漏的 v3.24 行**）。

**验证（实跑 + 只读回验）**：① dry-run 命令构造核验（--kb-id/--note-folder-id 均在）；② 实跑 backup-memory：笔记创建成功并归入《history-today》笔记本（list_note 回验 folder_id）、知识库首页出现新条目（get_knowledge_list 根目录回验 parent_folder_id=7457707061698771）；③ ima_history.md 追加 v7.1 行（版本序列连续，下次自动检测进位 v7.2 无撞车）；④ 版本门禁 FAIL-closed 校验通过（三处口径一致）。

**同日修正（10-20 v3.26，笔记本 ID 误配）**：上述验证②中笔记归入的《history-today》笔记本系 **Master 指出路径给错**——daily-why 备份应放《**daily-why**》笔记本（foldercf745788b7fb2800，list_notebook 实测 112 篇存量，v6.4 及更早历史备份本就住此，v3.25 误配属回归性错误）。已更正 config.json `ima_note_folder_id` 并升版本 v3.26（三处对齐）。**遗留**：IMA API 无笔记移动/删除能力，v7.0（10-19 L3 正式备份）与 v7.1（10-20 实测备份）两条已误入 history-today 笔记本无法自动迁移，从 v7.2 起新备份进《daily-why》。**教训（EXP-014）**：配置类落位参数改动前应先勘察「存量数据在哪」——112 篇存量就是最硬的证据，先查再改可避免此类回归。

**已知边界**：① 笔记本/文件夹 ID 为 IMA 侧资源标识，若在 IMA 客户端被删重建需重新勘察更新 config.json（已注释留档）；② 09-30 至 10-19 知识库备份缺口（v6.5 至 v7.0 共 6 个版本只建了笔记未进库）已于 10-20 当日经 add_knowledge 逐条补关联至首页并回验（首页现存 v6.5-v7.1 共 7 条）；v6.4 老条目在「20-daily-why/现行版」子文件夹未动（API 不支持移动/删除，且未要求）；③ history-today 项目的备份链路是否同样传错 kb_id 未勘察（Master 明示自行单独处理）；④ 2026-10-20（周二）工作日 L1 未执行（articles/投喂素材/review 三目录 + automation memory + check_topic 决策日志均无当日记录，09:40 应触发），Master 裁定先不管，待平台侧排查；⑤ config.json 含 IMA KB ID 仍受 .gitignore 保护不进 repo（安全决策优先）。

---

## v5.1 — 2026-10-13 check_topic 整改补充任务清算（F1 单字 specific 误杀修复 + F2 决策日志瘦身与截断修 + F3 prompt 改 --file 模式 + F4/F5 记录沉淀）

**来源**：`deliverables/2026-10-13-check_topic整改审查报告.md`（Saber 审查结论：通过，余 3 🟡 + 2 💭）→ `deliverables/2026-10-13-check_topic整改补充任务清单.md`（F1-F6）。Master 裁定：**F1 选方案 B**（同 concept 须双方 generic 均命中才硬拦）；**F6 不打包**（范围外既有项另立任务排期）。

**修复（五项，各自独立可回退）**：

1. **F1（🟡）单字 specific 误杀修复**：`check_concept_overlap` 硬重复判定增加「双方 generic 各 ≥1」（同主体才拦）。修复「汗水为什么是咸的」「为什么盐能让雪融化」被「海水是咸的」误拦（单字 specific 在中文子串匹配下精度不足，且原拦截理由具误导性）；A1/A2/A3 真阳性不回归（「大海」与「海水」互为 generic，输出新增主词+现象词双侧明细）。已知取舍：不含量化主词的措辞（如「海里的盐」）会漏拦，属精度优先的定向交换，generic 词表扩充候选（海里/大洋）留待月度复盘。dedup_selftest 新增 I13/I14 误杀回归，19 → 21 项。
2. **F2（🟡）决策日志瘦身 + 截断机制修**：matches 只记 score ≥0.3（实测原 78% 为零分噪声、单条最大 19,765 字符）；截断改字节预算（超 5MB 时尾部保留约 2MB、按行边界对齐），修复「按行数截断（保留 2000 行 ≈26MB）永不把文件压回 5MB 以下且每次全文件读写」缺陷。实测人造 6.5MB 假日志跑一次 → 2.1MB，末条为新记录，单条 293 字节。
3. **F3（🟡）T3 prompt 改 --file 模式**：步骤 9 成稿标题复查由裸传标题字符串改 `--file "articles/{年月}/{日期}-每日冷知识-{关键词}.md"`（脚本自行提取首行标题并去 emoji，彻底消除标题含引号、$、反引号时的 shell 解释风险，顺带去掉人工抄写出错面）；步骤 3 与降级①/② 候选话题统一单引号包裹 + 新增 shell 传参纪律条。已走 `--update-automation` 写库，回读与 latest.txt 逐字一致（121 行）。
4. **F4（💭）**：`topics/dedup_defense.md`「CHANGELOG v4.16」笔误改为 v5.0（v4.16 本身是违规两位数 patch）。
5. **F5（💭）**：`topics/defects.md` #64——硬编码测试话题随语料库腐化（「蛇」话题与库内话题包含率 75% 致自检基线误判）：测试锚点优先动态取自语料库，硬编码锚点须随语料库增长复核；自检基线 FAIL 先判测试数据腐化再判被测系统缺陷。

**验证（全部脚本实测）**：dedup_selftest **21/21 全绿**（原 19 项无回退 + I13/I14 新绿）；full_selfcheck **20/24**（第 12 项保持 PASS，余 4 项与基线完全一致，属 F6 范围外未动）；F1 真实库六例（A1/A2/A3 EXIT=1 概念硬拦、汗水咸/融雪盐/熟成 EXIT=0）；F2 截断三断言全过；F3 `--file` 组合实测（关节文 --angle --exclude-date EXIT=0；--file 不带 exclude 自匹配 EXIT=1）；prompt 写库回读 DB==FILE 逐字一致。

**旁记（证据锚点流失，如实记录）**：任务书与审查报告引作证据的 `articles/2026-10/2026-10-13-每日冷知识-牛排血水_废弃.md` 于 14:25 前后被人工移除（无脚本删痕：全脚本库 unlink 仅涉 message_handler 与临时校验脚本，均不碰 articles；备份目录无此文件）。R5 回归不受影响（锚点为 topic_summaries 字符串而非文件）；A2 场景改以字符串参数等价验证（F1-A2 EXIT=1）；F3 验收中「牛排废弃文 --file EXIT=1」因文件已不存在无法按字面复跑，实质覆盖由 R5 + F1-A2 提供。

**已知边界补充**：F1 后单字 specific 仅在双方 generic 命中时可拦截；F6 四项（full/compact 不一致 40 vs 42、素材池 6 条缺字段、SKILL.md 区间 `~` 残留、memory 新格式提取 26 条）按 Master 裁定不打包，另立任务排期。

---

## v5.0 — 2026-10-13 check_topic 去重防线整改（T1 概念重叠检测 + T2 全候选报告 + T3 L1 成稿标题复查 + T4 决策日志 + T5 回归扩展 + T6 记录纠正）

**版本号说明**：上一版 v4.15 的 patch 段为 15（历史两位数段，按 2026-09-28 版本号规范不回改历史引用）。本次为新编版本号，按「每段永不超一位数、满十进位」规范：patch 15+1=16 已超段 → minor 进位 4→5、patch 归 0，故为 **v5.0**。这是编号规范进位，不是语义上的大版本跳跃（本次主体是修复）。

**来源**：10-13 选题事故——L1 候选「生牛排渗出的红色汁液不是血是肌红蛋白」实为 09-07《牛排血水不是血》重复话题，`check_topic --angle` 放行（top-1 报雪 67%，牛排 50.0% 命中被掩蔽）；成稿后经人工质疑拦截，改名 `_废弃`，改用「关节预报天气」重做。Master 裁定「选 A 修 check_topic.py」，执行依据 `deliverables/2026-10-13-check_topic整改任务书.md`。hy3《2026-10-13-check_topic修复方案.md》实证数字全部有误（42.8%/57%/17.6% → 实为 50.0%/62.5%(66.7%)/22.2%）、S1 规则与验收用例自相矛盾，已被任务书取代（其头部已标注勿引用）。

**根因（按贡献排序）**：① 检测盲区——字符级单向包含率对「同主题换术语」结构性失明（50.0% < 70% 阈值无信号）；② 报告掩蔽——角度模式只报 top-1（66.7% 的雪掩盖 50.0% 的牛排）；③ 流程缺环——L1 只查候选话题串、不查成稿标题（废弃稿标题 66.7%，L3 严格模式本可硬拦）。

**修复（六项，各自独立可回退，零新增第三方依赖）**：

1. **T1 概念重叠检测**：新建 `config/topic_concepts.json`（generic 大类词仅提示 / specific 现象词双侧命中才拦；机制词禁止入表；首批仅 3 个有实证依据的家族：牛排血水 / 海水咸 / 关节痛天气）。`check_topic.py` 检查 3 后插入检查 4：新话题与已有话题命中同一 concept 且双方 specific 各 ≥1 → 硬重复（exit 1，`--angle` 不可覆盖）；仅 generic 命中不拦；概念表缺失或为空 → 降级现状 + stderr 醒目警告（防 Silent Fail-Open）。
2. **T2 角度模式全候选报告 + 标点规范化**：≥0.50 候选全部输出（分数降序，至少前 5 条并给出总数），不再只报 top-1；ASCII 引号 `"` `'` 加入剥离集（修复 0x22 残留虚增公共字符：A2 对文章 66.7% → 62.5%，与对台账一致）。
3. **T3 L1 成稿标题复查**：`generate_prompt.py` 多 Agent prompt 阶段1 新增步骤 9（文章落盘后、进入阶段2 前，跑 `check_topic --angle --exclude-date {今天日期} "文章首行标题"`，exit 1 不得进入审校）；步骤 3 的 ⚠️ 分支改为逐个确认全部候选。prompt 走 `--update-automation` 写库，回读与 `config/automation-prompt-latest.txt` 逐字一致（回读抓出一次转抄丢 `**` 已修正）。
4. **T4 去重决策日志**：`logs/check_topic_decisions.jsonl`，schema `{ts, mode, threshold, exclude_date, topic, verdict, matches[{source, topic, score}]}`；超 5MB 自动截断；不影响退出码与现有输出格式。漏判率/误杀率自此可度量。
5. **T5 回归测试扩展**：`dedup_selftest.py` 由 10 项扩至 **19 项**（新增 I7 牛排换术语概念拦截 / I8 海水同义改写概念拦截 / I9-I11 牛排熟成、真空绽色、解冻血水、肉色熟度零误杀 / I12 全候选报告双候选断言 / R5 真实库废弃标题 --angle+排除当日拦截 / L1-L2 锁行为：「不」必须保留在 core、ASCII 引号必须剥离）；`STOP_WORDS` 常量标记废弃勿用（其「不」与内联停用字表的不一致是灵敏度的一部分，hy3 手算错误正源于此）。`full_selfcheck.py` 第 12 项修复：原话题「为什么蛇没有脚还能爬行？」随话题库增长与「蛇没有脚还能爬得飞快」包含率达 75% ≥70%，基线即误判（测试话题过时，非检测器缺陷），换零候选话题「为什么煮粥时火太大会溢锅？」。
6. **T6 记录纠正**：`.workbuddy/memory/2026-10-13.md` 追加执行记录；MEMORY.md 分片索引行下沉至 `topics/dedup_defense.md`（顺修两个既有违规：分片索引区超配额 +82 字符、L18 超长行 160 字符；下沉后零损失校验 0 丢失、分区与单行全合规）；hy3 方案书头部「已被取代」标注核验完整。

**验证（全部脚本实测）**：`dedup_selftest.py` **19/19 全绿**（修复前基线 10/10，无回退）；`full_selfcheck.py` 第 12 项由基线 FAIL 修复为 PASS（总分 20/24，余 4 项失败均为基线既有、与本任务无关：话题库 full/compact 不一致 40 vs 42、素材池 6 条缺字段、SKILL.md 区间 `~` 写法、memory 新格式提取 26 条）；验收表 A1-A8 实测达标（A1/A2/A3 概念硬拦截、A4-A8 零误杀）；A9 行字面期望与事实不符（「为什么雪是白色的？」本身已存在，精确匹配拦截至正确行为），其实质意图（无概念命中、不掩蔽）已达成——已在完成报告标注。修复前后对比实测存档：`deliverables/2026-10-13-check_topic整改-修复前实测.txt` / `2026-10-13-check_topic整改-修复后实测.txt`；自检三连（基线/修复后/终验）：`2026-10-13-check_topic整改-基线自检.txt` / `-修复后自检.txt` / `-终验自检.txt`。

**已知边界（诚实声明）**：概念表是高价值家族的针对性补丁，不是通用语义引擎，未收录家族的「换说法」重复仍可能漏；单字 specific（盐/咸）存在误杀隐患（如「为什么盐能让雪融化」vs「海水是咸的」），待月度复盘收紧为多字词；topic_summaries 无 date 字段，exclude-date 依赖「topics_context 刷新先于当日文章写入」的时序假设。Phase 2 决策项（本次不做）：text2vec CoSENT 语义向量（数百 MB，与零依赖约束冲突）/ L2 四 AI 投喂兼做去重交叉验证（零新增依赖，推荐优先评估）。

---

## v4.15 — 2026-09-18 二轮审校 issue 闭环回应机制落地（缺陷 P2-a，validate_review v1.1 + reviewer_prompt v2.10 + feed-learning v3.6）+ L2后检查提示词样例过期修复（P2-b）

**来源**：同日 L2 后检查报告 P2 项遗留（P1 已随 v4.14 修复）；Master 令「3，就修了吧」。

**P2-a 根因（先查清再动手）**：09-18 实证 v1 审校提出「补选购建议 + 明适用边界（14 岁以下）」，v2 改进点已补，但 v2 审校对 v1 issues 只字未提闭环状态。**根因不在审校 AI，在输入链**：L2 SKILL spawn 审校子 agent 的任务清单（①至⑧）从未传入 `review/{date}_review.json`——子 agent 拿不到一轮 issues，自然无从回应（与缺陷 #59「工具有效但流程不调用」同构）。

**修复三处联动（EXP-004：光加提示词无校验 = 无效）**：
1. `validate_review.py` v1.0 → **v1.1**：新增第 8 项校验——对象为 `{date}_v2_review.json` 且同日 `{date}_review.json` 存在时，`issue_responses` 必须存在且覆盖一轮 issues 全部下标（0 至 N-1），每条含 `issue_index`（整数）/`status`（枚举 resolved、partial、unresolved）/`evidence`（非空）；任一命中即 FAIL。生效日 2026-09-18（历史 v2 review 仅警告）；同日 v1 review 不存在时 fail-open 跳过（仅警告，不阻断——熔断降级场景二轮无回应对象）。
2. `reviewer_prompt.md` v2.9 → **v2.10**：新增 **Step 5.10 二轮 issue 闭环回应**（Read 一轮报告 → 逐条核对 v2 文章处理结果 → status + evidence）；输出模板增 `issue_responses` 字段示例；落盘自检清单增第 8 项（无条件强制）。
3. `daily-why-feed-learning` SKILL v3.5 → **v3.6**：Phase 2 任务内容 ⑤ 补传一轮审校报告（若存在）并明确要求按 Step 5.10 输出 `issue_responses`。

**P2-b 修复**：`deliverables/L2后检查-提示词.md` 步骤 2「通过样例」的 `char_count=632`（09-17 历史值，09-18 实测 597）改为 `<实测>` 占位——样例值永不腐，不影响 Master「贴一句话开头 + 换日期」的用法。同文件顺带同步两处已过期内容：版本表补 reviewer-prompt 行（v2.10，其 v2.8 盲点已于 v4.14 消除）、feed-learning 权威值 v3.4 → v3.6，并加「权威版本列会过期、判定以 version.json 实时值为准」提醒。

**验证**：validate_review.py ast.parse 通过 + 双向用例（详见本轮工作日志）——正例（issue_responses 完整覆盖）rc=0；反例三连（缺字段 / 覆盖不全 / status 非法）均 rc=1 且错误信息精确；历史文件（09-17 v2 review）走警告路径不阻断；今日真实 `2026-09-18_v2_review.json` 新增 1 条 issue_responses 缺失错误（预期行为，该文件确未做闭环回应，已随 v4.14 缺陷 #60 一并记台账）。版本一致性 5 项全绿（version.json 为权威）。

---

## v4.14 — 2026-09-18 v2 审校 schema 门禁落地 + 审校定位断言回读校验 + reviewer_prompt 版本盲点消除（L2 线 v3.4→v3.5，reviewer_prompt v2.8→v2.9）

**来源**：Master 令「L2 后检查」提示词首次实战（09-18），产出 `deliverables/2026-09-18-L2后检查报告.md` 报出 2 项 P1；Master 裁定「A + C，你这边不做 L3」。

**核查前置（先查清再动手）**：
- **P1-1 复核**：实跑 `validate_review.py` 对 `2026-09-18_v2_review.json` → **rc=1，精确抓出 7 项 schema 错误**，与报告一致。
- **根因深一层**：校验器**本身完整有效**，问题在**流程不拿它当门禁** —— L2 SKILL 全文零处调用（第 217 行只写「报告写入」），L3 侧虽调用但对 schema 错误仅 `res.warn` 不 `res.fail`（第 805-809 行），唯独引用门禁走 `sys.exit(1)` 硬阻断。**与缺陷 #59 同构：工具有效但流程不调用 = 等于不存在**。
- **P1-2 复核**：逐行核验 v1 全文 → `——` 实际**仅 1 处**（L3 A 段），审校称「第 3 行与第 15 行共 2 处」，L15 实为逗号。**性质比"幻觉"更具体**：该断言把自己建议的**替换示例文本**（示例中含 `——`）误当成了**原文现状**，属位置与计数双错。

**修复 A（缺陷 #60，生产侧门禁）**：L2 SKILL Phase 2 第 7 步新增「⑨ 落盘后 schema 自检」硬约束 —— v2 审校子 agent 返回后**必须**立即跑 `validate_review.py` 校验 `_v2_review.json`；rc≠0 即重新 spawn 并要求补齐缺失字段（errors 原文贴给子 agent），最多 2 轮；仍不合规则在学习总结标注「⚠️ v2 审校 JSON 不合规（已重试 2 轮）」并列缺失清单。写法照抄 Phase 5 契约锚点自检模式（有先例）。依据 EXP-004 约束优于指令。

**修复 C（缺陷 #61，可观测性）**：`reviewer_prompt.md` Step 4 新增「🔒 定位断言必须回读原文校验」硬约束 —— 凡写出具体位置/计数的断言（「第 N 行有 X」「共 N 处 X」）落盘前必须回读原文核对；禁止凭印象给位置或计数；**计数只统计原文现状，不得把自己建议的替换文本算进去**。依据 EXP-014 可观测性即诚实性。

**附带修复（09-17 核查发现的版本盲点）**：`reviewer_prompt.md` **纳入 `version.json` skills 表**（`version_field: title`），消除「零机械校验」盲区。纳入过程即验证了防线有效：首次跑校验立刻报出我自己漏改的末条 `*Version:`（权威源 v2.9 vs 末条 v2.8），补写版本行后 5 技能全绿。

**版本号对齐**：L2 `daily-why-feed-learning` v3.4→**v3.5**（frontmatter + 末条 `*Version:` + version.json + CHANGELOG）；`reviewer_prompt.md` v2.8→**v2.9**（标题 + 末条 `*Version:` + version.json 新增条目）。

**验证（双向非抽样）**：
- 版本一致性：5 技能 **0 错误 0 警告**（reviewer-prompt 首次被覆盖：`日志末条:v2.9 与权威源 v2.9 全部一致`）。
- A 门禁双用例：不合规 v2 → **rc=1（7 项错误）**；合规 v1 → **rc=0（全部通过）**。证明判据正确、不误杀。
- C 条款与 A 条款落地自检：**10 项全过**（含硬约束标题、rc 分支处置、缺陷编号、版本位）。
- 日志卫生：验证全程用临时 `log_path`，`l3_run.log` 行数未变。

**未采纳**：报告推荐的「先 L3 回头修」—— Master 裁定先修再发布；以及报告对 P1-1 的定性「审校 agent 没按 schema 输出」（只说了一半，真问题是流程未接门禁）。

---

## v4.13 — 2026-09-17 改进点提取器双断裂根治（契约锚点）+ 人工补验机械校验 + git add 静默失败修复（L3 发布线 v3.22→v3.23）

**来源**：Master 令「查 L3 版本号漂移有没有再犯 + 查最新 L3 小问题原因」，并裁定「怎么推荐怎么来，你来优化」。

**核查结论（先查清再动手）**：
- **版本号漂移未再犯**。#56 三口径升级（v3.22）09-17 首次实战全绿：四技能的可探测版本位（writer 44 条 `*Version:` 末条 v3.6 / publish 四口径 v3.22 / feed-learning v3.3 / audit v1.6）全部等于 `config/version.json` 权威源；源与 repo 12 个关键同步文件 md5 逐字节一致，脱节 0 项。
- **发现 1 处版本覆盖盲区（低危）**：`reviewer_prompt.md` 不在 `version.json` skills 表 → `check_version_consistency` 完全不覆盖它，而它既是 `git_add_files` 成员又是 maker-checker v2.0 主路径资产；且 version.json 散文备注此前滞留 `v2.7`（实际已是 v2.8，09-07 Step 5.9 自证）。本次已更正备注并写明待办。

**修复 1（#58 闸门① 标题锚点位置）**：`IMPROVEMENT_HEADING_PATTERNS` 原要求关键词紧跟「`## ` + 可选中文序号」，09-17 学习总结标题为 `## 一、四 AI 核心差距与采纳/拒绝决策`（关键词「核心差距」在**中部**，且与「采纳」以「与」并列），两条 pattern 全不匹配 → 改进点 0 条、匹配度检查 FAIL，靠 `--force` + SOP Step 2.5 人工补验 8/8 兜住。现改为「标题任意位置含关键词即可」，并把「改写要点」纳入关键词。

**修复 2（#58 闸门② 章节选取）**：原实现 `re.search` 只取**首个**命中章节。09-17 首个命中章节正文是 8 行 markdown 表格、0 个列表项，空手而归后循环即结束，后面 `## 三、v2 改写要点`（6 项编号列表，本可抽出）从未被尝试。现抽公共函数 `_extract_improvements`，用 `re.finditer` **遍历全部命中章节**取首个非空列表，并把来源章节渲染进发布报告（EXP-014）。

**修复 3（#58 闸门③ 契约锚点，治本）**：新增最高优先模式，匹配 L2 SKILL **v3.4** 强制的逐字 `## 改进点`（无编号无修饰）。这是**在生产侧立契约**，终结「L2 自由命名 vs L3 硬正则」的格式漂移（历史第 5 次分叉：`→` / `到` / `三、采纳清单` / `v2 → v3 改进点` / `一、四 AI 核心差距`）。继续在消费侧堆正则是治标（EXP-003 指令文件法则 + EXP-004 约束优于指令）。

**修复 4（#58 兜底，`--verify-report`）**：新增子模式，校验判 `总体判定: ❌ FAIL` 的发布报告，其 checksum 之后的 AI 补充区必须有「人工补验」声明且 ≥3 行判定表格，否则 exit 1。SKILL Step 2.5 新增硬约束：补验后**必跑**本命令，exit 非 0 禁止进入 Step 3。人工补验此前是纯人肉防线，AI 漏做时脚本无从知晓、该 FAIL 会被后续读者当已知噪音放过（与缺陷 #47 静默放过同构）。

**修复 5（#59 git add 静默失败 + 双向自检假绿）**：`scripts/config.json` 因含 IMA KB ID 被 repo `.gitignore:2` **有意**忽略（commit ea6465e），但从未同步从 `git_add_files` 与复制清单摘除。实测：`git check-ignore` rc=0、`git add -n` rc=1 报 `paths are ignored`、`git ls-files --error-unmatch` 未跟踪、`git log -- scripts/config.json` 末次提交即那道 gitignore 提交（此后从未再进 GitHub）。而 Phase 3 的 `subprocess.run(..., capture_output=True)` 把返回码与 stderr 全吞了 → 无声失败；双向自检只校验「白名单项有无**复制源**」，反向灰区又算 `tracked - whitelist`（未跟踪 = 隐身），**两头都不报** → 输出「白名单全覆盖，无灰区文件」的**假绿**。处置：从 `git_add_files` 与 `extra_sync` 双双移除（安全决策优先：敏感文件不进版本同步比白名单看起来完整重要），并对 `git add` 逐项**回读校验**（返回非 0 或 add 后仍未被跟踪即 warn 点名），同类静默失败今后会被暴露。

**回归（双向，非抽样）**：工作区 v3.23 与 repo v3.22 副本的正则均经 **AST 原样提取**（零转录）对跑 **70 份历史学习总结全量**：

| 指标 | 结果 |
|------|------|
| 零命中份数 | 5 → **0** |
| 条数变化 | 5 份，**全部是「由 0 变非 0」**（06-19 / 07-06 / 07-29 / 08-11 二轮 / 09-17） |
| 回归（条数下降） | **0 份**，65 份历史命中文件条数逐一不变 |
| 防误抓抽检 | 「非零但来源章节不含关键词」0 例 |
| `--verify-report` | 正例（今日真实报告 8 行判定 → exit 0）+ 4 类反例（无补充区 / 未声明且不足 3 行 / PASS 报告跳过 / 报告不存在）全部符合预期 |

**顺带定性**：v3.9「已根治」与 v3.21「已修好」两次判定失准，共性根因是**回归样本全为同一格式**（只验证「格式不变时不退步」），属采样偏差；同一失效类 08-11 学习总结-二轮其实已失效而被主文件掩盖。已同步修正 `fixed.md` 中「已根治」的失真记录。

**版本对齐**：v3.23 六处（`config/version.json` + `l3_publish.py` VERSION 常量 + 文件头 docstring + SKILL frontmatter/标题/页脚/变更日志表）+ `daily-why-feed-learning` v3.4（frontmatter + 脚注 + version.json）+ CHANGELOG v4.13。

---

## v4.12 — 2026-09-16 报告 checksum 口径缺陷 + 补充区保留 + 版本校验升级（L3 发布线 v3.21→v3.22）

**来源**：Master 回贴 09-15 L3 交付报告要求核实。独立复核确认昨日 5 项（#54 前缀 glob、#55 复制源补齐、writer 三处对齐 v3.5、audit 脚注补记 v1.6、commit bddb86e 与远端 main 一致）**全部属实**；同时挖出两处更深的问题，Master 令「#57 + #56 全修」。

**修复 1（#57a checksum 校验口径与写入口径差 1 个换行）**：`_report_script_zone_md5` 取 `text[:cut]`，而写入侧 `script_zone = "\n".join(lines)` 不含 checksum 行前那个分隔换行，两侧差 1 个换行符。后果：**每次渲染 md5 必然不等**，`check_report_tampered` 恒报「脚本生成区已被手工改动」并全量覆盖，与版本号是否变化毫无关系。硬证据：`deliverables/2026-09-15-发布报告.md` 的 recorded checksum 与 `head[:-1]` 精确相等、与 `head` 不等。此前把该现象归因为「checksum 分不清脚本自己变了和人改的」（机制局限），**定性有误**，实为纯实现 bug。修法：抽公共指纹函数 `_script_zone_digest`（尾部换行 rstrip 归一）供写入/校验两侧共用，并新增写入后回读自校验，不等即报「脚本自身缺陷」而非甩锅给人工改动（EXP-014 可观测性即诚实性）。

**修复 2（#57b AI 补充区随重渲染被清空）**：`render_report` 全量 `write_text`，脚本区一有变化（典型：版本号演进）就把 AI 补充区一起覆盖（09-15 实测首轮 5 条判定 + 规则查证 + 处置意见丢失，只能重建）。修法：改为「**标记界定所有权**」——只重写 checksum 标记之前的脚本区，标记之后的 AI 补充区无条件原样保留。业界依据（联网调研）：SilverModel 把 checksum 与 User Code Blocks 做成两套互补机制；cddl-codegen 文档明确「生成器没有上次输出的记录，无法区分『自己改写』与『用户所写』」，因此放弃「检测篡改」、改用显式 keep 标记，契约是 never silent（绝不静默）。配套：真检出脚本区被手工改动时，覆盖前自动备份旧版到 `deliverables/.overwritten/` 并在告警里给出路径。

**修复 3（#56 版本校验盲区）**：`check_version_consistency` 原按 `version_field` 走单口径，实测三处漂移全部漏判、且均为人工核对才发现（writer 变更日志区滞留 v3.3、audit 脚注漏记 v1.6、publish frontmatter 漏升 v3.21）。修法：升级为**三口径全比**（frontmatter / 标题 / 末条 `*Version:`），任一不符即 warn 并指出具体是哪个口径；同时修正原实现取**首条** `*Version:` 的隐患（变更日志正序排列，首条永远是历史最早那条，writer 有 43 条会取到 v3.1）。

**本轮活体案例**：修 #56 过程中发现 `daily-why-publish` 的 frontmatter 仍滞留 `v3.20` / `last_updated 09-15`（标题与页脚已是 v3.21）。即昨日刚做完版本漂移治理、同一轮就漏改一处，且因 `title_and_footer` 口径恰好不查 frontmatter，dry-run 全绿照不出来。已补升至 v3.22。

**遗留（下一轮评估）**：`check_report_tampered` 仍是 warn 不阻断；是否升级为对 AI 补充区的完整性告警，待观察。

**回归**：隔离日往返测试全通过（R1 首次渲染 → R2 脚本区未动时误报 0（修前恒为 1）→ R3 数据更新后脚本区重写、补充区 5 行原样保留 → R4 重渲染后误报仍 0 → R5 真篡改检出 1 + 自动备份 1、重写后补充区仍保留）；测试产物已清理。

**版本对齐**：v3.22 六处（config/version.json + l3_publish.py VERSION 常量 + 文件头 docstring + SKILL frontmatter/标题/页脚/变更日志表）+ CHANGELOG v4.12。

---

## v4.11 — 2026-09-16 两处静默绕过修复 + 版本漂移治理（L3 发布线 v3.20→v3.21）

**来源**：09-15《熊猫第六指》L3 推送实跑暴露 2 个警告（AI 报告后 Master 令「修掉」），并附带报出两个未定性的版本号不一致项。

**修复 1（#54 学习总结命名漂移 → Phase 1 整段被绕过）**：`scan_articles` 原按固定名 `投喂素材/{YYYYMMDD}/学习总结.md` 检索；L2 实际产出为 `学习总结-{话题}.md`（09-15 实为 `学习总结-熊猫第六指.md`）。零命中时脚本走 ⏭️ 跳过分支，**Phase 1 匹配度检查（结构一致性 / 审核一致性 / 规则同步三道机械校验）整段不执行**，当日靠 AI 人工补验兜住——性质同 #47（静默通道=防线失效），且 v3.9「零命中即判 FAIL」只覆盖改进点提取、未覆盖学习总结文件。改为前缀 glob `学习总结*.md`，多份命中取字典序首个并告警。**未升为硬 fail**：避免重蹈 #45「约束过强=全面阻断」，保留 warn + AI 补验双通道，待 Master 裁定是否收紧。

**修复 2（#55 两个新增产出物漏配复制源）**：`scripts/code_review_check.py`、`docs/code-review-standard.md`（09-15 代码审查体系 v4.9 新增）在 `config.json` 的 `git_add_files` 中，但不在 `l3_publish.extra_sync` 复制清单 → 源改动永远同步不到 repo（同 v3.4「B 组文件在 git_add_files 却不在 files_to_copy」老毛病复发）。补入 G 组，双向自检由「2 项无复制源」告警转为 0。**教训**：新增产出物入 `git_add_files` 时必须同步补复制清单。

**修复 3（版本漂移治理）**：① `daily-why-writer` 四处不一致——frontmatter v3.4、变更日志物理尾部 v3.3(09-11)、权威源 version.json v3.4、且 v3.4/v3.5 两条日志被误插在列表中部（08-05 与 08-07 之间）；真实最新版为 v3.5（09-15 FP-73 已落地 FORBIDDEN.md L403 / FEEDBACK_LOG L101）。已统一三处至 v3.5 并把两条日志按时间正序归位到列表末尾；② `daily-why-health-audit` v1.6（09-08）只改了 frontmatter 与标题、脚注历史串漏记，已补记。

**遗留（待 Master 决策，未改脚本）**：L3 Phase 0 版本校验仅比对 frontmatter，writer 的日志区 v3.5 / audit 的脚注区漂移均检测不到——本次两处漂移都是人工核对发现，机制层无防线。建议扩展 `version.json` 的 `version_field` 支持 `footer_latest` 等第二校验位。已入缺陷 #56。

**回归**：09-15 `--dry-run` 全绿（学习总结命中、Phase 1 PASS、改进点=5、审核 100、规则 FP-74 命中、双向自检 0 告警，与 AI 人工补验结论一致）；dedup_selftest 10/10 ALL PASS。

**版本对齐**：v3.21 三处（version.json + l3_publish.py 含文件头 docstring + SKILL 标题/页脚/变更日志）+ CHANGELOG v4.11；writer 三处对齐 v3.5。

---

## v4.10 — 2026-09-15 话题提取双源漂移修复（L3 发布线 v3.19→v3.20）

**来源**：代码审查机制（v4.9）首轮示范审查 P1-3，Master 确认「都确认」后当轮修复。

**修复**：`l3_publish._extract_topic_from_file` 旧实现只取 `splitlines()[0]`，文章首行为空行时返回 None → 去重 fail-open 放行（静默绕过窗口）；而 `check_topic.extract_topic_from_article` 同日已修为跳空行取首个非空行——同链路两个提取器行为漂移（#51/#52 同源教训再现，旧标准查不出、人工审查抓出）。新实现跳过空行取首个非空行，emoji/markdown 处理不变。

**回归**：dedup_selftest 新增 R4 用例（首行空行文件 → 提取到标题非 None），全量 10/10 ALL PASS。

**版本对齐**：v3.20 三处（version.json + l3_publish.py 含文件头 docstring + SKILL 标题/页脚）+ CHANGELOG v4.10。

**附带**：quality-reviewer.json 归档至 archive/（Master 确认；路径失效且已被 maker-checker v2.0 取代，agents/ 目录现空）。

---

## v4.9 — 2026-09-15 代码审查机制建立（标准 + 机械工具 v2.0 + pre-commit 门禁）

**背景**：Master 判定「代码质量参差不齐」，要求建立系统性代码审查机制。资产盘点发现旧版 `CODE_REVIEW_GUIDE.md`（06-05）与 `code_review_check.py` 均为死文件（无流程挂接、无迭代），且旧规则库查不出本项目任何真实缺陷（09-15 三根因 Silent Fail-Open / SSOT 漂移 / 死环境变量注入全部漏检）。

**建立（四件套）**：
1. **`docs/code-review-standard.md` v1.0**：问题分级 🔴P0/🟡P1/💭P2 + 通过线 P0=0 且 P1≤2（继承 maker-checker）；守护类脚本红线档（fail-closed 默认、双向测试强制、版本对齐含文件头 docstring、ls-remote 权威验证、同源派生、产出物「谁读哪步读」判据）；触发时机表（守护脚本改动→自测+独立审查；git commit→hook 自动 strict）。
2. **`code_review_check.py` v2.0**：修复 snake_case_function 规则反转 bug（误报正常 snake_case 函数，停用 3 个月未察觉）；新增本项目历史缺陷模式规则（env fail-open 开关、eval/exec P0、shell=True、pickle、可变默认参数、requests 无 timeout、assert 校验）；新增 `--staged`（读 git 暂存区，`git -C` 显式绑定 repo，fail-closed）；stdout 强制 UTF-8（hook 场景防 GBK）。探针实测：干净文件放行 / eval 文件 P0 拦截 exit 1。
3. **pre-commit hook**（repo `daily-why-writer/.git/hooks/pre-commit`）：commit 时自动跑 `--staged --strict`，P0 非零拒绝提交——等效「L3 发布前必跑」，零侵入 l3_publish.py。
4. **示范审查**：v3.19 四文件首轮实战（`deliverables/2026-09-15-代码审查示范报告.md`），P0=0 / P1=3，当场修复 2 条注释级（文件头 docstring v3.12→v3.19、调用点过期注释），修复后 dedup_selftest 9/9 ALL PASS（R1/R2 正好用 08-28 事故原题「云重得像一百头大象」验证拦截）；1 条话题提取双源漂移（l3_publish `splitlines()[0]` vs check_topic 跳空行版）待 Master 裁定后随下一版修复。

**同步**：config.json git_add_files 36→38（+`scripts/code_review_check.py`、+`docs/code-review-standard.md`）；死文件处置建议（agents/quality-reviewer.json 归档）记录于新标准第 7 节，待 Master 确认。

---

## v4.8 — 2026-09-15 去重防线三重加固（L3 发布线 v3.18→v3.19）

**背景（09-15 云朵重复暴雷）**：《云有多重》与 08-28《云朵很重》同题重复（继 09-08 蜂蜜后第二次同类事故）。check_topic 判重成功但 L1 照写、L3 软 warn 放行。外部经验调研（`deliverables/2026-09-15-去重防线外部经验调研.md`）定性为业界 **Silent Fail-Open** 模式；EXP-014 独立重验更发现 v3.13 的 `DAILY_WHY_DEDUP_ENFORCE=1` SKILL 注入用的是 bash 前缀语法，在 Windows 实际执行环境**从未生效**——「文档注入≠运行时生效」。

**改造（三项，均经实测验证）**：
1. **dedup 卡点默认反转 enforce**（l3_publish.py）：默认硬拦截（命中重复 → exit 1），`DAILY_WHY_DEDUP_RELAX=1` 显式豁免降软 warn；检测器自身故障 fail-open 保留（可用性设计，Praesidia/readysolutions 共识：敏感路径默认拒绝，放行须显式留痕）。SKILL Step 1/3 移除失效 ENFORCE 前缀。
2. **check_topic.py 排除 `_废弃` 后缀文件**（Azure 软删除标记教训：标记必须被读取方识别，否则等于没删）；prepare_topics.py 扫描同步排除。
3. **prepare_topics.py full/compact 同源派生**：一次 `scan_all()` 同时产出两份文件（compact 由本次 result 派生），写后断言 `topic_summaries` 一致，不一致 exit 1——根治「同一构建函数跑两次」的漂移（09-15 实测 full=40/compact=47）。

**新增**：`scripts/dedup_selftest.py` 防线双向自检（隔离 workspace 5 用例：精确重复/语义相似/全新放行/废弃排除/当日自排除 + 真实库冒烟）——落实 #45 教训「硬卡点必须配不误杀正常样例的回归用例」的制度化。

**验证**：dedup_selftest 全绿（8/8）；版本号三处对齐 v3.19（version.json + l3_publish.py + SKILL 标题/脚注）。

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

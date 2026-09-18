---
name: daily-why-publish
description: >
  验证发布技能 — AI 语义验证 + 脚本执行：检查优化版是否匹配自动化产出，记笔记到IMA，推送技能更新到GitHub，记忆归档。
  当用户需要发布当日文章到 IMA 和 GitHub 时触发。
  触发词：每日一个为什么发布、每日一个为什么推送、每日一个为什么审计、每日一个为什么备份、每日一个为什么推送备份、每日一个为什么发布备份、dailywhy发布、dailywhy推送、dailywhy审计、dailywhy备份、dailywhy推送备份、dailywhy发布备份。
  路由规则：凡输入含「发布/推送/审计/备份」动作词（如 dailywhy发布），本技能优先于
  其他 dailywhy 系列技能触发（动作词优先），触发即执行 L3 发布流程。
agent_created: true
version: v3.23
last_updated: 2026-09-17
---

# daily-why-publish v3.23

AI 语义验证 + 脚本执行，各司其职。

---

## 触发裁决（先于一切执行，2026-08-28 新增）

收到以下任一触发词（发布/推送/审计/备份系列），必须立即加载本技能并输出「✅ L3 SOP已加载」，随后进入 Step 1 脚本预检：

- 每日一个为什么发布 / 每日一个为什么推送 / 每日一个为什么审计 / 每日一个为什么备份 / 每日一个为什么推送备份 / 每日一个为什么发布备份
- dailywhy发布 / dailywhy推送 / dailywhy审计 / dailywhy备份 / dailywhy推送备份 / dailywhy发布备份

**硬约束：**
1. 禁止仅确认收到后等待；触发即执行 L3 流程。
2. **动作词优先**：输入含「发布/推送/审计/备份」动作词时，即使匹配其他 dailywhy 技能（如 L1 前缀冲突），也路由到本技能。
3. 路由以 `F:\WorkBuddy\daily-why\config\skill-trigger-map.json` 为唯一权威源，触发前先读该表核对。

---

## 执行流程

### Step 1：脚本预检

```bash
C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe F:/WorkBuddy/daily-why/scripts/l3_publish.py [YYYY-MM-DD] --dry-run --force --no-git --no-ima
```

脚本自动完成：
- 文件扫描 + 幂等性检查
- 话题去重卡点（Phase 0，check_topic 严格模式）：**默认硬拦截**——命中历史重复 exit 1 中止发布，`DAILY_WHY_DEDUP_RELAX=1` 显式豁免降软 warn（v3.19 起默认 enforce，09-15）
- 结构一致性（A/C/F 段、分类、Q 数）
- validate_article.py 审核（P0/P1/得分）
- 规则文件存在性检查（FORBIDDEN/CHECKLIST）

脚本**不再做关键词匹配**，改进点验证交给 AI。

### Step 2：AI 语义验证

> **核心原则**：判定标准是**语义等价**，不是字面匹配。判断依据是"读者能学到什么"，不是"作者想表达什么"。

#### 2.1 三档判定标准

| 判定 | 定义 | 判定条件 |
|------|------|----------|
| ✅ 落实 | 改进点的核心概念/机制/信息在文章中出现 | 读者能从文中获取该知识点，即使用词完全不同 |
| ⚠️ 部分落实 | 核心概念在，但关键术语缺失或表达精度不够 | 读者能感知方向，但无法准确复述该知识点 |
| ❌ 未落实 | 核心概念完全缺失 | 读者无法从文中获取该知识点 |

**正反例速查**：

| 改进点 | 文章内容 | 判定 | 理由 |
|--------|----------|------|------|
| 补充"接触线钉扎"为环形形成的必要前提 | L9: "接触线钉扎，是环形形成的必要前提" | ✅ | 术语+概念双全 |
| 补充 Yunker 2011 Nature：椭球颗粒形成松散网络层 | L19: "Yunker 团队…把球形颗粒压扁成椭圆形…拉手结成一张网" | ✅ | 同机制通俗化表达 |
| 补充 Marangoni 流机制：表面张力梯度驱动反向流动 | L19: "改变表面的张力分布，让传送带反着转" | ⚠️ | 机制到位，"Marangoni"术语缺失 |
| 补充 Laplace 压力公式并给出数量级估算 | 文中无任何压力公式或量级数值 | ❌ | 概念完全缺失 |

**判定铁律**：
- **同机制不同措辞 → ✅**。通俗化 ≠ 未落实
- **概念在术语缺 → ⚠️**。尤其是学术关键词（人名、效应名、专业名词）
- **判断依据是"读者能学到什么"，不是"作者想表达什么"**

#### 2.2 证据规则

- 每条判定必须引用文章原句，格式：`→ L{行号}: "{原文}"`
- 禁止空口说"文章有""文中提到"——无行号引用视为无效
- ⚠️ 和 ❌ 必须额外说明缺失了什么（术语名、数据、精度）
- 同一改进点有多个证据时，列出最强的一条

#### 2.3 通过线

| 结果 | 条件 |
|------|------|
| ✅ 通过 | 0 条 ❌ |
| ⚠️ 有条件通过 | 恰好 1 条 ❌，报告中标注该条为后续必修复项 |
| ❌ 不通过 | ≥ 2 条 ❌ |

⚠️ 条不影响通过线，但 ≥3 条 ⚠️ 时需在汇总中提醒"术语精度偏低"。

#### 2.4 输出模板

```
### 语义验证结果

| # | 改进点 | 判定 | 证据 | 说明 |
|---|--------|------|------|------|
| 1 | {改进点原文} | ✅/⚠️/❌ | → L{N}: "{原文}" | {理由，⚠️❌ 必须说明缺失项} |

### 汇总
| 判定 | 数量 |
|------|------|
| ✅ 落实 | N |
| ⚠️ 部分落实 | N |
| ❌ 未落实 | N |

**结论**：✅ 通过 / ⚠️ 有条件通过（❌ #{N}: {摘要}）/ ❌ 不通过（{N}条未落实）

{≥3条⚠️时}术语精度提醒：{N} 条 ⚠️，建议下一版重点补全学术术语。
```

#### 2.5 执行步骤

1. 从脚本输出读取改进点列表（🤖 待 AI 验证 段落）
2. 读取优化版文章全文（Read 工具，带行号）
3. 逐条搜索核心概念的语义等价表述
4. 按三档标准判定，引用原文行号
5. 按 2.4 模板输出
6. 根据 2.3 通过线返回结论

**⚠️ 改进点 0 条处理（09-03 v3.9 新增，09-17 v3.23 补充契约口径）**：脚本报「改进点=0条」时**禁止**自动判定「无可验证内容、自动通过」。
0 条 = 脚本从学习总结提取改进点失败，不是「确实没有改进点」。09-17 v3.23 起提取器已支持三档回退
（契约锚点 `## 改进点` → `v1 → v2 改进点` 类前缀 → 标题任意位置含关键词，并遍历全部命中章节），
且 L2 SKILL v3.4 已强制学习总结必须含逐字 `## 改进点` 锚点 —— 所以 v3.4 之后**再报 0 条即等于 L2 未遵守契约**，
应在补验的同时回查 L2 落盘自检为何未拦住（属契约违规，不是提取器问题）。此时必须：
1. 用 Read 直接读当日 `投喂素材/{YYYYMMDD}/学习总结.md`，从「改进点 / 采纳清单 / 核心差距 / 改写要点」等章节
   人工提取改进点（至少 3 到 7 条）；
2. 按 2.1 到 2.4 正常执行语义验证，逐条给判定与行号证据；
3. 汇总里显式注明「⚠️ 脚本提取失败，本表为 AI 人工补验」，不得伪装成脚本输出；
4. **🔒 补验完成后必须跑机械校验（09-17 v3.23 新增，硬约束）**：
   ```bash
   C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe F:/WorkBuddy/daily-why/scripts/l3_publish.py --verify-report [YYYY-MM-DD]
   ```
   该命令校验发布报告的 AI 补充区：若报告判 `总体判定: ❌ FAIL`，则补充区必须有「人工补验」声明
   且至少 3 行判定表格（`| … | ✅/⚠️/❌ | …`），否则 exit 1。
   **exit 非 0 即视为 Step 2 未完成，禁止进入 Step 3**；命令输出须贴进报告 AI 补充区留痕。
   依据 EXP-014：人工补验是**人肉防线**，没有机械校验就等于没有防线（AI 漏做时脚本无从知晓，
   该 FAIL 会被后续读者当已知噪音放过，与缺陷 #47「引用空校验静默放过」同构）。

### Step 3：执行发布

AI 判断通过后：
```bash
C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe F:/WorkBuddy/daily-why/scripts/l3_publish.py [YYYY-MM-DD] --force
```

脚本执行 Phase 1（匹配度检查，默认开启）+ Phase 2/3/4（IMA 备份、GitHub 推送、记忆归档）。匹配度检查结果由脚本渲染进发布报告 checksum 保护区（防篡改）。

**⚠️ IMA 备份约束（2026-06-23 修复）**：
- Phase 2 的 IMA 备份使用 `--config-only` 参数，**只备份 MEMORY.md 配置**
- **不包含**今日日志（`memory/{date}.md`），防止文章元数据/发布记录混入 IMA
- 参照：history-today 的同一约束（2026-06-22 BUG 修复）

### Step 4：产出汇总

AI 汇总完整报告，格式如下：

```
## 发布报告 — {YYYY-MM-DD} {话题}

### 基本信息
- 话题：{话题}
- 分类：{分类}
- 初版：{文件名}（{字数}字，{Q数}Q）
- 优化版：{文件名}（{字数}字，{Q数}Q）

### 脚本预检（Step 1）
- 结构一致性：✅/❌（分类/Q数/A/C/F）
- 审核得分：{分数}（P0={N}, P1={N}, P2={N}）
- 规则同步：✅/❌（{涉及的FP/CHECKLIST}）

### 语义验证（Step 2）
| # | 改进点 | 判定 | 证据 |
|---|--------|------|------|
| 1 | ... | ✅/⚠️/❌ | → L{N}: "..." |

汇总：✅ {N} / ⚠️ {N} / ❌ {N}
结论：✅ 通过 / ⚠️ 有条件通过 / ❌ 不通过

### 发布结果（Step 3）
- IMA：note_id={id} / ⚠️ 失败 / ⏭️ 跳过
- GitHub：commit={hash} / ⚠️ 失败 / ⏭️ 跳过
- 记忆归档：✅ / ❌

### 总体结论
✅ 发布成功 / ⚠️ 部分成功（说明）/ ❌ 发布失败（说明）

### Step 5：同步 CHANGELOG（重大改造必做，EXP-004 约束）

> ⚠️ 2026-09-09 起固化：凡本次发布涉及脚本 / l3_publish / SKILL / SOP 的**重大改造**（如去重卡点、记忆治理、结构重构），必须在发布前于项目根 `CHANGELOG.md` 补对应版本条目；纯日常发文不强制。

- `CHANGELOG.md` 已纳入 `scripts/config.json` 的 `git_add_files`，会随 L3 发布自动进 GitHub（`git_repo_path` = `daily-why-writer`），**不要再当纯本地文件**。
- 新增 / 修改版本号必须三处对齐：`config/version.json`（权威源）→ `l3_publish.py VERSION` → `SKILL.md` 标题 / 脚注 / 变更日志表。
- 历史停更根因（缺陷 #46）：09-07 记忆压缩丢失「重大改造→CHANGELOG」规则 + 流程无步骤 + 09-01 审计建议未进待办。本步骤即补该机制缺口。
```

---

## 参数速查

```bash
l3_publish.py [YYYY-MM-DD] [--dry-run] [--force] [--no-git] [--no-ima] [--skip-match] [--no-verify]
```

| 参数 | 说明 |
|------|------|
| `[日期]` | 可选，默认自动探测 articles/ 最新文章 |
| `--dry-run` | 只检查不执行 |
| `--force` | 跳过所有交互确认 |
| `--no-git` | 跳过 GitHub 推送 |
| `--no-ima` | 跳过 IMA 备份 |
| `--skip-match` | 手动逃生阀：默认运行 Phase 1；仅当 Phase 1 误判需人工放行时由 AI 临时加传 |
| `--no-verify` | 跳过 Phase 3 发布后的远端核验（沙箱网络不通时可用，默认核验） |

---

## Phase 3 远端核验（v3.1 起内置）

**背景（铁律）**：判断 commit 是否推上远程，**禁止只看本地 `git status` 的 ahead 数**。沙箱下 `git fetch` / `update-ref` 传输成功但引用**静默不落盘**，`origin/main` 陈旧会**误报 `ahead N`**（08-21、08-28 两次踩坑）。

脚本在 push 成功后**自动**执行核验，无需 AI 手动介入：

| 核验结果 | 含义 | 脚本行为 |
|----------|------|----------|
| `verified` | `ls-remote` 远程 main 与本地 HEAD 一致（或本地 HEAD 是远程 main 的祖先） | ✅ 通过，并**自动同步 `origin/main` 引用**消除误报 |
| `ok_unfixed` | 核验一致，但引用同步失败（罕见） | ⚠️ 警告，不阻塞 |
| `unverified` | 网络不通 / 超时，无法核验 | ⚠️ 提示「未核验」，**不阻塞**（push 已成功返回） |
| `mismatch` | 本地 HEAD 未包含在远程 main 中（真正未落盘） | ❌ 判失败，返回 `push_fail` |

**引用修复机制**：沙箱下 `git update-ref` / `git fetch` 在 `.git/refs/remotes/origin/` 目录缺失时会**静默失败**（不报错也不写入）。脚本改用 `mkdir -p` + 直接写 loose ref 文件绕过，写后立即用 `rev-list --count origin/main..HEAD` 复查归零。

> **AI 注意**：`unverified` 是沙箱常态（git 出网被隔离），**不代表推送失败**，禁止据此判定「未发布」。若需权威确认，在沙箱外手动执行 `git ls-remote origin HEAD` 与本地 HEAD 对比即可。

---

## 依赖关系

```
L1 daily-why-writer（每日 09:40 自动运行）
  ↓ 产出 v1 初版文章
L2 daily-why-feed-learning（手动触发）
  ↓ 产出 v2 优化版 + 学习总结
L3 daily-why-publish（手动触发）← 本 Skill
  ↓ 验证 + 发布 + 归档
```

**前置条件**：
- L1 已完成（初版文章存在）
- L2 已完成（优化版 + 学习总结存在）
- 若 L2 未完成，Step 1 脚本预检会报错终止

---

## 关键文件路径

| 文件 | 路径 |
|------|------|
| 发布脚本 | `F:/WorkBuddy/daily-why/scripts/l3_publish.py` |
| 路径配置 | `F:/WorkBuddy/daily-why/scripts/config.json` |
| 写作技能 | `~/.workbuddy/skills/daily-why-writer/SKILL.md` |
| 投喂学习 | `~/.workbuddy/skills/daily-why-feed-learning/SKILL.md` |
| 日期记忆 | `.workbuddy/memory/{YYYY-MM-DD}.md` |

---

## 降级处理

| 退出码 | 含义 | 处理 |
|--------|------|------|
| 0 | 成功 | 无需处理 |
| 1 | 致命错误 | 检查 stderr，修复后重试 |
| 2 | 部分成功（有 warning） | 检查 ⚠️ Phase，按需补做 |

### 边界条件处理

| 场景 | 处理方式 |
|------|----------|
| **优化版文件不存在** | 终止发布，提示"请先运行 L2 投喂学习生成优化版" |
| **IMA 上传失败** | 重试 1 次；仍失败则跳过 IMA，记录 `⚠️ IMA 上传失败`，不阻塞 GitHub 推送 |
| **GitHub 推送失败** | 重试 1 次；仍失败则记录 `⚠️ GitHub 推送失败（本地 ahead N）`，下次发布时自动补推 |
| **GitHub 报 `git: 'credential-manager-core' is not a git command`（凭证损坏）** | 用 `git -c credential.helper=wincred pull/push` 重试（wincred 读 Windows 凭据管理器缓存的 GitHub token；08-17 实测，l3_publish.py 已内置该参数） |
| **Phase 3 报「网络失败：github.com 探活失败」但本地 commit 已生成** | **先查 `git log -1` 确认 commit 存在**。沙箱网络隔离常态：沙箱内 push 必失败（Connection reset），属环境限制非凭证/非冲突。处置：沙箱外执行 `git -c credential.helper=wincred push origin main`，再用 `curl -s https://api.github.com/repos/{owner}/{repo}/commits/main` 取 remote sha 与本地 HEAD 比对一致即确认成功（禁止以本地 ahead 数判定）。**github.com 可达性是间歇性的**（09-10 实测：11:14 通、11:20 至 11:26 连 3 次超时、11:27 又通），push 失败应隔数分钟重试 1 到 2 次再判失败，勿急改走 REST API 写入（本机通常无 GITHUB_TOKEN，`gh` CLI 亦不可用：node22 报 TypeError 且依赖被安全策略黑名单的 wmic.exe）。发布报告脚本区为 checksum 保护区不可改写，补推结论写入「AI 语义验证补充区」并在标题注明「补推记录（修正脚本区首轮结论）」 |
| **git status 误报 ahead N（沙箱静默阻止 packed-refs 重写，fetch/update-ref 返回 0 但不生效）** | 手动写 loose ref `.git/refs/remotes/origin/main=<HEAD sha>`，再 `git rev-list --count origin/main..HEAD` 复查归零（08-17 实测） |
| **语义验证不通过** | 终止发布，输出未落实的改进点清单，等 Master 决定是否强制发布 |
| **l3_publish.py 脚本不存在** | 终止，提示检查 `scripts/l3_publish.py` 路径 |
| **Python 环境不可用** | 终止，提示检查 `C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe` |

---

## 产出清单

| 产出物 | 说明 |
|-------|------|
| 匹配度检查 | 脚本渲染进发布报告 checksum 保护区（结构+审核+规则；语义验证仍由 AI 在补充区填） |
| IMA 笔记 | 上传到 IMA 知识库 |
| Git commit + push | 推送到 GitHub |
| 记忆归档 | 追加到 memory/{date}.md |

---

---

## 版本变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
| v3.23 | 2026-09-17 | **#58 改进点提取器双断裂（同防线第 2 次复发）+ 契约锚点 + #59 git add 静默失败（三处收口，Master 令「怎么推荐怎么来」全修）**：① **#58 闸门① 标题锚点位置**——原 pattern 要求关键词紧跟「`## ` + 可选中文序号」，09-17 标题为 `## 一、四 AI 核心差距与采纳/拒绝决策`（关键词「核心差距」在**中部**且与「采纳」以「与」并列），两条 pattern 全不匹配 → 改进点 0 条、匹配度检查 FAIL，靠 `--force` + SOP Step 2.5 人工补验 8/8 兜住。现改为「标题任意位置含关键词即可」，并把「改写要点」纳入关键词。② **#58 闸门② 章节选取**——原实现 `re.search` 只取**首个**命中章节；09-17 首个命中章节正文是 8 行 markdown 表格 0 个列表项，空手而归后循环即结束，后面 `## 三、v2 改写要点`（6 项编号列表）从未被尝试。现抽 `_extract_improvements` 用 `re.finditer` **遍历全部命中章节**取首个非空列表，并把来源章节渲染进报告（EXP-014）。③ **#58 闸门③ 契约锚点**——新增最高优先模式匹配 L2 SKILL **v3.4** 强制的逐字 `## 改进点`（无编号无修饰），**在生产侧立契约**，终结「L2 自由命名 vs L3 硬正则」的格式漂移（历史第 5 次分叉：`→` / `到` / `三、采纳清单` / `v2 → v3 改进点` / `一、四 AI 核心差距`）。依据 EXP-003 指令文件法则 + EXP-004 约束优于指令：继续在消费侧堆正则是治标。④ **#58 兜底**——新增 `--verify-report` 子模式：判 `总体判定: ❌ FAIL` 的报告，AI 补充区必须有「人工补验」声明 + ≥3 行判定表格，否则 exit 1；本 SKILL Step 2.5 硬约束「补验后必跑，exit 非 0 禁止进入 Step 3」。人工补验是人肉防线，没有机械校验就等于没有防线（与 #47 静默放过同构）。⑤ **#59**——`scripts/config.json` 因含 IMA KB ID 被 repo `.gitignore:2` **有意**忽略（commit ea6465e）却仍留在 `git_add_files` + 复制清单，`git add` 被拒且调用处 `capture_output=True` 吞掉返回码 → **静默失败**；双向自检只查「有无复制源」、反向灰区又算 `tracked - whitelist`（未跟踪 = 隐身），两头都不报 → 输出「白名单全覆盖」**假绿**。现从两份清单移除，并对 `git add` 逐项**回读校验**（被拒/未跟踪即 warn 点名）。⑥ **回归（双向，非抽样）**——工作区副本 vs repo v3.22 副本正则经 AST 原样提取对跑 **70 份历史学习总结全量**：零命中 **5 → 0**，条数变化 5 份**全部是「由 0 变非 0」**（06-19 / 07-06 / 07-29 / 08-11 二轮 / 09-17），65 份历史命中文件**条数零下降**，防误抓抽检「来源章节不含关键词」为 0 例；`--verify-report` 正例（今日真实报告 8 行判定 → exit 0）+ 4 类反例（无补充区 / 未声明且不足 3 行 / PASS 报告 / 报告不存在 → 符合预期）全通过。⑦ 版本号对齐——version.json + l3_publish.py（VERSION 常量 + 文件头 docstring）+ 本 SKILL frontmatter/标题/页脚/变更日志表 + feed-learning SKILL v3.4 + CHANGELOG v4.13 |
| v3.22 | 2026-09-16 | **#57 报告 checksum 缺陷 + 补充区保留 + #56 版本校验盲区（三处收口，Master 令全修）**：① **#57a 口径统一**——`_report_script_zone_md5` 与写入侧口径差 1 个换行（写入侧 `script_zone = join(lines)` 不含 checksum 行前那个分隔换行，校验侧 `text[:cut]` 却含），导致每次渲染 md5 必不等、`check_report_tampered` 恒报「脚本区已被手工改动」并全量覆盖，**与版本号是否变化无关**（09-15 报告实测：recorded 与 `head[:-1]` 精确相等、与 `head` 不等）；AI 补充区被清空是必然而非偶发。现抽公共指纹函数 `_script_zone_digest` 供写入/校验两侧共用（尾部换行 rstrip 归一），并新增**写入后回读自校验**（不等即报脚本自身缺陷，不再甩锅给「有人手改」，EXP-014）。② **#57b 补充区保留**——`render_report` 由全量 `write_text` 改为「只重写 checksum 标记之前的脚本区，标记之后的 AI 补充区无条件原样保留」。依据业界经验：SilverModel 把 checksum 与 User Code Blocks 做成两套互补机制、cddl-codegen 明确「生成器无法反推自己上次的输出，故放弃检测、改用显式标记」——**用标记界定所有权，而不是用 checksum 猜谁改的**。③ **#56 版本校验升级**——`check_version_consistency` 由单口径（frontmatter / title / title_and_footer）升级为**三口径全比**（frontmatter / 标题 / 末条 `*Version:`），任一不符即 warn 并指出具体是哪个口径；顺带修正原实现取**首条** `*Version:` 的隐患（变更日志正序排列，首条永远是历史最早那条，writer 有 43 条会取到 v3.1）。④ 配套——publish frontmatter 补升 v3.22 + `last_updated` 09-16（此前滞留 v3.20/09-15，因 title_and_footer 口径恰好不查 frontmatter，dry-run 全绿也照不出来，正是 #56 的活体案例）。⑤ 回归——隔离日往返测试全通过（首次渲染 → 补充区保留 → 脚本区随数据更新 → 真篡改检出+自动备份），dry-run 四处版本一致；CHANGELOG v4.12 |
| v3.21 | 2026-09-16 | **#54 学习总结检索 glob 化 + #55 复制清单补齐（两处静默绕过修复）**：① #54——`scan_articles` 原按固定名 `投喂素材/{YYYYMMDD}/学习总结.md` 检索，而 L2 实际产出为 `学习总结-{话题}.md`（09-15 为 `学习总结-熊猫第六指.md`），零命中时 Phase 1 匹配度检查（结构/审核/规则三道机械校验）整段被跳过，当日靠 AI 人工补验兜住；改为前缀 glob `学习总结*.md`，多份命中取字典序首个并告警。回归：09-15 重跑 dry-run 已命中学习总结，Phase 1 真实执行（改进点=5、审核 100 分、规则 FP-74 命中）。② #55——`scripts/code_review_check.py` 与 `docs/code-review-standard.md`（09-15 代码审查体系 v4.9 新增）在 `git_add_files` 但漏配复制源，源改动永远同步不到 repo（同 v3.4 老毛病复发）；补入 `extra_sync` G 组，双向自检由 2 项告警转 0。③ 版本号三处对齐 v3.21 + CHANGELOG v4.11 |
| v3.20 | 2026-09-15 | **话题提取跳空行对齐 check_topic（双源漂移修复）**：① 来源——代码审查机制首轮示范审查（v4.9 体系）P1-3 发现 `l3_publish._extract_topic_from_file` 只取 `splitlines()[0]`，文章首行为空行时返回 None → 去重 fail-open 放行（静默绕过窗口），而 `check_topic.extract_topic_from_article` 09-15 已修为跳空行取首个非空行——同链路两个提取器行为漂移（#51/#52 同源教训再现）；② 修复——提取器改为跳过空行取首个非空行（emoji/markdown 处理不变），Master 确认后当轮修复；③ 回归——dedup_selftest 新增 R4 用例（首行空行文件 → 提取到标题非 None），全量 10/10 ALL PASS；④ 版本号三处对齐 v3.20 + CHANGELOG v4.10 |
| v3.19 | 2026-09-15 | **dedup 卡点默认反转 enforce（Silent Fail-Open 根治）**：① 背景——09-15《云有多重》与 08-28 同题重复发布（继 09-08 蜂蜜后第二次同类暴雷），复盘确认 v3.13 的 `DAILY_WHY_DEDUP_ENFORCE=1` SKILL 注入**在 Windows 执行环境不生效**（bash 前缀语法 `VAR=1 cmd` 仅 bash 可用，hy3 实际执行环境非 bash）——「文档注入≠运行时生效」（EXP-014 实证，呼应铁律 EXP-004 约束优于指令：卡点的默认值就是它的真实行为）；② 改动——l3_publish.py `dedup_gate_check` 改代码默认值：默认硬拦截（命中重复 → res.fail + exit 1），`DAILY_WHY_DEDUP_RELAX=1` 显式豁免降软 warn（留痕），检测器自身故障 fail-open 保留（可用性设计），旧 `DAILY_WHY_DEDUP_ENFORCE` 不再读取；③ 配套——本 SKILL Step 1/3 命令移除 ENFORCE 前缀（默认已 enforce，前缀删除后语义不变）；check_topic.py 排除 `_废弃` 后缀文件（Azure 软删除标记教训：标记必须被读取方识别）；prepare_topics.py full/compact 同源派生+一致性断言；新增 scripts/dedup_selftest.py 双向自检（精确重复/语义相似/全新/废弃排除/自排除 5 隔离用例 + 真实库冒烟）；④ 验证——dedup_selftest 全绿 + 临时 workspace 双向实测；⑤ 版本号三处对齐 v3.19 + CHANGELOG v4.8 |
| v3.18 | 2026-09-11 | **灰区告警豁免清单落地（Master 授权 AI 查证后决策）**：① 背景——09-09/09-10 发布报告连续两日告警「repo 有 8 个文件不在 git_add_files（灰区）」，即 09-04 达尔文优化实验一次性产物（archive/optimize-test-v2.6/2.7 review 与 validation 5 项 + reviewer_prompt-v2.5-baseline + auto-optimize-results.tsv + test-prompts.json）；② 决策依据——外部经验（FJSP-DRL / problem-drift / Research-Engineering-OS 三个独立源）一致：git 只跟踪源码与配置，实验产物/测试结果不入版本同步、归档本地；这 8 项已归档 + 双备份保护、无后续改动，「源改动同步」语义不适用，进白名单属死条目（死文件判据），每周重复告警属噪音（EXP-014 告警疲劳）；③ 落地——config.json 新增 `git_gray_exemptions`（8 项 + 理由注释键 `git_gray_exemptions_note`），l3_publish.py 灰区检测减去豁免集；文件本身仍在 git 历史中（首次 commit 已固化），**未做任何删除**；④ 反向验证——豁免前模拟重现 8 条 warn、豁免后 0 条；⑤ 版本号三处对齐 v3.18（version.json + l3_publish.py + SKILL 标题/页脚） |
| v3.17 | 2026-09-10 | **沙箱网络隔离导致 push 失败的处置固化（09-10 实踩）**：① 现象——Phase 3 报「❌ 网络失败：github.com 探活失败」，但本地 commit 已正常生成，脚本 `--retry` 沙箱内重试同样失败；② 根因——沙箱网络隔离，沙箱内 `git ls-remote` 直接 Connection reset，与凭证/冲突无关；③ 修复（SOP 层，不改脚本）——边界条件表新增该场景处置：先 `git log -1` 确认 commit 存在 → 沙箱外 `git -c credential.helper=wincred push origin main` → `curl -s https://api.github.com/repos/{owner}/{repo}/commits/main` 取 remote sha 与本地 HEAD 比对做权威核验（呼应既有铁律「不信本地 ahead 数」）→ 补推结论写进发布报告「AI 语义验证补充区」（脚本区为 checksum 保护区不可改）；④ 版本号三处对齐 v3.17 + CHANGELOG v4.7 |
| v3.16 | 2026-09-09 | **引用机械门禁（补记，此前表格漏行）**：validate_review 检测正文含引用标记而 `quote_checks` 为空 → blocking，l3 侧 `sys.exit` 硬阻断；`CITATION_HINT` 正则收窄防误杀。落实「引用必须有出处校验」的机械约束（EXP-004） |
| v3.15 | 2026-09-09 | **CHANGELOG 补记机制落地（方案1）**：① 补记 09-07 记忆分片重构 / 09-08 记忆治理 v3 / 09-09 去重硬卡点三波欠账（CHANGELOG.md v4.2/v4.3/v4.4，此前因 09-07 记忆压缩丢失「重大改造→CHANGELOG」规则 + 流程无步骤 + 09-01 审计建议未进待办而停更 20 天，见缺陷 #46）；② L3 SKILL 新增「重大改造必更新 CHANGELOG」步骤（落实 EXP-004 约束优于指令，把补记从 AI 自觉变 SOP 步骤）；③ config.json `git_add_files` 纳入 CHANGELOG.md，使其真进 GitHub（此前纯本地文件）；④ 顺带修 S1（topic_summaries 无 date 字段，依赖发布时序约定并加注释锁死）/ S2（date_str 缺失由静默退化改为 res.warn 可见）；⑤ 版本号三处对齐 v3.15（config/version.json + l3_publish.py + SKILL 标题/脚注） |
| v3.14 | 2026-09-09 | **去重卡点自匹配缺陷修复（v3.13 上线即暴雷）**：① 现象——`DAILY_WHY_DEDUP_ENFORCE=1` 首次实跑，当日初版与优化版被各自判为「精确匹配文章文件」重复，Phase 0 exit 1，L3 100% 无法执行；② 根因——`check_topic.py` 扫描 `articles/**` 时包含当日自身文件，去重卡点未做自身排除，「与历史去重」语义变成「与自己比」；③ 修复——`check_topic.py` 新增 `--exclude-date YYYY-MM-DD`（`check_topic()` 增加 `exclude_date` 参数，topics 数组按 date 剔除 + 文章文件按文件名前缀剔除），`l3_publish.py dedup_gate_check()` 增加 `date_str` 形参并在调用时必传 `--exclude-date`；④ 版本号三处对齐 v3.14（config/version.json + l3_publish.py + SKILL 标题/脚注）。**教训（EXP-004）**：硬卡点上线前必须有「对已知正常样例不误杀」的回归用例，否则约束只会 100% 阻断 |
| v3.13 | 2026-09-09 | **去重硬卡点接入 L3 自动化（直接来硬的）**：① l3_publish.py 新增 `dedup_gate_check`（Phase 0.5 话题去重卡点，三态：默认软模式 warn 不阻断；`DAILY_WHY_DEDUP_ENFORCE=1` 硬拦截 exit 1；`DAILY_WHY_DEDUP_OFF=1` 紧急总关）；② SKILL.md Step 1 预检 + Step 3 发布命令均注入 `DAILY_WHY_DEDUP_ENFORCE=1`，使 L3 自动化实际调用即硬拦截（不再是 AI 可跳过的软提示，落实 EXP-004 约束优于指令）；③ 根因：原去重仅是 automation-prompt 内 AI 软约束 + check_topic.py 未被生产代码调用，致 09-08 蜂蜜重复暴雷 |
| v3.12 | 2026-09-08 | **记忆治理 v3 全量落地（闸门 0 至 5）**：① L1 prompt 经 generate_prompt.py 新增「阶段5 记忆体积门禁」（收尾前必跑 check_memory_size --strict-sections，带红线不得收尾，下沉后须 verify_memory_migration 零损失校验）；② P0-1 修复：阶段2 要求 Reviewer 输出 6 个强制键（fact_checks/quote_checks/mechanism_checks/attribution_checks/term_checks/gap_checks 7 条），阶段3 先用 validate_review.py 机械校验再审校结论放行；③ scripts/check_memory_size.py v1.2：分片索引配额改动态（38×条目+44）+ 用户级记忆 NON_BLOCKING（仅提示不阻塞）+ L3 Phase 0 展示分区/超长行告警；④ 新增 scripts/memory_decay.py（10 天降级/20 天下沉/pin 豁免/--touch/--boost/--apply 到期打标，只动 topics 元数据）；⑤ 新增 scripts/verify_memory_migration.py（下沉零损失通用校验）；⑥ 新增 scripts/memory_budget.py（写入准入：写前算账）；⑦ extra_sync F 组 + git_add_files 33→36 全对齐 |
| v3.11 | 2026-09-07 | **记忆治理脚本纳入 git 同步（09-07 决策3）**：① `scripts/check_memory_size.py` 与 `scripts/restructure_memory.py` 加入 config.json `git_add_files` + l3_publish.py `extra_sync`（E 组），双向自检恢复全对齐；② 同轮执行自动化记忆归档切割（2026-07-01至2026-08-31 段下沉 archive/，899 行降至 101 行）；③ 门禁维持 warn 观察至 09-14 评估升阻断（09-07 决策2） |
| v3.10 | 2026-09-07 | **记忆分片重构联动（切断 MEMORY.md 自动写入）**：① `_detect_ima_version`/`_append_ima_history` 读写目标从 MEMORY.md 迁移到 `topics/ima_history.md`（config.json 新增 `ima_history_path`）——消除 MEMORY.md 唯一自动增长源，根治注入超限截断（09-02 8684→2932、09-07 9108→6568 两次压缩追不上日均 +1235 增长）；② Phase 0 新增记忆体积门禁 `check_memory_health`（复用 scripts/check_memory_size.py，warn 不阻断，try/except 全包；观察一周后评估升阻断）；③ 配套新增 scripts/check_memory_size.py（三目标门禁：工作空间 3000 字符/用户级 4000 字符/自动化记忆 1000 行）与 scripts/restructure_memory.py（分片零损失搬家+sha256 逐字校验，8 分片全通过）；④ MEMORY.md 重构为「简报+规则+索引」2644 字符（原 6568），历史全文下沉 topics/ 八分片 |
| v3.9 | 2026-09-03 | **09-03 复查修复（A-1/A-2/A-3 联动）**：① 脚本侧改进点提取改多模式回退（v1→v2 前缀 / 纯中文标题均可命中，排除「质量概览」噪音）+ **零命中即判 FAIL**（不再恒 True），见 l3_publish.py phase1_match_check；② 本 Skill Step 2.5 新增「改进点 0 条处理」硬约束：禁止自动通过，必须人工读学习总结补验（EXP-004 约束优于指令）；③ `_detect_ima_version` 删除全文扫描降级路径（版本号污染根治，宁从头编号不猜）；④ Phase 1 结果落 l3_run.log（此前成功路径无痕）；⑤ frontmatter 补 version 字段（四技能统一机读版本号） |
| v3.8 | 2026-09-02 | **P1-3 方案A：恢复 L3 Phase 1 脚本验证**：① SKILL.md Step 3 默认不再传 `--skip-match`，Phase 1 匹配度检查真实开启（设计残留 fd1dedb v3.0 起被跳过，08-31 v3.6 用 AI 补充区合理化）；② `phase1_match_check` 返回结构化 report，主流程传入 `render_report` 并在 checksum 保护区渲染「匹配度检查」区块（结构/审核/规则结果防篡改，语义验证仍由 AI 补充区填）；③ `--skip-match` 保留为手动逃生阀（AI 误判时临时加传）；④ 版本号三处对齐 v3.8 |
| v3.7 | 2026-09-01 | **网络容错+防篡改**：① `git_pull_rebase_push()` 错误分类（网络失败不再误标「rebase 冲突」，仅真冲突才 `--abort`）；② 网络探活 + 退避重试（10s/30s/60s，最多 3 次）；③ 发布报告脚本生成区写入 checksum 标记，渲染前校验既有报告是否被手工改动（09-01 实证：报告被 AI 手工补写「15:58 重试成功」致 errors=0 与日志矛盾）；④ 新增 `--retry` 模式（仅重推已提交 commit，且强制 main 分支，禁止裸 git push，补推留日志）；⑤ 版本号统一：脚本/SKILL 标题/SKILL 脚注三处对齐 v3.7（此前标题 v3.4 与脚注 v3.6 自相矛盾） |
| v3.6 | 2026-08-31 | **可观测性+报告**：① Result 类恢复 l3_run.log 写入（此前停更于 08-14 且无任何写入逻辑，每次运行带时间戳，summary 写分隔线）；② 新增 `render_report()` 脚本渲染发布报告到 `deliverables/{date}-发布报告.md`（骨架全部来自脚本数据，杜绝 AI 手写字数/commit 失真；语义验证表留 AI 补充区） |
| v3.5 | 2026-08-31 | **Phase 时序修复**：Phase 5（FEEDBACK 休眠归档）前移至 Phase 2 之后、Phase 3（git commit）之前——否则归档产生的文件变更永远赶不上当天提交，FEEDBACK_ARCHIVE 每日脱节 8 行（08-31 实证：commit 11:58:45 早于归档 11:59:06）。同步修复：① `_append_ima_history` 正则兼容纯文本（原要求 4 列管道表格，MEMORY.md 实为一行文本，从未生效）并加失败告警；② commit message 由实际 staged 文件反推（原硬编码「+ 投喂优化 + 规则更新」）；③ commit 后 push 前新增源与 repo 一致性自检（脱节即 warn）。**通用约束：git_add_files 内文件的生产 Phase 必须先于 Phase 3** |
| v3.4 | 2026-08-28 | Phase 3 内置远端核验：push 后自动 `ls-remote` 比对 + 写 loose ref 修复 `origin/main`（verified/ok_unfixed/unverified/mismatch 四态；新增 `--no-verify`）。**注：`l3_publish.py` 内版本号此前长期滞留 v3.0（git 历史 6 次改动均未更新该字段），本次一次性对齐至 SOP 版本 v3.4，非新增 4 代功能** |
| v3.4 | 2026-08-28 | 同步清单补全：B 组文件（`FEEDBACK_ARCHIVE.md`/`CASE_STUDIES.md`/`generate_prompt.py`/`message_handler.py`/`topic_candidates.json` 等）此前在 `git_add_files` 却不在 `files_to_copy`，源改动从不复制进 repo，已纳入复制清单 |
| v3.3 | 2026-08-17 | 边界条件补充：wincred 凭证修复 + packed-refs/loose ref 引用坑（GitHub 推送实障排查） |
| v3.2 | 2026-06-23 | Darwin 优化：边界条件处理(6项) + 产出汇总模板 + 依赖关系图 + CHANGELOG |
| v3.1 | 2026-06-23 | 去掉"零 AI"假约束，关键词匹配 → AI 语义验证（三档判定+证据规则+通过线） |
| v3.0 | 2026-06-12 | 多 Agent 架构：脚本预检 + AI 语义验证 + 脚本执行 |
| v2.0 | 2026-06-05 | Phase B 脚本化：validate_article.py + update_history.py |
| v1.0 | 2026-04-23 | 初始版本：手动验证 + 发布 |

---

*Version: v3.22 | 2026-09-16 | #57a 发布报告 checksum 口径统一（写入与校验共用 _script_zone_digest，尾部换行 rstrip 归一 + 写入后回读自校验；此前两侧差 1 个换行，致每次渲染恒报「脚本区被手工改动」并全量覆盖，与版本号是否变化无关）+ #57b 补充区保留（render_report 只重写 checksum 标记之前，标记之后的 AI 补充区无条件原样保留；依据 cddl-codegen / SilverModel「标记界定所有权」共识，EXP-004）+ #56 版本校验三口径全比（frontmatter/标题/末条 Version，任一不符即告警；修原实现误取首条 Version 的隐患）+ publish frontmatter 补 v3.22（此前滞留 v3.20 / last_updated 09-15，title_and_footer 口径照不到，即 #56 活体案例）；v3.21 | 2026-09-16 | #54 学习总结检索改前缀 glob（学习总结*.md，固定名零命中会让 Phase 1 整段绕过）+ #55 code_review_check.py / docs/code-review-standard.md 补入 extra_sync G 组（消「无复制源」告警）；v3.20 | 2026-09-15 | 话题提取跳空行对齐 check_topic（P3 审查 P1-3 双源漂移：首行空行 → 旧实现 None → 去重 fail-open 静默绕过；Master 确认当轮修复）+ dedup_selftest R4 回归（10/10）；v3.19（2026-09-15）dedup 卡点默认反转 enforce（Silent Fail-Open 根治：默认硬拦 exit 1，DAILY_WHY_DEDUP_RELAX=1 显式豁免，检测器故障 fail-open 保留；v3.13 的 ENFORCE bash 前缀注入 Windows 不生效之 EXP-014 实证，Step 1/3 已移除失效前缀）+ check_topic 排除 _废弃 后缀 + prepare_topics full/compact 同源派生断言 + 新增 dedup_selftest.py 双向自检；v3.18（2026-09-11）灰区告警豁免清单落地（config.git_gray_exemptions 8 项达尔文实验产物，外部经验一致：实验产物不入同步；文件未删，仅消噪音）；v3.17（2026-09-10）沙箱网络隔离 push 失败处置固化（commit 已生成 → 沙箱外 push + api.github.com 核验 remote sha，补推结论写 AI 补充区）；v3.16（2026-09-09）引用机械门禁（正文含引用且 quote_checks 空 → 硬阻断，CITATION_HINT 收窄防误杀）；（补 09-07/08/09 三波欠账 + L3 SKILL 加「重大改造必更新 CHANGELOG」步骤 + git_add_files 纳入 CHANGELOG.md 真进 GitHub）；去重卡点自匹配修复（check_topic --exclude-date 排除当日自身，修 v3.13 首跑 100% 误杀）；v3.13（2026-09-08）记忆治理 v3 全量落地（闸门 0 至 5：阶段5 门禁前置 L1 + P0-1 强制输出物接线 + 动态配额 + NON_BLOCKING + 衰减 + 零损失校验 + 写入准入，详见变更日志）；v3.11（2026-09-07）记忆治理脚本纳入 git 同步（check_memory_size.py/restructure_memory.py 入 extra_sync + git_add_files，双向自检全对齐）+ 自动化记忆归档切割（07-01至08-31 段下沉 archive/）；v3.10（2026-09-07）记忆分片重构：IMA 历史读写迁移 topics/ima_history.md（切断 MEMORY.md 自动写入）+ Phase 0 记忆体积门禁（warn 不阻断）+ 新增 check_memory_size.py/restructure_memory.py；v3.9（2026-09-03）改进点提取多模式+零命中告警、Step 2.5 加 0 条处理硬约束、IMA 版本号降级路径删除、Phase 1 落日志、frontmatter 补 version；v3.8（2026-09-02）P1-3 方案A：恢复 Phase 1 脚本验证（默认开启+checksum 保护区渲染），--skip-match 降级手动逃生阀；v3.7（2026-09-01）网络容错（错误分类+探活+退避重试）+ 发布报告 checksum 防篡改 + --retry 模式禁止裸 push + 版本号三处统一（达尔文 Round 1）；v3.6（2026-08-31）恢复 l3_run.log + 发布报告脚本渲染；v3.5（2026-08-31）Phase 5 前移至 git 之前 + IMA 历史表正则修复 + commit 消息反推 + 一致性自检；v3.4（2026-08-28）Phase 3 内置远端核验（铁律固化：不信本地 ahead 数，push 后 ls-remote 比对 + 自动写 loose ref 修复 origin/main）*
*Version: v3.23 | 2026-09-17 | #58 改进点提取器双断裂根治（闸门①标题锚点由「须以关键词开头」放宽为「任意位置含关键词」并纳入「改写要点」；闸门②抽 _extract_improvements 用 re.finditer 遍历全部命中章节取首个非空列表，修掉「首个命中是表格章节即空手而归」；闸门③新增最高优先契约锚点 `## 改进点`，L2 SKILL v3.4 强制，在生产侧终结 L2/L3 格式漂移）+ `--verify-report` 子模式（判 FAIL 的报告须有「人工补验」声明 + ≥3 行判定表格，否则 exit 1；Step 2.5 硬约束补验后必跑）+ #59 修复（scripts/config.json 被 .gitignore 有意忽略却留在 git_add_files/复制清单 → git add 静默失败 + 双向自检假绿；现从两份清单移除 + git add 逐项回读校验）+ 70 份全量双向回归（零命中 5→0，条数零下降）+ CHANGELOG v4.13*

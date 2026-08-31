---
name: daily-why-publish
description: >
  验证发布技能 — AI 语义验证 + 脚本执行：检查优化版是否匹配自动化产出，记笔记到IMA，推送技能更新到GitHub，记忆归档。
  当用户需要发布当日文章到 IMA 和 GitHub 时触发。
  触发词：每日一个为什么发布、每日一个为什么推送、每日一个为什么审计、每日一个为什么备份、每日一个为什么推送备份、每日一个为什么发布备份、dailywhy发布、dailywhy推送、dailywhy审计、dailywhy备份、dailywhy推送备份、dailywhy发布备份。
  路由规则：凡输入含「发布/推送/审计/备份」动作词（如 dailywhy发布），本技能优先于
  其他 dailywhy 系列技能触发（动作词优先），触发即执行 L3 发布流程。
agent_created: true
---

# daily-why-publish v3.4

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

### Step 3：执行发布

AI 判断通过后：
```bash
C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe F:/WorkBuddy/daily-why/scripts/l3_publish.py [YYYY-MM-DD] --skip-match --force
```

脚本执行 Phase 2/3/4（IMA 备份、GitHub 推送、记忆归档）。

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
| `--skip-match` | 跳过 Phase 1（Step 3 使用） |
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
| **git status 误报 ahead N（沙箱静默阻止 packed-refs 重写，fetch/update-ref 返回 0 但不生效）** | 手动写 loose ref `.git/refs/remotes/origin/main=<HEAD sha>`，再 `git rev-list --count origin/main..HEAD` 复查归零（08-17 实测） |
| **语义验证不通过** | 终止发布，输出未落实的改进点清单，等 Master 决定是否强制发布 |
| **l3_publish.py 脚本不存在** | 终止，提示检查 `scripts/l3_publish.py` 路径 |
| **Python 环境不可用** | 终止，提示检查 `C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe` |

---

## 产出清单

| 产出物 | 说明 |
|-------|------|
| 匹配度检查报告 | AI 汇总（结构 + 审核 + 规则 + 语义验证） |
| IMA 笔记 | 上传到 IMA 知识库 |
| Git commit + push | 推送到 GitHub |
| 记忆归档 | 追加到 memory/{date}.md |

---

---

## 版本变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
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

*Version: v3.5 | 2026-08-31 | Phase 5 前移至 git 之前（归档脱节根因修复）+ IMA 历史表正则修复 + commit 消息反推 + 一致性自检；v3.4（2026-08-28）Phase 3 内置远端核验（铁律固化：不信本地 ahead 数，push 后 ls-remote 比对 + 自动写 loose ref 修复 origin/main）*

---
name: daily-why-health-audit
description: >
  Daily Why 全链路运行健康度审计技能。核查自动化触发是否按时、L1写作/L2学习/L3发布三技能执行质量、
  报错与数据异常、规则库条目数与文件同步一致性，输出结构化审计报告（含时间线重建、P0/P1/P2 问题分级、
  六维度改进建议、优先级排序）。
  触发词：dailywhy审计运行、dailywhy健康检查、每日冷知识运行审计、dailywhy体检、检查今日dailywhy运行。
  路由说明：本技能为**只读审计**，不产出文章、不发布、不改规则；与 L3 的「dailywhy审计」不同
  （L3 审计含发布动作），输入含「发布/推送/备份」时优先 L3。
agent_created: true
last_updated: 2026-09-01
---

# daily-why-health-audit v1.2

对 Daily Why 当日全链路做只读体检。核心原则：**只信实测，不信报告**——因为发布报告、学习总结、
工作区日志中的字数/得分/条数已被实证会系统性失真。

## 硬约束

1. **只读**：禁止修改文章、规则库、自动化配置。唯一可写产物是审计报告 + 记忆追加。
2. **穷尽核对**（Master 铁律）：必须逐个打开并完整读完所有相关文件，禁止抽样后宣称「全部正确」。
   报告末尾必须列出 (a) 实际读过的文件清单 (b) 跳过的文件及原因 (c) 未验证项并如实标注。
3. **禁 `~`** 作区间连接符，一律用「到」或「至」。
4. 结论必须附证据（文件 mtime / 数据库字段 / 脚本实测输出 / ls-remote 结果），不附证据的判定不写。

---

## 审计流程

### Step 0　确定目标日期

从系统 current_time 取 `YYYY-MM-DD`。若用户指定其他日期则用指定值。

**检查点（H1，09-01 新增）**：正式读取前，先向 Master 展示「审计范围 + 预计读取的文件类别清单 + 已探测到的当日产物文件数」，等 Master 确认或直接继续。防止对非预期范围开跑。

### Step 0.5　maker-checker 闭环复核（H2，09-01 新增，P1-4 固化）

比对 `review/{date}_review.json` 记录的 `script_result.char_count` 与实测 `validate_article.py` 的 char_count：
- 若不一致 → **maker-checker 闭环断裂**（审核后文章被修改但未重审），列 P1；
- 并列出 review.json 落盘 mtime 与初稿/优化版 mtime 的先后关系作为佐证；
- 09-01 实证：v1 review 记 416 字、实测落盘 456 字，Reviewer 在 09:56:10 完成审核但初稿 09:57:20 才落盘 → 审核对象与最终产物不一致。

### Step 0.6　版本号一致性检查（H3，09-01 新增，P1-7 固化）

```bash
grep -n "v3\.[0-9]" scripts/l3_publish.py          # 脚本版本（3 处：docstring/argparse/横幅）
grep -n "^# daily-why-publish v\|^# daily-why-writer" C:/Users/admin/.workbuddy/skills/daily-why-publish/SKILL.md
tail -1 C:/Users/admin/.workbuddy/skills/daily-why-publish/SKILL.md   # 脚注 Version
```
三处版本号不一致 → 列 P1（版本号易腐）。09-01 实证：标题 v3.4 vs 脚注 v3.6 vs 脚本 v3.6。

### Step 0.7　prompt 写库一致性检查（H4，09-01 新增，P1-3 固化）

```bash
# 归一化后比对 DB prompt 与 config/automation-prompt-latest.txt
python - << 'PY'
import sqlite3, os
db = os.path.expanduser("~/.workbuddy/workbuddy.db")
p = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True) \
    .execute("SELECT prompt FROM automations WHERE id='automation-1778312519754'").fetchone()[0]
t = open("config/automation-prompt-latest.txt", encoding="utf-8").read()
norm = lambda s: s.replace("\r\n", "\n").replace("\r", "\n").strip()
print("DB==FILE:", norm(p) == norm(t))
if norm(p) != norm(t):
    import difflib
    for l in difflib.unified_diff(norm(p).splitlines(), norm(t).splitlines(), "DB", "FILE", lineterm="", n=1):
        print(l[:150])
PY
```
不一致 → 列 P1（写库损坏无回读校验）。09-01 实证：DB 含错字「亲亲关系」（正确「亲缘关系」），源文件正确、损坏在写库环节。

### Step 1　自动化执行情况（数据库取证）

数据库：`~/.workbuddy/workbuddy.db`（**只读模式**，SQLite URI `file:...?mode=ro`）

```bash
PY="C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe"
```

查三张表：`automations` / `automation_runtime_state` / `automation_runs`。
目标 ID：`automation-1778312519754`。

**必取字段与判定口径**：

| 项 | 取法 | 判定 |
|---|---|---|
| 是否触发 | `automation_runs.created_at`（毫秒时间戳） | 与 rrule 计划时间比对 |
| 是否成功 | `result_success`（**不要用 status**，该字段恒为 PENDING_REVIEW，成功失败都一样） | 1=成功 |
| 执行时长 | `runs_json[0].startedAt` → `finishedAt` | 与近 3 次比对看趋势 |
| 是否卡死 | `automation_runtime_state.running` / `last_error` | running=0 且 last_error=None = 正常 |
| 下次计划 | `automations.next_run_at` | **重点**：若已偏离 rrule 基准，说明调度漂移被固化 |

**时间戳转换坑**：该环境 `zoneinfo.ZoneInfo('Asia/Shanghai')` 会报 `No module named 'tzdata'`。
用固定偏移：`datetime(1970,1,1) + timedelta(milliseconds=ms) + timedelta(hours=8)`。

**output 截断坑**：`runs_json[0].output` 被硬截断在 **4000 字符**，阶段 3/4 记录会丢失。
必须同时用文件 mtime 反推后半程。output 还存在**重复渲染**（同一段出现两次），属已知缺陷。

### Step 2　产物时间线重建

用 `ls -la --time-style=+"%Y-%m-%d %H:%M:%S"` 列出并比对 mtime：

- `articles/{YYYY-MM}/` — 初稿 / 优化版 / 通俗版
- `review/{date}_review.json`
- `投喂素材/{YYYYMMDD}/` — ds/ima/千问/豆包.txt + 学习总结.md
- `config/topic_candidates.json`、`config/topics_context_compact.json`
- `deliverables/{date}-发布报告.md`
- `.workbuddy/memory/{date}.md`、`.workbuddy/memory/MEMORY.md`
- `.workbuddy/automations/automation-1778312519754/memory.md`

**判读要点**：
- 自动化线程结束时间（Step 1 的 finishedAt）**之后**的文件，都是 Master 手动触发的产物，
  不属于自动化本身，报告里必须分区说明。
- 「通俗版」是 SOP 外产物，出现即需标注。

### Step 3　字数与得分实测复核（最易失真区）

对当日每一版文章跑实测，**不要采信任何文档里的字数**：

```bash
"$PY" scripts/validate_article.py --json "articles/2026-08/{文件名}.md"
```

**字数口径（09-01 已统一，W5 达尔文优化落地）**：
1. `validate_article.py` 的 `char_count` —— **09-01 起为全文口径**（`check_word_count` 不再 strip 结尾表格），与 l3 一致，上限 690
2. `l3_publish.py` 的 `chinese_chars`（正则 `[\u4e00-\u9fff]` 全文统计）—— 与 validate 应**相等**
3. automation memory.md 中自记的「汉字 N」—— 唯一可能失真的口径（AI 手写）

**注意（09-01 统一后）**：validate 与 l3 两口径应完全一致；若仍不等 → 检查是否 validate 缓存旧版或 l3 引用了错误文件，列 P1。
09-01 之前的历史差异（最大 84 字：validate 586 / l3 670）源于 validate 曾 strip 结尾表格，已随 W5 修复。
**判定规则**：字数合规以全文口径 690 为上限（写作规则 `writing_rules.json` word_count.max=690）；超限 → P1。

**得分**：对外公布得分一律取 `review/{date}_review.json` 的 `score`（含人工评分），
不可用 validate 脚本分冒充实得。若学习总结 / 工作区日志 / 质量仪表盘记为别的数字，列 P1。

### Step 4　规则库条目数实测

**不要用任何文档里写的条数**，一律脚本统计：

```bash
R="C:/Users/admin/.workbuddy/skills/daily-why-writer/references"
# FORBIDDEN：只匹配标题行 '## FP-NN:'。FP-58 已归档留空，实际条数 < 最大编号
"$PY" -c "import re;t=open(r'$R/FORBIDDEN.md',encoding='utf-8').read();\
h=[int(m) for m in re.findall(r'^## FP-(\d{2}):',t,re.M)];\
print(len(h),min(h),max(h),[i for i in range(min(h),max(h)+1) if i not in h])"
# CHECKLIST：条目格式是 '## N.'（数字后加点），§ 符号极少
"$PY" -c "import re;t=open(r'$R/CHECKLIST.md',encoding='utf-8').read();\
n=[int(m) for m in re.findall(r'^## (\d+)\.',t,re.M)];print(len(n),min(n),max(n))"
```

⚠️ **正则陷阱（09-01 实测踩坑）**：**禁止**用 `re.findall(r'FP-(\d{2})', t)` 全文匹配。
FORBIDDEN.md 头部声明行会写「FP 总数：FP-01~67（含 FP-58 归档空缺，实际 66 条）」，
其中 FP-58 只是**说明文字**却被计入，导致误报 67 条（实际 66 条）。
必须锚定标题行 `^## FP-(\d{2}):`。

基线（2026-09-01 实测）：FORBIDDEN **66 条**（FP-01 到 67，缺 FP-58）；CHECKLIST **100 条**（无缺失无重复）。
条数会随新 FP 增长，**每次审计以实测为准**，勿沿用旧基线。判定失真看的是「与实测是否一致」，不是「与某个固定数字是否一致」。

**顺带核对**：FORBIDDEN.md 文末「## 新增规则」模板写的是 `### FP-XX:`（三级），而实例是 `## FP-XX:`（二级）。
按模板新增会产生三级标题 → 被上述正则漏统计。若发现条数不增，先查此项。

### Step 5　同步一致性核验

```bash
cd /f/WorkBuddy/daily-why-writer
git rev-parse HEAD                    # 本地
git ls-remote origin HEAD             # 远端真实值
git log -1 --format="%ci %s"
git show --stat --oneline HEAD        # 本次提交实际含哪些文件
```

**铁律（08-28 误判教训）**：判断「是否推上远程」**禁止只看本地 `git status` 的 ahead 数**，
沙箱下 origin/main 引用可能静默不落盘导致误报。必须 `git ls-remote origin HEAD` 与本地 HEAD 比对。

**同步清单核对**：`scripts/config.json` 的 `git_add_files`（当前 17 项）与
`l3_publish.py` 的 `files_to_copy` 必须逐项对齐。脚本内已内置自检（第 660 行）会告警缺项。

**源/repo 脱节检查**（每日必查）：
```bash
wc -l references/FEEDBACK_ARCHIVE.md "C:/Users/admin/.workbuddy/skills/daily-why-writer/references/FEEDBACK_ARCHIVE.md"
```
行数不一致即为脱节。已知根因：**Phase 5 休眠归档排在 Phase 3 git 之后**，归档变更永远赶不上提交。

### Step 6　IMA 备份校验

`note_id` 的可信度判断：由 `l3_publish.py` 第 565 行 `re.search(r"note_id[:\s]+(\d+)", output)`
从 `ima_archive.py` 的 stdout 正则解析，属**脚本级产出而非 AI 生成**，可信度较高。

但必须校验 `_append_ima_history()` 是否真的写入 MEMORY.md：比对 MEMORY.md 的 mtime 与
L3 执行时间。若 MEMORY.md mtime 早于 L3 执行时间，则该函数**静默失效**，列 P1
（后果：IMA 备份历史表无锚点，「压缩前先备份」铁律失去校验依据）。

### Step 7　技能配置核验

```bash
for f in daily-why-writer daily-why-feed-learning daily-why-publish; do
  head -12 "C:/Users/admin/.workbuddy/skills/$f/SKILL.md"
  ls -la --time-style=+"%Y-%m-%d %H:%M:%S" "C:/Users/admin/.workbuddy/skills/$f/"
done
```

检查 frontmatter `last_updated` 是否与文件 mtime 一致、是否有版本号、三份是否统一。
writer 的 `last_updated` 已知落后于 mtime（版本号易腐字段问题复发点）。

另查 automations 表的 `model_id`（当前 hy3）、`permission_mode`、`expert_id`。

### Step 8　四 AI 素材真实性（L2 专项）

投喂素材 txt 若为空壳（接近 0 字节）说明 L2 未真执行。正常为 4 到 6 KB。

重点核查 L2 的**拒绝裁定粒度**：若某条 AI 指控被整体拒绝，需确认该指控是否部分成立
（08-31 教训：IMA「关键数据无出处」对 550°C 不成立、对 193°C **成立**，整体拒绝留下溯源缺口）。

### Step 9　输出审计报告

写入 `deliverables/{date}-运行健康度审计报告.md`，结构：

0. 今日时间线（实测重建表格）
1. 自动化任务执行情况（触发及时性 / 成功性 / 时长趋势 / 模型配置）
2. 问题与异常清单（🔴P0 🟡P1 🟢P2，每项含：现象、发生时间、根因、影响范围、验证命令）
3. 相关技能表现（L1/L2/L3 各一张检查表 + 误触发漏触发判定）
4. 可优化改进项（按 **稳定性 S / 效率 E / 准确性 A / 资源配置 R / 逻辑流程 L / 容错 F** 六维分表，每项标优先级）
5. 汇总（六维度健康度评分 + 一句话结论 + 三级优先级待办 + 值得肯定的做法）
6. 附录：实际读过的文件清单 / 跳过的文件及原因 / 未验证项（如实标注）

报告生成后追加摘要到 `.workbuddy/memory/{date}.md`，并把跨会话有效的教训写入
`.workbuddy/memory/MEMORY.md`（注意 3000 字符/session 限制）。

---

## 健康度评分维度

| 维度 | 主要依据 |
|---|---|
| 任务执行 | 触发偏差、成功标志、时长趋势、是否残留卡死 |
| 产物质量 | 各版得分、事实查证覆盖度、字数合规性、溯源缺口 |
| 流程合规 | 阶段 0 到 4 完整性、SOP 外产物、Phase 顺序正确性 |
| 数据可信度 | 字数/得分/条数/commit 描述各处是否自洽（**历史最弱项**） |
| 可观测性 | 日志是否存在、output 是否截断、时间戳是否可信 |
| 综合 | 上述加权，附一句话结论 |

---

## 已知常驻缺陷（每次审计直接对照，不必重新发现）

1. L3 Phase 5（归档）在 Phase 3（git）之后 → FEEDBACK_ARCHIVE 每日脱节
2. 字数三口径并存 → 600 上限可被绕过
3. Reviewer 严重性判定低于 L2 四 AI 共识（P0 常被判 P2）
4. `automation_runs.status` 恒为 PENDING_REVIEW，不可用
5. review.json 的 `review_timestamp` 由子 agent 自造，可能指向未来
6. `l3_run.log` 已死（脚本无写入逻辑），L3 无独立日志
7. automation memory.md 持续膨胀（08-31 分片后 789 行，09-01 已回涨至 811 行 / 98KB，约 +22 行/天）
8. FORBIDDEN 条数随新 FP 增长（09-01 实测 66 条），**任何文档写死的条数都会过期**
9. 调度器对本自动化为**稳定 +5 分钟延迟**（非提前），且已固化进 next_run_at
10. 「通俗版」为 SOP 外产物，无命名规范、未进 git

### 09-01 审计新增常驻缺陷（今日新发现，后续每次审计直接对照）

11. **Reviewer 机制自洽性盲区**（头号质量风险）：Reviewer 只核验「可搜索的事实断言」（人物/机构/年份/数据），
    **不验因果机制的方向自洽性**。09-01 v1「重量压出上翘小弧」物理方向矛盾被独立 Reviewer 完全漏判，
    靠 L2 四 AI 一致指出才救回（沉淀为 FP-67）。**每次审计必查**：当日四 AI 指出的核心差距中，
    有多少条是 v1 Reviewer 漏判的 —— 这是衡量审校有效性的核心指标。
12. **`writing_rules.json` 严重滞后**：自 2026-05-28（v1.4）未更新，与 FORBIDDEN.md（66 条 / 09-01）分裂 3 个多月，
    不含任何 FP 语义规则 → 新规则无法机械化，只能靠 AI 主动读 md。**每次审计查其 mtime 与 `_updated`**。
13. **prompt 写库无回读校验**：DB prompt 与 `config/automation-prompt-latest.txt` 可能不一致。
    09-01 实测 DB 含错字「亲亲关系」（正确「亲缘关系」，源文件与 generate_prompt.py 均正确）→ 损坏在写库环节。
    **每次审计必做**：取 DB prompt 与文件做归一化后 diff（长度相同不等于内容相同，须比对 hash）。
14. **L3 网络失败被误标为「rebase 冲突」**：`l3_publish.py` L112-118 只要 `git pull --rebase` 非零即报冲突并
    执行 `rebase --abort`；网络不可达同样归入此桶，且重试为**立即重试无退避**（09-01 两次各耗 21 秒超时）。
15. **P2 采纳后未回归验证**：Orchestrator 按 Reviewer 意见修改文章后不重跑 validate、不更新 review.json，
    导致 review 分数与最终落盘产物不一致（09-01：审 416 字 → 落盘 456 字）。
    **每次审计必查**：`review.json.script_result.char_count` vs 实测 `validate_article.py` 的 char_count。
16. **Reviewer 会提出违反 SOP 硬约束的建议**：`reviewer_prompt.md` 无分类 6 选 1 枚举约束，
    09-01 连续两轮建议改「物理·界面现象」（枚举外，不可执行）。
17. **版本号跨文件脱节**：`daily-why-publish/SKILL.md` 标题 v3.4 与脚注 v3.6 自相矛盾（`l3_publish.py` 实为 v3.6）。
18. **`.git/packed-refs` 残留陈旧 `refs/remotes/origin/main`**（09-01 为 f290902），当前靠 loose ref 覆盖，属隐患。
19. **工作区日志 / 学习总结中的「⚠️ 异常」标记存在误报**：09-01 日志与学习总结均记「review_timestamp 自造
    （写 10:50 实 <10:38）」，但实测 mtime 序列自洽（优化版 10:45:43 → timestamp 10:50:42 → review 文件 10:52:01），
    **系误报**。判定「时间戳自造」必须给出 mtime 序列证据，禁止凭片段观察下结论 —— 误报会持续污染决策链。

## 09-01 修复记录（按「已修复」核对，不再重报）

| # | 缺陷 | 验证 |
|---|------|------|
| 1 | Phase 5 时序 | 09-01 实证：FEEDBACK_ARCHIVE 源与 repo **均 197 行**，无脱节 ✅ |
| 6 | l3_run.log | 09-01 三条带时间戳记录（14:58:34 / 14:59:29 / 15:00:27）✅ |
| 5 | review_timestamp 自造 | 09-01 v1/v2 均与 mtime 自洽，修复生效 ✅（日志中的复现指控为误报，见缺陷 19）|
| — | 源/repo 同步清单 | files_to_copy 含 extra_sync 9 项，与 git_add_files 对齐 ✅ |

⚠️ **回归项**：「发布报告 AI 手写」缺陷**未根治** —— 09-01 L3 失败后人工手动 push（15:58），
未走脚本故 `l3_run.log` 无记录，报告随后被手工补入「15:58 重试成功」字样
（脚本内无此文案，可用 `grep "重试成功" scripts/l3_publish.py` 实证）。
**每次审计必查**：① 报告 mtime 是否晚于 l3_run.log 最后一条记录；② 报告中是否含脚本不存在的自然语文案。

## 08-31 晚修复记录（下列常驻缺陷已修复，审计时按「已修复」核对不再重报）

| # | 缺陷 | 修复 | 验证 |
|---|------|------|------|
| 1 | Phase 5 时序 | v3.5 前移至 Phase 3 前 | 08-31 16:00 发布实证（FEEDBACK_ARCHIVE 变更入 commit ebe256c） |
| 3 | Reviewer 分级未接通 | generate_prompt 加「加载 reviewer_prompt.md」+ 绝对化至少 P1 | prompt 已入库（DB==latest.txt） |
| 5 | 时间戳自造 | prompt 强制 `date +%Y-%m-%dT%H:%M:%S%z` | Git Bash 实测可用 |
| 6 | l3_run.log 已死 | v3.6 Result._log 恢复写入 | 16:00 发布写入带时间戳记录 |
| 7 | memory 膨胀 | 分片至 `memory_archive_2026H1.md`，主文件 789 行；prompt 改 **`head -n 150`**（⚠️ memory.md 倒序新在前，**用 head 不用 tail**，08-31 晚发现 tail 方向反了已修） | DB prompt 含 head 约束 |
| 8 | FP 66 口径 | reviewer_prompt v2.1 改「实际 65 条」 | grep 确认 ⚠️ **09-01 又过期**（新增 FP-67 → 实际 66 条），见新增缺陷 8 |
| — | 发布报告 AI 手写 | v3.6 `render_report()` 脚本渲染 | 16:00 发布生效 ⚠️ **09-01 回归**，见上表回归项 |

---

*Version: v1.2 | 2026-09-01 | 新增 Step 0 检查点（H1）+ Step 0.5 maker-checker 闭环复核（H2，P1-4 固化）+ Step 0.6 版本号一致性（H3，P1-7 固化）+ Step 0.7 prompt 写库一致性（H4，P1-3 固化）；Step 3 字数口径更新为「已统一全文口径」（W5 落地）。v1.1（2026-09-01）修正 Step4 正则陷阱 + 基线更新 66 条 + 字数最大差 77→84 字；新增常驻缺陷 11 到 19。首次建立 v1.0 沉淀自 08-31 全链路审计（20+ 工具调用，12 类问题）*

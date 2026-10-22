> 本文件由 2026-09-08 记忆治理 v3 第 0 步从 MEMORY.md「## 3. ⚠️ 铁律级教训」区**原文整段搬家**而来，正文逐字未改动（搬家前快照：archive/MEMORY-pre-ironrules-split-2026-09-08.md，sha256 ced2446801bbc9b3…）。
> 依橙皮书 **EXP-006**：铁律属**程序性记忆**，归属地是 skills/；本分片是迁往 skills 前的中转与冷存层。
> 依橙皮书 **EXP-012**：**永不删除**，只降级/下沉；跑前快照可回滚。
> MEMORY.md 只保留 5 条跨技能全局红线全文 + 10 条触发式索引行。
> 落位核查（2026-09-08）：writer(§13/§14)、publish(§04/§05/§06/§12) 正文在对应 SKILL.md **已存在**（grep 实证：publish SKILL 含 ls-remote 4 / git_add_files 4 / Phase 13；writer SKILL 含 check_topic 6 / WebSearch 7），本文件是索引+冷存；audit(§09) 已补入 daily-why-health-audit v1.6 硬约束 5（强制全文加载防漏 Step），§08 部分在。**结论：四层归位 = 确认已有 + 精简索引，禁止再做重复迁移**。

# 铁律全文（程序性记忆）

衰减参数（Master 2026-09-08 裁定）：**10 天未触发 → 降级；20 天 → 下沉；被引用或对应错误再犯 → 立即升回最高**。
`pin: true` = 低频高代价规则，**豁免衰减**（20 天只降到索引行，不从 MEMORY.md 消失）。

---

## §01 EXP-004 约束优于指令
- owner: global ｜ type: procedural ｜ pin: false
- trigger: 改 prompt / 加防复发机制 / 加校验
- created: 2026-09-01 ｜ last_accessed: 2026-09-08 ｜ access_count: 12
- decay: 待降级(闲置10天) ｜ 判定 2026-09-18 ｜ 人工：MEMORY.md 该条常驻→降为触发索引行
- 正文：
> **EXP-004 约束优于指令**：改 prompt 文本而不加机械校验 = 无效（09-01 至 09-04 三次补丁实战零改善）。任何「防复发」必须配脚本校验。**09-08 四演新形态：改子 prompt 未同步父 prompt，机制在 L1 入口断开 → 见 topics/review_defense.md**

## §02 EXP-014 可观测性即诚实性
- owner: global ｜ type: procedural ｜ pin: false
- trigger: 写报告 / 判定"通过" / 复述结论
- created: 2026-08-18 ｜ last_accessed: 2026-09-18 ｜ access_count: 9
- 正文：
> **EXP-014 可观测性即诚实性**；日志说「通过」不等于真通过

## §03 反向验证铁律
- owner: global ｜ type: procedural ｜ pin: false
- trigger: 修完防复发机制后
- created: 2026-09-07 ｜ last_accessed: 2026-09-07 ｜ access_count: 2
- decay: 待降级(闲置11天) ｜ 判定 2026-09-18 ｜ 人工：MEMORY.md 该条常驻→降为触发索引行
- 正文：
> **反向验证铁律（09-07 新增）**：修完防复发机制必须喂入缺陷样本确认能报出，只跑一遍「✅通过」不算证据

## §04 git 判定
- owner: publish ｜ type: procedural ｜ **pin: true**（低频高代价）
- trigger: 判断代码是否推上远程 / 处理 [gone] 分支
- created: 2026-08-28 ｜ last_accessed: 2026-09-08 ｜ access_count: 5
- 正文：
> **git 判定**：权威 = `git ls-remote origin HEAD`；禁凭本地 ahead 判推送，`git fetch` 亦不可信；`[gone]` 用 mkdir loose ref 强写

## §05 同步清单
- owner: publish ｜ type: procedural ｜ **pin: true**
- trigger: 新增 git_add_files / 改复制源
- created: 2026-09-01 ｜ last_accessed: 2026-09-08 ｜ access_count: 3
- 正文：
> **同步清单**：`files_to_copy` 须与 `config.json git_add_files` 逐项对齐；新增 git_add_files 须同步加复制源（config.json 被 .gitignore 有意忽略，勿移除）

## §06 L3 Phase 时序
- owner: publish ｜ type: procedural ｜ **pin: true**
- trigger: 新增进 git_add_files 的产出物
- created: 2026-08-31 ｜ last_accessed: 2026-09-08 ｜ access_count: 2
- 正文：
> **L3 Phase 时序**：进 git_add_files 的产出物其 Phase 须在 Phase3 之前（0→1→2 IMA→5 归档→3 git→4 记忆）

## §07 数据可信度
- owner: global ｜ type: procedural ｜ pin: false
- trigger: 引用字数/得分/条数/版本号等数字
- created: 2026-09-01 ｜ last_accessed: 2026-09-18 ｜ access_count: 10
- 正文：
> **数据可信度**：字数/得分/规则条数由 AI 手写必失真，须脚本渲染

## §08 得分口径
- owner: audit ｜ type: procedural ｜ pin: false
- trigger: 报告或比较审校得分
- created: 2026-09-08 ｜ last_accessed: 2026-09-08 ｜ access_count: 4
- decay: 待降级(闲置10天) ｜ 判定 2026-09-18 ｜ 人工：MEMORY.md 该条常驻→降为触发索引行
- 正文：
> **得分口径（09-08 实证修正）**：v1/v2 的 `review.json.score` **都是 Reviewer 综合分**（09-08 实测 95 / 93）；`script_result.score`（恒 100）才是 validate 脚本分、无区分度。旧记「v2=脚本分」有误

## §09 审计流程铁律
- owner: audit ｜ type: procedural ｜ pin: false
- trigger: 复查/审计类任务（含自然语句「检查dailywhy运行」）
- created: 2026-09-01 ｜ last_accessed: 2026-09-18 ｜ access_count: 7
- 正文：
> **审计流程铁律**：复查/审计类任务（含自然语句「检查dailywhy运行」）开局必须加载 `daily-why-health-audit`，否则漏 Step0.5/0.7/1/3/4/8.5
> 常驻依据（2026-09-18 A3 校准）：非 pin 候选中实测频次最高（cnt=6、分 0.687），换入 MEMORY.md 常驻 5 条；§10 模型无关性（cnt=2、闲置 15d、分 0.524 全场最低）对调降为触发索引行

## §10 模型无关性
- owner: global ｜ type: procedural ｜ pin: false
- trigger: 任务失败归因 / 讨论换模型
- created: 2026-09-03 ｜ last_accessed: 2026-09-03 ｜ access_count: 2
- decay: 待降级(闲置15天) ｜ 判定 2026-09-18 ｜ 人工：MEMORY.md 该条常驻→降为触发索引行
- 正文：
> **模型无关性（Master 09-03 定调）**：不绑定具体模型，失败先查 SOP/脚本/流程，不归因模型；DB model_id 仅记录

## §11 死文件判据
- owner: global ｜ type: procedural ｜ pin: false
- trigger: 新增文件/字段/脚本
- created: 2026-09-02 ｜ last_accessed: 2026-09-08 ｜ access_count: 3
- decay: 待降级(闲置10天) ｜ 判定 2026-09-18 ｜ 人工：MEMORY.md 该条常驻→降为触发索引行
- 正文：
> **死文件判据**：新增项须答出「谁读？哪步读？」，答不出即死文件

## §12 版本号易腐
- owner: publish ｜ type: procedural ｜ **pin: true**
- trigger: 改任何脚本版本号
- created: 2026-09-01 ｜ last_accessed: 2026-09-08 ｜ access_count: 5
- 正文：
> **版本号易腐**：改脚本须同步 SKILL 头/脚/变更日志；`config/version.json` 为唯一权威，l3_publish Phase0 校验

## §13 去重与事实核验
- owner: writer ｜ type: procedural ｜ pin: false
- trigger: 选题 / 引用 AI 给的建议或数据
- created: 2026-09-01 ｜ last_accessed: 2026-09-08 ｜ access_count: 4
- decay: 待降级(闲置10天) ｜ 判定 2026-09-18 ｜ 人工：MEMORY.md 该条常驻→降为触发索引行
- 正文：
> 去重必跑 `check_topic.py` 机械校验；AI 给的建议/数据/人物/年份必 WebSearch 二次确认

## §14 信源甄别双向
- owner: writer ｜ type: procedural ｜ pin: false
- trigger: 判断某条 AI 指控是否成立
- created: 2026-09-04 ｜ last_accessed: 2026-09-08 ｜ access_count: 3
- decay: 待降级(闲置10天) ｜ 判定 2026-09-18 ｜ 人工：MEMORY.md 该条常驻→降为触发索引行
- 正文：
> 信源甄别双向：多数AI一致≠正确；多数AI没提≠没错（09-04 千问独家 5 处硬伤经核实全真）

## §15 同文件多处编辑禁并行
- owner: global ｜ type: procedural ｜ **pin: true**（低频高代价）
- trigger: 同一文件需改多处
- created: 2026-09-07 ｜ last_accessed: 2026-09-08 ｜ access_count: 2
- 正文：
> **同文件多处编辑禁并行**：并行 Edit 同一文件会 last-write-wins 互相覆盖（09-07 实证：五处版本号三处被吞，dry-run 校验器兜底捕获），必须逐处串行改

---

## 元数据字段说明

| 字段 | 含义 | 取值 |
|---|---|---|
| owner | 归属技能（第 1 步四层归位用） | global / writer / publish / audit |
| type | 记忆类型 | procedural（EXP-006 第三层） |
| pin | 低频高代价，豁免衰减 | true / false |
| trigger | 触发场景，写进 MEMORY 索引行 | 场景短语 |
| created / last_accessed | 衰减计时基准 | YYYY-MM-DD |
| access_count | 被引用/命中次数，Refresh-on-Read 累加 | 整数 |

**衰减规则**：`10 天未触发 → 从常驻降为索引行；20 天 → 下沉本文件（MEMORY 仅留指针）；被引用或对应错误再犯 → 立即升回最高；pin:true 永不从 MEMORY 消失。`

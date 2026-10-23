# 长期记忆 - Daily Why 项目（2026-09-07 分片重构版）

> 定位：会话简报 + 常驻规则 + 分片索引；历史全文见 memory/topics/（逐字原文）
> 零损失校验：deliverables/2026-09-07-记忆分片零损失校验.md｜快照：archive/MEMORY-full-precompress-restructure-2026-09-07.md

## 写入纪律（写本文件前必读）
1. 写前跑 `memory_budget.py --add N --section 区名`，放不下先砍再写
2. 写前重读，合并进现有章节，禁止盲目追加
3. 每行自问「删掉会导致犯错吗」，过期内容顺手清理
4. 历史细节写进 topics/ 分片，此处只留索引行

## 分片索引（全文逐字原文）
- 铁律全文（15条）→ iron_rules.md（主文件留5常驻+触发索引）
- 审校防线漏判率 → review_defense.md（审计Step 8.5必读）
- A方案 gap_checks → a_plan.md
- maker-checker 熔断链/触发词/命名 → maker_checker.md
- 缺陷台账 → defects.md（审计必查，全文；#60至#66已修）
- 选题去重盲区（10-13 实测50.0%/62.5%）→ topics/dedup_defense.md；T1-T6 已执行完
- 已修复 → fixed.md（勿重复发现）
- IMA 备份历史 → ima_history.md（l3_publish 追加目标）
- 归档删除索引 → archive_index.md（勿重建）
- 质量趋势 → trends.md；待决策观察 → pending.md
- 关键教训（L2重大教训全文）→ lessons.md（§6 全文逐字）

## 1. 架构与自动化
- L1 `daily-why-writer`（工作日09:40计划，波动至10:11）→ L2 `daily-why-feed-learning`（手动）→ L3 `daily-why-publish`（手动）
- 代码审查标准 `docs/code-review-standard.md`（pre-commit hook 拦P0）
- 自动化 ID `automation-1778312519754`；改 prompt 走 `generate_prompt.py --update-automation`，写库后须回读比对
- 触发词唯一权威源 `config/skill-trigger-map.json`（明细 → topics/maker_checker.md）
- 自动化只覆盖L1（设计如此非缺陷）；L2/L3手动高不得列缺陷
- L1 不靠谱=不得已取舍，L2仅被迫补偿；**禁为小缺陷改 L1**，稳定优先
- 文章命名`{YYYY-MM-DD}-每日冷知识-{2-6字}.md`，仅存本地articles/，不进git/IMA

## 3. ⚠️ 铁律（常驻5条 + 触发索引10条｜全文 topics/iron_rules.md）
- **EXP-004 约束优于指令**：改 prompt 不加机械校验=无效；防复发须配脚本校验
- **EXP-014 可观测性即诚实性**：日志说「通过」不等于真通过
- **数据可信度**：字数/得分/条数须脚本渲染，AI手写必失真
- **死文件判据**：新增项须答出「谁读？哪步读？」
- **审计流程铁律**：复查/审计类任务开局必须加载 daily-why-health-audit（含自然语句「检查dailywhy运行」），否则漏Step 0.5/0.7/1/3/4/8.5
- 触发索引（命中场景再查全文，⭐=pin豁免衰减）：
  修防复发机制→§03｜git判定→§04⭐｜加git_add_files→§05⭐｜新增产出物→§06⭐｜报审校得分→§08
  任务失败归因/讨论换模型→§10｜改版本号→§12⭐｜选题引用→§13｜判AI指控→§14｜同文件多处改→§15⭐

## 2. 写作规范（指针，权威在 SKILL.md）
- 唯一权威 `daily-why-writer` SKILL.md（阶段0强制加载）；FORBIDDEN 81条（FP-01~82，含 FP-58 空缺，实际 81 条）全文在 references/FORBIDDEN.md
- 字数上限690全文口径，600仅软目标不得作判定阈值
- 信源甄别纪律 → topics/writing_spec.md

## 4. IMA 备份约束
- 压缩/重构前须全量备份到 archive/（kb_id 见 `scripts/config.json`）
- v3.7 为污染脏值勿作基线，真实序列看 l3_run.log Phase 2 行

## 5. L2 后检查（每日手动流程，09-18 起）
- 提示词唯一权威：`deliverables/L2后检查-提示词.md`（Master新对话首条贴「L2 后检查 YYYY-MM-DD」即触发）
- **角色边界**：只出报告，**不修、不触发 L3**；Master复核后自行决定修否与L3
- 判据 A-G（当日文件/契约锚点/提取器/版本三口径/报告自洽/git同步/产出质量）
- 实测坑位：`l3_publish.py` 日期是位置参数（非 `--date`）；`--dry-run` 撞当日已发布会整体跳过
- 任何 CLI 调用都写真实 l3_run.log（须显式传临时 log_path）；Bash环境不可用一律走 managed python
- Bash缺head/tail(exit127)、PowerShell直读stdout失灵时改subprocess包装脚本落UTF-8文件再Read
- 检查报告产出 `deliverables/{日期}-L2后检查报告.md`

## 6. 关键教训（L2 重大教训索引）
- 关键教训全文 → topics/lessons.md（逐字）：
  FP-77主因归表面活性剂｜§101信源甄别
  FP-78类比机制边界｜§73早期Q焊接
  FP-79相变放热非位置成因｜§101案例跨物种外推须查实测值
  FP-82前沿实验科普缺边界声明
  §101案例转述源物种混写（10-20戴胜化学成分：3家AI一致错+初版原本正确，须深挖原始论文Table层，"已核实"禁停在转述级）
  FP-83物种招牌能力错配（10-21白蚁蚁酸整链错误：中文科普链转抄数十年，经典机制须回原始文献）
  视锥归因（10-22天空蓝）：S视锥峰值420nm≠「对紫光弱」；审校据转述源误判correct→审校侧也须回原始数据源（§125）
  §124表格格式须进CHECKLIST（10-21：约束没接到审校输入链=没有防线，与#59/#60同构）
  标题主体口径（10-23介形虫P0）：审校只核数字不核「谁灭绝了/主体未圈定=过度外推」→lessons.md

# 长期记忆 - Daily Why 项目（2026-10-27 根治重构版）

> 定位：会话简报 + 常驻规则 + 分片索引；历史全文见 memory/topics/（逐字原文）
> 零损失校验：deliverables/2026-09-07-记忆分片零损失校验.md｜历次重构快照：archive/MEMORY-pre-*.md

## 写入纪律（写本文件前必读）
1. 写前跑 `memory_budget.py --add N --section 区名`，放不下先砍再写；写后跑 check_memory_size.py 复核
2. **砍前先 IMA 备份**（kb_id 见 scripts/config.json）；**教训一律写 topics/lessons.md（无字数限制），禁止写进本文件**——§6 是冻结指针区
3. 历史细节写进 topics/ 分片，此处只留索引行；每行自问「删掉会导致犯错吗」，过期内容顺手清理

## 分片索引（全文逐字原文）
- 铁律15条→iron_rules.md｜审校防线漏判率→review_defense.md（审计Step 8.5必读）｜A方案gap_checks→a_plan.md
- maker-checker熔断链/触发词→maker_checker.md｜缺陷台账→defects.md（审计必查，#60至#66已修）｜已修复→fixed.md
- 选题去重盲区→dedup_defense.md（T1-T6已完）｜IMA备份历史+约束→ima_history.md｜归档删除索引→archive_index.md
- 质量趋势→trends.md｜待决策观察→pending.md｜关键教训（唯一写入地）→lessons.md
- L2后检查流程+坑位→`deliverables/L2后检查-提示词.md`；代码审查标准→`docs/code-review-standard.md`

## 1. 架构与自动化
- L1 `daily-why-writer`（工作日09:40，波动至10:11）→ L2 `daily-why-feed-learning`（手动）→ L3 `daily-why-publish`（手动）
- 自动化 ID `automation-1778312519754`；改 prompt 走 `generate_prompt.py --update-automation`，写库后须回读比对
- 触发词唯一权威源 `config/skill-trigger-map.json`（明细 → topics/maker_checker.md）
- 自动化只覆盖L1（设计如此非缺陷）；L1 不靠谱=不得已取舍，L2仅被迫补偿；**禁为小缺陷改 L1**，稳定优先
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

## 6. 教训索引（冻结区·教训禁入本区，写入地=topics/lessons.md）
- 教训唯一写入地：topics/lessons.md（全文逐字+顶部主题词索引）；已证伪断言 → eval/historical_claims.tsv
- FP/§权威沉淀 → writer references/CHECKLIST.md+FORBIDDEN.md（审校侧输入链，改审校约束须同步）

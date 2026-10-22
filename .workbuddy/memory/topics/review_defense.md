> 本文件由 restructure_memory.py 于 2026-09-07 从 MEMORY.md「## 4. 审校防线（头号质量风险）」区**原文整段搬家**而来，正文逐字未改动（搬家前全量快照：archive/MEMORY-full-precompress-restructure-2026-09-07.md）。修改历史内容请直接编辑本文件，MEMORY.md 只保留一行索引。

- **漏判率 M/N = 唯一有效质量指标**（N=L2 找出的核心差距数，M=v1 Reviewer 漏掉的数）。实测：09-02 4/4、09-03 2/2、09-04 3/3、09-07 3/3，**连续四天 100%**
- 根因（09-07 定论）：**不是没看见，是看见了判对**。铁证：v1 `attribution_checks` 引用了「少运动的鸡胸」却判 `is_primary_cause=true`「主因正确」→ 判断标准松，比漏看更严重
- 漏判类型库：A 机制要素 / B 归因 / C 引用精度 / D 行为建议（**仍待修**）/ E 来源存在但细节未逐字核对
- 历史补丁（均只改 prompt，实战零改善，仅作记录）：v2.4 Step5.6 归因、v2.5 Step5.5 扩维+5.7 引用精度、v2.7 Step5.8 术语核验（**实战零触发**：离线验证通过 ≠ 生产生效）
- 其他：`review.json` 时间戳不可信（判自造须有 mtime 序列证据）；v2 schema 漂移已修（p0_count 整数/pass 非 passed/script_result.char_count 必填）

## 09-08 审计追加（第四次重演：机制在 L1 入口断开）

- 漏判率实测 **3/4 = 75%**（09-08 蜂蜜不坏）：L2 四条核心差距，v1 漏 3 条。其中 **P0 级**「1913 金字塔蜂蜜」讹传被 v1 降为 P2，且定性错成「表述强度问题」而非「事实错误」，靠手动 L2 才拦下
- **根因确诊（新形态，EXP-004 第四次重演）**：09-07 A 方案只改了 `reviewer_prompt.md`（子文件），**没同步改驱动它的父 prompt** —— `config/automation-prompt-latest.txt` 阶段2 任务清单只列 pass/p0/p1/p2/score/issues，通篇无一个强制输出物字段名；`generate_prompt.py` 全文 grep `gap_checks|fact_checks|quote_checks|强制输出物` **零命中**。机制链条在 L1 入口断开，v1 六项强制输出物 100% 缺失（gap_checks=0）
- **分裂态**：v2（手动环节）gap_checks 7 条完整、checked 全 true、triggered 3 条并转化 P1×1+P2×2 → 证明 A 方案本身有效，问题在没送到 v1 手上
- **门禁失效**：validate_review 判 v1 🔴 错误 6 项，l3 Phase 1.4 仅 warn，Phase 1 仍判 PASS
- **空数组绕过**：校验器只把「键缺失」判错误，`quote_checks: []` 仅警告 → Reviewer 有低成本绕过路径（09-08 v2 的 quote_checks/term_checks 均空数组但判通过）
- C 方案计数口径未定：v1 未执行、v2 执行完整，需 Master 裁定以谁为准

## 09-14 A1 评估收口（validate_review 空数组观察项，窗口 09-07 至 09-14）

- **结论：维持现状**。v3.16 引用机械门禁（09-09 落地：CITATION_HINT 强信号命中 + quote_checks 空 + fact_checks 无留痕 → blocking + l3 sys.exit）窗口实测 **0 误杀 0 漏阻**（6 个 v2 review，脚本渲染：quote 空 3 天均为无强信号引用文章，quote 非空 3 天均 G-06 triggered）。
- **口径差记录（G-06 vs CITATION_HINT，设计取舍非缺陷）**：Reviewer G-06 判据宽（正文含研究引用标记即 triggered）；脚本 CITATION_HINT 窄（书名号+年份 / 期刊名 / 年份+机构+研究动词 / DOI，09-09 收窄防误杀）。09-09 反转浮力一例：G-06 true 但 CITATION_HINT 不命中、fact_checks 非空（`_has_quote_verification` 允许 fact 留痕替代）→ 未阻断属防误杀取舍。**升级为缺陷的条件**：出现「G-06 true 且 fact_checks 也空」→ 引用核验完全无留痕，届时扩 CITATION_HINT 或改查 G-06。
- 09-08 追加的「空数组绕过」条目状态更新：**v3.16 已对「文中有具体引用」场景闭环**（quote 空 + fact 也空 → 硬阻断）；无引用文章的空数组属设计允许的正常态。
- **09-14 新证据（Reviewer 有效性）**：mechanism_checks 窗口内首次出现 direction_ok=false（毛巾吸水 Q2「不润湿液面往下凹」方向错，note 明确判 P1）→ 发布前已修复（正文改「往下压/往下掉」，凹凸表述清零），顶层 p1_count 归零、note 保留发现记录。**「mechanism 全 true = 必然漏判」担忧部分破除：该 false 时会 false**。
- ⚠️ 小规范缺口（记 pending 观察项）：09-14 修复后 review.json **缺 `revised_after_review: true` + `post_revision` 标注**（09-10 先例有），顶层计数与 mechanism note 字面矛盾易误导后续审计。
- omission_severity 窗口累计：minor 15 / major 1 / none 7 / 旧格式缺字段 2（09-07 v2 schema 旧）。major（09-10 人工增雨「正是用干冰」以偏概全）为真问题且已修；minor 均附具体修正建议 → **非「过度纠偏」，观察关闭**。
- term_checks 死字段评估：**非死字段，维持现状**——09-14 植物学话题首次真实触发（2 条：木质部 / 内聚力-张力理论，含规范译名核验）；触发条件 = 话题含专业术语，窗口触发率 1/6 属低频有效。

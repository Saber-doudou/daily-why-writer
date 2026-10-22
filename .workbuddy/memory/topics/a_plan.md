> 本文件由 restructure_memory.py 于 2026-09-07 从 MEMORY.md「## 5. A 方案「换判定主体」已落地（09-07，Master 裁定）」区**原文整段搬家**而来，正文逐字未改动（搬家前全量快照：archive/MEMORY-full-precompress-restructure-2026-09-07.md）。修改历史内容请直接编辑本文件，MEMORY.md 只保留一行索引。

- **三件套**：① `references/GAP_PATTERNS.md`（7 条 G-01 至 G-07，全部源自 L2 实证）② `reviewer_prompt.md` **v2.8 Step 5.9** 对照核验 + 自检第7项无条件强制 + 输出 `gap_checks` ③ `scripts/validate_review.py` 机械校验（条数=类型库总数且 `checked` 全 true）
- **与前三次补丁的本质区别**：配了脚本机械校验
- 校验器已接入 `l3_publish.py` **Phase 1.4**（v1+v2 都校），策略 **warn 不阻断**（新校验器未经实战），try/except 包住不得影响发布主流程
- `GAP_ENFORCE_SINCE="2026-09-08"`：历史文件只 warn 不误报
- 新类型条目须靠实证增补，禁凭空写；新增须同步改 `validate_review.py`
- **C 方案触发条件（已固化进 audit SKILL Step 8.5）**：09-08/09-09/09-10 连续三个工作日 `gap_checks` 完整（7 条、`checked` 全 true）**且** M/N 仍 ≥1/2 → **自动切 C 方案**，不再打 prompt 补丁。C 方案 = L2 为质量主防线，Reviewer 降级为格式守门员，Step 8.5 漏判率改「参考值」

# Daily Why 代码审查标准与流程

**版本**：v1.0
**日期**：2026-09-15
**制定背景**：09-15 去重事故复盘（Silent Fail-Open / SSOT 漂移 / 死环境变量注入）暴露代码质量参差不齐；旧版 `CODE_REVIEW_GUIDE.md`（2026-06-05）为通用教科书式指南，从未挂接流程，且查不出本项目任何一个真实缺陷。本文取代其地位。
**权威关系**：本文 > `CODE_REVIEW_GUIDE.md`（保留仅作历史参考）；机械执行以 `scripts/code_review_check.py` v2.0 为准。

---

## 1. 问题分级与通过线

| 标记 | 级别 | 定义 | 处置 |
|------|------|------|------|
| 🔴 | P0 blocker | 安全漏洞、fail-open 数据泄漏、数据丢失风险、破坏 API 契约、守护逻辑失效 | **必须修复**，不得带病合并 |
| 🟡 | P1 suggestion | 缺输入校验、吞异常、豁免无留痕、逻辑易误读、缺双向测试 | 应修复；发布前未修须在报告中列明理由 |
| 💭 | P2 nit | 风格、命名、文档缺口、可选优化 | 可选；机械检查只计数不拦截 |

**通过线（继承 maker-checker v2.0）**：P0=0 且 P1≤2。
**独立审查原则（继承生成者/评判者分离，EXP-005）**：守护类脚本的改动，审查者不得是同一轮生成者本人；无法满足时（单人会话），报告中必须显式声明「生成者=审查者折衷」，由 Master 终审。

## 2. 红线档：守护类脚本

**清单**：`l3_publish.py`、`validate_article.py`、`validate_review.py`、`check_topic.py`、`prepare_topics.py`、`dedup_selftest.py`、`doubao_review.py`、`generate_prompt.py`。此清单随红线脚本扩充而更新。

改动任一守护脚本，除通用标准外**必须**满足：

1. **fail-closed 默认**：敏感路径（去重拦截、发布阻断、版本校验）默认执行；豁免只能用显式环境变量，且默认关闭、豁免时必须留痕（日志或 review 文件）。禁止「出错就放行」的兜底。
2. **双向测试强制**：改动拦截/放行逻辑后，必须跑双向自测（`dedup_selftest.py` 或等价用例）：已知该拦的样本必须拦 + 已知该放的样本必须放。只测单侧 = 未测试。
3. **约束落在代码默认值**（EXP-004）：文档注入式约束（如 `VAR=1 cmd` 前缀）不算约束；开关行为必须由代码默认值决定。教训：v3.13 的 `DAILY_WHY_DEDUP_ENFORCE=1` 前缀在 Windows 运行时从未生效。
4. **版本号跨文件对齐**：以 `config/version.json` 为权威源；`l3_publish.py` 改动须同步 SKILL.md 标题/脚注/changelog。
5. **git 权威验证**：本地 commit 成功 ≠ push 成功，以 `ls-remote` 比对为准。
6. **同源派生**：派生数据（compact/full 等）必须是同一次扫描的构建产物 + 一致性断言，禁止两处独立维护。

## 3. 通用档（所有 scripts/*.py）

- 异常处理：禁止裸 `except:`；`except: pass` 静默吞异常禁止（至少 log）。
- 输入校验：外部输入（文件路径、JSON 字段）必须校验存在性与类型；缺字段走明确报错而非静默默认。
- 硬编码：路径优先配置/env；敏感信息（token）不得入库。
- 退出码语义化：0 成功 / 非 0 各有明确含义并写入 docstring（参照 check_topic 0/1/2 惯例）。
- 新增产出物（文件/字段/规则）先答「**谁读？哪一步读？**」，答不出即死文件，不建。
- 可观测性即诚实性（EXP-014）：日志说「通过」必须来自脚本真实校验，禁止手写结论。

## 4. 触发时机（流程）

| 场景 | 必做动作 | 落盘 |
|------|----------|------|
| 改动守护类脚本 | 双向自测 + 独立审查（🔴/🟡/💭 报告）+ 版本对齐 | `deliverables/YYYY-MM-DD-主题.md` |
| 新脚本入库 / 一般改动 | `code_review_check.py <file>` 机械检查，P0 清零 | 无需报告，命令输出即证据 |
| git commit（repo `daily-why-writer`） | pre-commit hook 自动跑 `code_review_check.py --staged --strict`，P0 非零则拒绝提交 | hook 输出 |
| L3 发布 | 发布链路必经 commit，hook 即等效「发布前必跑」；另 l3 自身校验（validate_article / dedup gate / version）不变 | 现有链路 |
| 月度（或抽查） | 全量扫描 `code_review_check.py`，观察分数趋势，规则棘轮迭代 | 结果并入月度复盘 |

**规则棘轮（EXP-012）**：每次真实事故/审查发现新缺陷模式 → 优先固化为 `code_review_check.py` 规则或本文红线条目；废弃条目标 `[已废弃]` 不删除。

## 5. 机械检查工具

```bash
# 检查全部脚本
python scripts/code_review_check.py
# 检查指定文件
python scripts/code_review_check.py scripts/l3_publish.py
# 严格模式（P0 非零退出码 1；--staged 读 git 暂存区）
python scripts/code_review_check.py --staged --strict
```

工具覆盖面有限（正则级），**机械通过 ≠ 合规**（教训：脚本 100 分 ≠ 真合规，08-13 实证）。机械检查是底线，人工审查照常执行。

## 6. 审查报告模板

```markdown
# 代码审查报告：{对象/版本}
**审查者**：{人/agent}　**日期**：YYYY-MM-DD　**模式**：{独立审查 | 生成者=审查者折衷}

## 结论
{通过（P0=0 且 P1≤2）| 不通过}；一句话总评。

## 🔴 P0（必须修复）
1. **{标题}**（文件:行号）：现象 → 为什么危险 → 修复建议。

## 🟡 P1（建议修复）
（同上格式）

## 💭 P2（可选）
（逐条一行）

## ✅ 值得保留
{点名好代码/好设计，说明为什么好}

## 局限与后续
{未覆盖范围、遗留决定、待 Master 裁定项}
```

## 7. 死文件处置记录

- `agents/quality-reviewer.json`（06-05 v1.0）：引用根目录旧路径，已被 maker-checker v2.0 取代，判定死文件。建议归档（待 Master 确认后移 `archive/`）。
- `C:/Users/admin/.workbuddy/skills/daily-why-writer/CODE_REVIEW_GUIDE.md`：通用部分被本文取代，skill 包内文件暂不改动，以本节标注权威关系。
- `scripts/code_review_check.py`：由死工具激活升级为 v2.0（2026-09-15），成为流程挂接件。

## 8. 本标准的演进

版本号在文件头维护；实质变更（红线新增、流程变化）须记 `CHANGELOG.md`。修 bug 级微调不必升版。

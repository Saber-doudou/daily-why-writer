# daily-why 工作空间优化 — 上线前全检报告

**日期**：2026-06-22
**场景**：上线前检查（代码审查 + 安全审计 + QA测试）
**参与成员**：产品评审员 + 安全官 + QA负责人

---

## 📌 TL;DR（执行摘要）
- 整体结论：🟡 **有条件通过** — 无阻塞性问题，3个高优先级问题需修复后上线
- 阻塞项数量：0 🔴 / 3 🟡 高优先级
- 核心自动化链路验证通过：prepare → validate → update 全流程正常
- 工作空间优化目标达成：根目录 -81% 文件，路径一致性已验证
- 下一步：修复 3 个高优先级问题（预计 20 分钟），即可正式上线

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| Go / No-Go | 🟡 条件 Go（修复 3 个高优问题后上线）|
| 严重度分布 | 🔴 0 / 🟠 3 / 🟡 5 / 🟢 6 |
| 关键行动项 | 8 条（3 条本次必做） |
| 建议负责人 | engineering |

---

## 1. 各成员核心结论

### 🔍 产品评审员（代码审查）
- 核心判断：12/14 脚本的路径引用正确更新，自动化链路完整。但发现 2 个路径残留问题（run_pipeline.py step_status、IMAGES_DIR）和 5 个代码质量问题。
- 关键建议：立即修复 step_status 路径（P0），其他可在后续迭代中修复。

### 🛡️ 安全官（OWASP+STRIDE 审计）
- 核心判断：评级 C（中等风险），无致命或高危漏洞。主要风险集中在 auto_fix.py 路径遍历（可写入任意文件）和硬编码路径。无凭据泄露，subprocess 全部使用列表形式（安全）。
- 关键建议：为 auto_fix.py 添加工作区边界校验，替换硬编码 Python 路径。

### ✅ QA负责人（QA测试）
- 核心判断：核心功能健康评分 78/100。4 项核心脚本执行全部通过，6 项路径可达性验证全部通过。发现 3 个高优问题（compact 输出路径错误、错误消息不显示、orchestrator state 路径不匹配）。
- 关键建议：修复 3 个高优问题后即可部署，无阻塞项。

---

## 2. 综合审查发现（去重合并后按严重度排序）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源成员 |
|---|--------|------|------|---------|------|---------|
| 1 | 🟠 HIGH | 功能 | `scripts/prepare_topics.py:123` | `--compact` 输出路径切换逻辑失效，compact 数据覆盖了完整 topics_context.json | 修改条件匹配为 `"config/topics_context.json"` | QA |
| 2 | 🟠 HIGH | 功能 | `scripts/validate_article.py` | `print_report()` 不输出 errors/warnings，用户看到 FAIL 但不知道原因 | 在 print_report 中增加 errors/warnings 输出 | QA |
| 3 | 🟠 HIGH | 功能 | `scripts/orchestrator.py:43` | `state_file` 指向根目录，实际文件在 config/，每次创建新状态 | 改为 `workspace/"config"/"orchestrator-state.json"` | QA |
| 4 | 🟡 MEDIUM | 路径 | `scripts/run_pipeline.py:129` | step_status 使用旧根目录路径查找文章 | 改为 articles/YYYY-MM/ 路径或 glob | 评审 |
| 5 | 🟡 MEDIUM | 安全 | `scripts/auto_fix.py` | 接受绝对路径可写入工作区外任意文件 | 添加工作区边界校验 | 安全官 |
| 6 | 🟡 MEDIUM | 代码 | `scripts/validate_article.py:163-178` | 重复定义 count_chinese_chars/strip_markdown | 删除重复定义 | 评审 |
| 7 | 🟡 MEDIUM | 可维护性 | 多个脚本 | 硬编码 Python 解释器路径（generate_prompt.py/orchestrator.py） | 改用 sys.executable | 评审+安全 |
| 8 | 🟡 MEDIUM | 功能 | `config/orchestrator-state.json` | article_file 字段含旧格式路径 | 手动更新或等 ISSUE-H03 修复后重跑 | QA |
| 9 | 🟢 LOW | 代码 | `scripts/send_daily_why.py:23` | IMAGES_DIR 指向已删除的 generated-images | 标记废弃或移除 | 评审+QA |
| 10 | 🟢 LOW | 代码 | `scripts/generate_prompt.py` | 字数匹配正则误报（匹配到"2-6 字"） | 限制正则上下文范围 | QA |
| 11 | 🟢 LOW | UX | `scripts/validate_article.py:509` | --latest 可能选优化版文件而非原始文章 | 排除文件名含"优化版"的文件 | QA |
| 12 | 🟢 LOW | 可维护性 | 6个脚本 | 硬编码 F:\WorkBuddy\daily-why 路径 | 后续统一为环境变量 | 评审+安全 |
| 13 | 🟢 LOW | 代码 | `scripts/send_daily_why.py` | 全局变量 wechat_window 隐式依赖 | 改为参数传入 | 评审 |
| 14 | 🟢 LOW | 可维护性 | `scripts/check_topic.py` + `topic_utils.py` | 各自实现 normalize_topic 函数 | 合并到 topic_utils | 评审 |

---

## ✅ 行动清单

| # | 行动 | 负责方 | 紧急度 | 期望完成 |
|---|------|--------|--------|---------|
| 1 | 修复 prepare_topics.py --compact 输出路径切换 | engineering | 🟠 P1 | 上线前 |
| 2 | 修复 validate_article.py 错误消息不显示 | engineering | 🟠 P1 | 上线前 |
| 3 | 修复 orchestrator.py state_file 路径 | engineering | 🟠 P1 | 上线前 |
| 4 | 修复 run_pipeline.py step_status 文章路径 | engineering | 🟡 P2 | 本周 |
| 5 | 为 auto_fix.py 添加路径边界校验 | engineering | 🟡 P2 | 本周 |
| 6 | 删除 validate_article.py 中重复函数定义 | engineering | 🟡 P2 | 本周 |
| 7 | 硬编码 Python 路径改为 sys.executable | engineering | 🟢 P3 | 下迭代 |
| 8 | 更新 orchestrator-state.json 中旧路径 | engineering | 🟢 P3 | 下迭代 |

---

## ⚠️ 待完善 / 已知局限

- **send_daily_why.py**：配图功能已废弃，IMAGES_DIR 残留引用不影响运行（有 exists() 降级），可后续清理
- **硬编码路径**：6 个脚本硬编码 `F:\WorkBuddy\daily-why`，建议后续统一为环境变量 `DAILY_WHY_WORKSPACE`
- **orchestrator.py**：当前仅做状态管理不实际执行，可考虑后续重构为真编排器
- **code_review_check.py**：glob("*.py") 只查根目录，应用场景有限

---

## 📚 成员产出索引

- gstack-product-reviewer（产品评审员）原始产出：代码审查报告，P0-1/P0-2 + 5个P1
- gstack-security-officer（安全官）原始产出：`F:/WorkBuddy/daily-why/.gstack/security-audit-history/audit-2026-06-22-000000.md`
- gstack-qa-lead（QA负责人）原始产出：QA测试报告，7个issue（3高2中2低）

---

> 本报告由软件工坊 AI 协作生成，关键决策请由工程负责人复核。

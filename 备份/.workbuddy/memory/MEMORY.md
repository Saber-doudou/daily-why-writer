# 长期记忆 - Daily Why 项目

## 写作规范（详见 skill）
- **Skill 路径**：`~/.workbuddy/skills/daily-why-writer/SKILL.md`
- **自检清单**：`references/CHECKLIST.md`（12大类，2026-06-12 §1/§3/§5新增遗传术语+数据核实+比喻色彩规则）
- **黑名单**：`references/FORBIDDEN.md`（FP-01~28，2026-06-19 新增FP-25~28：渲染不安全字符/非实体膨胀/单因素归因/伪术语加粗）
- **判例库**：`review/CASE_STUDIES.md`（CS-001~011）
- **规则数值源**：`writing_rules.json`（唯一权威）
- **分类**：人体奥秘 / 自然科学 / 生活常识 / 宇宙探索 / 动物世界 / 物理化学

## 三 Skill 架构（2026-06-12 建立）
- **L1: daily-why-writer** — 每日09:40自动运行，产出v1初版文章
- **L2: daily-why-feed-learning** — 四AI投喂学习（DeepSeek/IMA/千问/豆包），产出v2优化版+新规则
- **L3: daily-why-publish** — 匹配检查+IMA备份+GitHub推送+记忆归档
- **参照**：history-today 的三Skill架构（writer/feed-learning/publish）
- **触发词**（2026-06-12 标准化，统一前缀防串门）：
  - L1：`每日一个为什么`、`每日一个为什么写作`、`dailywhy`、`dailywhy写作`、`每日冷知识`
  - L2：`每日一个为什么学习`、`每日一个为什么学习总结`、`每日一个为什么投喂`、`dailywhy学习`、`dailywhy学习总结`
  - L3：`每日一个为什么发布`、`每日一个为什么推送`、`每日一个为什么审计`、`dailywhy发布`、`dailywhy推送`、`dailywhy审计`

## 自动化运营配置
- **当前自动化**：`automation-1778312519754`（文件系统级，非 SQLite 注册）
- **旧自动化**：`automation-2`（SQLite 注册），valid_until=2026-04-28 已过期
- **触发时间**：工作日 09:40（2026-05-07 从 14:00 改为 09:30，05-09 改为 09:40）
- **运行记录路径**：`.workbuddy/automations/automation-1778312519754/memory.md`
- **Python 环境**：`C:\Users\admin\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- **发送脚本**：`send_daily_why.py` 已从自动化移除，手动可用
- **prompt 版本**：v3.0（2026-06-05 多Agent工作流，generate_prompt.py --multi-agent --compact 生成）
- **validUntil**: 无（永久运行）

## 文件命名规范
- **格式**：`{YYYY-MM-DD}-每日冷知识-{话题关键词}.md`
- **关键词**：2-6 字，从话题中提取（如"手指泡水起皱""打哈欠""海水是咸的"）
- **示例**：`2026-06-08-每日冷知识-手指泡水起皱.md`
- **兼容**：旧格式 `{日期}-每日冷知识.md` 仍可被 validate/update 脚本识别

## Phase B 脚本
| 脚本 | 功能 |
|------|------|
| `prepare_topics.py` | 扫描历史文章，输出 topics_context.json（支持 --compact 精简版） |
| `validate_article.py` | P0/P1/P2 分级审核（P0=0 且 P1≤2 通过） |
| `update_history.py` | 更新 automation memory.md（去重+排序） |
| `generate_prompt.py` | 从 writing_rules.json + SKILL.md 自动生成 automation prompt（支持 --compact 精简版） |
| `run_pipeline.py` | 编排器（prepare/validate/update/send） |
| `check_topic.py` | 话题去重机械校验（退出码 0=通过, 1=重复, 2=参数错误） |
| `scripts/code_review_check.py` | 代码审查自动化检查工具（命名、安全、性能、风格、文档） |

## Token 优化（2026-06-05 实施）
- **精简版 SKILL.md**：`SKILL_COMPACT.md`，只保留核心规则，文件大小减少57%
- **精简版 topics_context.json**：`topics_context_compact.json`，只保留 topic_summaries 数组，Token 减少75%
- **generate_prompt.py --compact**：使用精简版组件生成 prompt，总 Token 消耗减少56%
- **去重完整性**：保持全量话题用于去重，优化数据格式而非减少话题数量

## 代码优化（2026-06-05 实施）
- **公共模块**：`topic_utils.py`，统一 prepare_topics.py 和 update_history.py 中的话题提取逻辑
- **格式检查模块**：`format_checker.py`，从 validate_article.py 分离出来的格式检查功能
- **职责分离**：validate_article.py 只负责内容质量审核，format_checker.py 负责格式检查
- **Prompt 精简**：generate_prompt.py 优化，移除与 SKILL.md 重复的内容，减少30%

## 质量保障（2026-06-05 实施）
- **实时自检**：generate_prompt.py 添加"边写边自检"步骤，每写完一段立即检查
- **智能判例匹配**：`case_matcher.py`，根据问题关键词自动匹配相关判例，替代 Grep 搜索
- **审核流程优化**：审核不通过时，使用 case_matcher.py 智能匹配判例，提高修正效率

## 多Agent架构（2026-06-05 实施，2026-06-21 升级为真双Agent）
- **真双Agent架构**（2026-06-21）：Orchestrator 选题+写作+自检+精修，spawn Reviewer 做独立审校
- **参照**：history-today v9.1 的 1 Agent spawn 模式
- **模块化原则**：Orchestrator 写作阶段不加载 CHECKLIST/FORBIDDEN；Reviewer 不加载 SKILL.md
- **新增文件**：`reviewer_prompt.md`（Reviewer Agent 专用审校 prompt）
- **SKILL.md 更新**：新增「🤖 多 Agent 执行模式（v1.0）」章节
- **旧架构**：orchestrator.py + message_handler.py（单Agent模拟两阶段，已废弃）

## 系统自测（2026-06-05 实施）
- **测试结果**：所有脚本测试通过，系统运行正常
- **测试项目**：prepare_topics.py、generate_prompt.py、validate_article.py、update_history.py、case_matcher.py、message_handler.py、format_checker.py、topic_utils.py
- **审核结果**：最新文章审核通过（P0=0, P1=1, 得分95）

## 代码审查机制（2026-06-05 实施）
- **审查指南**：`CODE_REVIEW_GUIDE.md`，包含代码质量、安全、性能标准
- **自动化工具**：`scripts/code_review_check.py`，支持命名、安全、性能、风格、文档检查
- **报告模板**：`scripts/review_report_template.md`
- **使用文档**：`scripts/README.md`

## 关键教训（详细版见 FEEDBACK_LOG.md + CASE_STUDIES.md）
- **话题去重**：选话题后必须运行 `check_topic.py` 机械校验（退出码1=重复），不能凭记忆判断（2026-05-19 CS-001 + 2026-06-08 修复）
- **四家AI投喂**：DeepSeek/千问/IMA/豆包 优化建议，详见 `投喂素材/AI能力特点.md`
- **排版规范**（2026-05-26 统一）：Q 加粗禁 h3、分隔线恰好 2 处、F 段标签"冷知识反转"、风格表格 4 行含分类
- **其他AI建议需二次验证**（2026-06-11 教训）：千问建议替换Reusch 2023为"Philholz 2005"——验证后Reusch 2023真实存在(PMC9929504)，而"Philholz 2005"是AI幻觉。投喂建议中的"查证类"建议必须WebSearch二次确认
- **AI数据范围需核实**（2026-06-12 教训）：DeepSeek给出"15%-30%"人群比例，实际文献为"18%-35%"——AI可能凭印象自创范围，写入具体百分比前必须WebSearch确认
- **非病理遗传特征不能称"病"**（2026-06-12 教训）：千问称光喷嚏反射为"常染色体显性遗传病"——它不是病，是正常遗传变异，应称"特质/特征/反射"
- **比喻情感色彩也需检查**（2026-06-12 教训）：FP-21——"泄漏""故障"等负面词暗示身体有问题，应改用"串线""串扰"等中性措辞
- **历史人物学科身份必须核实**（2026-06-15 教训）：Paul Janet是哲学家非心理学家，贝扬是机械工程教授非神经物理学家——引用人物时WebSearch确认学科身份，不能凭印象归类
- **"偷懒"等暗示主观行为的词不应用于生理变化**（2026-06-15 教训）：FP-21细化——神经传导退化是衰老自然过程，应称"高效压缩/优化存储"而非"偷懒"
- **奖项年份和实验时长必须核实**（2026-06-16 教训）：搞笑诺贝尔奖年份1999→实际2009，四家AI均指出——FP-14细化，引用任何奖项/荣誉时WebSearch确认颁奖年份
- **A段悬念必须在后文解答**（2026-06-16 教训）：A段提到"上瘾感"但后文未展开，DeepSeek指出——设下的钩子必须在C段或F段收
- **Markdown 渲染不安全字符**（2026-06-19 教训）：`~`（波浪号）和 `——`（双破折号）在某些渲染器中被误解析为删除线/下标——文章中用"到/至"替代 `~`，用逗号替代 `——`（FP-25）
- **非实体结构不用"膨胀"**（2026-06-19 教训）：瞳孔是孔洞不是实体，用"扩张/放大"而非"膨胀"（FP-26）
- **自主神经调控是复合机制**（2026-06-19 教训）：瞳孔调节涉及副交感退场+交感登场，不能只提单方面（FP-27）
- **非标准术语不加粗强调**（2026-06-19 教训）："瞳孔情绪反应"非标准术语，加粗引号会误导读者（FP-28）

## Darwin 进化系统（2026-06-12 建立）
- **Skill 路径**：`.workbuddy/darwin/SKILL.md`
- **触发词**：进化审查、达尔文审查、darwin-review
- **自动化**：Daily-Why-Health（cron `40 9 * * *`，每日09:40自动审查）
- **审查范围**：10个Skill（daily-why×3, history-today×3, ecommerce, shipping, modular-refactor, deep-research）
- **评分体系**：8维度，结构60分+效果40分=100分，A(90+)/B(80-89)/C(70-79)/D(<70)
- **状态追踪**：`.workbuddy/darwin/darwin_progress.json`（10 Skills 进度）
- **单Skill状态**：`.workbuddy/darwin/{skill_name}/darwin_state.json`
- **历史报告**：`.workbuddy/darwin/reports/{skill_name}/{date}_v{n}.md`
- **反馈格式**：`{SKILL缩写}-{3位数}`（如 DW-001, HTW-001）
- **首次审查**：daily-why-writer，95分（A级），3个改进项

## 文件写入规则
- 新规范 → SKILL.md
- 新自检项 → references/CHECKLIST.md
- 新禁止模式 → references/FORBIDDEN.md（编号 FP-XX）
- 新教训 → references/FEEDBACK_LOG.md
- 新判例 → review/CASE_STUDIES.md（编号 CS-XXX）
- 重大改造 → CHANGELOG.md（版本日志）

## 变更日志
- **路径**：`F:\WorkBuddy\daily-why\CHANGELOG.md`
- 记录每次重大改造的详细变更（v1.3→v2.0→v2.95）

## 四家AI投喂参考
- **路径**：`F:\WorkBuddy\daily-why\投喂素材\AI能力特点.md`
- DeepSeek=事实核查强，千问=结构分析强，IMA=前沿敏感，豆包=表达润色细
- 投喂素材路径：`F:\WorkBuddy\daily-why\投喂素材\{日期}\`

## IMA 工具
- **路径**：`C:\Users\admin\WorkBuddy\tools\`
- `ima_upload.py` — `IMAUploader` 类，创建/追加/搜索笔记
- `ima_archive.py` — `IMAArchiver` 类，backup-memory/archive/list/restore
- **备份标题格式**：`daily-why 自动化配置 v{版本号} 备份{YYYYMMDD}`（版本号自动推算）
- **知识库**：`workbuddy自动化备份`（kb_id=7457707061698771），需手动在IMA客户端添加

## IMA 备份历史
| 版本 | note_id | 日期 | 说明 |
|------|---------|------|------|
| v2beta1 | 7458171333397208 | — | 旧版 |
| v2.5 | 7458186067992839 | — | 当时最新 |
| v2.8 | 7458780677694054 | — | 自动化 prompt v1.8 |
| v2.95 | 7459544548533546 | 2026-05-11 | 完整架构文档 |
| — | 7468319141557501 | 2026-06-04 | 自动化配置+今日文章+优化版+技能更新 |
| — | 7468495935664875 | 2026-06-05 | 自动化配置备份+优化版+四家AI投喂学习+新增规则 |
| v3.1 | 7469070991497635 | 2026-06-07 | 伪多Agent优化：validate增强+auto_fix+prompt精简+case_matcher嵌入 |
| v3.2 | 7469576346409877 | 2026-06-08 | 去重防护升级(check_topic.py)+文件命名规范+github推送 |
| v3.3 | 7470653489836475 | 2026-06-11 | 四家AI投喂优化+FP-20比喻方向性+CHECKLIST§5+千问幻觉教训 |
| v3.4 | 7471063592104049 | 2026-06-12 | 光喷嚏反射优化版+三Skill架构+FP-21+触发词标准化+Darwin首次审查 |
| — | 7472183727125066 | 2026-06-15 | 时间感知加速优化版+FP-14细化+FP-21细化+四家AI投喂 |
| — | 7472482961332706 | 2026-06-16 | 关节咔咔响优化版+FP-14细化(奖项年份)+FP-03强化+四家AI投喂 |
| — | 7474503475020881 | 2026-06-22 | v3.0两Agent架构+Darwin优化+L2 prompt自动更新（v9.2为bug） |
| v3.5 | 7474633989177720 | 2026-06-22 | 修复后正确版本 |

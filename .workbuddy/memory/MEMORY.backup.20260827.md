# 长期记忆 - Daily Why 项目

## 写作规范
- **Skill 路径**：`~/.workbuddy/skills/daily-why-writer/SKILL.md`
- **自检清单**：`references/CHECKLIST.md`（95项 §1到§95）
- **黑名单**：`references/FORBIDDEN.md`（FP-01到66）
- **判例库**：`review/CASE_STUDIES.md`（CS-001~011）
- **规则数值源**：`writing_rules.json`（唯一权威）
- **分类**：人体奥秘 / 自然科学 / 生活常识 / 宇宙探索 / 动物世界 / 物理化学

## 三 Skill 架构（2026-06-12 建立）
- **L1: daily-why-writer** — 每日09:40自动运行，产出v1初版
- **L2: daily-why-feed-learning** — 四AI投喂学习，产出v2优化版+新规则
- **L3: daily-why-publish** — 脚本预检+AI语义验证+脚本执行（v3.1）
- **触发词**：L1=`dailywhy/每日冷知识`, L2=`dailywhy学习/学习总结/投喂`, L3=`dailywhy发布/推送/审计`

## 自动化运营
- **自动化ID**：`automation-1778312519754`；工作日 09:40
- **Python**：`C:\Users\admin\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- **prompt 生成**：`generate_prompt.py --update-automation` 生成最新 prompt → 用 automation_update 工具写入数据库（规则变更后强制执行；改规则脚本后必须同步源码模板）

## 文件命名
- **格式**：`{YYYY-MM-DD}-每日冷知识-{2-6字关键词}.md`；优化版前缀 `{YYYY-MM-DD}-优化版-每日冷知识-{关键词}.md`

## 脚本工具
| 脚本 | 功能 |
|------|------|
| `prepare_topics.py` | 扫描历史→topics_context.json（--compact 精简版） |
| `validate_article.py` | P0/P1/P2分级审核 |
| `update_history.py` | 更新automation memory.md |
| `generate_prompt.py` | 生成prompt（--update-automation 更新数据库） |
| `check_topic.py` | 话题去重校验（退出码0过/1重/2参数错） |
| `case_matcher.py` / `format_checker.py` / `topic_utils.py` | 判例匹配/格式检查/公共话题提取 |
| `archive_lessons.py` | FEEDBACK 休眠教训归档 + 激活检测（--mode archive/check） |
| `rule_lifecycle.py` | CHECKLIST 规则升降级分区（--update 重写三区；默认统计） |

## 多Agent架构（2026-08-20，v2.0 独立 Reviewer 审校）
- Orchestrator 选题+写作+自检+精修；审校由 **spawn 独立 Reviewer** 执行（maker-checker，橙皮书 EXP-005）
- **spawn 规范**：`Agent(subagent_type="general-purpose", model="reasoning")`，**禁止传 name 参数**（name 依赖 team 上下文必失败；08-13 隔壁实证去掉 name 成功，08-20 本项目 agent-649f7e2c 实证成功）
- **熔断链**：spawn 报错 → 去 name 重试 1 次 → 仍失败 → 熔断 → Orchestrator 自审 + 标注「⚠️ 未独立审校」（自审仅降级兜底）
- **文件检测等待**：reviewer 写 `review/{date}_review.json` 落盘，Orchestrator 每 1 分钟轮询，15min 上限，不依赖 SendMessage
- **Reviewer 不加载写作规则**（纯粹审核视角）；审校含事实断言独立 WebSearch 核验（人物/机构/亲缘/数字）
- 历史教训（08-06/08-13 曾放弃 spawn，v4.0 改同步自审）→ v4.1 撤销：当时未穷尽 workaround，08-20 实证去 name 可成功
- 模块化：写作阶段不加载CHECKLIST/FORBIDDEN；Reviewer 审校阶段加载做对照

## Skill 调用修复（07-07排查→07-08部署→08-04验证✅）
- 修法：①generate_prompt.py 阶段0插入强制 Skill 调用 ②Reviewer FP 编号动态扫描 ③prompt 只留编排壳 ④阶段0守卫（显式输出"✅ SOP已加载"）⑤最小结构验证
- 08-04 起 L1 自动化已真实调用 Skill 工具加载 daily-why-writer

## IMA 备份约束（2026-06-23）
- `l3_publish.py` Phase 2 用 `--config-only`，IMA 只备份 MEMORY.md 配置（脚本 `C:/Users/admin/WorkBuddy/tools/ima_archive.py`，kb_id=7457707061698771，备份命令 backup-memory）
- **MEMORY.md 超限压缩前必须先 IMA 备份当前版本（2026-08-04 Master 确认）**

## 字数限制约定（2026-07-10 Master 决策）
- 字数上限暂不强制，实测超 700 字再处理；不要把"超600字"当发布阻塞项反复提出
- 计数口径：仅汉字（[\u4e00-\u9fff]），不含标点/英文/数字

## 文件写入规则
- 新规范→SKILL.md | 自检项→CHECKLIST.md | 禁止模式→FORBIDDEN.md(FP-XX)
- 教训→FEEDBACK_LOG.md | 休眠教训(>30天)→FEEDBACK_ARCHIVE.md | 判例→CASE_STUDIES.md | 重大改造→CHANGELOG.md
- 归档：`archive_lessons.py --mode archive`（L3 Phase 5）；激活检测：`--mode check --feedback "..."`（L2）

## CHECKLIST 规则升降级（2026-08-26 建立）
- 命令：`rule_lifecycle.py --update`（L2 Phase 3 Step 9 自动跑，重写 CHECKLIST 三区）
- 三区：🔥活跃区（近30天被引用，必查）/ 🛡️预防区（有教训+零触发，按需）/ 🔬待验证区（从未引用，保留）
- **基线（08-26）**：活跃46 / 预防35 / 待验证19；TOP触发 §66/§68/§91 (4次)、§2/§100 (3次)
- **验证方法（30天后对照）**：跑 `rule_lifecycle.py` 看三区变化——①待验证区应减少（新规则被触发）②预防区应增长（活跃区规则稳定后降级）③活跃区 TOP 应变化（老问题被压住、新问题浮出）④任何区不该出现"规则消失"（零删除原则）
- FORBIDDEN 66 条不动（Master 决策，仅 CHECKLIST 做升降级）

## Darwin 进化系统
- `.workbuddy/darwin/SKILL.md`；10个Skill 8维度评分（结构60+效果40=100）；daily-why-writer 首审 95分（A级）

## 关键教训（速查，完整规则见 CHECKLIST.md/FORBIDDEN.md）
- 话题去重必须 `check_topic.py` 机械校验；AI建议必须WebSearch二次确认（数据/人物/奖项/年份）
- 非病理特征不称"病"；比喻不用负面词；生理变化不暗示主观行为；A段悬念必须后文解答
- Markdown 用"到/至"替`~`、逗号替`——`；子 agent prompt 末尾必须附【硬约束】禁`~`条款（08-10）
- 免疫细胞：B细胞=抗体工厂、树突状=侦察兵、肥大细胞=哨兵（FP-34）；致敏用"反复接触"（FP-35）
- 数量级要验证（恒星10²²~10²⁴，FP-43）；因果不倒置（FP-44）；化学类比用"共享分子"（FP-47）
- 悖论开头先制造认知冲突（§38）；离体实验不外推活体（FP-45）；气压差用"高/低"（§43）
- 健康科普覆盖易感人群（§44）；标题概念域一致（§47）；辟谣保留中间态（FP-49）
- 黑膜成因含半波损失（FP-53/54）；湿表面区分光照（FP-57）
- 机制拟人：感知归受体、终止归物理过程停止、倍数限定时段（FP-64/§65/§66）；病理术语勿用（FP-65）
- 数值衔接逻辑、引用融入行文（§68/§9）；概括动词覆盖全部机制（§69）
- 历史断言加前提与强度限定（§70）；同一表述前后一致（§71）；习惯化非"学会"（§72）
- 强因果点明因果链（§73）；组织成分禁"没有水分"绝对化（§74）；耐受机制双重防线（§75）
- 实证化表述"未观测到"不等于"不存在"（§2案例）；多数值显式消歧（§68案例）
- 机制归因"以A为主、B极小"禁"不是A而是B"（§79）；抽象统计给数量级对比（§80）
- 化学黑话可省略留核心概念（FP-17案例）；微观可动性：交联固定、链段绕结点扭转（§81）
- 通俗版保留术语锚点（§82）；分子受体"结合并激活"禁"撞上"（§83）
- 类比禁暗示真实病理（§84）；发现史说清"用什么发现什么"（§85）
- 提问禁强化错误预设（§86）；**标题动词禁目的论（§87，08-14）**；**列举物种须核实行为归属（§88，08-14）**
- **实验描述忠实研究设置：摆锤模拟≠真人动作、垂直冲击降摩擦非"拽松"（§89，08-17）**；结论须配一秒自检/辨别法（§20案例）；类比精确物理阶段：再入大气层（FP-20案例）
- **收尾金句"A是X其实是Y"对照词情绪一致且语法完整（§90，08-17 Master真人反馈）**：副词不能单独做"是"宾语（突然/终于→补中心词），期待色彩词勿用于负面事件
- 规则修复须同步源码模板+数据库（08-11）；Master 反馈闭环：AI审不出"看不懂"，真人反馈暴露通俗度缺口（08-11）
- **git 凭证/引用坑（08-17 L3 发布 / 08-18 补推再次踩坑）**：全局 credential.helper=manager-core 指向不存在程序（git 2.55 缺 git-credential-manager-core）→ **已文件级修复**：.gitconfig 直接写 `credential.helper=wincred`；但 WorkBuddy 内置 PortableGit 在**系统级** `etc/gitconfig` 配置了 `credential.helper=helper-selector`，Git 会**顺序调用多个 credential.helper**，导致即使全局配了 wincred 仍会弹 CredentialHelperSelector；**彻底修复**需同时把系统级 gitconfig 和全局 .gitconfig 都写成 `credential.helper=wincred`（wincred 读 Windows 凭据管理器缓存的 GitHub token；⚠️ `git config --global` 写入被沙箱静默阻止=rc0 假成功，必须直接编辑文件）；l3 脚本另保留 `-c credential.helper=wincred` 三保险；沙箱静默阻止 packed-refs 重写（update-ref/fetch 返回 0 但不生效）→ 手动写 loose ref `.git/refs/remotes/origin/main` 修复

- **蛇没脚爬行 L2（08-26）**：CHECKLIST §100 三自检（数量须与正文实际对应 / 标题·开头定性速度·程度卖点须正文用数据或机制兑现 / 机制描述特定组织不得扩大为"全身/所有"同类结构）；信源甄别再验（DS 误判"直线式不适合粗树干"，经 WebSearch 核实为误判，多数 AI 一致≠正确，重验 §91）；脚本机械 100 分≠内容无优化空间，L2 差额分析仍有语义级可优化点

## 质量趋势（最近10次投喂）
| 日期 | 话题 | AI数 | 新FP | v1分→v2分 | 状态 |
|------|------|------|------|-----------|------|
| 2026-08-26 | 蛇没脚爬行 | 4 | 无FP + §100 + §91再验(DS误判直线式) | 100→100 | ✅ |
| 2026-08-25 | 保鲜膜贴碗口 | 4 | 无FP + §99 + §63/§91案例 + FP-49案例 | 100→100 | ✅ |
| 2026-08-24 | 左右鼻孔轮班 | 4 | 无FP + §96/§97/§98 + §2/§35/§41案例 | 96→100 | ✅ |
| 2026-08-21 | 关灯留亮光 | 4 | 无FP + §95 + §68/§20/§79/§82/§91案例 + FP-55案例 | 100→100 | ✅ |
| 2026-08-20 | 湿了变深 | 4 | 无FP + §94 + §2/§16/§82/§93案例 | 100→100 | ✅ |
| 2026-08-19 | 红酒挂杯 | 4 | FP-66 + §91/§92/§93 | 100→100 | ✅ |
| 2026-08-18 | 喷嚏闭眼 | 4 | 无FP + FP-05/22/33案例 + §1案例 | 100→100 | ✅ |
| 2026-08-17 | 鞋带松开 | 4 | 无FP + §89 + §20/FP-20案例 | 100→100 | ✅ |
| 2026-08-14 | 飞蛾扑灯 | 4 | 无FP + §87/§88 + §16/§60案例 | 100→100 | ✅ |
| 2026-08-13 | 辣椒为什么辣 | 4 | 无FP + §83/84/85/86 | 100→100 | ✅ |
| 2026-08-12 | 指纹独一无二 | 4 | 无FP + §19/§66/FP-24/FP-05案例 | 100→95 | ✅ |
| 2026-08-11 | 橡皮筋弹回 | 4 | 无FP + §79/80 + FP-17案例 | 95→95 | ✅ |
| 2026-08-11 | 橡皮筋弹回(二轮) | 4 | 无FP + §81/§82 | 95→95 | ✅ |
| 2026-08-10 | 雪是白色的 | 4 | 无FP + §76/77/78/73案例 | 100→95 | ✅ |
| 2026-08-07 | 企鹅脚不怕冻 | 4 | §74/§75（无FP） | 100→95 | ✅ |
## IMA 备份历史（最近）
| 版本 | note_id | 日期 | 说明 |
|------|---------|------|------|
| v5.6 | 7493852780824301 | 2026-08-14 | MEMORY.md 压缩前备份（L2） |
| v5.5 | 7493707569829926 | 2026-08-13 | l3_publish.py 自动备份 |
| v5.4 | 7493706735161486 | 2026-08-13 | l3_publish.py 自动备份 |
| v5.3 | 7493187799089499 | 2026-08-12 | l3_publish.py 自动备份 |
| v5.2 | 7492851285889592 | 2026-08-11 | l3_publish.py 自动备份 |
| v5.1 | 7492407918594667 | 2026-08-10 | l3_publish.py 自动备份 |
| v5.0 | 7491341130931191 | 2026-08-07 | l3_publish.py 自动备份 |
| v4.9 | 7490965963017800 | 2026-08-06 | l3_publish.py 自动备份 |
| v4.8 | 7490616879482590 | 2026-08-05 | l3_publish.py 自动备份 |
| v4.7 | 7490227362877885 | 2026-08-04 | l3_publish.py 自动备份 |
| v5.7 | 7493854857009169 | 2026-08-14 | l3_publish.py 自动备份 |
| v5.8 | 7494963696768442 | 2026-08-17 | l3_publish.py 自动备份 |
| v5.9 | 7495303720600978 | 2026-08-18 | l3_publish.py 自动备份 |
| v6.0 | 7495684345301925 | 2026-08-19 | l3_publish.py 自动备份 |
| v6.1 | 7496086755218252 | 2026-08-20 | l3_publish.py 自动备份 |
| v6.2 | 7496087145288761 | 2026-08-20 | l3_publish.py 自动备份 |
| v6.3 | 7496396823337094 | 2026-08-21 | l3_publish.py 自动备份 |
| v6.4 | 7497566488887310 | 2026-08-24 | l3_publish.py 自动备份 |
| v6.5 | 7497843854022129 | 2026-08-25 | l3_publish.py 自动备份 |
| v6.6 | 7498308582903137 | 2026-08-26 | l3_publish.py 自动备份 |

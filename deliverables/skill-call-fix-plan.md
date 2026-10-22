# 最终版修复方案：自动化 Skill 调用修复

> 状态：**已执行**（2026-07-07 11:35 部署）
> 目标：修复 L1 自动化 prompt 中 "加载 skill" 是自然语言描述而非工具调用的问题

---

## 一、Bug 根因（一句话）

`generate_multi_agent_prompt()` 生成的 prompt 第 4 步写的是：
```
4. 加载 daily-why-writer skill，按 A+C+F 结构……
```
这是**自然语言描述**（模型理解为"按 skill 的规则写文章"），不是**工具调用**（`Skill("daily-why-writer")`）。模型照做了规则，但从未触发 Skill 工具 → `usage-log.json` 无记录 → "已使用"指示器为 0。

**存活时间：≥16 天**（2026-06-21 多 Agent 上线 → 2026-07-07 发现）。

**为什么没早发现：**
1. 输出完全正确——文章合规，质检通过，表面无异常
2. CHECKLIST.md / FORBIDDEN.md 按绝对路径现场读（活的），制造了虚假安全感
3. usage-log.json 不在任何质量检查流程范围内
4. 定时任务在后台沙箱跑，无人盯屏
5. "加载 skill" 对人而言语义正确，没有人意识到它应该是工具调用

---

## 二、修复范围

| 层级 | Skill | 当前状态 | 是否修复 |
|------|-------|---------|---------|
| L1 | daily-why-writer | ❌ 自然语言描述，无工具调用 | ✅ 本次修复 |
| L2 | daily-why-feed-learning | ❌ 同样问题（usage-log 无记录） | 🔍 本次同步排查 |
| L3 | daily-why-publish | ✅ 聊天窗口手动触发，Skill 工具正常工作 | 无需修复 |

---

## 三、具体改动

### 改动 1：Phase 1 插入"强制加载 SOP"（第 0 步）

**位置**：`generate_prompt.py` 的 `generate_multi_agent_prompt()` 函数，阶段 1 开头

**新 prompt 片段**（替换原第 4 步）：

```
## 阶段0：强制加载写作SOP（必须在写任何字之前完成）

优先执行①，若失败则执行②：

① 调用 Skill 工具，参数 skill=`daily-why-writer`，将其 SKILL.md 完整加载为本轮写作SOP；
② 若当前环境无 Skill 工具或调用失败，则读取文件全文：
   `C:/Users/admin/.workbuddy/skills/daily-why-writer/SKILL.md`

加载完成后，写作/自查/精修严格以 SKILL.md 的最新内容为准。
本 prompt 内关于写法的描述仅作对齐参考。未完成 SOP 加载不得动笔。

## 阶段1：选题+写作（Orchestrator 亲自执行）

1. 运行……（后续步骤不变，原第4步"加载 daily-why-writer skill"删除）
```

**设计理由**：
- 明确写了工具名 `Skill` + 参数 `skill=daily-why-writer`（不再是自然语言描述）
- 提供②路径读取兜底（即使自动化沙箱无 Skill 工具，漂移照样根除）
- "未完成 SOP 加载不得动笔" 防止跳过

---

### 改动 2：Reviewer 阶段去掉写死的 FP 编号

**位置**：`generate_multi_agent_prompt()` 函数，阶段 2 Reviewer prompt

**改前**：
```
4. 加载 `{SKILL_DIR}/references/FORBIDDEN.md` 扫描 FP-01~42
```

**改后**：
```
4. 加载 `{SKILL_DIR}/references/FORBIDDEN.md`，逐条扫描其中【全部】FP 规则（数量以文件实际内容为准，不要写死编号）
```

**设计理由**：
- 当前硬编码 "FP-01~42"，FORBIDDEN.md 加新条目后 prompt 过期
- 改为"以文件实际内容为准"，永久免维护

---

### 改动 3（验证通过后执行）：瘦身内联副本

**条件**：改动 1、2 验证通过（usage-log 出现 daily-why-writer + 文章质量不变）

**内容**：删除 `generate_multi_agent_prompt()` 中关于 A+C+F 写法、排版格式的大段内联描述，只保留自动化专属编排壳（脚本调用、Reviewer spawn、文件夹创建、update_history）

**风险**：低（SKILL.md 已是活的，内联副本冗余）

---

## 四、Darwin 补充项

### 补充 1：验证检查点

改动部署后，在自动化 prompt 末尾追加验证步骤：

```
## 阶段5：技能调用验证

执行结束后，读取 `C:/Users/admin/.workbuddy/usage-log.json`，
查找是否包含 `daily-why-writer`：
- 包含 → 输出 "✅ Skill 工具调用生效"
- 不包含 → 输出 "⚠️ Skill 工具不可用，已回退到路径读取模式（B路径）"
```

**目的**：第一次手动触发后就知道 A 路径是否生效，不用猜测。

---

### 补充 2：沉淀判例 CS-012

**文件**：`F:/WorkBuddy/daily-why/review/CASE_STUDIES.md`

**新增内容**：

```
### CS-012: 自动化 prompt 中的"加载 skill"不等于 Skill 工具调用

- **日期**：2026-07-07
- **场景**：generate_prompt.py 生成的多 Agent 自动化 prompt 含"加载 daily-why-writer skill"
- **问题**：模型将这句话理解为自然语言指令（"按 skill 的规则写文章"），不触发 Skill 工具调用
- **后果**：
  - usage-log.json 无 daily-why-writer 记录，"已使用"指示器为空
  - SKILL.md 修改后自动化不感知（漂移风险）
- **根因**：prompt 中的技能引用必须用工具调用语法（明确写"调用 Skill 工具，参数 skill=XXX"），不能用自然语言描述
- **修正方案**：
  1. 强制指令：`调用 Skill 工具，参数 skill=daily-why-writer`（A 路径）
  2. 兜底：若工具不可用，按路径读 SKILL.md 全文（B 路径）
  3. 末尾加验证步骤，回读 usage-log.json 确认是否生效
- **教训**：
  - 自然语言的"加载 skill"对人语义正确，对系统不是工具调用
  - 定时任务在后台沙箱运行，无人工盯屏，需要自动化验证环节
  - usage-log.json 应纳入质量检查流程
```

---

### 补充 3：同步排查 L2（daily-why-feed-learning）

**现状**：MEMORY.md 第 44 行明确记录 L2 同样无使用记录。

**排查步骤**（明天改完 L1 后执行）：
1. 查看 L2 skill 的触发方式（是手动聊天触发还是定时任务？）
2. 如果是手动触发：检查 usage-log 是否同样缺少记录
3. 如果同样缺少：L2 的 SKILL.md 调用方式是否存在同样问题
4. 按相同 A+B 模式修复

---

## 五、执行计划

| 步骤 | 时间 | 内容 |
|------|------|------|
| 1 | 2026-07-07 全天 | 保持现状，等今天自动化正常走完 |
| 2 | 2026-07-08 | 修改 `generate_prompt.py`（改动1+2） |
| 3 | 2026-07-08 | 运行 `python generate_prompt.py --compact --update-automation` 部署新 prompt |
| 4 | 2026-07-08 | 手动触发一次自动化，观察 usage-log.json 是否出现 daily-why-writer |
| 5 | 2026-07-08 | 确认无误后，补充 CASE_STUDIES.md（CS-012） |
| 6 | 2026-07-08 | 排查 L2（daily-why-feed-learning）是否存在同样问题 |
| 7 | 验证通过后 | 执行改动 3（瘦身内联副本） |

---

## 六、风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| A 路径不生效（自动化沙箱无 Skill 工具） | 中 | 低 | B 路径兜底，漂移照样根除，仅"已使用"仍为空 |
| 改动后文章质量下降 | 低 | 中 | Reviewer + validate_article.py 不变，质量把关仍在 |
| L2 存在问题未及时发现 | 中 | 低 | 补充 3 已列入排查计划 |

# FEEDBACK_ARCHIVE 休眠教训库 — 恢复+自动化方案

> 版本：v1 | 日期：2026-06-26 | 状态：待审阅

---

## 一、现状诊断

### 好消息：功能还在，只是藏得深

| 文件 | 位置 | 状态 |
|------|------|------|
| `FEEDBACK_LOG.md` | `~/.workbuddy/skills/daily-why-writer/references/` | ✅ 活跃，记录101条教训（2026-05-19 至今） |
| `FEEDBACK_ARCHIVE.md` | `~/.workbuddy/skills/daily-why-writer/references/` | ✅ 存在，但有设计无数据 |
| SKILL.md 引用 | 两个文件都有引用逻辑 | ✅ 写对了 |
| 休眠策略 | 30天+已转化规则→归档；再犯→激活回活跃 | ✅ 设计已定 |

### 坏消息：三个问题

**① 项目级路径断裂**
`scripts/config.json` 写的是 `references/FEEDBACK_LOG.md`（项目根目录），但实际文件在 skill 目录下。`l3_publish.py` 也引用了这个路径，是死链。

**② 从未归档过**
2026-05-19 至今的101条教训全堆在 `FEEDBACK_LOG.md`。最早的可归档数据（2026-05-19 ~ 2026-05-26）已经超30天，但从未被挪到休眠库。

**③ 再犯检测纯靠人脑**
没有自动化脚本去对比新 AI 反馈和休眠库的匹配度。

---

## 二、方案设计

### 核心原则

- **文件位置不动**：`FEEDBACK_LOG.md` 和 `FEEDBACK_ARCHIVE.md` 继续留在 skill 的 `references/` 目录下（Skill 架构原始设计如此）
- **项目级引用修复**：脚本中指向 skill references 的路径改为绝对路径
- **自动化归为两步**：归档脚本 + 激活检测，分别在 L2 和 L3 流程中触发

### 2.1 文件归属

```
文件存放：~/.workbuddy/skills/daily-why-writer/references/
    ├── FEEDBACK_LOG.md       ← 活跃教训（30天内）[已有]
    ├── FEEDBACK_ARCHIVE.md   ← 休眠教训（超30天+已转化）[已有空壳]
    ├── FORBIDDEN.md          ← 黑名单 [已有]
    └── CHECKLIST.md          ← 自检清单 [已有]

脚本存放：scripts/
    └── archive_lessons.py    ← 新增：归档 + 激活检测
```

### 2.2 归档逻辑（`archive_lessons.py`）

```
输入  → FEEDBACK_LOG.md
条件 → 同时满足：
        ① 距今 > 30 天
        ② 已转化为 FP-XX 或 CHECKLIST §XX 规则
动作 → 将整行从 FEEDBACK_LOG.md 剪切到 FEEDBACK_ARCHIVE.md
输出 → FEEDBACK_ARCHIVE.md（追加）+ FEEDBACK_LOG.md（删除行）
备注 → 保留原日期信息，追加一列「归档日期」
```

### 2.3 激活检测（同一个脚本，`--check-recur` 模式）

```
输入  → 新的 AI 审校反馈文本
匹配 → 在 FEEDBACK_ARCHIVE.md 的「教训」列中进行模糊匹配
动作 → 找到匹配项 → 整行移回 FEEDBACK_LOG.md，标记 `[再犯]`
输出 → 激活警告：「⚠️ 休眠教训 [原日期] 被激活：XXX」
备注 → 同时记录再犯次数
```

### 2.4 触发时机

| 触发点 | 操作 | 集成位置 |
|--------|------|---------|
| **L2 投喂学习完成后** | 检查新反馈是否匹配休眠教训 → 激活 | `daily-why-feed-learning` skill 尾部 |
| **每日/每周定时** | 检查 FEEDBACK_LOG 中是否有可归档条目 | 新增 cron，或集成到 `update_history.py` |
| **L3 发布流程** | 如果发生了激活，在发布报告中输出 | `l3_publish.py` Phase 3 |

### 2.5 路径修复

| 文件 | 当前 | 修复为 |
|------|------|--------|
| `scripts/config.json` | `"references/FEEDBACK_LOG.md"` | 改为 skill references 的**绝对路径** |
| `scripts/l3_publish.py` 第511行 | `"references/FEEDBACK_LOG.md"` | 同上 |
| `MEMORY.md` | 已有写入规则 | ✅ 无需修改 |

---

## 三、影响范围

| 影响范围 | 说明 | 风险 |
|---------|------|------|
| `scripts/` | 新增 `archive_lessons.py` | 低 |
| `scripts/config.json` | 改1行路径 | 低 |
| `scripts/l3_publish.py` | 改1行路径 | 低 |
| `daily-why-feed-learning` | 尾部加激活检测调用 | 中（需修改 SKILL.md） |
| `update_history.py` | 可选集成归档触发 | 低 |
| `FEEDBACK_LOG.md` | 数据只移出不修改结构 | 低 |
| `FEEDBACK_ARCHIVE.md` | 从空壳变为有数据 | 低 |

---

## 四、开放问题

1. **首次归档什么时候做？** 手动跑一次脚本将2026-05-19~2026-06-26中已转规则的条目批量归档？还是保留全部历史，只对之后的新教训启用自动归档？
2. **激活检测的匹配阈值？** 精确匹配还是模糊匹配？建议先用关键词模糊匹配（教训列扫描），人工确认后再移回。
3. **归档时机？** L2完成后自动触发，还是独立定时任务？建议先用 L2 尾部触发，稳定后再考虑独立定时。

---

## 五、实施步骤（审阅后执行）

```
1. 修复 config.json / l3_publish.py 中的死链接路径
2. 编写 archive_lessons.py（归档 + 激活检测双模式）
3. 手动执行首次批量归档
4. 集成到 L2 流程尾部（激活检测）
5. 集成到 update_history.py（每日归档检查）
6. 更新 MEMORY.md 记录本次改动
```

---

*请 Master 审阅以上方案，确认后再开始实施。*

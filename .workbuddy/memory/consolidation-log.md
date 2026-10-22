# daily-why · memory 治理审计日志（consolidation-log）

> 建立时间：2026-09-15 ｜ 建立方：memory 治理整改会话（整改任务 P1-7 第 3 条）
> **本文件为事后追记，非实时记录**：本条建立之前本项目发生的治理动作没有逐条留痕，无法回放。建立原因：09-14/09-15 两轮验收报告 P2-2 指出本项目「有治理痕迹但无审计日志」，审计链不完整。
> 日志纪律：append-only，只增不改；每次治理动作（压缩/下沉/归档/备份）追加一条，含 动作/对象/字符数变化/备份路径/操作人/时间。

## 建立时点实测（2026-09-15 20:15 前后，时点值）

| 项 | 实测 |
|---|---|
| L0 日志 | 107 份（2026-04-13.md 至 2026-09-15.md） |
| topics/ 文件 | 10 份（a_plan / archive_index / defects / fixed / ima_history / iron_rules / maker_checker / pending / review_defense / trends） |
| 其他 | MEMORY.md、MEMORY.backup.20260827.md、darwin_experiment_log.tsv |
| backups/ | 建立时为空目录（2026-09-15 整改创建） |

## 2026-09-15 · memory 治理整改（P1-7 第 5 条）

- 动作：`topics/iron_rules.md.bak-20260908-171934`（7167B）移出 topics，移入 `memory/backups/`（判据 F3：文件名带时间戳后缀且为同名文件旧版本，属机制副产物，不得混入 L3 主题层）。
- 校验：移动后源路径不存在、目标存在、size 7167B 一致；sha256 `16C3A963…48E1B` 留档于整改证据包 `step1_fix5_movebak.txt`。
- 本项目本次未做其他治理动作（daily-why 不在本轮 9 单整改范围内）。
- 操作人：memory 治理整改会话 ｜ 时间：2026-09-15 20:15 前后（时点值）

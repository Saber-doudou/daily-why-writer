> 本文件由 restructure_memory.py 于 2026-09-07 从 MEMORY.md「## 9. 归档/删除索引」区**原文整段搬家**而来，正文逐字未改动（搬家前全量快照：archive/MEMORY-full-precompress-restructure-2026-09-07.md）。修改历史内容请直接编辑本文件，MEMORY.md 只保留一行索引。

- `orchestrator.py`：09-01 删（多Agent残留，架构已内化进 SKILL），副本 `archive/orchestrator.py`，勿重建同名
- `orchestrator-state.json`：09-03 已归档删除（`archive/orchestrator-state-2026-09-03-归档.json`）；`config/messages` 空目录同日清理（message_handler.py 会自动 mkdir）
- `备份/` 下 writing_rules 旧版为有意历史快照，勿删
- 2026-10-27：9-27 及之前的 116 个每日日志移入 `memory/archive/daily-logs/`（30天蒸馏，可逆移动未删除）；9-28 起仍在 memory/ 根目录

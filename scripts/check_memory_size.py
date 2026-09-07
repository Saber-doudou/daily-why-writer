#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_memory_size.py —— 记忆文件体积机械门禁

背景（EXP-004「约束优于指令」）：
    09-02 把 MEMORY.md 从 8684 压到 2932 字符（合规），
    09-07 又涨到 9108，压缩后仍有 6568 —— 超限 2.19 倍。
    历次教训：只靠 AI「下次写短点」的自觉，零效果。必须有脚本卡。

作用：
    校验各层记忆文件的字符数是否超限，超限即 exit 1，
    并打印体积最大的章节 TOP3，指明该切哪一块。

用法：
    python check_memory_size.py                 # 检查全部默认目标
    python check_memory_size.py --json          # 机器可读输出
    python check_memory_size.py --path X.md --limit 3000   # 临时校验任意文件
    python check_memory_size.py --warn-only     # 只告警不返回非零（接入主流程用）

退出码：
    0 = 全部合规（或 --warn-only）
    1 = 存在超限文件
    2 = 参数/文件错误

v1.0 2026-09-07
"""
import argparse
import io
import json
import os
import sys

# 默认检查目标：(名称, 路径, 硬限制, 预警阈值, 计量单位)
# 限制值来源：WorkBuddy 对 MEMORY.md 的注入上限（字符）；自动化记忆为行数纪律（09-07 新增）
DEFAULT_TARGETS = [
    ("工作空间长期记忆", "F:/WorkBuddy/daily-why/.workbuddy/memory/MEMORY.md", 3000, 2400, "chars"),
    ("用户级长期记忆", "C:/Users/admin/.workbuddy/MEMORY.md", 4000, 3200, "chars"),
    ("自动化执行记忆", "F:/WorkBuddy/daily-why/.workbuddy/automations/automation-1778312519754/memory.md", 1000, 850, "lines"),
]


def section_stats(text):
    """按 ## 标题切分，返回 [(章节标题, 字符数)]，降序。"""
    acc = {}
    cur = "(文件头/无章节)"
    for line in text.split("\n"):
        if line.startswith("## "):
            cur = line.strip()
        acc[cur] = acc.get(cur, 0) + len(line) + 1
    return sorted(acc.items(), key=lambda x: -x[1])


def check_one(name, path, limit, warn_at, metric="chars"):
    if not os.path.exists(path):
        return {"name": name, "path": path, "error": "文件不存在", "ok": True}
    text = io.open(path, encoding="utf-8").read()
    if metric == "lines":
        n = text.count("\n") + 1
        unit = "行"
    else:
        n = len(text)
        unit = "字符"
    return {
        "name": name,
        "path": path,
        "metric": metric,
        "chars": n,
        "unit": unit,
        "limit": limit,
        "warn_at": warn_at,
        "over": n > limit,
        "warn": warn_at < n <= limit,
        "ratio": round(n / limit, 2),
        "top_sections": ([] if metric == "lines" else
                         [{"section": s, "chars": c} for s, c in section_stats(text)[:3]]),
        "ok": n <= limit,
    }


def main():
    ap = argparse.ArgumentParser(description="记忆文件体积机械门禁")
    ap.add_argument("--path", help="临时校验单个文件（需配合 --limit）")
    ap.add_argument("--limit", type=int, default=3000, help="临时校验的硬限制，默认 3000")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--warn-only", action="store_true", help="只告警，退出码恒为 0")
    args = ap.parse_args()

    if args.path:
        targets = [("指定文件", args.path, args.limit, int(args.limit * 0.8), "chars")]
    else:
        targets = DEFAULT_TARGETS

    results = [check_one(*t) for t in targets]
    over = [r for r in results if r.get("over")]

    if args.json:
        print(json.dumps({"over_count": len(over), "results": results},
                         ensure_ascii=False, indent=2))
    else:
        print("=" * 64)
        print("记忆文件体积检查")
        print("=" * 64)
        for r in results:
            if r.get("error"):
                print(f"\n[{r['name']}]  {r['error']}：{r['path']}")
                continue
            flag = "❌ 超限" if r["over"] else ("⚠️ 接近" if r["warn"] else "✅ 合规")
            print(f"\n[{r['name']}] {flag}  {r['chars']} / {r['limit']} {r['unit']}（{r['ratio']}x）")
            print(f"  {r['path']}")
            if r["over"] or r["warn"]:
                print("  体积 TOP3 章节（优先切这三块）：")
                for s in r["top_sections"]:
                    print(f"    {s['chars']:6d}  {s['section'][:56]}")
        print("\n" + "=" * 64)
        print(f"结论：{len(over)} 个文件超限" if over else "结论：全部合规")
        print("=" * 64)

    if over and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

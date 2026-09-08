#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_memory_size.py —— 记忆文件体积机械门禁（总量 + 分区 + 单行）

背景（EXP-004「约束优于指令」）：
    09-02 把 MEMORY.md 从 8684 压到 2932 字符（合规），
    09-07 又涨到 9108，压缩后仍有 6568 —— 超限 2.19 倍。
    历次教训：只靠 AI「下次写短点」的自觉，零效果。必须有脚本卡。

作用：
    1. 总量校验：各层记忆文件字符/行数是否超限，超限 exit 1
    2. 分区配额（v1.1 新增，v3 闸门 2）：MEMORY.md 逐章节配额，
       解决「总量合规但某区已膨胀」——09-08 实测总量 0.72x 时架构区已超配额 134
    3. 单行长度闸（v1.1 新增，v3 闸门 3）：单行 >120 字符即告警，
       杜绝 history 那种「把论证压进 250 字符单行」的伪精简

用法：
    python check_memory_size.py                 # 检查全部默认目标
    python check_memory_size.py --json          # 机器可读输出
    python check_memory_size.py --path X.md --limit 3000   # 临时校验任意文件
    python check_memory_size.py --warn-only     # 只告警不返回非零（接入主流程用）
    python check_memory_size.py --strict-sections   # 分区/单行问题也计入退出码

退出码：
    0 = 全部合规（或 --warn-only）
    1 = 存在超限文件（加 --strict-sections 时分区/单行问题也计入）
    2 = 参数/文件错误

v1.2 2026-09-08  分片索引配额改为按条目数动态计算（新增分片不再需要人手改配额）
v1.1 2026-09-08  新增分区配额 + 单行长度闸（v3 闸门 2/3）；总量逻辑与接口不变
v1.0 2026-09-07  初版：总量门禁 + TOP3 章节提示
"""
import argparse
import io
import json
import os
import sys

# 默认检查目标：(名称, 路径, 硬限制, 预警阈值, 计量单位)
# 限制值来源：WorkBuddy 对 MEMORY.md 的注入上限（字符）；自动化记忆为行数纪律（09-07 新增）
# ⚠️ 元组长度不可变更：l3_publish.py 以五元解包方式遍历本表
DEFAULT_TARGETS = [
    ("工作空间长期记忆", "F:/WorkBuddy/daily-why/.workbuddy/memory/MEMORY.md", 3000, 2400, "chars"),
    ("用户级长期记忆", "C:/Users/admin/.workbuddy/MEMORY.md", 4000, 3200, "chars"),
    ("自动化执行记忆", "F:/WorkBuddy/daily-why/.workbuddy/automations/automation-1778312519754/memory.md", 1000, 850, "lines"),
]

# ── v1.1：分区配额（v3 闸门 2）────────────────────────────
# 匹配方式：章节标题中包含 key 即命中（按列表顺序，先命中先算）
SECTION_QUOTAS = [
    ("写入纪律", 160),  # 09-08 由 120 上调：要容纳「写前跑 memory_budget 算账」准入条目
    ("1.", 550),      # 架构与自动化
    ("2.", 200),      # 写作规范（指针）
    ("3.", 660),      # 铁律（常驻 + 触发索引；09-08 由 700 下调：实测仅用 338，让出预算给纪律区）
    ("4.", 150),      # IMA 备份约束
]

# 动态配额章节：quota = 每行预算 × 条目数 + 标题预算
# 目的：分片索引的行数 = 分片数，是刚性增长的。写死配额会导致「每新增一个分片就告警一次」，
# 逼着人去改配额数字来适配内容 —— 那是典型的改规则迁就现状（违反 EXP-004）。
# 改成按条目数自动伸缩，新增分片只增一行，配额跟着走，无需人工干预。
SECTION_DYNAMIC_QUOTAS = {
    "分片索引": (38, 44),  # (每行预算, 标题+余量)
}
MAX_LINE_CHARS = 120  # v3 闸门 3：单行字符上限

# 仅对主记忆做分区审计（用户级格式不同、automation 按行计）
WORKSPACE_MEMORY = DEFAULT_TARGETS[0][1]

# 只报告、不计入退出码的目标（2026-09-08 v1.2 新增）
# 理由：Master 明确划定「用户级记忆不归本项目管理」，但门禁不能假装看不见 ——
# 若计入退出码，门禁前置到 L1 后会每天阻塞在一个「已知且不会被处理」的告警上，
# 结果是告警疲劳 → 真告警也被忽略（违反 EXP-014 可观测性即诚实性）。
# 折中：照常打印（保持可见），但不阻塞流程。哪天 Master 要接手，从本集合删掉即可。
NON_BLOCKING = {"用户级长期记忆"}


def quota_of(title, items=0):
    """返回该章节配额；无配额定义返回 None（不审计）。items 用于动态配额章节。"""
    for key, q in SECTION_QUOTAS:
        if key in title:
            return q
    for key, (per_item, base) in SECTION_DYNAMIC_QUOTAS.items():
        if key in title:
            return per_item * items + base
    return None


def section_stats(text):
    """按 ## 标题切分，返回 [(章节标题, 字符数)]，降序。"""
    acc = {}
    cur = "(文件头/无章节)"
    for line in text.split("\n"):
        if line.startswith("## "):
            cur = line.strip()
        acc[cur] = acc.get(cur, 0) + len(line) + 1
    return sorted(acc.items(), key=lambda x: -x[1])


def section_audit(text):
    """分区配额 + 单行长度审计。

    返回 (配额问题 list, 超长行 list)。配额问题按超出量降序，便于优先处理。
    """
    quota_issues, long_lines = [], []
    buckets = []  # [(标题, 字符数, 条目数)]
    cur, cur_chars, cur_items = "(文件头/无章节)", 0, 0

    # 注意：分区字符数**不含本区标题行**（标题在 switch 时结算上一区，自身不计入任何区）。
    # 因此配额只约束内容行；压缩标题不会改变分区余量（只降总量）。要腾分区余量必须删/精简内容行。
    for i, line in enumerate(text.split("\n"), 1):
        if len(line) > MAX_LINE_CHARS:
            long_lines.append({"line": i, "chars": len(line),
                               "preview": line[:40] + "…"})
        if line.startswith("## "):
            buckets.append((cur, cur_chars, cur_items))
            cur, cur_chars, cur_items = line.strip(), 0, 0
        else:
            cur_chars += len(line) + 1
            s = line.strip()
            if s.startswith("- ") or s.startswith("* "):
                cur_items += 1
    buckets.append((cur, cur_chars, cur_items))

    for title, n, items in buckets:
        q = quota_of(title, items)
        if q and n > q:
            quota_issues.append({"section": title[:56], "chars": n,
                                 "quota": q, "over": n - q, "items": items})
    quota_issues.sort(key=lambda x: -x["over"])
    return quota_issues, long_lines


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

    r = {
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

    # v1.1：分区 + 单行审计（仅主记忆，且保持向后兼容——新增字段不影响旧调用方）
    if metric == "chars" and os.path.abspath(path) == os.path.abspath(WORKSPACE_MEMORY):
        qi, ll = section_audit(text)
        r["section_issues"] = qi
        r["long_lines"] = ll
    else:
        r["section_issues"], r["long_lines"] = [], []
    return r


def main():
    ap = argparse.ArgumentParser(description="记忆文件体积机械门禁（总量+分区+单行）")
    ap.add_argument("--path", help="临时校验单个文件（需配合 --limit）")
    ap.add_argument("--limit", type=int, default=3000, help="临时校验的硬限制，默认 3000")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--warn-only", action="store_true", help="只告警，退出码恒为 0")
    ap.add_argument("--strict-sections", action="store_true",
                    help="分区超配额/超长行也计入退出码（默认只告警）")
    args = ap.parse_args()

    if args.path:
        targets = [("指定文件", args.path, args.limit, int(args.limit * 0.8), "chars")]
    else:
        targets = DEFAULT_TARGETS

    results = [check_one(*t) for t in targets]
    over = [r for r in results if r.get("over") and r["name"] not in NON_BLOCKING]
    noted = [r for r in results if r.get("over") and r["name"] in NON_BLOCKING]

    if args.json:
        print(json.dumps({"over_count": len(over), "results": results},
                         ensure_ascii=False, indent=2))
    else:
        print("=" * 64)
        print("记忆文件体积检查（总量 + 分区配额 + 单行长度）")
        print("=" * 64)
        for r in results:
            if r.get("error"):
                print(f"\n[{r['name']}]  {r['error']}：{r['path']}")
                continue
            if r["over"] and r["name"] in NON_BLOCKING:
                flag = "⏸ 超限（仅提示，不计入退出码）"
            else:
                flag = "❌ 超限" if r["over"] else ("⚠️ 接近" if r["warn"] else "✅ 合规")
            print(f"\n[{r['name']}] {flag}  {r['chars']} / {r['limit']} {r['unit']}（{r['ratio']}x）")
            print(f"  {r['path']}")
            if r["over"] or r["warn"]:
                print("  体积 TOP3 章节（优先切这三块）：")
                for s in r["top_sections"]:
                    print(f"    {s['chars']:6d}  {s['section'][:56]}")

            # v1.1 分区配额
            if r.get("section_issues"):
                print(f"  ⚠️ 分区超配额 {len(r['section_issues'])} 项（总量合规也可能单区膨胀）：")
                for s in r["section_issues"]:
                    print(f"    {s['chars']:5d} / {s['quota']:<4d} 超 {s['over']:+d}  {s['section']}")
            elif r.get("metric") == "chars" and os.path.abspath(r["path"]) == os.path.abspath(WORKSPACE_MEMORY):
                print("  ✅ 分区配额：全部合规")

            # v1.1 单行长度闸
            if r.get("long_lines"):
                print(f"  ⚠️ 超长行 {len(r['long_lines'])} 处（>{MAX_LINE_CHARS} 字符，须拆行或下沉）：")
                for l in r["long_lines"]:
                    print(f"    L{l['line']:<4d} {l['chars']} 字符  {l['preview']}")

        n_sec = sum(len(r.get("section_issues", [])) for r in results)
        n_line = sum(len(r.get("long_lines", [])) for r in results)
        print("\n" + "=" * 64)
        if over:
            print(f"结论：{len(over)} 个文件超限"
                  + (f"；另有分区超配额 {n_sec} 项、超长行 {n_line} 处" if (n_sec or n_line) else ""))
        else:
            print(f"结论：总量全部合规"
                  + (f"，但分区超配额 {n_sec} 项、超长行 {n_line} 处" if (n_sec or n_line) else "，分区与单行均合规"))
        if noted:
            print(f"⏸ 仅提示（不计退出码）：{[r['name'] for r in noted]}")
        print("=" * 64)

    if over and not args.warn_only:
        return 1
    if args.strict_sections and not args.warn_only:
        n_sec = sum(len(r.get("section_issues", [])) for r in results)
        n_line = sum(len(r.get("long_lines", [])) for r in results)
        if n_sec or n_line:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

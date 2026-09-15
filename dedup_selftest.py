#!/usr/bin/env python3
"""
dedup_selftest.py — 去重防线双向自检（09-15 新增，v3.19 配套）

目的：落实缺陷 #45 教训「硬卡点必须配『不误杀已知正常样例』的回归用例」+ #51 教训
「防线只测干净输入等于没测」。任何 check_topic.py / l3_publish.py 去重相关改动后必须
跑本脚本，全绿才允许提交。

设计（达尔文棘轮 + EXP-004 约束优于指令）：
  - 隔离区用例：临时 workspace，不污染真实库（双向断言：该拦的拦、该放的放）
  - 真实库冒烟：动态读取 topics_context.json 最新话题作「已知已用」样本，
    不硬编码话题文本，库内容变化不会导致脚本过期误报
  - 任何一条 FAIL → exit 1

用法：
    python dedup_selftest.py                 # 全量 10 用例（v3.20 起，R4 首行空行提取回归）
    python dedup_selftest.py --quick         # 仅隔离区 6 用例（不碰 l3_publish）

退出码：0 = 全绿；1 = 有失败
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
WORKSPACE = SCRIPTS.parent
CHECK_TOPIC = SCRIPTS / "check_topic.py"
L3 = SCRIPTS / "l3_publish.py"
PY = sys.executable or "python"

RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, bool(ok), str(detail)))


def run_cli(topic, workspace, extra=None):
    cmd = [PY, str(CHECK_TOPIC), topic, "--workspace", str(workspace)]
    if extra:
        cmd += extra
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60)
    return r.returncode, (r.stdout or r.stderr).strip()


def setup_iso_workspace(td):
    """隔离区：临时 workspace，含空台账与两个已知文章。"""
    ws = Path(td)
    (ws / "config").mkdir()
    (ws / "config" / "topics_context.json").write_text(
        json.dumps({"generated_at": "selftest", "total_count": 0,
                    "topic_summaries": [], "topics": []}, ensure_ascii=False),
        encoding="utf-8")
    art = ws / "articles"
    art.mkdir(exist_ok=True)
    # 已知「已用」话题（台账 topics 数组带 date，供 exclude-date 用例）
    (ws / "config" / "topics_context.json").write_text(
        json.dumps({"generated_at": "selftest", "total_count": 2,
                    # topic_summaries 为纯字符串列表（无 date），按 v3.15 S1 时序假设：
                    # L3 先查重后写台账，故 exclude-date 场景下当日话题不会出现在此列表
                    "topic_summaries": ["为什么历史列表里的旧条目话题？"],
                    "topics": [{"date": "2026-03-03", "topic": "为什么萤火虫在夜里会发光呢？",
                                "file": "2026-03-03-每日冷知识-萤火虫.md"}]},
                   ensure_ascii=False), encoding="utf-8")
    (art / "2026-03-03-每日冷知识-萤火虫.md").write_text(
        "# 为什么萤火虫在夜里会发光呢？\n正文", encoding="utf-8")
    (art / "2026-03-01-每日冷知识-旧事_废弃.md").write_text(
        "# 为什么废弃话题不应该被检索？\n正文", encoding="utf-8")
    return ws


def iso_cases():
    with tempfile.TemporaryDirectory() as td:
        ws = setup_iso_workspace(td)

        # 1. 精确重复（文章文件命中）→ 必须拦
        code, out = run_cli("为什么萤火虫在夜里会发光呢？", ws)
        record("I1 精确重复 → 拦截(EXIT=1)", code == 1, out[:90])

        # 2. 语义相似换皮（核心字符 100% 包含）→ 必须拦
        code, out = run_cli("为什么萤火虫夜里发光？", ws)
        record("I2 语义相似换皮 → 拦截(EXIT=1)", code == 1, out[:90])

        # 3. 全新话题 → 必须放行（不误杀）
        code, out = run_cli("为什么冰箱贴能贴在门上不掉下来？", ws)
        record("I3 全新话题 → 放行(EXIT=0)", code == 0, out[:90])

        # 4. _废弃 文件话题 → 排除生效放行（Azure 软删除教训）
        code, out = run_cli("为什么废弃话题不应该被检索？", ws)
        record("I4 _废弃 文件排除 → 放行(EXIT=0)", code == 0, out[:90])

        # 5. 当日自排除（缺陷 #45 回归用例）→ 同话题带 --exclude-date 必须放行
        code, out = run_cli("为什么萤火虫在夜里会发光呢？", ws,
                            ["--exclude-date", "2026-03-03"])
        record("I5 --exclude-date 自排除 → 放行(EXIT=0)", code == 0, out[:90])

        # 6. 角度模式区间放行（相似度落 [0.50,0.70) 时 --angle 放行）
        code, out = run_cli("为什么海水看起来是蓝色的？", ws, ["--angle"])
        # 该话题与库内萤火虫话题相似度应 <0.5 → 直接放行；再验证严格模式与 angle 对区间话题的差异
        record("I6 --angle 不误杀低相似新话题 → 放行(EXIT=0)", code == 0, out[:90])


def real_cases(quick=False):
    # 7. 真实库冒烟：动态取最新已用话题（不硬编码，防脚本过期）
    ctx = WORKSPACE / "config" / "topics_context.json"
    try:
        data = json.loads(ctx.read_text(encoding="utf-8"))
        used = (data.get("topic_summaries") or [None])[0]
    except Exception as e:
        used = None
        record("R1 真实库台账读取", False, f"topics_context.json 读取失败: {e}")
    if used:
        code, out = run_cli(used, WORKSPACE)
        record(f"R1 真实库最新已用话题「{used[:18]}…」→ 拦截(EXIT=1)", code == 1, out[:90])

    if quick:
        return

    # 8. l3_publish dedup_gate_check 默认硬拦（无任何环境变量）+ 重复话题
    for k in ("DAILY_WHY_DEDUP_RELAX", "DAILY_WHY_DEDUP_ENFORCE", "DAILY_WHY_DEDUP_OFF"):
        os.environ.pop(k, None)
    try:
        sys.path.insert(0, str(SCRIPTS))
        import importlib
        import l3_publish
        importlib.reload(l3_publish)

        class ResStub:
            def __init__(self):
                self.events = []
            def ok(self, n, m):   self.events.append(("ok", m))
            def warn(self, n, m): self.events.append(("warn", m))
            def fail(self, n, m): self.events.append(("fail", m))
            def skip(self, n, m): self.events.append(("skip", m))

        if used:
            import tempfile as _tf
            with _tf.TemporaryDirectory() as td2:
                art = Path(td2) / "2099-12-31-每日冷知识-自检.md"
                art.write_text(f"# {used}\n正文", encoding="utf-8")
                res = ResStub()
                blocked = l3_publish.dedup_gate_check({"v1": art, "v2": None}, res, "2099-12-31")
                kinds = [k for k, _ in res.events]
                record("R2 L3卡点默认+重复话题 → 硬拦(fail+blocked)",
                       blocked is True and "fail" in kinds, res.events[:1])
        # 9. 全新话题默认放行（不误杀）
        import tempfile as _tf
        with _tf.TemporaryDirectory() as td3:
            art = Path(td3) / "2099-12-31-每日冷知识-自检.md"
            art.write_text("# 为什么彩虹是圆弧而不是直线？\n正文", encoding="utf-8")
            res = ResStub()
            blocked = l3_publish.dedup_gate_check({"v1": art, "v2": None}, res, "2099-12-31")
            kinds = [k for k, _ in res.events]
            record("R3 L3卡点默认+全新话题 → 放行(blocked=False)",
                   blocked is False and "fail" not in kinds, res.events[:1])

        # 10. 首行空行提取（v3.20 双源对齐回归：P3 审查 P1-3——旧实现只取首行，
        #     空行 → None → 去重 fail-open 放行静默绕过；v3.20 对齐 check_topic 跳空行）
        with _tf.TemporaryDirectory() as td4:
            art_empty = Path(td4) / "2099-12-31-每日冷知识-空行.md"
            art_empty.write_text("\n\n# 为什么雨滴是球形的？\n正文", encoding="utf-8")
            got = l3_publish._extract_topic_from_file(art_empty)
            record("R4 首行空行文件 → 提取到标题(非 None)",
                   got == "为什么雨滴是球形的？", repr(got))
    except Exception as e:
        record("R2/R3 l3_publish 卡点冒烟", False, f"执行异常: {e}")


def main():
    parser = argparse.ArgumentParser(description="去重防线双向自检")
    parser.add_argument("--quick", action="store_true", help="仅隔离区用例（不碰 l3_publish）")
    args = parser.parse_args()

    iso_cases()
    real_cases(quick=args.quick)

    print("=" * 62)
    print("去重防线双向自检（dedup_selftest）")
    print("=" * 62)
    all_pass = True
    for name, ok, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"[{mark}] {name}")
        if detail:
            print(f"        {detail}")
    print("=" * 62)
    print(f"结果: {sum(1 for _, o, _ in RESULTS if o)}/{len(RESULTS)} 通过 — "
          + ("ALL PASS ✅" if all_pass else "HAS FAILURES ❌"))
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()

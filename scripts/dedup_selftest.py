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

2026-10-13 T5 扩展（依据 deliverables/2026-10-13-check_topic整改任务书.md）：
  - I7 至 I12：T1 概念重叠检测（该拦的拦：牛排换术语/海水同义改写；该放的放：
    牛排熟成/真空绽色/解冻血水/肉色熟度）+ T2 角度模式全候选报告（双候选齐全断言）
  - R5：真实库冒烟——10-13 牛排废弃标题（--angle --exclude-date 当日）→ 概念硬重复拦截
  - L1/L2 锁行为：「不」必须保留在 core 字符中（防 STOP_WORDS 被「统一」进内联停用
    字表后灵敏度无声削弱：牛排 A1 50.0%→42.9%、A2 62.5%→57.1%）；ASCII 引号必须
    被剥离（防 0x22/0x27 残留虚增公共字符回退）
  - 隔离区 setup 同步放入 config/topic_concepts.json 副本（T1 概念检测依赖）

2026-10-13 F1 补充（依据 deliverables/2026-10-13-check_topic整改补充任务清单.md，
Master 选方案 B）：
  - I13/I14：单字 specific 误杀回归——「汗水为什么是咸的」「盐能让雪融化」与
    「海水是咸的」共享属性词而非主体词，F1 前遭硬拦；F1 后（同 concept 须双方
    generic 均命中才拦）必须放行。真阳性不回归：I7/I8 与 A1/A3 仍须拦。

用法：
    python dedup_selftest.py                 # 全量 21 项（I1 至 I14、R1 至 R5、L1 至 L2）
    python dedup_selftest.py --quick         # 仅隔离区用例（不碰 l3_publish）

退出码：0 = 全绿；1 = 有失败
"""

import argparse
import json
import os
import shutil
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
    """隔离区：临时 workspace，含台账与已知文章。

    2026-10-13 T5 扩展：
      - 同步放入 config/topic_concepts.json 副本（T1 概念检测依赖；源缺失时写空表，
        由 load_concepts 走降级警告路径，I7/I8 会因此 FAIL——视为正确告警）
      - 补入 4 个受控话题：09-07 牛排血水 / 04-03 海水是咸的（T1 概念命中锚点），
        青蛙夏天 / 刺猬冬眠（T2 全候选报告的双候选锚点，与冬眠查询各 60% 落角度区间）
    """
    ws = Path(td)
    (ws / "config").mkdir()
    (ws / "config" / "topics_context.json").write_text(
        json.dumps({"generated_at": "selftest", "total_count": 5,
                    # topic_summaries 为纯字符串列表（无 date），按 v3.15 S1 时序假设：
                    # L3 先查重后写台账，故 exclude-date 场景下当日话题不会出现在此列表
                    "topic_summaries": ["为什么历史列表里的旧条目话题？"],
                    "topics": [
                        {"date": "2026-03-03", "topic": "为什么萤火虫在夜里会发光呢？",
                         "file": "2026-03-03-每日冷知识-萤火虫.md"},
                        {"date": "2026-09-07", "topic": "为什么牛排里的血水其实不是血？",
                         "file": "2026-09-07-每日冷知识-牛排血水.md"},
                        {"date": "2026-04-03", "topic": "为什么海水是咸的？",
                         "file": "2026-04-03-每日冷知识-海水是咸的.md"},
                        {"date": "2026-05-01", "topic": "为什么青蛙夏天叫得欢？",
                         "file": "2026-05-01-每日冷知识-青蛙夏天.md"},
                        {"date": "2026-05-02", "topic": "为什么刺猬冬天也要冬眠？",
                         "file": "2026-05-02-每日冷知识-刺猬冬眠.md"},
                    ]},
                   ensure_ascii=False), encoding="utf-8")
    art = ws / "articles"
    art.mkdir(exist_ok=True)
    # 已知「已用」话题（台账 topics 数组带 date，供 exclude-date 用例）
    (art / "2026-03-03-每日冷知识-萤火虫.md").write_text(
        "# 为什么萤火虫在夜里会发光呢？\n正文", encoding="utf-8")
    (art / "2026-03-01-每日冷知识-旧事_废弃.md").write_text(
        "# 为什么废弃话题不应该被检索？\n正文", encoding="utf-8")
    # T1 概念表副本（与真实库同源，防隔离区与生产行为漂移）
    src = WORKSPACE / "config" / "topic_concepts.json"
    dst = ws / "config" / "topic_concepts.json"
    if src.exists():
        shutil.copyfile(src, dst)
    else:
        dst.write_text(json.dumps({"concepts": {}}, ensure_ascii=False), encoding="utf-8")
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
        # 该话题与库内海水话题 67% 落角度区间：--angle 放行（含⚠️提示），严格模式才拦
        record("I6 --angle 不误杀低相似新话题 → 放行(EXIT=0)", code == 0, out[:90])

        # ── 以下为 2026-10-13 T5 新增（T1 概念重叠 + T2 全候选报告）──

        # 7. 牛排换术语（验收 A1）→ 概念[牛排血水] specific 双侧命中 → 硬重复，
        #    --angle 不可覆盖（10-13 事件主修复点）
        code, out = run_cli("生牛排渗出的红色汁液不是血是肌红蛋白", ws, ["--angle"])
        record("I7 牛排换术语 → 概念拦截(EXIT=1，--angle 不可覆盖)", code == 1, out[:90])

        # 8. 海水同义改写（验收 A3，hy3 自设用例按其规则判不出）→ 概念硬重复
        code, out = run_cli("为什么大海里的盐是从哪儿来的？", ws, ["--angle"])
        record("I8 海水同义改写 → 概念拦截(EXIT=1)", code == 1, out[:90])

        # 9. 牛排熟成（验收 A4）→ specific 零命中 → 放行（防误杀回归）
        code, out = run_cli("为什么牛排要熟成？", ws, ["--angle"])
        record("I9 牛排熟成 → 放行(EXIT=0)", code == 0, out[:90])

        # 10. 真空包装绽色（验收 A5）→ 机制词不入表 → 放行（防误杀回归）
        code, out = run_cli("为什么真空包装牛排拆开是暗紫色，遇空气才变鲜红", ws, ["--angle"])
        record("I10 真空包装绽色 → 放行(EXIT=0)", code == 0, out[:90])

        # 11. 解冻血水（A6）+ 肉色熟度（A7）→ specific 零命中 → 放行（防误杀回归）
        code6, out6 = run_cli("为什么原切牛排解冻别用水冲", ws, ["--angle"])
        code7, out7 = run_cli("为什么看肉色判断不了牛排熟不熟", ws, ["--angle"])
        record("I11 解冻血水+肉色熟度 → 放行(EXIT=0)",
               code6 == 0 and code7 == 0, f"A6={code6} A7={code7}")

        # 12. 角度模式全候选报告（T2）：查询与青蛙/刺猬两话题各落角度区间，
        #     stdout 必须同时出现两个候选话题（修复前只报 top-1）
        code, out = run_cli("为什么青蛙冬天要冬眠？", ws, ["--angle"])
        record("I12 角度模式全候选报告 → 放行且双候选齐全(EXIT=0)",
               code == 0 and "青蛙夏天" in out and "刺猬冬天" in out, out[:90])

        # ── 以下为 2026-10-13 F1 新增（单字 specific 误杀回归，Master 选方案 B）──

        # 13. 汗水咸（F1 误杀面实证）：specific「咸」双侧命中，但新话题不含 generic
        #     主词（海水/大海/海洋）→ 不构成同主体 → 必须放行（F1 前 EXIT=1 误拦）
        code, out = run_cli("为什么汗水是咸的？", ws, ["--angle"])
        record("I13 汗水咸（单字 specific 误杀回归）→ 放行(EXIT=0)", code == 0, out[:90])

        # 14. 融雪盐（同款误杀）：specific「盐」命中但无 generic 主词 → 放行
        code, out = run_cli("为什么盐能让雪融化？", ws, ["--angle"])
        record("I14 融雪盐（单字 specific 误杀回归）→ 放行(EXIT=0)", code == 0, out[:90])


def lock_behavior_cases():
    """T5 锁行为测试（防灵敏度无声削弱，hy3 手算错误的同源教训）。

    L1：「不」必须保留在 core 字符中。若 STOP_WORDS 的「不」被并入内联停用字表，
        A1 从 50.0% 跌到 42.9%、A2 从 62.5% 跌到 57.1%，字符级检测灵敏度被无声削弱。
    L2：ASCII 引号必须被剥离。若 0x22/0x27 回落进 core，含引号标题各虚增公共字符
        （10-13 牛排 66.7% 实为 62.5% 的成因）。
    """
    try:
        sys.path.insert(0, str(SCRIPTS))
        import check_topic
        core = check_topic.extract_core_chars("为什么牛排里的血水其实不是血？")
        record("L1 锁行为：「不」保留在 core 中", "不" in core, repr(core))
        core_q = check_topic.extract_core_chars("为什么\"血水\"是'液体'？")
        record("L2 锁行为：ASCII 引号被剥离",
               '"' not in core_q and "'" not in core_q, repr(core_q))
    except Exception as e:
        record("L1/L2 锁行为测试", False, f"执行异常: {e}")


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

        # 11. R5（2026-10-13 T5 新增）：真实库冒烟——10-13 牛排废弃标题
        #     （--angle --exclude-date 2026-10-13）→ 概念[牛排血水]硬重复拦截。
        #     该场景修复前 --angle 会放行（66.7% 角度区间），是 L1 缺口的活体回归。
        code, out = run_cli("为什么切牛排时流出的\"血水\"根本不是血？", WORKSPACE,
                            ["--angle", "--exclude-date", "2026-10-13"])
        record("R5 真实库牛排废弃标题(--angle+排除当日) → 拦截(EXIT=1)",
               code == 1, out[:90])
    except Exception as e:
        record("R2/R3 l3_publish 卡点冒烟", False, f"执行异常: {e}")


def main():
    parser = argparse.ArgumentParser(description="去重防线双向自检")
    parser.add_argument("--quick", action="store_true", help="仅隔离区用例（不碰 l3_publish）")
    args = parser.parse_args()
    iso_cases()
    lock_behavior_cases()
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

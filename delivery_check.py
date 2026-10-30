#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""R3.9 交付链路四方一致自检（R4 准入）。

查什么：**四方一致**，缺一即 exit 1 并指名。

    ① 本轮改动的交付物（工作区未提交 + 未跟踪 + 最近 N 次提交，过滤到交付范围）
    ② config.json 的 git_add_files（git add 白名单）
    ③ l3_publish.py 的同步清单 extra_sync / files_to_copy（复制源 -> repo 相对路径）
    ④ 镜像仓库 HEAD 树里该文件是否真的存在

为什么需要它（缺陷 #67 的根因）：
现有三道检查全在「清单内部」打转——① 白名单每项有没有复制源、② 已跟踪文件在不在
白名单、③ full_selfcheck 只扫本地不读镜像。**没有一道问「当期交付物有没有进清单」**，
也没有一道问「清单里的东西到底有没有落到镜像里」。于是 R2/R3 的一整批产物
（evidence_gate.py / safe_pool.py / validate_contract.py / contracts 四份 schema /
safe_topics.json / historical_claims.tsv）全都不在镜像里，而双向自检与发布报告一路报绿。

设计取舍：
- ③ 用 **AST 从 l3_publish.py 原样提取**，不是 import，也不是复制一份清单。
  import 会触发发布路径的副作用；复制一份则立刻开始漂移，正是本脚本要治的病。
  读脚本真身，清单改了这里自动跟着变（与 #58 回归验证同一手法）。
- ④ 只查本地镜像，远端校验要显式 `--remote`。网络不通时不能让它把轮次判红——
  那会变成新的假失败，正是 10-28 D1 的教训（单次探活失败被当成「不可重试」）。
- ① 的「交付范围」是白名单式过滤：内容产物（文章/评审/证据/报告/素材/日志）
  每日新增，进清单会制造死条目，不在此列。

用法：
    python scripts/delivery_check.py                 # 四方一致（默认查最近 1 次提交）
    python scripts/delivery_check.py --commits 3     # 扩大本轮范围
    python scripts/delivery_check.py --remote        # 额外比对远端 main
    python scripts/delivery_check.py --json          # 机器可读输出
"""

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

# ── 交付范围过滤 ──
# 只认「工程交付物」：脚本、配置、契约、规则库、文档。
DELIVERABLE_SCOPES = ("scripts/", "config/", "contracts/", "docs/")
DELIVERABLE_SUFFIX = (".py", ".json", ".md", ".tsv", ".txt")
# 内容产物与运行痕迹：每日新增，不是可复用资产，进清单=死条目（死文件判据）
DELIVERABLE_EXCLUDE = (
    "投喂素材/", "articles/", "review/", "evidence/", "deliverables/",
    ".workbuddy/", "eval/sim-artifacts/", "logs/", "archive/", "备份/",
    "daily-why-backup-", "messages/",
)
# 每日刷新/自动派生的数据文件：每天都会被 prepare_topics 等脚本重写，
# 属于运行时状态而非可复用资产（与 topic_candidates.json 素材池性质不同）。
# 它们本就不在任何同步清单里，纳入判定只会制造每天必红的噪音（EXP-014）。
AUTO_DERIVED = (
    "config/topics_context.json",
    "config/topics_context_compact.json",
)


# ────────────────────────── 清单提取 ──────────────────────────

def load_cfg():
    return json.loads((SCRIPTS / "config.json").read_text(encoding="utf-8"))


class PathExprError(ValueError):
    pass


def _eval_path(node, env, cfgmap):
    """求值路径表达式。支持 l3_publish 里实际用到的四种写法：

        "a/b"                     常量
        Name                      已绑定别名
        Path(CFG["scripts_dir"])  配置下标
        <以上任意> / "x" / "y"    拼接

    出现别的节点就报错——宁可让自检红，也不要静默算出一个错路径。
    """
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, str):
            raise PathExprError(f"非常量字符串: {ast.dump(node)[:60]}")
        return Path(node.value)
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise PathExprError(f"未绑定的路径变量: {node.id}")
        return Path(env[node.id])
    if isinstance(node, ast.Subscript):
        # CFG["scripts_dir"]
        if not (isinstance(node.value, ast.Name) and node.value.id == "CFG"):
            raise PathExprError(f"不支持的下标对象: {ast.dump(node)[:60]}")
        key = node.slice.value if isinstance(node.slice, ast.Constant) else None
        if key is None or key not in cfgmap:
            raise PathExprError(f"CFG 中无此键: {key!r}")
        return Path(cfgmap[key])
    if isinstance(node, ast.Call):
        # Path(<上面任意一种>)
        if not (isinstance(node.func, ast.Name) and node.func.id == "Path"):
            raise PathExprError(f"不支持的调用: {ast.dump(node)[:60]}")
        if len(node.args) != 1:
            raise PathExprError("Path() 参数个数不符")
        return _eval_path(node.args[0], env, cfgmap)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _eval_path(node.left, env, cfgmap) / _eval_path(node.right, env, cfgmap)
    raise PathExprError(f"无法解析的路径表达式: {ast.dump(node)[:80]}")


def _collect_aliases(fn, env, cfgmap):
    """收集函数内 `X = <路径表达式>` 的别名，供后续求值使用。"""
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        tgt = node.targets[0]
        if not isinstance(tgt, ast.Name):
            continue
        try:
            env[tgt.id] = str(_eval_path(node.value, env, cfgmap))
        except PathExprError:
            pass


def extract_sync_map(l3_path, cfg):
    """从 l3_publish.py 的 phase3_git 提取同步清单，返回 (src, rel) 列表。

    用列表而不是 {src: rel} 字典：**同一个源文件会被复制到镜像的两个位置**
    （如 generate_prompt.py 同时落在 `generate_prompt.py` 与 `scripts/generate_prompt.py`），
    用字典会让后一条静默覆盖前一条，凭空造出「无复制源」的假缺口。

    覆盖两处：① 函数体里的 files_to_copy.append((src, dst))
             ② extra_sync 字面量列表（大头，40 余项）
    """
    tree = ast.parse(Path(l3_path).read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "phase3_git"), None)
    if fn is None:
        raise SystemExit("[delivery_check] 在 l3_publish.py 里找不到 phase3_git，清单提取中止")

    cfgmap = {k: str(v) for k, v in cfg.items() if isinstance(v, str)}
    env = {
        "scripts_dir": cfg["scripts_dir"],
        "project_dir": cfg.get("base_dir", str(ROOT)),
        "src_base": str(Path(cfg["references_dir"]).parent),
        "repo": cfg["git_repo_path"],
    }
    _collect_aliases(fn, env, cfgmap)

    pairs = []          # [(src_abs, repo_rel)]

    # ① 直接 append 的小组（SKILL.md / reviewer_prompt.md / references 等）
    refs = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "refs" \
                and isinstance(node.value, ast.List):
            refs = [e.value for e in node.value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]

    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "append"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Tuple):
            continue
        t = node.args[0]
        if len(t.elts) != 2:
            continue
        try:
            src = _eval_path(t.elts[0], env, cfgmap)
            dst = _eval_path(t.elts[1], env, cfgmap)
        except PathExprError:
            continue  # `repo / ref` 这类循环变量，走下面 refs 展开
        rel = _rel(dst, cfg["git_repo_path"])
        if rel:
            pairs.append((_norm(src), rel))

    # refs 循环：src_base/references/X.md -> references/X.md
    src_base = Path(env["src_base"])
    for r in refs:
        pairs.append((_norm(src_base / r), r.replace("\\", "/")))

    # ② extra_sync 字面量列表
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "extra_sync" \
                and isinstance(node.value, ast.List):
            for elt in node.value.elts:
                if not (isinstance(elt, ast.Tuple) and len(elt.elts) == 2):
                    continue
                src = _eval_path(elt.elts[0], env, cfgmap)
                rel = elt.elts[1].value
                pairs.append((_norm(src), rel.replace("\\", "/")))
    return pairs


def _norm(p):
    return str(Path(p)).replace("\\", "/")


def _rel(dst, repo):
    """把镜像内的绝对路径还原成 repo 相对路径。"""
    try:
        return str(Path(dst).relative_to(Path(repo))).replace("\\", "/")
    except ValueError:
        return None


# ────────────────────────── 四方数据 ──────────────────────────

def _git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=str(cwd or ROOT),
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def changed_files(commits):
    """① 本轮改动：未提交（含未跟踪）+ 最近 N 次提交。"""
    files = set()

    rc, out, _ = _git("diff", "--name-only", "HEAD")
    files |= {l.strip() for l in out.splitlines() if l.strip()}

    rc, out, _ = _git("ls-files", "--others", "--exclude-standard")
    files |= {l.strip() for l in out.splitlines() if l.strip()}

    if commits > 0:
        rc, out, _ = _git("diff", "--name-only", f"HEAD~{commits}", "HEAD")
        if rc == 0:
            files |= {l.strip() for l in out.splitlines() if l.strip()}

    return {f for f in files if in_deliverable_scope(f)}


def in_deliverable_scope(rel):
    r = rel.replace("\\", "/")
    if r in AUTO_DERIVED:
        return False
    if any(r.startswith(x) for x in DELIVERABLE_EXCLUDE):
        return False
    if not r.endswith(DELIVERABLE_SUFFIX):
        return False
    # 顶层文件（如 CHANGELOG.md）也算交付物
    return "/" not in r or any(r.startswith(s) for s in DELIVERABLE_SCOPES)


def mirror_missing(repo, rels):
    """④ 镜像仓库 HEAD 树中缺失的项。"""
    missing = []
    for rel in sorted(rels):
        rc, _, _ = _git("cat-file", "-e", f"HEAD:{rel}", cwd=repo)
        if rc != 0:
            missing.append(rel)
    return missing


# ────────────────────────── 主检查 ──────────────────────────

def run_checks(commits, with_remote):
    cfg = load_cfg()
    repo = Path(cfg["git_repo_path"])
    problems = []

    whitelist = list(cfg.get("git_add_files", []))
    pairs = extract_sync_map(SCRIPTS / "l3_publish.py", cfg)
    rels_of_sync = {rel for _, rel in pairs}
    srcs_of_sync = {src for src, _ in pairs}
    changed = changed_files(commits)

    # ── 缺口 1：本轮改动未纳入同步清单（#67 的同款病，当期产物没人问）──
    uncovered = [f for f in sorted(changed) if _norm(ROOT / f) not in srcs_of_sync]
    if uncovered:
        problems.append((
            "changed_not_in_sync",
            f"本轮改了 {len(uncovered)} 个交付物，但不在 l3_publish 的同步清单里"
            f"（源改动不会复制进镜像，#67 就是这么漏的）",
            uncovered,
        ))

    # ── 缺口 2：同步清单有源，但 git_add_files 里没有（会被 git add 漏掉）──
    not_added = sorted(rels_of_sync - set(whitelist))
    if not_added:
        problems.append((
            "sync_not_in_gitadd",
            f"同步清单有复制源，但 {len(not_added)} 项不在 config.json 的 git_add_files"
            f"（复制进镜像了却不会被 git add）",
            not_added,
        ))

    # ── 缺口 3：git_add_files 有项，但没有复制源（源改动永远到不了镜像）──
    no_source = [f for f in whitelist if f not in rels_of_sync]
    if no_source:
        problems.append((
            "gitadd_no_source",
            f"git_add_files 里 {len(no_source)} 项在 l3_publish 中找不到复制源",
            no_source,
        ))

    # ── 缺口 4：清单里有，镜像 HEAD 树里却没有（从来没人查的一层）──
    # 10-29 修正：区分「在途」与「历史遗漏」，否则每新增一个清单项、到下一次 L3
    # 送达之间都会判红一次，混进高频自检就是告警疲劳（与 10-28 D1 同源）。
    #   - 在途 = 缺项能反查到 src→rel 映射，且该 src 同时出现在本轮 changed 集里
    #     （本轮刚进清单、有复制源，只是还没跑 L3），不判红但必须显式列出；
    #   - 历史遗漏 = 缺项反查不到映射、或映射源不在本轮改动里（清单里写了个
    #     根本送不到的名字，才是 #67 那类真缺陷），判红。
    if not (repo / ".git").exists():
        problems.append(("mirror_missing_repo", f"镜像仓库不存在: {repo}", [str(repo)]))
        miss = []
    else:
        miss = mirror_missing(repo, whitelist)

    changed_abs = {_norm(ROOT / f) for f in changed}
    rel_to_srcs = {}
    for src, rel in pairs:
        rel_to_srcs.setdefault(rel, []).append(src)

    in_transit, truly_missing = [], []
    for m in miss:
        srcs = rel_to_srcs.get(m, [])
        if any(s in changed_abs for s in srcs):
            in_transit.append(m)
        else:
            truly_missing.append(m)

    if truly_missing:
        problems.append((
            "not_in_mirror",
            f"git_add_files 里 {len(truly_missing)} 项在镜像仓库 HEAD 树中不存在，"
            f"且反查不到本轮复制源（清单写了却送不到，#67 类历史遗漏）",
            truly_missing,
        ))

    # ── 可选：远端比对（网络不通不得判红，需显式 --remote）──
    remote_note = "未校验（默认不查远端；加 --remote 才比对）"
    if with_remote:
        rc, out, err = _git("ls-remote", "origin", "HEAD", cwd=repo)
        if rc != 0:
            # 网络失败只是「没验成」，不等于「没推送」——08-28 误判教训
            remote_note = f"远端探活失败，未校验（{err.strip().splitlines()[0][:60] if err.strip() else 'unknown'}）"
        else:
            remote_sha = out.split()[0] if out.split() else ""
            _, local, _ = _git("rev-parse", "HEAD", cwd=repo)
            local_sha = local.strip()
            remote_note = ("远端与本地一致: " + local_sha[:12]) if remote_sha == local_sha \
                else f"本地 {local_sha[:12]} != 远端 {remote_sha[:12]}（待推送）"

    return {
        "whitelist_count": len(whitelist),
        "sync_count": len(pairs),
        "changed_deliverables": sorted(changed),
        "in_transit": in_transit,
        "remote": remote_note,
        "problems": [{"code": c, "message": m, "items": it} for c, m, it in problems],
    }


def selftest():
    """固化「在途 vs 历史遗漏」的反向夹具，防『一修就松』把 #67 检查修没了。

    用 mock 造三类场景，不碰真实 git/镜像：
      1. 本轮新增、有复制源、还没送达 → 在途，不判红但单列
      2. 清单有、复制源不在本轮改动集 → 历史遗漏，判红且 items 精确
      3. 真冲突无关这里（git_push_selftest.py 覆盖）
    """
    from unittest import mock
    fake_pairs = [
        ("F:/WorkBuddy/daily-why/scripts/some_old_asset.py", "some_old_asset.py"),
        ("F:/WorkBuddy/daily-why/scripts/git_push_selftest.py", "git_push_selftest.py"),
    ]
    with mock.patch.object(sys.modules[__name__], "extract_sync_map", lambda *a, **k: fake_pairs), \
         mock.patch.object(sys.modules[__name__], "changed_files",
                           lambda *a, **k: {"scripts/git_push_selftest.py"}), \
         mock.patch.object(sys.modules[__name__], "mirror_missing",
                           lambda repo, wl: ["some_old_asset.py", "git_push_selftest.py"]):
        r = run_checks(1, False)
    codes = [p["code"] for p in r["problems"]]
    nm = next((p for p in r["problems"] if p["code"] == "not_in_mirror"), None)
    ok = ("not_in_mirror" in codes and nm is not None
          and nm["items"] == ["some_old_asset.py"]
          and r["in_transit"] == ["git_push_selftest.py"])
    print(f"[{'PASS' if ok else 'FAIL'}] 在途不判红单列、历史遗漏仍判红且 items 精确")
    if not ok:
        print(f"       codes={codes} in_transit={r['in_transit']} "
              f"nm_items={nm['items'] if nm else None}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="dailywhy 交付链路四方一致自检（R3.9 / R4 准入）")
    ap.add_argument("--commits", type=int, default=1,
                    help="本轮范围：除未提交改动外，再向前看 N 次提交（默认 1）")
    ap.add_argument("--remote", action="store_true",
                    help="额外比对远端 main（默认不查，网络不通不得判红）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--selftest", action="store_true", help="跑内置反向夹具并退出")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    result = run_checks(args.commits, args.remote)
    problems = result["problems"]

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 70)
        print("交付链路四方一致自检（R3.9）")
        print("=" * 70)
        print(f"  ② git_add_files        : {result['whitelist_count']} 项")
        print(f"  ③ l3_publish 同步清单  : {result['sync_count']} 项")
        print(f"  ① 本轮交付物（范围过滤后）: {len(result['changed_deliverables'])} 项")
        for f in result["changed_deliverables"]:
            print(f"       - {f}")
        _has_hist_miss = any(p["code"] == "not_in_mirror" for p in problems)
        if _has_hist_miss:
            _mirror_state = "有历史遗漏（见下）"
        elif result["in_transit"]:
            _mirror_state = f"齐全（{len(result['in_transit'])} 项在途，待下次 L3 送达）"
        else:
            _mirror_state = "齐全"
        print(f"  ④ 镜像仓库             : {_mirror_state}")
        if result["in_transit"]:
            for it in result["in_transit"]:
                print(f"       ⏳ 在途: {it}（本轮新增，已有复制源，下次 L3 自动送达）")
        print(f"  远端                   : {result['remote']}")
        print("-" * 70)
        if not problems:
            print("✅ 四方一致，无缺口（在途项非缺陷，已显式列出）")
        else:
            for p in problems:
                print(f"❌ [{p['code']}] {p['message']}")
                for it in p["items"]:
                    print(f"       - {it}")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

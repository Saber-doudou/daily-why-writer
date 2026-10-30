#!/usr/bin/env python3
"""git_push_selftest.py — R3.8 推送门修复的回归夹具（10-29）

验证 l3_publish.py 的 D1 / D2 两处修复，防「约束只写在注释里、代码没接上」：
- D1：github_reachable 单次抖动不再让整条重试链作废；探活失败仍尝试真实 pull/push
      （探活只用来省时间，不当裁判）。
- D2：dirty 类（工作区有未提交改动）正确分类，不执行 rebase --abort、不谎报冲突；
      真冲突才 abort。

全部用 unittest.mock 模拟外部命令，不产生真实网络/git 副作用，可安全反复跑。
退出码：0 全通过｜1 有失败。
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import l3_publish as L

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def _run(returncode=0, stderr="", stdout=""):
    return mock.Mock(returncode=returncode, stderr=stderr, stdout=stdout)


# ── 1. classify_git_error 四类分流（dirty 必须在 conflict 之前）──
for label, stderr, want in [
    ("dirty/unstaged", "error: cannot pull with rebase: You have unstaged changes.", "dirty"),
    ("dirty/local", "error: Your local changes to the following files would be overwritten by merge", "dirty"),
    ("dirty/commit-or-stash", "error: cannot pull with rebase: Please commit or stash them.", "dirty"),
    ("conflict", "CONFLICT (content): Merge conflict in foo.py", "conflict"),
    ("network", "fatal: unable to access 'https://github.com/x': Could not resolve host", "network"),
    ("other", "fatal: bad revision 'HEAD~'", "other"),
]:
    got, _ = L.classify_git_error(stderr)
    check(f"分类 {label} -> {want}", got == want, f"实际={got}")


# ── 2. D1：探活失败仍尝试真实操作并成功 ──
# 场景：第 1 次 pull 遇网络错 → 退避；第 2 次循环 github_reachable 抖动返回 False，
# 但代码不再 early-return，仍真实 pull 且成功 → push 成功 → 整体 ok。
pull_net_fail = _run(1, "fatal: unable to access 'x': Failed to connect to github.com")
pull_ok = _run(0)
push_ok = _run(0)
with mock.patch.object(L, "github_reachable", return_value=False), \
     mock.patch.object(L.time, "sleep"), \
     mock.patch.object(L.subprocess, "run",
                       side_effect=[pull_net_fail, pull_ok, push_ok]):
    ok, err, kind = L.git_pull_rebase_push(Path("."), timeout=5)
check("D1 探活失败仍尝试真实 pull/push 并成功", ok and kind == "ok",
      f"ok={ok} kind={kind} err={err}")
check("D1 不再报『不可重试』", "不可重试" not in err, f"err={err}")


# ── 3. D1：github_reachable 自身重试（前两次失败第三次成功）──
curl_fail = _run(7, stdout="000")
curl_ok = _run(0, stdout="200")
with mock.patch.object(L.time, "sleep"), \
     mock.patch.object(L.subprocess, "run",
                       side_effect=[curl_fail, curl_fail, curl_ok]) as m_reach:
    reached = L.github_reachable()
check("探活自身重试 3 次（前2失败第3成功）", reached is True and m_reach.call_count == 3,
      f"reached={reached} 调用次数={m_reach.call_count}")


# ── 4. D2：dirty 场景不 abort、不谎报冲突 ──
dirty_pull = _run(1, "error: cannot pull with rebase: You have unstaged changes.")
with mock.patch.object(L.subprocess, "run", side_effect=[dirty_pull]) as m_dirty:
    ok, err, kind = L.git_pull_rebase_push(Path("."), timeout=5)
check("D2 归类 dirty", kind == "dirty", f"kind={kind}")
check("D2 不谎报 rebase 冲突", "冲突" not in err and "工作区" in err, f"err={err}")
_dirty_cmds = [" ".join(c.args[0]) for c in m_dirty.call_args_list]
check("D2 未执行 rebase --abort",
      not any("--abort" in cmd for cmd in _dirty_cmds), f"调用命令={_dirty_cmds}")


# ── 5. 对照：真冲突仍会 abort（防「一修就松」）──
conflict_pull = _run(1, "CONFLICT (content): Merge conflict in foo.py")
with mock.patch.object(L.subprocess, "run",
                       side_effect=[conflict_pull, _run(0)]) as m_conf:
    ok, err, kind = L.git_pull_rebase_push(Path("."), timeout=5)
_conf_cmds = [" ".join(c.args[0]) for c in m_conf.call_args_list]
check("真冲突归类 conflict 且执行 abort",
      kind == "conflict" and any("--abort" in cmd for cmd in _conf_cmds),
      f"kind={kind} 调用命令={_conf_cmds}")


# ── 6. 对照：真实网络错误耗尽重试后返回 network（防误判成 always-success）──
net_pull = _run(1, "fatal: unable to access 'x': Could not connect to server")
with mock.patch.object(L, "github_reachable", return_value=True), \
     mock.patch.object(L.time, "sleep"), \
     mock.patch.object(L.subprocess, "run", return_value=net_pull):
    ok, err, kind = L.git_pull_rebase_push(Path("."), timeout=5, retries=2)
check("真实网络错耗尽重试后返回 network", (not ok) and kind == "network",
      f"ok={ok} kind={kind} err={err}")


# ── 汇总 ──
passed = sum(1 for _, c, _ in results if c)
for name, cond, detail in results:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  | {detail}" if detail and not cond else ""))
print(f"\nR3.8 推送门自检 {passed}/{len(results)} 通过")
sys.exit(0 if passed == len(results) else 1)

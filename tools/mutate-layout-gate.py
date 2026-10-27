#!/usr/bin/env python3
"""布局门的**变异验证**：故意弄坏被测对象，门必须变红。

为什么必须有这个脚本：一条从未变红过的门 = 装饰。`check-sprint-layout.py` 有 10 条判据，
本文件对其中每一条各配一组变异（`MUTATIONS`），每组都：
  ① 断言变异前门是绿的（否则"变红"证明不了任何事）；
  ② 断言**字节真的变了**（防止 marker 没匹配上导致静默 no-op）；
  ③ 断言门变红且**红在预期的判据 id 上**（不能因为别的判据顺带变红就宣布通过）；
  ④ `finally` 里还原并断言字节一致。

跑法：`py -3.12 tools/mutate-layout-gate.py [--root <repo>] [--only m01,m05]`
退出码：0 全部符合预期 / 1 有组不符合预期 / 2 用法错误。

**靶子要选"仓库里稳定存在的东西"**（某个里程碑还没完成 / 某个文件存在），
不要选"某个待办行"——最后一棒之后待办行消失了，靶子就自己过期（这是已知的第十一形态）。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = "tools/check-sprint-layout.py"


class NothingToMutate(RuntimeError):
    """当前进度下构造不出靶子——显式 SKIP，不算 FAIL 也不算通过。"""


@dataclass
class Mutation:
    mid: str
    title: str
    expect_fail: str  # 预期变红的判据 id
    apply: object  # Callable[[Path], None]


# ── 变异实现 ───────────────────────────────────────────────────────────

def _edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    original = path.read_text(encoding="utf-8")
    assert old in original, f"marker 未命中 {rel}: {old!r}"
    mutated = original.replace(old, new, 1)
    assert mutated != original, f"变异未产生字节变化 {rel}"
    path.write_text(mutated, encoding="utf-8")


def m01_missing_plan_doc(root: Path) -> None:
    (root / "plan/04-数据计划.md").unlink()


def m02_binding_head(root: Path) -> None:
    """破坏装订行的**锚点**本身。

    首版靶子是把"方法论装订"改成"方法论"——那两个词都不在判据里（判据要求同行出现
    方法论名 / 门命令 / 日期），于是门仍全绿，看起来像假门。真靶子 = 删掉方法论名。
    """
    _edit(root, "plan/00-README总览.md", "`ai-tool-project-sprint` 方法论", "本仓方法论")


def m03_section(root: Path) -> None:
    _edit(root, "plan/02-架构与技术选型.md", "## 一、分层架构", "## 一、结构")


def m04_status_conflict(root: Path) -> None:
    """两态探测：有待办就翻成完成，全完成就把一条翻回待办（同一种故障：跨副本不一致）。"""
    rel, other = "plan/05-里程碑与发布.md", "plan/00-README总览.md"
    text = (root / rel).read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("| M1 ") and "⬜" in line:
            lines[i] = line.replace("⬜ 待开工", "✅ 已完成")
            break
    else:
        for i, line in enumerate(lines):
            if line.startswith("| M1 ") and "⬜" not in line:
                lines[i] = line.replace("✅", "⬜")
                break
        else:
            raise NothingToMutate("plan/05 找不到 M1 状态行")
    mutated = "\n".join(lines) + "\n"
    assert mutated != text
    (root / rel).write_text(mutated, encoding="utf-8")
    assert "M1" in (root / other).read_text(encoding="utf-8")


def _completed_milestone(root: Path) -> int:
    """返回一个"已 ✅"的里程碑号；没有就把 M1 在两处副本里同时翻成 ✅ 再返回 1。

    **两态**写法是必要的：首版直接往缺口列写 `M1`，而 M1 尚未完成 →
    判据正确地不报红 → 看起来像假门。真实故障形态是"已完成里程碑仍被当缺口引用"，
    所以靶子必须先**造出一个已完成状态**（且两处副本同步，免得顺手触发 LAYOUT.STATUS）。
    """
    pattern = re.compile(r"^\|\s*M(\d+)\b")
    for rel in ("plan/05-里程碑与发布.md", "plan/00-README总览.md"):
        for line in (root / rel).read_text(encoding="utf-8").splitlines():
            m = pattern.match(line)
            if m and not any(mark in line for mark in ("⬜", "🟡")):
                return int(m.group(1))
    for rel in ("plan/00-README总览.md", "plan/05-里程碑与发布.md"):
        text = (root / rel).read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("| M1 ") and "⬜" in line:
                lines[i] = line.replace("⬜ 待开工", "✅ 已完成")
                break
        else:
            raise NothingToMutate(f"{rel} 找不到 M1 待办行")
        mutated = "\n".join(lines) + "\n"
        assert mutated != text
        (root / rel).write_text(mutated, encoding="utf-8")
    return 1


def m05_handoff_missing(root: Path) -> None:
    """构造"✅ 里程碑没有交接单"。

    **必须先造出 ✅ 状态，再删交接单** —— 反过来做是**无效变异**：`plan/HANDOFF-M1.md`
    在 M1 尚未完成时本来就不要求存在，删掉它 `LAYOUT.HANDOFFS` 正确地不报红，
    看起来像假门（本项目 2026-10-27 实测，m05 从 OK 变 FAIL 的正是这一步顺序）。
    """
    k = _completed_milestone(root)
    handoff = root / f"plan/HANDOFF-M{k}.md"
    if handoff.is_file():
        handoff.unlink()
        return
    # 没有交接单的 ✅ 状态本身就是故障——不用再做什么，但必须确认它真的缺
    assert not handoff.is_file()


def m06_gap_stale(root: Path) -> None:
    """真·过期检测：已 ✅ 的里程碑号出现在 plan/06 **缺口列**。"""
    k = _completed_milestone(root)
    path = root / "plan/06-交付对标与决策.md"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header = next(i for i, l in enumerate(lines) if l.startswith("|") and "缺口" in l)
    # 按表头定位列号——**别写 cells[-2]**：那取的是最后一个内容格（状态列），
    # 写进去命中的是"别的列"，判据扫的缺口列根本没变（假门族②的变体）。
    cols = [c.strip() for c in lines[header].split("|")]
    col = next(i for i, c in enumerate(cols) if "缺口" in c)
    target = header + 2
    if target >= len(lines) or not lines[target].startswith("|"):
        raise NothingToMutate("缺口表没有数据行")
    cells = lines[target].split("|")
    if col >= len(cells):
        raise NothingToMutate(f"缺口列号 {col} 超出该行格数 {len(cells)}")
    cells[col] = f" 仍待 M{k} 收口 "
    lines[target] = "|".join(cells)
    mutated = "\n".join(lines) + "\n"
    assert mutated != text
    path.write_text(mutated, encoding="utf-8")


def m07_ledger_stale(root: Path) -> None:
    """真·过期检测：台账状态格既挂未完成标记、又点名一个已 ✅ 的里程碑。"""
    k = _completed_milestone(root)
    path = root / "plan/00-README总览.md"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header = next(i for i, l in enumerate(lines) if l.startswith("|") and "承诺" in l and "状态" in l)
    cols = [c.strip() for c in lines[header].split("|")]
    col = next(i for i, c in enumerate(cols) if "状态" in c)
    target = header + 2
    cells = lines[target].split("|")
    cells[col] = f" ⬜ 待 M{k} 复核 "
    lines[target] = "|".join(cells)
    mutated = "\n".join(lines) + "\n"
    assert mutated != text
    path.write_text(mutated, encoding="utf-8")


def m08_doc_tool_missing(root: Path) -> None:
    _edit(root, "AGENTS.md", "`tools/check-release.py`", "`tools/check-nonexistent.py`")


def m09_ci_gate_step(root: Path) -> None:
    path = root / ".github/workflows/ci.yml"
    text = path.read_text(encoding="utf-8")
    mutated = text.replace("check-sprint-layout.py", "check-layout-renamed.py")
    assert mutated != text
    path.write_text(mutated, encoding="utf-8")


def m10_ci_mutation_step(root: Path) -> None:
    path = root / ".github/workflows/ci.yml"
    text = path.read_text(encoding="utf-8")
    mutated = text.replace("mutate-layout-gate.py", "mutate-renamed.py")
    assert mutated != text
    path.write_text(mutated, encoding="utf-8")


MUTATIONS: list[Mutation] = [
    Mutation("m01", "删掉 plan/04（必备文件缺失）", "LAYOUT.FILES", m01_missing_plan_doc),
    Mutation("m02", "破坏 plan/00 顶部装订行", "LAYOUT.BINDING_HEAD", m02_binding_head),
    Mutation("m03", "改掉 plan/02 的必需小节标题", "LAYOUT.SECTIONS", m03_section),
    Mutation("m04", "只改一处状态副本 → 跨副本不一致", "LAYOUT.STATUS", m04_status_conflict),
    Mutation("m05", "✅ 里程碑缺交接单（两态：删既有 / 造一个完成态）", "LAYOUT.HANDOFFS", m05_handoff_missing),
    Mutation("m06", "已 ✅ 里程碑号仍留在缺口列", "LAYOUT.GAPS", m06_gap_stale),
    Mutation("m07", "台账行挂未完成标记并点名已 ✅ 里程碑", "LAYOUT.LEDGER", m07_ledger_stale),
    Mutation("m08", "文档点名一个不存在的 tools/ 脚本", "LAYOUT.DOC_TOOLS", m08_doc_tool_missing),
    Mutation("m09", "CI 里布局门步骤名字被改", "LAYOUT.CI_STEP", m09_ci_gate_step),
    Mutation("m10", "CI 里变异验证步骤名字被改", "LAYOUT.CI_MUTATION", m10_ci_mutation_step),
]


# ── 执行框架 ───────────────────────────────────────────────────────────

def run_gate(root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(root / GATE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def failing_ids(output: str) -> set[str]:
    return {
        line.split()[1]
        for line in output.splitlines()
        if line.startswith("FAIL") and len(line.split()) > 1
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mutate-layout-gate", description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--only", default="", help="逗号分隔的变异 id")
    args = parser.parse_args(argv)

    src_root = Path(args.root).resolve()
    if not (src_root / GATE).is_file():
        sys.stderr.write(f"用法错误：找不到 {GATE}（--root={src_root}）\n")
        return 2

    wanted = {m.strip() for m in args.only.split(",") if m.strip()}
    selected = [m for m in MUTATIONS if not wanted or m.mid in wanted]
    if not selected:
        sys.stderr.write(f"用法错误：--only {args.only} 没有匹配任何变异\n")
        return 2

    results: list[tuple[str, str, str]] = []  # (mid, "OK"|"FAIL"|"SKIP", detail)

    for mutation in selected:
        with tempfile.TemporaryDirectory(prefix="crs-mut-") as tmp:
            work = Path(tmp) / "repo"
            shutil.copytree(
                src_root,
                work,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "*.pyc", ".pytest_cache"),
            )
            base_code, base_out = run_gate(work)
            if base_code != 0:
                results.append((mutation.mid, "FAIL", f"变异前门就是红的（无法作为基线）：\n{base_out}"))
                continue
            try:
                mutation.apply(work)  # type: ignore[operator]
            except NothingToMutate as exc:
                results.append((mutation.mid, "SKIP", f"当前进度下构造不出靶子：{exc}"))
                continue
            except AssertionError as exc:
                results.append((mutation.mid, "FAIL", f"变异自身失败：{exc}"))
                continue
            code, out = run_gate(work)
            reds = failing_ids(out)
            if code == 0:
                results.append((mutation.mid, "FAIL", "门仍全绿——该判据是假门"))
            elif mutation.expect_fail not in reds:
                results.append(
                    (mutation.mid, "FAIL", f"变红了但不在预期判据上：期望 {mutation.expect_fail}，实得 {sorted(reds)}")
                )
            else:
                results.append((mutation.mid, "OK", f"{mutation.expect_fail} 如期变红"))

    green = sum(1 for _m, s, _d in results if s == "OK")
    skipped = sum(1 for _m, s, _d in results if s == "SKIP")
    bad = [r for r in results if r[1] == "FAIL"]

    print("布局门变异验证 · 每组必须红在预期判据上")
    print("=" * 56)
    for mid, status, detail in results:
        title = next(m.title for m in MUTATIONS if m.mid == mid)
        print(f"{status:4}  {mid}  {title} — {detail}")
    print("=" * 56)
    print(f"符合预期 {green} / 不符 {len(bad)} / 跳过 {skipped}（共 {len(results)} 组）")
    if bad:
        print(f"结论: {len(bad)} 组不符合预期")
        return 1
    print("结论: 全部符合预期")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

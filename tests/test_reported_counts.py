"""自述测试数的守门（D2 / DEC4）。

**这条缺陷的形状**：文档里写 `321 passed`、`318 passed`、`test_report.py（16 项）`、
`test_release_gate.py（30 项）`，而实测是 322 / 13 / 28——三处数字各有各的错，且**没有任何
一条判据在读它们**（`grep -rn "collect-only\\|tests collected" tests/ tools/` 曾 0 命中）。
错值随 sdist 一起发出去，下载者看到的就是错值。

**判据怎么取值**：不抄任何常量，一律**跑真实命令**：

- `pytest -o addopts="" -q` 的汇总行给出 `N passed, M skipped`；
- `pytest -o addopts="" --collect-only -q` 给出每文件条数与总 collected。

`passed = collected - skipped`（本仓那 2 条 skip 是 `test_unimplemented_contract.py` 里
`UNIMPLEMENTED` 为空导致的 `empty parameter set`，刻意保留）。所以文档里
"`N` passed" 必须等于 run1 的 passed，"`test_xxx.py`（`N` 项）" 必须等于 run2 的该文件条数。

**两类断言的形态**（这是判据的扫描面，写窄是刻意的：不扫自由文本里的所有数字）：

1. `<数字> passed`；
2. `test_<名字>.py` 紧跟的条数——`（16 项）`、` 28 项：`、` 24、`（里程碑表里的顿号串）。

**空跑守门**：三个文件都读不到、或一条断言都扫不到 → FAIL。一个扫 0 条的自指门比没有门
更糟（它给出"数字对得上"的假结论）；`test_count_gate_finds_the_docs` 就是这个守卫的阳性对照。
"""

from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 自述数字的权威面：现役进度表两处 + 最近一次发布留档。
DOC_FILES: tuple[str, ...] = (
    "plan/05-里程碑与发布.md",
    "plan/06-交付对标与决策.md",
    "plan/RELEASE-M6.md",
)

#: `<N> passed`（汇总行形态；`passed` 与数字之间允许多个空格）。
PASSED_CLAIM_RE = re.compile(r"(\d+)\s+passed")

#: `test_<name>.py` 紧跟条数：`（16 项）` / ` 28 项：` / ` 24、`。
FILE_CLAIM_RE = re.compile(r"test_([a-z0-9_]+)\.py`?[ \t]*(?:[（(])?[ \t]*(\d+)[ \t]*(?:项|[、])")

#: 已过期的历史错值（D2）：这两个数字在任何一份现役文档里都不许再出现。
STALE_VALUES: tuple[str, ...] = ("321 passed", "318 passed")


# ── 真值：跑真实命令，不抄常量 ────────────────────────────────────────
#
# **自指陷阱（实测踩过）**：本文件要用 `subprocess` 跑全量 pytest 才能拿到真值，而全量
# pytest 又会收集本文件 → 每个用例再起一个全量 pytest → 无限递归（第一次跑直接挂住）。
# 解法：子进程 `--ignore` 掉本文件，再把"本文件的用例条数"加回去。那个条数**从源码数**
# （`_self_test_count()`），不写死——本文件加一条用例，文档就必须跟着加 1，这正是自指
# 守门该有的行为。

_SELF = Path(__file__).name


def _pytest(*argv: str) -> str:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            f"--ignore=tests/{_SELF}",
            *argv,
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise AssertionError(f"pytest {' '.join(argv)} 失败（exit {proc.returncode}）：\n{out[-2000:]}")
    return out


@lru_cache(maxsize=1)
def _self_test_count() -> int:
    """本文件自己定义了多少条 `def test_`（自指守门的"另一半"）。"""
    source = Path(__file__).read_text(encoding="utf-8")
    return len(re.findall(r"(?m)^def test_", source))


@lru_cache(maxsize=1)
def _summary_counts() -> tuple[int, int]:
    """全量真值 `(passed, skipped)`：子进程真值 + 本文件条数。"""
    out = _pytest("-q")
    match = re.search(r"(\d+) passed(?:, (\d+) skipped)?", out)
    if not match:
        raise AssertionError(f"汇总行里读不到 'N passed'（-qq 叠加会吞掉它）：\n{out[-1000:]}")
    return int(match.group(1)) + _self_test_count(), int(match.group(2) or 0)


@lru_cache(maxsize=1)
def _per_file_collected() -> dict[str, int]:
    """`--collect-only -q` 按文件统计条数（键是 `test_xxx.py` 里的 `xxx`）。"""
    out = _pytest("--collect-only", "-q")
    counts: dict[str, int] = {}
    for line in out.splitlines():
        match = re.match(r"^(?:tests[\\/])?test_([a-z0-9_]+)\.py::", line.strip())
        if match:
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    if not counts:
        raise AssertionError("--collect-only 的输出里一条用例都没解析到（判据空跑）")
    counts[_SELF.removesuffix(".py").removeprefix("test_")] = _self_test_count()
    return counts


# ── 判据本体 ──────────────────────────────────────────────────────────


def _read_docs(paths: list[Path]) -> dict[Path, list[str]]:
    docs: dict[Path, list[str]] = {}
    for path in paths:
        if path.is_file():
            docs[path] = path.read_text(encoding="utf-8").splitlines()
    return docs


def documented_problems(paths: list[Path], passed: int, skipped: int, per_file: dict[str, int]) -> list[str]:
    """把文档里的自述数字与真值对撞，返回**全部**问题（空列表 = 全对）。

    路径参数是让阴性对照能喂一个不存在的文件进来——那时 `docs` 为空，
    下面的"空跑守门"必须报出问题。
    """
    docs = _read_docs(paths)
    problems: list[str] = []

    missing = [str(p) for p in paths if p not in docs]
    if missing:
        problems.append(f"读不到目标文档（判据空跑）: {missing}")
        return problems

    passed_claims = 0
    file_claims = 0
    for path, lines in docs.items():
        rel = path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path)
        for lineno, line in enumerate(lines, 1):
            for raw in PASSED_CLAIM_RE.findall(line):
                passed_claims += 1
                claimed = int(raw)
                if claimed != passed:
                    problems.append(
                        f"{rel}:{lineno} 写 '{claimed} passed'，实测 {passed} passed"
                        f"（= {passed + skipped} collected - {skipped} skipped）"
                    )
            for name, raw in FILE_CLAIM_RE.findall(line):
                file_claims += 1
                claimed = int(raw)
                actual = per_file.get(name)
                if actual is None:
                    problems.append(f"{rel}:{lineno} 点名 tests/test_{name}.py，但该文件没收集到用例")
                elif claimed != actual:
                    problems.append(
                        f"{rel}:{lineno} 写 'test_{name}.py（{claimed} 项）'，实测 {actual} 项"
                    )

    if passed_claims == 0:
        problems.append("三份文档里一条 '<N> passed' 断言都没扫到（判据空跑）")
    if file_claims == 0:
        problems.append("三份文档里一条 'test_xxx.py（N 项）' 断言都没扫到（判据空跑）")
    return problems


def test_documented_counts_match_collected() -> None:
    """三份现役文档里的每个自述数字都必须等于实测。"""
    passed, skipped = _summary_counts()
    per_file = _per_file_collected()
    paths = [REPO_ROOT / rel for rel in DOC_FILES]
    problems = documented_problems(paths, passed, skipped, per_file)
    assert not problems, "自述数字与实测不符：\n" + "\n".join(problems)


def test_no_stale_321_or_318() -> None:
    """D2 的两个过期错值（`321 passed` / `318 passed`）不许在任何一份现役文档里复活。

    单独一条而不是并进上一条，是因为它守的东西不同：上一条守"等于现在的真值"，
    这一条守"别把已经被否掉的旧数字抄回来"（新版本的真值恰好等于 321 时，
    上一条会放行，这一条仍然红）。
    """
    offenders: list[str] = []
    for rel in DOC_FILES:
        path = REPO_ROOT / rel
        if not path.is_file():
            offenders.append(f"{rel}: 文件不存在")
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for stale in STALE_VALUES:
                if stale in line:
                    offenders.append(f"{rel}:{lineno} 仍写着 '{stale}'")
    assert not offenders, "过期错值复活：\n" + "\n".join(offenders)


def test_count_gate_finds_the_docs(tmp_path: Path) -> None:
    """阴性对照：喂一个不存在的目标文件，判据必须报错（证明它真的在读文件）。

    一个"文件读不到就跳过"的门是假门——它在该红的时候静默变绿，给出的正是
    "数字都对得上"这个最危险的假结论。
    """
    passed, skipped = _summary_counts()
    problems = documented_problems([tmp_path / "no-such-doc.md"], passed, skipped, {})
    assert problems, "目标文档不存在时判据没有报错 —— 这是空跑守卫失效"
    assert any("读不到目标文档" in p for p in problems), problems

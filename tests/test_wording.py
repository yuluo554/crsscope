"""措辞守门：用户接触面上不得出现**断言式**的 `crs` 强制禁用表述（`plan/00` 决策 ①）。

RFC 7946 §4 只说 `crs` 成员 "no longer used"，**没有任何强制禁用条款**。

**扫描面为什么收窄到 `README.md` / `AGENTS.md` / `src/**`**：
- `plan/` 是工作笔记，风险登记表里"**把 crs 写成 MUST NOT**"是**故障名称**（左列写的是要避免的
  东西），按自由文本扫必然假红（假门族⑤"扫自由文本 / 张冠李戴"）。
- 真正会被用户读到、被命令输出的是 README、AGENTS 与产品文案——这才是判据该锚的面。

判据分两条，各自可证伪：
1. **文档面**：扫描面上出现 `MUST NOT` 的行必须有否定语境（"没有" / "禁止" / "不含" …）；
2. **产品面**：`src/` 里所有字符串字面量（AST 级，不是源码文本）都不得构成
   "crs 与强制禁用同现"的断言——这条锚的是**工具会打印出去的话**。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 文档面：用户/读者真正会读的入口文件。`plan/` 不在此列（见模块文档串）。
DOC_SURFACES = ("README.md", "AGENTS.md")

#: 否定语境（命中行必须同时含其一）
NEGATION = (
    "没有",
    "无此",
    "无该",
    "不含",
    "不写",
    "不得",
    "不是",
    "非",
    "禁止",
    "严禁",
)

MUST_NOT = re.compile(r"MUST\s+NOT", re.IGNORECASE)
CRS = re.compile(r"\bcrs\b", re.IGNORECASE)


def _doc_hits() -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for rel in DOC_SURFACES:
        path = REPO_ROOT / rel
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if MUST_NOT.search(line):
                hits.append((path, lineno, line.strip()))
    return hits


def test_doc_surfaces_exist() -> None:
    """阳性对照：扫描面必须真的存在，否则"零命中"什么都没证明。"""
    for rel in DOC_SURFACES:
        assert (REPO_ROOT / rel).is_file(), rel


def test_doc_hits_are_all_negations() -> None:
    bad = [
        (p.relative_to(REPO_ROOT), n, line)
        for p, n, line in _doc_hits()
        if not any(neg in line for neg in NEGATION)
    ]
    assert not bad, "README/AGENTS 出现断言式的 crs 禁用表述：\n" + "\n".join(
        f"{p}:{n}: {l}" for p, n, l in bad
    )


def _src_string_literals() -> list[tuple[Path, str]]:
    """收集源码里所有字符串字面量（含 f-string 的常量片段），附带来源文件。"""
    out: list[tuple[Path, str]] = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append((path, node.value))
    return out


def test_no_src_string_asserts_crs_prohibition() -> None:
    """产品会打印出去的每一句话都不得构成"crs 强制禁用"的断言。"""
    offenders = [
        (p.relative_to(REPO_ROOT), s)
        for p, s in _src_string_literals()
        if MUST_NOT.search(s) and CRS.search(s)
    ]
    assert not offenders, f"产品文案含断言式禁用表述：{offenders}"


def test_src_string_scan_is_not_empty() -> None:
    assert len(_src_string_literals()) > 20, "扫到 0/极少字面量——判据空跑"


def test_crs_wording_constant_is_correct() -> None:
    from crsscope import geojson

    assert not MUST_NOT.search(geojson.CRS_REMOVED_WORDING)
    assert "no longer used" in geojson.CRS_REMOVED_WORDING


@pytest.mark.parametrize(
    "fragment",
    ["A linear ring MUST follow the right-hand rule", "parsers SHOULD NOT reject"],
)
def test_rfc_quotes_are_intact(fragment: str) -> None:
    """R1 / R2 原文必须逐字保留——改一个字就不是"照录"了。"""
    from crsscope import geojson

    assert fragment in geojson.RFC_R1 or fragment in geojson.RFC_R2


def test_wording_gate_sees_planted_violation() -> None:
    """探活：给一段虚构文本，判据必须能判出来（否则"零命中"是判据没工作）。"""
    planted = "本文件的 crs 成员 MUST NOT 被使用"
    assert MUST_NOT.search(planted) and CRS.search(planted)
    assert not any(neg in planted for neg in NEGATION)

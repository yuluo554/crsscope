"""零第三方运行时依赖守门（`plan/02` §三）。

用 **AST** 而不是字符串/正则：`import` 的三种形态（绝对 / 相对 / `from X import Y` /
`importlib.import_module` 动态导入）都要覆盖——只查 `node.module` 会静默漏判相对导入。
`sys.stdlib_module_names` 是 3.10+ 才有，项目下限 3.11，可用。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

#: 允许的标准库之外的"本包"名
OWN_PACKAGE = "crsscope"


def _iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _top_level_imports(tree: ast.AST) -> set[str]:
    """收集**模块级** import 的顶层名。

    `from X import Y` 里 `Y` 通常是 X 里的符号，不是模块——把别名当模块会误判
    （本项目 2026-10-27 实测：`from dataclasses import dataclass` 被报成第三方 `dataclass`）。
    只有 `import a.b as c` 与 `from a.b import c` 的 `a` 才是模块。
    相对导入（`level > 0`）指向本包内部，记为 OWN_PACKAGE。
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 or not node.module:
                names.add(OWN_PACKAGE)
            else:
                names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "import_module":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        names.add(arg.value.split(".")[0])
    return names


def test_src_imports_only_stdlib_or_own_package() -> None:
    allowed = set(sys.stdlib_module_names) | {OWN_PACKAGE}
    offenders: dict[str, list[str]] = {}
    scanned = 0
    for path in _iter_python_files(SRC_DIR):
        scanned += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        bad = sorted(_top_level_imports(tree) - allowed - {"__future__"})
        if bad:
            offenders[str(path.relative_to(REPO_ROOT))] = bad
    assert scanned > 0, "扫到 0 个源文件——判据空跑"
    assert not offenders, f"出现第三方 import: {offenders}"


def test_pyproject_declares_no_runtime_dependencies() -> None:
    import tomllib

    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"].get("dependencies", []) == [], "零运行时依赖是承诺，不是巧合"


def test_detector_sees_planted_third_party_import() -> None:
    """探活：判据必须能抓到阳性样本（绝对 / 相对 / 动态导入四种形态）。"""
    src = "import requests\nfrom numpy import array\nimport yaml\n"
    found = _top_level_imports(ast.parse(src))
    assert {"requests", "numpy", "yaml"} <= found
    assert _top_level_imports(ast.parse("from . import errors\n")) == {OWN_PACKAGE}

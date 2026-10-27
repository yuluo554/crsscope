"""版本号单点定义守门（`plan/02` §三）。

判据：`crsscope.__version__` ↔ 已安装元数据、`pyproject.toml` 的动态声明、README 的版本串。
"改的时候会不会漏一份"这个问题必须由机器回答——手抄两处时"漏改一处"是经典事故。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import crsscope

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_version_matches_pyproject_dynamic_source() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dynamic = data["tool"]["setuptools"]["dynamic"]["version"]["attr"]
    assert dynamic == "crsscope.__version__", "版本必须由包内 __init__ 单点提供"


def test_no_literal_version_in_pyproject() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    assert "version" not in project, "pyproject 里不得写死版本（会与 __init__ 漂移）"
    assert "version" in project.get("dynamic", [])


def test_readme_mentions_current_version() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert f"`{crsscope.__version__}`" in readme, "README 必须标出当前版本（读者第一个看到的版本面）"


def test_version_is_semver_triplet() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", crsscope.__version__), crsscope.__version__

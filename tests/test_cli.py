"""CLI 参数面与退出码契约（`plan/03` §七）。

判据只锚**被测的那一条**：不写 `assert "命中列表为空"` 这种"断言了全世界"的形态。

**`main()` 不抛 `SystemExit`**：`argparse` 内部抛出的 `SystemExit(2/0)` 已被 `main()` 统一
捕获并转成整数返回（`plan/03` §七："`cli.main()` 是唯一把异常转成退出码的地方"）。
因此这里断言**返回值**，不写 `pytest.raises(SystemExit)`——那是另一种入口形态，
混用会让"这条命令在某些入口答 2、另一些答 1"的漂移重新长出来。
"""

from __future__ import annotations

import pytest

from crsscope import __version__
from crsscope.cli import build_parser, main

SUBCOMMANDS = ("decl", "detect", "xdiff", "geojson", "tiles", "report")


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    for name in SUBCOMMANDS:
        assert name in out, f"--help 总览缺子命令 {name}"


@pytest.mark.parametrize("name", SUBCOMMANDS)
def test_subcommand_help_exits_zero(name: str) -> None:
    assert main([name, "--help"]) == 0


def test_version_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_no_subcommand_prints_help_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage:" in capsys.readouterr().out.lower()


def test_unknown_subcommand_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["nope"]) == 2
    assert "invalid choice" in capsys.readouterr().err.lower()


def test_missing_required_arg_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["xdiff"]) == 2  # 缺 file 与 --target
    capsys.readouterr()


def test_invalid_declared_crs_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """GCJ-02 无 EPSG 代码，不是合法声明值（`data/README.md` §1.2）。"""
    assert main(["decl", "x.geojson", "--declared-crs", "gcj02"]) == 2
    assert "gcj02" in capsys.readouterr().err


def test_parser_exposes_all_declared_crs_choices() -> None:
    parser = build_parser()
    sub = next(a for a in parser._actions if getattr(a, "choices", None) and "decl" in a.choices)
    decl_parser = sub.choices["decl"]
    opt = next(a for a in decl_parser._actions if a.dest == "declared_crs")
    assert tuple(opt.choices) == ("4326", "3857", "4490", "crs84")

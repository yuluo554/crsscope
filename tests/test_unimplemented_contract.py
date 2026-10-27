"""未实现能力的契约守门（`plan/00` 决策 ⑦b）。

历史形态：骨架阶段把未落位的子命令登记进 `UNIMPLEMENTED`，逐个断言
`exit 3` + stderr 含 `not implemented`——若哪天有人把子命令改成"返回空结果集"，
退出码会变成 0，下游 CI 会把"没跑"读成"跑过且没问题"，这条测试就是防这一种的。

**M6 之后的形态**（HANDOFF-M6 §2.3 第 19/20 条）：六个子命令全部落位，表已清空。
参数化测试**保留**（空参数集静默通过）：将来若有新子命令以占位实现进仓，
登记进表的那一刻契约自动重新生效，不需要重新发明守门。同时保留一条显式断言：
"M6 起表为空"是仓库的固定事实——有人把已落位的命令改回占位却没登记，
或登记后没写退出码契约，都会在这里红。
"""

from __future__ import annotations

import pytest

from crsscope import cli

#: {子命令: 落位里程碑}。M6 后全部子命令已实现，**表保持为空**；
#: 新增占位子命令时必须在此登记（参数化契约会自动接管它）。
UNIMPLEMENTED: dict[str, str] = {}

ARGS: dict[str, list[str]] = {}


def test_contract_table_matches_handlers() -> None:
    """契约表必须覆盖全部已注册子命令——新增子命令而忘了登记，会静默漏测。"""
    assert set(UNIMPLEMENTED) <= set(cli._HANDLERS)


def test_unimplemented_table_is_empty_after_m6() -> None:
    """M6 起 `decl`/`detect`/`xdiff`/`geojson`/`tiles`/`report` 全部落位，表必须为空。"""
    assert UNIMPLEMENTED == {}, f"仍有未落位子命令: {sorted(UNIMPLEMENTED)}"


def test_every_registered_handler_is_reachable() -> None:
    """六个子命令的处理器都在位且可调用——防止登记表清空后处理器被顺手删掉。"""
    assert set(cli._HANDLERS) == {"decl", "detect", "xdiff", "geojson", "tiles", "report"}


@pytest.mark.parametrize("command", sorted(UNIMPLEMENTED))
def test_unimplemented_command_exits_3(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main([command, *ARGS[command]])
    err = capsys.readouterr().err
    assert code == 3, f"{command} 未实现应以 3 退出（实际 {code}）——返回 0 会把'没跑'读成'没问题'"
    assert "not implemented" in err.lower()
    assert f"里程碑 {UNIMPLEMENTED[command]}" in err or UNIMPLEMENTED[command] in err


@pytest.mark.parametrize("command", sorted(UNIMPLEMENTED))
def test_unimplemented_command_writes_no_report(command: str, tmp_path, capsys) -> None:
    """失败路径零副作用：未实现时不得落任何报告文件。"""
    out_dir = tmp_path / "out"
    args = [command, *ARGS[command], "--out-dir", str(out_dir)]
    cli.main(args)
    capsys.readouterr()
    assert not out_dir.exists() or not list(out_dir.iterdir())

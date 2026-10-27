"""未实现能力的契约守门（`plan/00` 决策 ⑦b）。

骨架阶段的五个判定子命令必须**显式失败**：`exit 3` + stderr 含 `not implemented`。
若哪天有人把它们改成"返回空结果集"，退出码会变成 0 —— 下游 CI 会把"没跑"读成
"跑过且没问题"。这条测试就是防这一种的。

**收尾时要复核**：M2–M6 逐个落位后，对应条目要从 `UNIMPLEMENTED` 里删掉，
否则它会一直"通过"而实际早已实现（靶子过期 = 判据失效）。
"""

from __future__ import annotations

import pytest

from crsscope import cli

#: {子命令: 落位里程碑}。实现完成后**必须**从本表删除对应项。
UNIMPLEMENTED = {
    "report": "M6",
}

ARGS = {
    "report": ["report.json"],
}


def test_contract_table_matches_handlers() -> None:
    """契约表必须覆盖全部已注册子命令——新增子命令而忘了登记，会静默漏测。"""
    assert set(UNIMPLEMENTED) <= set(cli._HANDLERS)


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

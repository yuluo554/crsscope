"""README 命令面的反射对账（阶段 7 出口门）。

判据：README 里每个 ```bash 代码块中的 `crsscope …` 行，都必须能被 `build_parser()`
**真正解析通过**。成本极低，且不依赖任何数据（纯参数面）——它能直接抓住
"文档写了 `--show-kind=a,b` 而 code 里给该参数加了 `choices`"这类只有真敲才暴露的缺陷。

**不执行**这些命令（骨架阶段它们会 exit 3），只做 parser 反射：
`argparse` 的 `SystemExit(2)` 就是"parser 不认识这个参数形态"的硬信号。
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from crsscope.cli import build_parser

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"

BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
LINE = re.compile(r"^\s*crsscope\s+(.*)$")


def _readme_commands() -> list[str]:
    text = README.read_text(encoding="utf-8")
    cmds: list[str] = []
    for block in BLOCK.findall(text):
        for raw in block.splitlines():
            m = LINE.match(raw)
            if m:
                cmds.append(m.group(1).strip())
    return cmds


def test_readme_has_commands() -> None:
    """阳性对照：README 必须真的含 `crsscope` 命令块，否则这条断言什么都没证明。"""
    cmds = _readme_commands()
    assert len(cmds) >= 2, f"README 只找到 {len(cmds)} 条命令"


@pytest.mark.parametrize("command_line", _readme_commands())
def test_readme_command_parses(command_line: str) -> None:
    """README 每条命令都要能被 parser 接受（不执行，只解析）。

    `SystemExit(0)` 是 `--help` 的正常出口，**不算失败**——只把非 0 当作"parser 不认"。
    """
    argv = shlex.split(command_line)
    parser = build_parser()
    try:
        parser.parse_args(argv)
    except SystemExit as exc:  # argparse 对未知/缺参就是 SystemExit(2)
        if exc.code:
            pytest.fail(f"README 命令 parser 不接受（exit {exc.code}）：crsscope {command_line}")


def test_every_subcommand_is_documented() -> None:
    """五个子命令 + report 必须都在 README 里出现过——读者找不到入口等于没有。"""
    text = README.read_text(encoding="utf-8")
    for sub in ("decl", "detect", "xdiff", "geojson", "tiles", "report"):
        assert f"crsscope {sub}" in text or f"`crsscope {sub}" in text, sub

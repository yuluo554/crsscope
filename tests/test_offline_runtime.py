"""断网**实跑**守门（`plan/02` §四 + HANDOFF-M6 §三C 第 12 条）。

`tests/test_no_network.py` 是 AST 静态判据（源码里没有网络客户端 import）。本文件补的是
**运行时**证据：在子进程启动时通过 `sitecustomize` 装一个审计钩子，任何 `socket.*` /
`urllib.Request` 事件一出现就立刻以专用退出码 99 结束；然后在这个进程里跑真实命令。

为什么不 monkeypatch `socket.socket`：`sys.addaudithook` 拦的是**所有**底层网络事件
（含 C 扩展直接调用），monkeypatch 只能拦 Python 层的一个入口——后者会漏。

为什么用 `sitecustomize` 而不是 `-c "exec(...)"`：解释器启动即加载，不需要把代码拼成
字符串交给 `exec`，也不碰 `eval`——守门代码本身不该带动态执行面。

判据分三层：
1. 探活：钩子本身必须真的能拦住一次联网尝试（否则"零命中"什么都没证明）。
2. 实跑：三个子命令 + `report` 在钩子下 exit 码与不带钩子时**相同**（网络不是结果来源）。
3. 产物：`report.json` 逐字节一致（不因断网环境产生任何额外字段）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "data" / "fixtures"

#: 审计钩子模块：命中任何网络事件即写 stderr 并以专用退出码 99 结束。
#:
#: `socket.gethostname` 是**本地**调用（`report.scrub()` 用它去掉报告里的主机名），
#: 不起连接也不解析名字——必须放行，否则断网守门会误伤它自己的脱敏逻辑。
_BLOCKER_SOURCE = '''\
import sys

# 只放行纯本地调用；建 socket / 连接 / 解析 / 发送一律拦截。
_LOCAL_ONLY = frozenset({"socket.gethostname"})
_BLOCKED_EVENTS = frozenset({"urllib.Request"})


def _hook(event, args):
    blocked = (event.startswith("socket.") and event not in _LOCAL_ONLY) or event in _BLOCKED_EVENTS
    if blocked:
        sys.stderr.write("NETWORK-ATTEMPT: " + event + "\\n")
        sys.stderr.flush()
        raise SystemExit(99)


sys.addaudithook(_hook)
'''


def _blocker_dir(tmp_path: Path) -> Path:
    """把钩子写成 `sitecustomize.py`；解释器启动时会自动 import 它。"""
    site = tmp_path / "netsite"
    site.mkdir(exist_ok=True)
    (site / "sitecustomize.py").write_text(_BLOCKER_SOURCE, encoding="utf-8", newline="\n")
    return site


def _env(extra_path: Path | None = None) -> dict[str, str]:
    env = dict(os.environ)
    parts = [str(SRC_DIR)]
    if extra_path is not None:
        parts.insert(0, str(extra_path))  # sitecustomize 所在目录优先
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONUTF8"] = "1"
    env.pop("SOURCE_DATE_EPOCH", None)
    return env


def _run(tmp_path: Path, argv: list[str], *, blocked: bool) -> subprocess.CompletedProcess[str]:
    env = _env(_blocker_dir(tmp_path) if blocked else None)
    return subprocess.run(
        [sys.executable, "-m", "crsscope", *argv],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ── 一、探活：钩子必须真的能拦住联网 ──────────────────────────────────


def test_blocker_catches_a_real_connection_attempt(tmp_path: Path) -> None:
    """阳性对照：钩子若没装上，它会静默放行一切——所以必须先证明它拦得住。"""
    env = _env(_blocker_dir(tmp_path))
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import socket; s = socket.socket(); s.settimeout(0.01); s.connect(('127.0.0.1', 9))",
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 99, f"钩子没拦住 socket.socket（exit {proc.returncode}）"
    assert "NETWORK-ATTEMPT" in proc.stderr


# ── 二、实跑：子命令在断网下行为不变 ──────────────────────────────────


@pytest.mark.parametrize(
    "argv",
    [
        ["geojson", str(FIXTURES / "geojson_struct/out/case-001_ring_cw.geojson"), "--strict-ring"],
        ["tiles", str(FIXTURES / "tile_flip/out/tile_flip.json")],
        ["decl", str(FIXTURES / "swapped_axis/out/swapped_axis.geojson"), "--declared-crs", "4326"],
    ],
)
def test_command_behaves_identically_with_network_blocked(
    tmp_path: Path, argv: list[str]
) -> None:
    blocked = _run(tmp_path, [*argv, "--json", "--out-dir", str(tmp_path / "b")], blocked=True)
    plain = _run(tmp_path, [*argv, "--json", "--out-dir", str(tmp_path / "p")], blocked=False)

    assert "NETWORK-ATTEMPT" not in blocked.stderr, blocked.stderr
    assert blocked.returncode != 99, f"{argv[0]} 在断网下尝试联网: {blocked.stderr}"
    assert blocked.returncode == plain.returncode, (
        f"{argv[0]} 断网态 exit {blocked.returncode} != 常规态 {plain.returncode}"
    )
    assert blocked.stdout == plain.stdout, f"{argv[0]} 断网态 stdout 与常规态不一致"


def test_report_aggregates_offline(tmp_path: Path) -> None:
    """`report` 汇总同样零网络：先备好输入，再在钩子下聚合。"""
    reports: list[Path] = []
    for name, argv in (
        ("tiles", ["tiles", str(FIXTURES / "tile_flip/out/tile_flip.json")]),
        ("decl", ["decl", str(FIXTURES / "swapped_axis/out/swapped_axis.geojson"), "--declared-crs", "4326"]),
    ):
        out = tmp_path / f"src-{name}"
        assert _run(tmp_path, [*argv, "--json", "--out-dir", str(out)], blocked=False).returncode in (0, 1, 5)
        reports.append(out / "report.json")

    blocked = _run(
        tmp_path,
        ["report", *[str(p) for p in reports], "--json", "--out-dir", str(tmp_path / "agg")],
        blocked=True,
    )
    assert "NETWORK-ATTEMPT" not in blocked.stderr, blocked.stderr
    assert blocked.returncode != 99
    payload = json.loads((tmp_path / "agg" / "report.json").read_text(encoding="utf-8"))
    assert payload["header"]["command"] == "report"
    assert len(payload["sources"]) == 2


# ── 三、产物：断网态与常规态逐字节一致 ────────────────────────────────


def test_report_payload_is_byte_identical_without_network(tmp_path: Path) -> None:
    argv = ["tiles", str(FIXTURES / "tile_flip/out/tile_flip.json"), "--json"]
    _run(tmp_path, [*argv, "--out-dir", str(tmp_path / "b")], blocked=True)
    _run(tmp_path, [*argv, "--out-dir", str(tmp_path / "p")], blocked=False)
    assert (tmp_path / "b" / "report.json").read_bytes() == (tmp_path / "p" / "report.json").read_bytes()

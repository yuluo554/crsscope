"""零网络守门（`plan/02` §四）。

判据落在 AST 上：`src/` 里不得出现任何网络客户端 import（`socket` / `http` / `urllib.request` /
`ftplib` / `smtplib` / `telnetlib` / `asyncio` 的 stream 也不允许，因为它是通用 socket 面）。
`urllib.parse` 与 `urllib.error` 是纯字符串/异常工具，**不算网络能力**，放行。

同时配一条**守护门自己的**探活：把 `socket` 拼进一个假文件，断言检测函数真的能抓到——
否则"零命中"可能只是判据从没工作过。
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

#: 硬禁：这些模块一出现就意味着能联网 / 能监听
FORBIDDEN = {
    "socket",
    "ssl",
    "http",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
    "asyncio",
    "requests",
    "urllib3",
    "httpx",
}


def _imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


def _network_hits(source: str) -> set[str]:
    tree = ast.parse(source)
    hits: set[str] = set()
    for name in _imports(tree):
        head = name.split(".")[0]
        if head in FORBIDDEN:
            hits.add(name)
        # urllib 只有 request 面算网络；parse/error 是纯工具
        if name == "urllib" or name.startswith("urllib.request"):
            hits.add(name)
    return hits


def test_detector_sees_a_planted_import() -> None:
    """探活：判据必须能抓到阳性样本，否则"零命中"毫无意义。"""
    assert _network_hits("import socket\n") == {"socket"}
    assert _network_hits("from urllib.request import urlopen\n") == {"urllib.request"}
    assert _network_hits("import urllib.parse\n") == set()


def test_src_has_no_network_imports() -> None:
    offenders: dict[str, set[str]] = {}
    scanned = 0
    for path in sorted(SRC_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        scanned += 1
        hits = _network_hits(path.read_text(encoding="utf-8"))
        if hits:
            offenders[str(path.relative_to(REPO_ROOT))] = hits
    assert scanned > 0, "扫到 0 个源文件——判据空跑"
    assert not offenders, f"出现网络客户端 import: {offenders}"

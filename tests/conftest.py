"""测试共享夹具与路径常量。

**session 级 autouse 的"补齐缺件"**：语料生成物不入仓（`.gitignore` 封 `*.geojson` 等），
干净 clone 上跑测试会缺件。本文件在需要时先跑生成器，**不传 `--suite`**，以确保写出的产物与
入仓版本同内容（否则"跑测试"这个动作会污染入仓文件）。M1 落位前生成器不存在，直接跳过。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
FIXTURES_DIR = REPO_ROOT / "data" / "fixtures"
MASK_DIR = REPO_ROOT / "data" / "mask"

# 让测试不必先 pip install 就能 import 本包（同时这也是"干净环境"里最容易忘的一步）。
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(scope="session", autouse=True)
def ensure_fixtures() -> None:
    """缺件则先跑生成器。生成器不存在（M1 之前）时不做任何事——**不伪造数据**。"""
    if not FIXTURES_DIR.is_dir():
        return
    import subprocess

    for gen in sorted(FIXTURES_DIR.glob("*/gen.py")):
        if (gen.parent / "expect.json").is_file():
            continue
        # 不传 --suite：让写出的 manifest 与入仓版本同内容
        subprocess.run(
            [sys.executable, str(gen), "--out", str(gen.parent)],
            check=True,
            stdout=subprocess.DEVNULL,
        )


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture()
def write_file(tmp_path: Path):
    """写一个临时文本文件，返回路径。用 `newline='\\n'` 保证与仓库口径一致。"""

    def _write(name: str, text: str) -> Path:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    return _write

"""布局门自身的门（方法论装订第②件的自检）。

三条判据，全部落**仓库内文件**，与 `git` 元数据无关：

1. **门不读 git**：`tools/*.py` 里不得出现 `subprocess` / `git` 调用。浅克隆下 tag 与历史深度
   会让判据翻转——这是"本机绿、CI 红"的经典成因，所以要在源码层面钉死。
2. **门在无 `.git` 的树里能跑**（发布包形态）：复制一份仓库、排除 `.git` 与缓存，再跑门必须 exit 0。
   判别 = "这条断言，在一棵刚从 tarball 解出来的树里成立吗？"
3. **门能报出"这轮扫到了几个"**：输出必须含扫描计数行，0 计数时不许报全绿。
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
GATE = TOOLS_DIR / "check-sprint-layout.py"

GIT_TOKENS = ("git", "rev-parse", "ls-files", "check-ignore")


def _all_source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(TOOLS_DIR.glob("*.py")))


def test_gate_files_exist() -> None:
    assert GATE.is_file()
    assert (TOOLS_DIR / "mutate-layout-gate.py").is_file()


def test_gate_does_not_shell_out() -> None:
    """门本身必须纯文件判据：出现 subprocess/socket 就是"读环境"的信号。"""
    for path in sorted(TOOLS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        # 变异脚本要起子进程跑门，是**唯一**允许的例外
        if path.name == "mutate-layout-gate.py":
            continue
        assert "subprocess" not in imported, f"{path.name} 不得起子进程"


def _non_docstring_literals(source: str) -> list[str]:
    """源码里的字符串字面量，**排除 docstring**。

    docstring 是给读者看的说明（本项目就写着"不读 git 元数据"），把它算进扫描面会把
    "解释"判成"命令"——这正是假门族⑤"扫自由文本"的形态。判据只锚**可执行代码里的字面量**。
    """
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    docstrings.add(id(body[0].value))
    return [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    ]


def test_layout_gate_does_not_depend_on_git_tokens() -> None:
    """布局门**可执行代码**里不得出现 git 命令形态的字面量（docstring 不算）。

    只查命令专属标志（`rev-parse` / `ls-files` / `check-ignore`）与 `git `（带尾空格）；
    裸词 `git` 不查——门自己的说明里就写着"不读 git 元数据"。
    """
    command_tokens = ("rev-parse", "ls-files", "check-ignore", "git ")
    offenders = [
        s for s in _non_docstring_literals(GATE.read_text(encoding="utf-8"))
        if any(tok in s for tok in command_tokens)
    ]
    assert not offenders, f"布局门里出现 git 命令形态的字面量: {offenders}"


def test_scanner_sees_planted_git_call() -> None:
    """探活：判据必须能抓到阳性样本，且必须放行 docstring 里的说明句。"""
    planted = '''
"""本门不读 git 元数据。"""
import subprocess
subprocess.run(["rev-parse", "HEAD"])
'''
    found = _non_docstring_literals(planted)
    assert any("rev-parse" in s for s in found)
    assert not any("不读 git" in s for s in found), "docstring 必须被排除"


def test_layout_gate_passes_in_tree_without_git(tmp_path: Path) -> None:
    """发布包形态：无 `.git` 的树里门必须照样能跑（exit 0）。"""
    work = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        work,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "*.pyc", ".pytest_cache", "dist", "build"),
    )
    assert not (work / ".git").exists(), "复制出的树必须没有 .git（否则测的不是发布包形态）"
    proc = subprocess.run(
        [sys.executable, str(work / "tools" / "check-sprint-layout.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "这轮扫到" in proc.stdout, "门必须报出扫描计数（空跑自证）"


def test_gate_reports_zero_hits_as_failure(tmp_path: Path) -> None:
    """构造缺件态：清空 plan/ 后门必须红（证明"全绿"不是恒真）。"""
    work = tmp_path / "repo"
    shutil.copytree(REPO_ROOT, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "dist", "build"))
    for path in (work / "plan").glob("*.md"):
        path.unlink()
    proc = subprocess.run(
        [sys.executable, str(work / "tools" / "check-sprint-layout.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 1, proc.stdout
    assert "FAIL" in proc.stdout


@pytest.mark.parametrize("bad_root", ["/nonexistent/path/xyz"])
def test_gate_usage_error_on_missing_root(bad_root: str) -> None:
    proc = subprocess.run(
        [sys.executable, str(GATE), "--root", bad_root],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 2

"""发布门 `tools/check-release.py` 的守门（HANDOFF-M6 §三B）。

判据分六组，各自可证伪：

1. **SHA256SUMS 复核**：正确清单通过；**篡改一个字节必红**；点名带路径的文件
   （穿越）直接拒绝。
2. **共有文件逐字节比较**：树 × 附件解包树交集为零差异；**篡改附件一个字节必红**
   （HANDOFF-M6 §三B 第 9 条的变异验证）；归档成员含穿越组件拒绝解包。
3. **tag 名白名单**：`-rf`、含空白/元字符/`..` 的 tag 进不了任何 subprocess。
4. **三档端到端**：离线档在合成骨架上全绿（不依赖本仓状态）；--pre-tag 档在真
   git 仓库上"tag 前绿 / 打 tag 后必红"（前置事实翻转）；缺产物必红。
5. **Release 正文版本面**（`REL.BODY_VERSION`，D1 的回归门）：正文点名的产物名
   必须全是当前版本——**错版必红**（阳性对照）、**0 处命中必红**（空跑守卫）、
   全对才绿。判据是纯函数 `body_version_verdict(body, version)`：吃文本不吃网络，
   `gh` 调用留在 `online_checks()` 一侧。
6. **用法**：--online 缺 --tag、双档互斥 → 2。

--online 档的 gh/git 全流程不进单测（要网络与已发布事实）；它的纯核心
（比较 / 复核 / 解包 / 校验 / 正文版本面）由上面各组覆盖，全流程在真实发布时跑一遍并留档。
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"


def _load():
    spec = importlib.util.spec_from_file_location("check_release", TOOLS / "check-release.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass 处理时要能按 __module__ 找回本模块
    spec.loader.exec_module(mod)
    return mod


cr = _load()


# ── 测试脚手架 ────────────────────────────────────────────────────────


def _skeleton(tmp_path: Path) -> Path:
    """合成一个"交付面齐备"的最小仓库骨架（必备文件 + dynamic 版本 + 六子命令 README）。"""
    root = tmp_path / "repo"
    for rel in ("src/crsscope", "tools"):
        (root / rel).mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools>=77"]\n'
        '[project]\nname = "crsscope"\ndynamic = ["version"]\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# crsscope\n\n" + " ".join(f"`crsscope {s}`" for s in cr.SUBCOMMANDS) + "\n",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (root / "src/crsscope/__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    (root / "src/crsscope/cli.py").write_text("", encoding="utf-8")
    (root / "src/crsscope/errors.py").write_text("", encoding="utf-8")
    for name in ("check-sprint-layout.py", "mutate-layout-gate.py", "check-release.py"):
        (root / "tools" / name).write_text("", encoding="utf-8")
    return root


def _fake_dist(root: Path, version: str = "0.1.0") -> Path:
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    names = (f"crsscope-{version}-py3-none-any.whl", f"crsscope-{version}.tar.gz")
    lines = []
    for name in names:
        data = f"payload of {name}".encode()
        (dist / name).write_bytes(data)
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
    (root / cr.SUMS_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dist


def _git_init_commit(root: Path) -> None:
    def git(*argv: str) -> None:
        subprocess.run(["git", "-C", str(root), *argv], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "gate@example.invalid")
    git("config", "user.name", "gate")
    git("add", "-A")
    git("commit", "-q", "-m", "skeleton")


# ── 一、SHA256SUMS 复核 ───────────────────────────────────────────────


def test_sums_verify_roundtrip(tmp_path: Path) -> None:
    dist = _fake_dist(tmp_path)
    assert cr.verify_sums(tmp_path / cr.SUMS_NAME, dist) == [
        "crsscope-0.1.0-py3-none-any.whl",
        "crsscope-0.1.0.tar.gz",
    ]


def test_sums_tampered_byte_must_go_red(tmp_path: Path) -> None:
    """HANDOFF-M6 §三B：故意篡改一个附件字节 → 门必须红。"""
    dist = _fake_dist(tmp_path)
    wheel = dist / "crsscope-0.1.0-py3-none-any.whl"
    data = wheel.read_bytes()
    wheel.write_bytes(data[:-1] + bytes([data[-1] ^ 0x01]))  # 同长度单字节翻转
    with pytest.raises(cr.GateFailure, match="哈希不合"):
        cr.verify_sums(tmp_path / cr.SUMS_NAME, dist)


def test_sums_rejects_traversal_name(tmp_path: Path) -> None:
    sums = tmp_path / cr.SUMS_NAME
    digest = hashlib.sha256(b"x").hexdigest()
    sums.write_text(f"{digest}  ../outside.txt\n", encoding="utf-8")
    with pytest.raises(cr.GateFailure, match="basename"):
        cr.verify_sums(sums, tmp_path)


def test_sums_empty_is_explicit_failure(tmp_path: Path) -> None:
    sums = tmp_path / cr.SUMS_NAME
    sums.write_text("# 只有注释\n", encoding="utf-8")
    with pytest.raises(cr.GateFailure, match="空跑"):
        cr.verify_sums(sums, tmp_path)


# ── 二、共有文件逐字节比较 ─────────────────────────────────────────────


def _tree_and_assets(tmp_path: Path) -> tuple[Path, Path]:
    tree = tmp_path / "tree"
    assets = tmp_path / "unpacked"
    common = {
        "pyproject.toml": "[project]\nname = 'crsscope'\n",
        "README.md": "# crsscope\n",
        "src/crsscope/__init__.py": '__version__ = "0.1.0"\n',
        "src/crsscope/cli.py": "def main():\n    return 0\n",
        "src/crsscope/errors.py": "class E(Exception):\n    pass\n",
    }
    for rel, text in common.items():
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        (tree / rel).write_text(text, encoding="utf-8", newline="\n")
        (assets / rel).parent.mkdir(parents=True, exist_ok=True)
        (assets / rel).write_text(text, encoding="utf-8", newline="\n")
    # 树多出来的文件（tests / .gitignore 等）与附件多出来的（dist_info）不算差异
    (tree / "tests").mkdir()
    (tree / "tests/test_x.py").write_text("x = 1\n", encoding="utf-8")
    (assets / "crsscope-0.1.0.dist-info").mkdir()
    (assets / "crsscope-0.1.0.dist-info/METADATA").write_text("m\n", encoding="utf-8")
    return tree, assets


def test_common_files_zero_diff_and_only_intersection(tmp_path: Path) -> None:
    tree, assets = _tree_and_assets(tmp_path)
    mismatches, count = cr.compare_common_files(tree, [assets])
    assert mismatches == []
    assert count == 5  # 交集判据：只比共有文件，两侧各自独有的不算


def test_common_files_tampered_asset_byte_must_go_red(tmp_path: Path) -> None:
    """HANDOFF-M6 §三B 第 9 条的变异验证：篡改附件一个字节 → 门必须红。"""
    tree, assets = _tree_and_assets(tmp_path)
    target = assets / "src/crsscope/cli.py"
    data = target.read_bytes()
    target.write_bytes(data[:-1] + bytes([data[-1] ^ 0x01]))
    mismatches, count = cr.compare_common_files(tree, [assets])
    assert count == 5
    assert mismatches == ["src/crsscope/cli.py"]


def test_zip_member_traversal_is_rejected(tmp_path: Path) -> None:
    evil = tmp_path / "evil.whl"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../evil.py", "x = 1\n")
    with pytest.raises(cr.GateFailure, match="穿越"):
        cr.unpack_archive(evil, tmp_path / "out")
    assert not (tmp_path / "evil.py").exists()


def test_wheel_layout_is_normalised_to_source_paths(tmp_path: Path) -> None:
    """wheel 是**安装态布局**（`crsscope/x.py`），必须归一化到源树 `src/crsscope/x.py`。

    实测教训：不归一化时共有文件恒为 0，判据报"0 个（下限 5）"——门在真发布时变红，
    但原因不是产物坏了，而是判据没读懂归档布局。
    """
    tree = tmp_path / "tree"
    (tree / "src/crsscope").mkdir(parents=True)
    (tree / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    body = '__version__ = "0.1.0"\n'
    (tree / "src/crsscope/__init__.py").write_text(body, encoding="utf-8")

    wheel = tmp_path / "unpacked"
    (wheel / "crsscope").mkdir(parents=True)
    (wheel / "crsscope/__init__.py").write_text(body, encoding="utf-8")
    (wheel / "crsscope-0.1.0.dist-info").mkdir()
    (wheel / "crsscope-0.1.0.dist-info/METADATA").write_text("m\n", encoding="utf-8")

    mismatches, count = cr.compare_common_files(tree, [wheel])
    assert mismatches == []
    assert count == 1  # 只有 src/crsscope/__init__.py 是共有文件；dist-info 不在源树


def test_sdist_container_directory_is_stripped(tmp_path: Path) -> None:
    """sdist 解包出唯一顶层目录 `crsscope-0.1.0/`；判据必须剥掉它再比。"""
    tree = tmp_path / "tree"
    (tree / "src/crsscope").mkdir(parents=True)
    body = "x = 1\n"
    (tree / "src/crsscope/cli.py").write_text(body, encoding="utf-8")

    sdist = tmp_path / "sdist"
    (sdist / "crsscope-0.1.0/src/crsscope").mkdir(parents=True)
    (sdist / "crsscope-0.1.0/src/crsscope/cli.py").write_text(body, encoding="utf-8")

    mismatches, count = cr.compare_common_files(tree, [sdist])
    assert mismatches == []
    assert count == 1


def test_normalised_common_file_mismatch_is_still_caught(tmp_path: Path) -> None:
    """归一化不能把判据变松：布局对上之后，字节不同仍必须红。"""
    tree = tmp_path / "tree"
    (tree / "src/crsscope").mkdir(parents=True)
    (tree / "src/crsscope/cli.py").write_text("x = 1\n", encoding="utf-8")

    wheel = tmp_path / "unpacked"
    (wheel / "crsscope").mkdir(parents=True)
    (wheel / "crsscope/cli.py").write_text("x = 2\n", encoding="utf-8")

    mismatches, count = cr.compare_common_files(tree, [wheel])
    assert count == 1
    assert mismatches == ["src/crsscope/cli.py"]


# ── 三、tag 名白名单 ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad", ["", "-rf", "a b", "a;b", "x$(y)", "x`y", "..", "a/../b", "a|b"]
)
def test_tag_validation_rejects_hostile_names(bad: str) -> None:
    with pytest.raises(cr.GateFailure):
        cr.validate_tag(bad)


def test_tag_validation_accepts_normal_names() -> None:
    assert cr.validate_tag("v0.1.0") == "v0.1.0"
    assert cr.validate_tag("release/M6") == "release/M6"


# ── 四、三档端到端 ────────────────────────────────────────────────────


def test_offline_tier_green_on_skeleton_without_dist(tmp_path: Path) -> None:
    root = _skeleton(tmp_path)
    assert cr.main(["--root", str(root)]) == 0


def test_offline_tier_reports_zero_artifacts_explicitly(tmp_path: Path, capsys) -> None:
    root = _skeleton(tmp_path)
    cr.main(["--root", str(root)])
    out = capsys.readouterr().out
    assert "0 份产物" in out  # 空跑必须显式报出，不许静默全绿


def test_pre_tag_red_without_dist_then_green_with_dist(tmp_path: Path) -> None:
    root = _skeleton(tmp_path)
    _git_init_commit(root)
    assert cr.main(["--pre-tag", "--root", str(root)]) == 1  # 产物缺失必红
    _fake_dist(root)
    assert cr.main(["--pre-tag", "--root", str(root)]) == 0  # 齐备 + 无 tag → 绿


def test_pre_tag_must_go_red_once_target_tag_exists(tmp_path: Path) -> None:
    """目标 tag 建好后 `--pre-tag` 必红：它守的是"这次要打的 tag 还未创建"。

    **判据不能写成"仓库里一个 tag 都没有"**：发布过一次之后，任何后续版本都永远过不了这一档，
    判据会自己把自己判死（v0.1.1 实测发现）。
    """
    root = _skeleton(tmp_path)
    _git_init_commit(root)
    _fake_dist(root)
    assert cr.main(["--pre-tag", "--root", str(root)]) == 0
    subprocess.run(
        ["git", "-C", str(root), "tag", "-a", "v0.1.0", "-m", "release"],
        check=True,
        capture_output=True,
    )
    # v0.1.0 已存在，但当前版本是 0.1.0 → 目标 tag 就是 v0.1.0 → 必红
    assert cr.main(["--pre-tag", "--root", str(root)]) == 1


def test_pre_tag_green_for_a_new_version_even_when_older_tags_exist(tmp_path: Path) -> None:
    """打过 v0.1.0 之后，为**新版本**（0.2.0）跑 `--pre-tag` 必须能绿。"""
    root = _skeleton(tmp_path)
    (root / "src/crsscope/__init__.py").write_text('__version__ = "0.2.0"\n', encoding="utf-8")
    _git_init_commit(root)
    subprocess.run(
        ["git", "-C", str(root), "tag", "-a", "v0.1.0", "-m", "first"], check=True, capture_output=True
    )
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    _fake_dist(root, version="0.2.0")
    assert cr.main(["--pre-tag", "--root", str(root)]) == 0
    # 显式 --tag 指向一个已存在的 tag → 红
    assert cr.main(["--pre-tag", "--tag", "v0.1.0", "--root", str(root)]) == 1


def test_sums_mismatch_makes_pre_tag_red(tmp_path: Path) -> None:
    root = _skeleton(tmp_path)
    _git_init_commit(root)
    _fake_dist(root)
    sums = root / cr.SUMS_NAME
    lines = sums.read_text(encoding="utf-8").splitlines()
    # 把第一条哈希改成另一个合法形状但错误的值（翻转前 8 个十六进制位）
    head, name = lines[0].split(None, 1)
    lines[0] = head[:8] + ("".join("0" if c != "0" else "1" for c in head[8:16])) + head[16:] + "  " + name
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert cr.main(["--pre-tag", "--root", str(root)]) == 1


# ── 五、Release 正文版本面（REL.BODY_VERSION） ────────────────────────
#
# 背景（D1）：`v0.1.1` 的 Release 正文照抄了上一版的「安装」与「附件」两节，
# 写的是 `crsscope-0.1.0-*.whl`，而附件是 `0.1.1`——照抄那条 `pip install`
# 直接 `No such file or directory`。正文是用户唯一会照抄的地方（从 Releases 页
# 进来的人只看正文），而此前 8 条判据里没有一条读 `body`。
#
# 判据是纯函数：吃正文文本 + 当前版本，不碰 `gh`（单测不能联网）。


def test_body_version_catches_wrong_version() -> None:
    """阳性对照：正文点名 0.1.0 而当前是 0.1.1 → 必红（D1 的原始形态）。"""
    body = (
        "## crsscope v0.1.1\n\n"
        "```bash\n"
        "pip install crsscope-0.1.0-py3-none-any.whl       # wheel\n"
        "pip install crsscope-0.1.0.tar.gz                 # sdist\n"
        "```\n"
    )
    ok, detail = cr.body_version_verdict(body, "0.1.1")
    assert ok is False
    assert "0.1.0" in detail  # 错版必须被点名报出


def test_body_version_zero_hits_is_explicit_failure() -> None:
    """空跑守卫：正文里一处 `crsscope-<x.y.z>-` 都没有 → FAIL，不许静默全绿。"""
    body = "## crsscope v0.1.1\n\n安装方式见 README。\n"
    ok, detail = cr.body_version_verdict(body, "0.1.1")
    assert ok is False
    assert "0 处" in detail


def test_body_version_all_matching_passes() -> None:
    """全对 → PASS（v0.1.1 修正后的形态）。"""
    body = (
        "## crsscope v0.1.1\n\n"
        "```bash\n"
        "pip install crsscope-0.1.1-py3-none-any.whl       # wheel\n"
        "pip install crsscope-0.1.1.tar.gz                 # sdist\n"
        "```\n\n"
        "```\nSHA256SUMS\ncrsscope-0.1.1-py3-none-any.whl\ncrsscope-0.1.1.tar.gz\n```\n"
    )
    ok, detail = cr.body_version_verdict(body, "0.1.1")
    assert ok is True, detail
    assert "4 处" in detail  # 正文的 4 处全部命中（安装 2 + 附件清单 2）


# ── 六、用法 ──────────────────────────────────────────────────────────


def test_online_without_tag_is_usage_error(capsys) -> None:
    assert cr.main(["--online"]) == 2
    assert "--tag" in capsys.readouterr().err


def test_mutually_exclusive_tiers() -> None:
    assert cr.main(["--pre-tag", "--online", "--tag", "v0.1.0"]) == 2

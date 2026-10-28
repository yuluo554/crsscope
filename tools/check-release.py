#!/usr/bin/env python3
"""发布门（M6）· 三档——离线（默认，进 CI）/ --pre-tag（零网络前置）/ --online（已发布事实）。

判据只回答一个问题："**现在能不能把这批产物当发布物**"。

- **离线档（默认）**：判据只落仓库内文件（不读 git 元数据、不联网）——进 CI 的是它。
  `dist/` 与 `SHA256SUMS` 在本档是**条件判据**：在场就逐条复核，不在场显式报
  "0 份产物"（不许静默装作查过）。
- **--pre-tag**：零网络；`dist/` 与 `SHA256SUMS` 在此档**必须**齐备（这是"可以打
  tag"的前置事实），且本地 git 不得已有任何 tag——tag 一旦创建，本档必红：
  它检查的是"tag 还未创建"这一前置事实，不是发布后的状态。
- **--online**：需要网络与已发布事实（`gh release` / `git archive <tag>`）。判据：
  附件与 tag 树解包后的**共有文件**逐字节相等——不是 `diff -r` 零差异
  （附件不含 .git / tests / data 等仅归档侧文件；共有交集至少 MIN_COMMON_FILES
  个，交集为空 = 判据空跑 = FAIL）；`SHA256SUMS` 可复核；README 命令面可跑
  （用 tag 树的 src 起 `--help`，零运行时依赖所以不需要安装）；**Release 正文点名
  的产物文件名必须都是当前版本**（`REL.BODY_VERSION`——正文是用户唯一会照抄的地方，
  写错版本号等于让人敲一条必然失败的 `pip install`）。

退出码：0 全绿 / 1 有 FAIL / 2 用法错误。判据输出与布局门同构：一行一条 PASS/FAIL。

安全边界（本脚本是仓库门，输入一律先过校验）：
- `--tag` 只接受 `[A-Za-z0-9][A-Za-z0-9._/-]*`——以 `-` 开头的值会变成选项，
  含空白/引号的值直接拒绝；所有 subprocess 调用都是参数列表形式（shell=False）。
- `SHA256SUMS` 的文件名必须是纯 basename（不含路径分隔符与 `..`）——它指向的
  文件永远在 base 目录内解析。
- 归档（zip/tar）成员名先校验再解包：拒绝绝对路径与穿越组件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 交付面最小文件集（离线档即可断言，不依赖 git）。
REQUIRED_FILES: tuple[str, ...] = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "src/crsscope/__init__.py",
    "src/crsscope/cli.py",
    "src/crsscope/errors.py",
    "tools/check-sprint-layout.py",
    "tools/mutate-layout-gate.py",
    "tools/check-release.py",
)

#: README 命令面必须点名全部六个子命令（少一个 = 交付面与实现漂移）。
SUBCOMMANDS: tuple[str, ...] = ("decl", "detect", "xdiff", "geojson", "tiles", "report")

#: SHA256SUMS 文件名（生成在仓库根，行格式与 `sha256sum` 一致：`<hex>  <basename>`）。
SUMS_NAME = "SHA256SUMS"

#: 附件解包树与 tag 树的共有文件下限——低于它说明"交集"判据在空跑。
MIN_COMMON_FILES = 5

_TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

#: Release 正文里点名产物文件名的形态（`crsscope-0.1.1-py3-none-any.whl` / `crsscope-0.1.1.tar.gz`）。
#: 只抓 `crsscope-<x.y.z>` 这一段——正文标题里的 `crsscope v0.1.1` 中间是空格，不参与判定。
#:
#: 版本后必须紧跟 `-` 或 `.`：**只写 `crsscope-<x.y.z>-` 会漏掉 `.tar.gz` 两处**（实测：
#: v0.1.1 正文 4 处产物名里 2 处是 wheel、2 处是 sdist，sdist 版本号后跟的是 `.`）。
#: 判据宁可多抓（加严），不许因为形态写得窄而让 2/4 静默通过。
BODY_ASSET_RE = re.compile(r"crsscope-(\d+\.\d+\.\d+)(?=[-.])")


class GateFailure(Exception):
    """单条判据失败（收集到 Gate 里统一报出）。"""


def validate_tag(tag: str) -> str:
    """tag 名先过白名单再进任何 subprocess（防选项注入 / 元字符注入）。"""
    if not _TAG_RE.fullmatch(tag) or ".." in tag:
        raise GateFailure(f"非法 tag 名: {tag!r}（只允许字母数字与 . _ / -，且不以 - 开头）")
    return tag


def safe_basename(name: str) -> str:
    """只接受纯 basename：SHA256SUMS 与归档成员都靠它挡住路径穿越。"""
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
        or PurePosixPath(name).name != name
    ):
        raise GateFailure(f"非法文件名（要求纯 basename，无路径分隔符）: {name!r}")
    return name


def check_archive_member(name: str) -> str:
    """归档成员名必须落在解包目录内：拒绝绝对路径与 `..` 组件。"""
    if name.startswith(("/", "\\")) or ":" in name.split("/")[0] and len(name.split("/")[0]) == 2:
        raise GateFailure(f"归档成员是绝对路径: {name!r}")
    parts = PurePosixPath(name.replace("\\", "/")).parts
    if not parts or any(p == ".." for p in parts):
        raise GateFailure(f"归档成员含穿越组件: {name!r}")
    return name


# ── 判据收集 ──────────────────────────────────────────────────────────


@dataclass
class Entry:
    name: str
    ok: bool
    detail: str


class Gate:
    def __init__(self) -> None:
        self.entries: list[Entry] = []

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.entries.append(Entry(name=name, ok=ok, detail=detail))

    def exit_code(self) -> int:
        return 0 if all(e.ok for e in self.entries) else 1

    def report(self) -> str:
        lines = [f"{'PASS' if e.ok else 'FAIL'}  {e.name}  {e.detail}" for e in self.entries]
        total = len(self.entries)
        bad = sum(1 for e in self.entries if not e.ok)
        lines.append(f"共 {total} 条判据，FAIL {bad} 条")
        return "\n".join(lines)


# ── 共用工具 ──────────────────────────────────────────────────────────


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_version(root: Path) -> str:
    """版本唯一定义处 = `src/crsscope/__init__.py` 的 `__version__`（K02）。"""
    init = root / "src/crsscope/__init__.py"
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise GateFailure("src/crsscope/__init__.py 里找不到 __version__ 字面量")
    return match.group(1)


def parse_sums(text: str) -> list[tuple[str, str]]:
    """`<hex>  <name>`（sha256sum 兼容）。空行与注释行跳过；文件名限纯 basename。"""
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            raise GateFailure(f"SHA256SUMS 行不合法: {line!r}")
        name = parts[1].strip().lstrip("*")
        rows.append((parts[0].lower(), safe_basename(name)))
    return rows


def verify_sums(sums_path: Path, base: Path) -> list[str]:
    """逐行复核 SHA256SUMS；返回通过复核的文件名。任何缺文件/哈希不合都抛 GateFailure。"""
    rows = parse_sums(sums_path.read_text(encoding="utf-8"))
    if not rows:
        raise GateFailure(f"{SUMS_NAME} 里 0 条有效行——判据空跑")
    verified: list[str] = []
    for expected, name in rows:
        target = base / name
        if not target.is_file():
            raise GateFailure(f"{SUMS_NAME} 点名的文件不存在: {name}")
        actual = sha256_file(target)
        if actual != expected:
            raise GateFailure(f"哈希不合: {name}（SUMS {expected[:12]}… != 实测 {actual[:12]}…）")
        verified.append(name)
    return verified


def collect_relative_files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def _candidate_roots(unpacked: Path, tree_files: set[str]) -> list[Path]:
    """候选解包根：先试原样，再试剥掉归档自带的唯一顶层目录（sdist 的 `crsscope-0.1.0/`）。

    **不能无条件剥**：wheel 只有一个顶层包目录 `crsscope/`，剥掉它就丢光 `crsscope/*.py`
    （实测：判据变成 0 个共有文件）。所以每个候选都要求"归一化后能命中 tag 树"才采用。
    """
    entries = [
        p for p in unpacked.iterdir() if p.name != "__pycache__" and not p.name.endswith(".dist-info")
    ]
    dirs = [p for p in entries if p.is_dir()]
    stripped = dirs[0] if len(dirs) == 1 and not any(p.is_file() for p in entries) else None
    roots = [unpacked] + ([stripped] if stripped is not None else [])
    hit = [r for r in roots if _asset_map(r, tree_files)]
    return hit or [unpacked]


def _asset_map(root: Path, tree_files: set[str]) -> dict[str, Path]:
    """附件解包树 → **tag 树相对路径** 的映射。

    两种归档布局都要归一化到源树路径，否则"共有文件"永远为空：
    - **sdist**：`crsscope-<版本>/src/crsscope/x.py` → 剥容器目录 → `src/crsscope/x.py`；
    - **wheel**：`crsscope/x.py`（安装态布局）→ 补 `src/` 前缀 → `src/crsscope/x.py`。

    补前缀只在目标路径**确实存在于 tag 树**时进行（不猜测）；两条都不命中就丢弃该项
    （`*.dist-info/` 之类本来就不在源树里）。
    """
    mapping: dict[str, Path] = {}
    for rel in collect_relative_files(root):
        if rel in tree_files:
            mapping.setdefault(rel, root / rel)
        elif f"src/{rel}" in tree_files:
            mapping.setdefault(f"src/{rel}", root / rel)
    return mapping


def files_byte_equal(a: Path, b: Path) -> bool:
    if a.stat().st_size != b.stat().st_size:
        return False
    return a.read_bytes() == b.read_bytes()


def unpack_archive(archive: Path, dest: Path) -> None:
    """解包一份附件（.whl → zip；.tar.gz/.tgz → tar）。成员名先校验再落盘。"""
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(".whl") or name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                check_archive_member(member)
            zf.extractall(dest)
    elif name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive) as tf:
            for member in tf.getnames():
                check_archive_member(member)
            tf.extractall(dest, filter="data")
    else:
        raise GateFailure(f"附件不是可解包归档: {archive.name}")


def compare_common_files(tree: Path, unpacked_dirs: list[Path]) -> tuple[list[str], int]:
    """附件解包树 × tag 树的**共有文件**逐字节比较。

    返回 `(不一致的相对路径, 共有文件数)`。共有 = 各附件解包树按 `_asset_map` 归一化到
    **tag 树相对路径**后与 tag 树的交集；附件缺 .git / tests / data、树缺 dist 附件——
    两侧各自多出来的不算差异（这正是"不是 `diff -r` 零差异"的含义）。
    """
    tree_files = collect_relative_files(tree)
    merged: dict[str, Path] = {}
    for unpacked in unpacked_dirs:
        for root in _candidate_roots(unpacked, tree_files):
            for rel, path in _asset_map(root, tree_files).items():
                merged.setdefault(rel, path)
    common = sorted(merged)
    mismatches = [rel for rel in common if not files_byte_equal(tree / rel, merged[rel])]
    return mismatches, len(common)


# ── 各档判据 ──────────────────────────────────────────────────────────


def static_checks(gate: Gate, root: Path) -> str:
    """交付面静态判据（三档共用；只读仓库内文件）。返回读到的版本号。"""
    missing = [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]
    gate.add(
        "REL.FILES",
        not missing,
        f"交付面 {len(REQUIRED_FILES)} 个必备文件，缺 {len(missing)} 个"
        + (f": {missing}" if missing else ""),
    )

    version = ""
    try:
        version = read_version(root)
    except GateFailure as exc:
        gate.add("REL.VERSION", False, str(exc))
    if version:
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        dynamic_ok = re.search(r'(?m)^dynamic\s*=\s*\[.*"version".*\]', pyproject) is not None
        static_version = re.search(r'(?m)^version\s*=\s*"', pyproject) is not None
        gate.add(
            "REL.VERSION",
            dynamic_ok and not static_version and bool(version),
            f"版本 {version}；pyproject dynamic 单点: {dynamic_ok}，"
            f"无静态 version 字面量: {not static_version}",
        )

    readme = (root / "README.md").read_text(encoding="utf-8")
    absent = [name for name in SUBCOMMANDS if name not in readme]
    gate.add(
        "REL.README_CMDS",
        not absent,
        f"README 命令面扫到 {len(SUBCOMMANDS) - len(absent)}/{len(SUBCOMMANDS)} 个子命令"
        + (f"，缺 {absent}" if absent else ""),
    )
    return version


def dist_checks(gate: Gate, root: Path, dist: Path, *, required: bool) -> None:
    """dist/ 判据。`required=False`（离线档）时缺件是显式记录的跳过；`True`（--pre-tag）时缺件即红。"""
    artifacts = sorted(p for p in dist.glob("*") if p.is_file()) if dist.is_dir() else []
    wheels = [p for p in artifacts if p.name.endswith(".whl")]
    sdists = [p for p in artifacts if p.name.endswith((".tar.gz", ".tgz"))]
    sums = root / SUMS_NAME

    if not artifacts:
        gate.add(
            "REL.DIST",
            not required,
            "0 份产物"
            + ("（--pre-tag 要求 dist/ 齐备）" if required else "（未构建态：产物判据显式跳过）"),
        )
        gate.add(
            "REL.SUMS",
            not required,
            "无产物，SHA256SUMS 判据一并跳过" if not required else "缺产物，无从复核",
        )
        return

    version = read_version(root)
    version_ok = all(version in p.name for p in wheels + sdists)
    gate.add(
        "REL.DIST",
        bool(wheels) and bool(sdists) and version_ok,
        f"{len(artifacts)} 份产物（wheel {len(wheels)} / sdist {len(sdists)}）；"
        f"文件名含版本 {version}: {version_ok}",
    )

    if not sums.is_file():
        gate.add("REL.SUMS", False, f"仓库根缺 {SUMS_NAME}（产物在场时必须可复核）")
        return
    try:
        verified = verify_sums(sums, dist)
        gate.add("REL.SUMS", True, f"{SUMS_NAME} 复核通过 {len(verified)}/{len(artifacts)} 份产物")
    except GateFailure as exc:
        gate.add("REL.SUMS", False, str(exc))


def pre_tag_checks(gate: Gate, root: Path, dist: Path, tag: str | None = None) -> None:
    """--pre-tag：零网络。唯一读 git 的事实是"**本次要打的这个 tag** 还未创建"。

    首版判据写的是"仓库里没有任何 tag"——发布过一次之后，任何后续版本都永远过不了这一档，
    判据自己把自己判死（第二版实测发现）。正确的前置事实是"目标 tag 名尚不存在"；
    缺省目标名按版本号推 `v<version>`，也可用 `--tag` 显式给。
    """
    static_checks(gate, root)

    target = tag
    if target is None:
        try:
            target = f"v{read_version(root)}"
        except GateFailure:
            target = None
    if target is not None:
        validate_tag(target)

    proc = subprocess.run(
        ["git", "-C", str(root), "tag", "--list"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        gate.add("REL.TAG_ABSENT", False, f"git tag --list 失败: {(proc.stderr or '').strip()[:200]}")
    else:
        existing = {ln.strip() for ln in proc.stdout.splitlines() if ln.strip()}
        if target is None:
            gate.add("REL.TAG_ABSENT", False, "推不出目标 tag 名（版本号读不到）")
        else:
            gate.add(
                "REL.TAG_ABSENT",
                target not in existing,
                f"目标 tag {target} 尚未创建（前置事实成立）"
                if target not in existing
                else f"目标 tag {target} 已存在——本档只用于打 tag 之前（已存在 {len(existing)} 个 tag）",
            )

    dist_checks(gate, root, dist, required=True)


def _run_checked(argv: list[str], *, cwd: Path, what: str) -> str:
    proc = subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if proc.returncode != 0:
        raise GateFailure(
            f"{what} 失败（exit {proc.returncode}）: {(proc.stderr or proc.stdout or '').strip()[:400]}"
        )
    return proc.stdout


def body_version_verdict(body: str, version: str) -> tuple[bool, str]:
    """Release **正文**里点名的产物文件名必须都是当前版本。

    这是纯函数（只吃正文文本），`gh` 调用留在 `main()` / `online_checks()` 一侧——单测不联网。

    三条纪律，全部来自本仓 `MIN_COMMON_FILES` 的同款逻辑：
    - **至少命中 1 处**：0 处 = 判据空跑 = FAIL（正文若改成不带文件名的散文，这条必须红，
      否则它就成了永远绿的装饰）；
    - **全部等于当前版本**：命中集合里去掉当前版本后必须为空集；
    - 判据只认 `crsscope-<x.y.z>-<...>` 这个形态，正文标题里的 `v0.1.1` 不参与（标题用
      `v` 前缀，产物名不用，形态不同是刻意的区分）。
    """
    found = BODY_ASSET_RE.findall(body)
    if not found:
        return False, (
            "Release 正文里 0 处 `crsscope-<x.y.z>-` 形态的产物名——判据空跑"
            "（正文必须点名安装用的文件名，否则用户无从照抄）"
        )
    wrong = sorted({v for v in found if v != version})
    detail = f"正文点名产物 {len(found)} 处，版本分布 {sorted(set(found))}，当前版本 {version}"
    if wrong:
        return False, detail + f"；错版: {wrong}"
    return True, detail


def cli_smoke_checks(gate: Gate, tree: Path) -> None:
    """README 命令面可跑：用 tag 树的 src 直接起 `--help`（零运行时依赖，无需安装）。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tree / "src")
    env["PYTHONUTF8"] = "1"
    runs: list[list[str]] = [["--version"], ["--help"]]
    runs += [[sub, "--help"] for sub in SUBCOMMANDS]
    try:
        ok = True
        detail = ""
        for argv in runs:
            proc = subprocess.run(
                [sys.executable, "-m", "crsscope", *argv],
                cwd=str(tree),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode != 0:
                ok = False
                detail = (
                    f"crsscope {' '.join(argv)} exit {proc.returncode}: "
                    f"{(proc.stderr or '').strip()[:200]}"
                )
                break
        gate.add("REL.SMOKE", ok, detail or f"tag 树 CLI 冒烟 {len(runs)} 条全部 exit 0")
    except OSError as exc:
        gate.add("REL.SMOKE", False, f"无法启动解释器: {exc}")


def online_checks(gate: Gate, root: Path, tag: str, dist: Path) -> None:
    """--online：需要网络与已发布事实。判据落在"已发布"的证据上。"""
    _ = dist  # 附件以 Release 上下载的为准，本地 dist 不参与判据
    validate_tag(tag)
    work = Path(tempfile.mkdtemp(prefix="crs-release-online-"))
    try:
        # ① tag 存在且是 annotated（git 元数据在本档是判据对象，不再是禁区）
        kind = _run_checked(
            ["git", "-C", str(root), "cat-file", "-t", tag], cwd=root, what=f"git cat-file -t {tag}"
        )
        gate.add(
            "REL.ARCHIVE_TAG",
            kind.strip() == "tag",
            f"{tag} 对象类型: {kind.strip() or '不存在'}（annotated tag 应为 tag）",
        )

        # ② tag 树（git archive 解包）
        tree = work / "tree"
        tree.mkdir()
        archive_tar = work / "tag.tar"
        _run_checked(
            ["git", "-C", str(root), "archive", "--format=tar", "--output", str(archive_tar), tag],
            cwd=root,
            what=f"git archive {tag}",
        )
        with tarfile.open(archive_tar) as tf:
            for member in tf.getnames():
                check_archive_member(member)
            tf.extractall(tree, filter="data")
        static_checks(gate, tree)

        # ③ Release 在场且非草稿，附件齐备
        view = _run_checked(
            ["gh", "release", "view", tag, "--json", "assets,isDraft,body"],
            cwd=root,
            what="gh release view",
        )
        info = json.loads(view)
        assets = [a["name"] for a in info.get("assets", [])]
        draft = bool(info.get("isDraft"))
        gate.add(
            "REL.GH_RELEASE",
            bool(assets) and not draft,
            f"Release {tag}: {len(assets)} 份附件（draft={draft}）: {assets[:6]}",
        )

        # ③b 正文点名的产物名必须都是**该 tag 树**的版本（D1 的回归门）
        # 这一条与附件无关，所以放在"附件是否齐备"的早退**之前**——正文写错版的
        # 仓库不该因为附件恰好缺一份就少报一条判据。
        #
        # **版本必须取自 tag 树，不能取工作树**（发布 v0.1.2 时实测踩到）：本档的判据
        # 对象是"那次发布"，工作树版本随时会领先于 tag（改版准备期必然领先）。拿工作树
        # 版本去比旧 tag 的正文，会让 `--online --tag v0.1.1` 在准备 v0.1.2 时**假红**，
        # 而这恰恰是本仓"任何时候都能复核历史发布"的能力本身。tag 树读不到版本时才回退。
        try:
            body_version = read_version(tree)
            version_src = f"{tag} 树"
        except GateFailure:
            try:
                body_version = read_version(root)
                version_src = "工作树（tag 树版本读取失败）"
            except GateFailure:
                body_version = ""
                version_src = ""
        if not body_version:
            gate.add("REL.BODY_VERSION", False, "tag 树与工作树都读不到版本，正文判据无从比较")
        else:
            ok, detail = body_version_verdict(info.get("body") or "", body_version)
            gate.add("REL.BODY_VERSION", ok, f"{detail}（版本源: {version_src}）")

        if draft or not assets:
            return  # 后续判据依赖已下载的附件，这里已红，不再空转

        # ④ 下载附件并复核 SHA256SUMS
        assets_dir = work / "assets"
        assets_dir.mkdir()
        _run_checked(
            ["gh", "release", "download", tag, "--dir", str(assets_dir), "--clobber"],
            cwd=root,
            what="gh release download",
        )
        try:
            verified = verify_sums(assets_dir / SUMS_NAME, assets_dir)
            gate.add("REL.SUMS", True, f"附件 {SUMS_NAME} 复核通过 {len(verified)} 份")
        except GateFailure as exc:
            gate.add("REL.SUMS", False, str(exc))
            return

        # ⑤ 附件 × tag 树共有文件逐字节相等
        unpacked: list[Path] = []
        unpack_fail: list[str] = []
        for name in verified:
            if name.lower().endswith((".whl", ".zip", ".tar.gz", ".tgz")):
                dest = work / "unpacked" / name
                try:
                    unpack_archive(assets_dir / name, dest)
                    unpacked.append(dest)
                except GateFailure as exc:
                    unpack_fail.append(str(exc))
        if unpack_fail:
            gate.add("REL.COMMON_FILES", False, "; ".join(unpack_fail))
        else:
            mismatches, common_n = compare_common_files(tree, unpacked)
            gate.add(
                "REL.COMMON_FILES",
                not mismatches and common_n >= MIN_COMMON_FILES,
                f"共有文件 {common_n} 个（下限 {MIN_COMMON_FILES}），逐字节不一致 {len(mismatches)} 个"
                + (f": {mismatches[:5]}" if mismatches else ""),
            )

        # ⑥ README 命令面可跑（tag 树）
        cli_smoke_checks(gate, tree)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ── 入口 ──────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check-release",
        description="发布门三档：离线（默认）/ --pre-tag / --online",
        epilog="退出码：0 全绿 / 1 有 FAIL / 2 用法错误",
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help="仓库根（默认脚本上一级）")
    parser.add_argument("--dist", default=None, help="产物目录（默认 <root>/dist）")
    tier = parser.add_mutually_exclusive_group()
    tier.add_argument("--pre-tag", action="store_true", help="零网络前置档：tag 尚未创建 + 产物齐备")
    tier.add_argument("--online", action="store_true", help="在线档：核对已发布的 tag / Release 附件")
    parser.add_argument("--tag", default=None, help="--online 档必填：要核对的 tag 名")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse 的用法错误统一成整数返回（与 cli.main 同一形态）
        return int(exc.code or 0)
    if args.online and not args.tag:
        sys.stderr.write("用法错误：--online 需要 --tag <tag>\n")
        return 2

    root = Path(args.root).resolve()
    dist = Path(args.dist).resolve() if args.dist else root / "dist"
    gate = Gate()
    try:
        if args.pre_tag:
            pre_tag_checks(gate, root, dist, args.tag)
        elif args.online:
            online_checks(gate, root, args.tag, dist)
        else:
            static_checks(gate, root)
            dist_checks(gate, root, dist, required=False)
    except GateFailure as exc:
        gate.add("REL.GATE", False, str(exc))
    print(gate.report())
    return gate.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())

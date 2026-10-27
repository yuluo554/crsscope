#!/usr/bin/env python3
"""`data/**/gen.py` 的共用框架 —— 生成器确定性纪律的**唯一落点**（`plan/04` §1.1）。

三条约定由本文件强制，各生成器只写 `build()`：

1. **固定输入 / 无随机 / 无时间依赖**：`build()` 每次调用必须返回**逐字节相同**的内容。
   `--check` 的全部效力就建立在这一点上——它重跑 `build()`，再与冻结产物比字节。
2. **自检写在 `build()` 末尾**：`--check` 不走 `__main__`。自检若写在 `__main__` 里，
   就等于"在门下从没跑过"（这是 M1 最容易踩的形态）。
3. **`expect.json` 只存"输入 + 期望"**：本框架不提供写"观测值"的入口。
   金标里出现 `observed` 一类字段即视为违规（`tests/test_fixtures.py` 递归扫键名）。

产物分两类，`--check` 对它们**判据不同**：

- `expect.json` —— 入仓金标，**缺失即 FAIL**（金标是契约）；
- `out/**` —— 语料生成物，`.gitignore` 封禁，干净 clone 上**必然缺失**。
  缺失只报"未落盘"并给 `--out` 提示，不 FAIL——否则 `--check` 在干净 clone 上恒红，
  而"恒红的门"和"从不红的门"等价。存在时**逐字节**比对（冻结产物 vs 重生成）。

用法：每个生成器末尾

    if __name__ == "__main__":
        raise SystemExit(FixtureRun(NAME, VERSION, build, here=_HERE).main())
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

#: 入仓金标名。缺失 = FAIL（语料可以重建，金标不能凭空出现）。
REQUIRED_ARTIFACT = "expect.json"

#: 生成物目录（相对 fixture 根）。目录下不属于本次产物的文件 = 陈旧残留 → FAIL。
OUT_DIR = "out"


def dumps_json(obj: object, *, indent: int | None = 2) -> str:
    """确定性 JSON：键序固定、中文不转义、末尾单个换行（与 `report.dumps_json` 同口径）。

    `indent=None` 用于**大网格**（掩膜）：一格一行的缩进版会让文件膨胀十倍，
    而网格是生成物（不入仓、不做人读 diff），紧凑单行更合适。
    """
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=indent) + "\n"


def dumps_geojson(obj: object) -> str:
    """GeoJSON 走同一序列化口径（`sort_keys` 只影响键序，不影响可解析性）。"""
    return dumps_json(obj)


def repo_src() -> Path:
    """返回本仓库 `src/` 目录，供生成器 import 生产包（`plan/06` §六：前向变换只服务生成器）。"""
    return Path(__file__).resolve().parent.parent / "src"


def add_src_to_path() -> None:
    """把 `src/` 塞进 `sys.path`。

    必要性：生成器既会被 `py -3.12 data/.../gen.py` 直接跑（未安装本包），
    也会被 `tests/conftest.py` 以 **子进程** 跑（不继承 pytest 的 `sys.path` 补丁）。
    两条通道都必须能 import 到 `crsscope`，否则干净 clone 上补齐缺件这一步直接崩。
    """
    src = str(repo_src())
    if src not in sys.path:
        sys.path.insert(0, src)


# ── 语料构造小工具（只拼 dict，不做判定）────────────────────────────────

def point_feature(fid: str, lon: float, lat: float) -> dict:
    return {
        "type": "Feature",
        "id": fid,
        "properties": {"id": fid},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def feature_collection(features: list[dict], **extra: object) -> dict:
    fc: dict = {"type": "FeatureCollection", "features": features}
    fc.update(extra)
    return fc




def _ensure_utf8_stdio() -> None:
    """中文控制台（cp936 管道）下不许因编码崩，也不把编码问题伪装成判据失败。"""
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", "") or "").lower()
        if enc.replace("-", "") in {"utf8", "utf_8"}:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover - 老终端兜底
            pass


class FixtureRun:
    """一个 fixture 生成器的运行框架。`build()` 返回 `{相对路径: 文本内容}`。"""

    def __init__(
        self,
        name: str,
        version: str,
        build: Callable[[], dict[str, str]],
        *,
        here: Path,
    ) -> None:
        self.name = name
        self.version = version
        self.build = build
        self.here = here

    # ── 入口 ────────────────────────────────────────────────────────────
    def main(self, argv: list[str] | None = None) -> int:
        _ensure_utf8_stdio()
        parser = argparse.ArgumentParser(
            prog=f"{self.name}/gen.py",
            description=f"生成 data fixture `{self.name}`（固定输入、无随机、无时间依赖）。",
        )
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--out", type=Path, metavar="DIR", help="写出金标与语料生成物")
        group.add_argument("--check", action="store_true", help="重生成并与冻结产物逐字节比对")
        args = parser.parse_args(argv)

        try:
            files = self.build()
        except AssertionError as exc:
            print(f"FAIL  {self.name} 自检失败（build() 末尾的断言）: {exc}")
            return 1

        if REQUIRED_ARTIFACT not in files:
            print(f"FAIL  {self.name} build() 未产出 {REQUIRED_ARTIFACT} —— 金标是契约，不许缺")
            return 1

        print(f"{self.name} · 自检通过（build() 末尾断言全过）")
        if args.out is not None:
            return self._write(args.out.resolve(), files)
        return self._check(self.here, files)

    # ── --out ───────────────────────────────────────────────────────────
    def _write(self, base: Path, files: dict[str, str]) -> int:
        for rel in sorted(files):
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = files[rel].encode("utf-8")
            path.write_bytes(payload)
            print(f"  写出 {rel} ({len(payload)} B)")
        print(f"共 {len(files)} 个文件 → {base}")
        return 0

    # ── --check ─────────────────────────────────────────────────────────
    def _check(self, base: Path, files: dict[str, str]) -> int:
        problems: list[str] = []
        matched = 0
        missing: list[str] = []
        for rel in sorted(files):
            path = base / rel
            fresh = files[rel].encode("utf-8")
            if not path.is_file():
                if rel == REQUIRED_ARTIFACT:
                    problems.append(f"{rel} 缺失 —— 金标必须入仓，不许靠 --out 现补")
                else:
                    missing.append(rel)
                continue
            frozen = path.read_bytes()
            if frozen == fresh:
                matched += 1
            else:
                problems.append(
                    f"{rel} 与重生成结果不一致（冻结 {len(frozen)} B / 重生成 {len(fresh)} B）"
                )

        extra = self._stale_artifacts(base, files)
        for rel in extra:
            problems.append(f"{rel} 是产物目录里的陈旧残留（本次 build() 不产出它）")

        summary = (
            f"CHECK 逐字节一致 {matched}/{len(files)}；"
            f"未落盘 {len(missing)}（不入仓，可 --out 补齐）；残留 {len(extra)}"
        )
        print(summary)
        if missing:
            print(f"  未落盘: {', '.join(missing)}")
        if problems:
            for p in problems:
                print(f"FAIL  {p}")
            print(f"结论: {len(problems)} 项与冻结产物不一致")
            return 1
        print("结论: 与冻结产物逐字节一致")
        return 0

    @staticmethod
    def _stale_artifacts(base: Path, files: dict[str, str]) -> list[str]:
        out_dir = base / OUT_DIR
        if not out_dir.is_dir():
            return []
        return sorted(
            p.relative_to(base).as_posix()
            for p in out_dir.rglob("*")
            if p.is_file() and p.relative_to(base).as_posix() not in files
        )

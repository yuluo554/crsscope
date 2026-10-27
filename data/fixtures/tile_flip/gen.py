#!/usr/bin/env python3
"""F6 · `tile_flip` —— `y` 轴翻转（XYZ vs TMS）与 `y` 越界（`plan/04` §一 / F6）。

判据来源（`data/README.md` §4.7）：

| 项 | 口径 |
|---|---|
| `y` 轴混用 | 同一 `z` 下同时出现 `y` 与 `(2^z - 1 - y)` 且两者都指向同一 bbox → `axis_flip` |
| `y` 越界 | `y ∉ [0, 2^z - 1]` → `error`（**单点即判**，静态可检） |
| 跨 180° | `x` 环绕必须显式记录 `wrap: true` |

**语料是纯 `z/x/y` 数字**，不含任何地物、不需要底图——这正是"静态检出"的含义（题面 §M5）。
金标里的 `flipped_y` 由 `2**z - 1 - y` **直接算出**（`math` 全量交叉验证，`plan/04` §二）。

四组用例：

| 用例 | 内容 | 期望 |
|---|---|---|
| `case-001` `xyz_vs_tms` | `z=5` 同时出现 `y=3` 与 `y=2^5-1-3=28`，且注释指向同一 bbox | `axis_flip: true` |
| `case-002` `y_out_of_range` | `z=3, y=9`（`2^3-1=7`） | `y_range: error`，单点即判 |
| `case-003` `wrap_declared` | 跨日界线的 `x` 环绕，显式 `wrap: true` | `wrap` 通过 |
| `case-004` `wrap_missing` | 同样跨日界线但**缺** `wrap` 标记 | `wrap: conflict` |

跑法：

    py -3.12 data/fixtures/tile_flip/gen.py --out data/fixtures/tile_flip
    py -3.12 data/fixtures/tile_flip/gen.py --check
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in _HERE.parents:
    if (_p / "_genlib.py").is_file():
        sys.path.insert(0, str(_p))
        break
else:  # pragma: no cover
    raise SystemExit("tile_flip/gen.py: 向上找不到 data/_genlib.py")

from _genlib import FixtureRun, dumps_json  # noqa: E402

NAME = "tile_flip"
VERSION = "1"

#: `case-001`：同一 bbox 的两种 `y` 写法。`z=5` → 32 行。
FLIP_Z = 5
FLIP_Y_XYZ = 3
FLIP_Y_TMS = 2**FLIP_Z - 1 - FLIP_Y_XYZ  # = 28

#: `case-002`：`z=3` 只有 0..7，写 9 必越界。
RANGE_Z = 3
RANGE_Y = 9


def build() -> dict[str, str]:
    tiles = {
        "format": "z/x/y",
        "note": "纯瓦片编号，不含地物；y 轴语义见 data/README.md §4.7",
        "cases": [
            {
                "id": "case-001",
                "role": "xyz_vs_tms",
                "bbox": [116.0, 39.0, 117.0, 40.0],
                "tiles": [
                    {"z": FLIP_Z, "x": 26, "y": FLIP_Y_XYZ, "scheme": "xyz"},
                    {"z": FLIP_Z, "x": 26, "y": FLIP_Y_TMS, "scheme": "tms"},
                ],
            },
            {
                "id": "case-002",
                "role": "y_out_of_range",
                "tiles": [{"z": RANGE_Z, "x": 3, "y": RANGE_Y, "scheme": "xyz"}],
            },
            {
                "id": "case-003",
                "role": "wrap_declared",
                "tiles": [
                    {"z": 2, "x": 3, "y": 1, "wrap": True},
                    {"z": 2, "x": 0, "y": 1, "wrap": True},
                ],
            },
            {
                "id": "case-004",
                "role": "wrap_missing",
                "tiles": [
                    {"z": 2, "x": 3, "y": 1},
                    {"z": 2, "x": 0, "y": 1},
                ],
            },
        ],
    }

    # ── 金标：全部由 `2**z` 算术直接推出（可手算复算）────────────────────
    cases = []
    for case in tiles["cases"]:
        rows = 2**case["tiles"][0]["z"]
        entry = {"id": case["id"], "role": case["role"]}
        if case["id"] == "case-001":
            ys = sorted(t["y"] for t in case["tiles"])
            entry["expected"] = {
                "axis_flip": True,
                "flipped_y": FLIP_Y_TMS,
                "flip_formula": "2**z - 1 - y",
                "same_bbox": True,
                "row_span": [0, rows - 1],
            }
            assert ys == sorted([FLIP_Y_XYZ, FLIP_Y_TMS])
        elif case["id"] == "case-002":
            entry["expected"] = {
                "y_range": "error",
                "allowed": [0, rows - 1],
                "offending_y": RANGE_Y,
                "single_point_sufficient": True,
            }
        elif case["id"] == "case-003":
            entry["expected"] = {"wrap": "ok", "wrap_declared": True}
        else:
            entry["expected"] = {"wrap": "conflict", "wrap_declared": False}
        cases.append(entry)

    files = {"out/tile_flip.json": dumps_json(tiles)}
    expect = {
        "fixture": NAME,
        "generator_version": VERSION,
        "notes": (
            "金标由 2**z - 1 - y 直接算出，不含任何观测值。"
            "axis_flip 要求两枚瓦片指向同一 bbox 且互为翻转；y 越界单点即判。"
        ),
        "cases": cases,
    }
    files["expect.json"] = dumps_json(expect)

    # ── 自检（build() 末尾，--check 也走这里）──────────────────────────
    assert FLIP_Y_TMS == 28 and FLIP_Y_XYZ + FLIP_Y_TMS == 2**FLIP_Z - 1
    assert FLIP_Y_XYZ != FLIP_Y_TMS
    assert RANGE_Y > 2**RANGE_Z - 1, "越界样本必须真的越界"
    # 全量交叉验证：对 z ∈ [0,10] 的每个 y，翻转两次必须回到自身
    for z in range(0, 11):
        n = 2**z - 1
        for y in range(0, n + 1):
            assert n - y >= 0 and n - (n - y) == y, f"z={z} y={y} 翻转不闭合"
    by_id = {c["id"]: c["expected"] for c in cases}
    assert by_id["case-001"]["axis_flip"] is True
    assert by_id["case-002"]["y_range"] == "error"
    assert by_id["case-003"]["wrap"] == "ok"
    assert by_id["case-004"]["wrap"] == "conflict"
    assert len(files) == 2, f"产物应为语料 + 金标，实得 {sorted(files)}"
    return files


if __name__ == "__main__":
    raise SystemExit(FixtureRun(NAME, VERSION, build, here=_HERE).main())

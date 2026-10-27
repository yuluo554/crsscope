#!/usr/bin/env python3
"""M1 · `mask-v1` —— 离线极低分辨率陆水网格（`plan/04` §四 / `data/README.md` §2.1）。

**这份网格不是地理真值。** 它是**构造**出来的：若干矩形块按经纬度摆放，没有任何真实
海岸线数据（检索窗口内没能核对任何真实全球陆水数据的许可，见 `data/README.md` §二）。
它只有三个用途：演示"落水率"启发式、固定分母口径、给下游模块一个可回归的固定输入。
报告必须同时输出 `mask_version` 与 `mask_max_resolution_deg`，并声明这一点。

**格式**（`mask.load_mask` 的契约）：

```json
{"version": "...", "resolution_deg": 1.0, "lon_min": -180.0, "lat_min": -85.0,
 "n_lon": 360, "n_lat": 170, "cells": [{"lat_idx": 0, "lon_idx": 0, "value": "land"}, ...]}
```

`cells` 按 `(lat_idx, lon_idx)` 索引，值 ∈ `land | water | unknown`。

**为什么步长正好 1°**：`data/README.md` §4.3 规定首期**上限 1°**；`mask.MAX_RESOLUTION_DEG`
是硬上限，超限直接 `EnvironmentMissing`（exit 3）。1° 既合法又是最省体积的选择。

**覆盖率自检**（`plan/04` §四 明确要求打印）：`unknown_ratio` / `coastal_ratio` 必须由
生成器自己算一遍并打印。它们与 `mask.MaskStats.as_header()` 的**同名字段同义**
（`unknown` 不计入落水分母；海岸带单独计数），但本文件**独立实现**——不得 import
`crsscope.mask`，否则"自检"就变成了复述被测物。

跑法：

    py -3.12 data/mask/gen.py --out data/mask
    py -3.12 data/mask/gen.py --check
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
    raise SystemExit("mask/gen.py: 向上找不到 data/_genlib.py")

from _genlib import FixtureRun, dumps_json  # noqa: E402

NAME = "mask"
VERSION = "v1"

#: 首期分辨率（度）。`data/README.md` §4.3 的**上限**也是 1.0（`mask.MAX_RESOLUTION_DEG`）。
RESOLUTION_DEG = 1.0
LON_MIN = -180.0
LAT_MIN = -85.0
N_LON = 360  # −180 … 180
N_LAT = 170  # −85 … 85（Web Mercator 的纬度上限处截断，避免极区奇点）

LAND = "land"
WATER = "water"
UNKNOWN = "unknown"

#: 构造陆块：`(lon_min, lon_max, lat_min, lat_max)`，**闭区间**的格索引范围。
#: 这些矩形是**人为摆的**，不对应任何真实陆地；名字也刻意用序号而非地名
#: （`data/README.md` §三.3：不出现真实地名）。
LAND_BLOCKS = (
    (-10.0, 40.0, 5.0, 45.0),  # 块 A
    (60.0, 140.0, 0.0, 55.0),  # 块 B
    (95.0, 125.0, 20.0, 45.0),  # 块 C（与 B 重叠，构造嵌套以便出现内陆）
    (-120.0, -70.0, -50.0, 60.0),  # 块 D
    (110.0, 160.0, -45.0, -10.0),  # 块 E
)

#: `unknown` 区域：刻意留出两块，用来验证"unknown 不进分母"这条纪律真的被下游执行。
#: 未覆盖的格子默认 `water`（不是 `unknown`）——否则整张图会被 unknown 淹没。
UNKNOWN_BLOCKS = (
    (-180.0, -170.0, 70.0, 85.0),  # 北极附近一条
    (170.0, 180.0, -85.0, -75.0),  # 南极附近一条
)

#: 抽样格（`plan/04` §2.1：金标 = 输入 + 期望）。每格由 (lon, lat) 定位、给出期望取值。
#: 这些点覆盖 land / water / unknown 三类，且数量 ≥ 5（与 §4.1 的样本下限同量级）。
SAMPLES = (
    (20.0, 25.0, LAND),  # 块 A 内部
    (100.0, 30.0, LAND),  # 块 B ∩ C 重叠处
    (0.0, -40.0, WATER),  # 南大西洋
    (175.0, -80.0, UNKNOWN),  # 南极附近 unknown 条
    (-175.0, 78.0, UNKNOWN),  # 北极附近 unknown 条
    (60.0, 0.0, LAND),  # 块 B 的南边缘内侧
)


def _idx(lon: float, lat: float) -> tuple[int, int]:
    """格索引。与 `mask.Mask.index_of` 同一算式（金标要能从坐标复算）。"""
    return int((lat - LAT_MIN) // RESOLUTION_DEG), int((lon - LON_MIN) // RESOLUTION_DEG)


def _in_block(lon: float, lat: float, block: tuple[float, float, float, float]) -> bool:
    lon_min, lon_max, lat_min, lat_max = block
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def _cell_value(row: int, col: int) -> str:
    if not (0 <= row < N_LAT and 0 <= col < N_LON):
        return UNKNOWN
    # 格中心反算经纬度：判定用中心，避免"半个格在块内"的歧义
    lon = LON_MIN + (col + 0.5) * RESOLUTION_DEG
    lat = LAT_MIN + (row + 0.5) * RESOLUTION_DEG
    if any(_in_block(lon, lat, b) for b in UNKNOWN_BLOCKS):
        return UNKNOWN
    if any(_in_block(lon, lat, b) for b in LAND_BLOCKS):
        return LAND
    return WATER


def _is_coastal(row: int, col: int, cells: dict[tuple[int, int], str]) -> bool:
    """四邻存在异类即海岸带（与 `mask.Mask.is_coastal` 同语义；unknown 邻格不算证据）。"""
    here = cells[(row, col)]
    if here not in (LAND, WATER):
        return False
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        there = cells.get((row + dr, col + dc), UNKNOWN)
        if there in (LAND, WATER) and there != here:
            return True
    return False


def _coverage(cells: dict[tuple[int, int], str]) -> dict:
    """覆盖率自检：独立实现，**不 import `crsscope.mask`**（自检不许复述被测物）。"""
    total = len(cells)
    counts = {LAND: 0, WATER: 0, UNKNOWN: 0}
    for value in cells.values():
        counts[value] += 1
    coastal = sum(1 for idx in cells if _is_coastal(idx[0], idx[1], cells))
    evaluable = counts[LAND] + counts[WATER] - coastal
    return {
        "cells_total": total,
        "land_cells": counts[LAND],
        "water_cells": counts[WATER],
        "unknown_cells": counts[UNKNOWN],
        "coastal_cells": coastal,
        "unknown_ratio": round(counts[UNKNOWN] / total, 6) if total else 0.0,
        "coastal_ratio": round(coastal / total, 6) if total else 0.0,
        "evaluable_cells": evaluable,
    }


def build() -> dict[str, str]:
    cells = {
        (row, col): _cell_value(row, col)
        for row in range(N_LAT)
        for col in range(N_LON)
    }
    coverage = _coverage(cells)

    mask = {
        "version": VERSION,
        "resolution_deg": RESOLUTION_DEG,
        "lon_min": LON_MIN,
        "lat_min": LAT_MIN,
        "n_lon": N_LON,
        "n_lat": N_LAT,
        "kind": "constructed",
        "disclaimer": "掩膜为构造低分辨率网格，非地理真值；仅用于固定落水启发式的口径",
        "cells": [
            {"lat_idx": row, "lon_idx": col, "value": value}
            for (row, col), value in sorted(cells.items())
        ],
    }

    expect = {
        "fixture": NAME,
        "generator_version": VERSION,
        "notes": (
            "构造的 1° 陆水网格，非地理真值。cells 按 (lat_idx, lon_idx) 索引，"
            "取值 land/water/unknown；unknown 与海岸带不计入落水分母（data/README.md §4.2）。"
        ),
        "mask": {
            "version": VERSION,
            "resolution_deg": RESOLUTION_DEG,
            "lon_min": LON_MIN,
            "lat_min": LAT_MIN,
            "n_lon": N_LON,
            "n_lat": N_LAT,
        },
        "coverage": coverage,
        "cases": [
            {
                "id": f"case-{i:03d}",
                "lon": lon,
                "lat": lat,
                "expected": {
                    "cell": want,
                    "row": _idx(lon, lat)[0],
                    "col": _idx(lon, lat)[1],
                    # 海岸带 = 四邻存在 land/water 异类（unknown 邻格不算证据）
                    "coastal": _is_coastal(_idx(lon, lat)[0], _idx(lon, lat)[1], cells),
                },
            }
            for i, (lon, lat, want) in enumerate(SAMPLES, start=1)
        ],
        "expected": {
            # 下游报告必须报这几个字段（§4.3）
            "required_header_fields": [
                "mask_version",
                "mask_max_resolution_deg",
                "unknown_ratio",
                "coastal_ratio",
                "evaluable_points",
            ],
            "max_resolution_deg": RESOLUTION_DEG,
            # unknown 与 coastal 必须都真的出现过，否则这两条纪律在掩膜上无从验证
            "has_unknown_cells": coverage["unknown_cells"] > 0,
            "has_coastal_cells": coverage["coastal_cells"] > 0,
        },
    }

    files = {
        "out/mask_v1.json": dumps_json(mask, indent=None),
        "expect.json": dumps_json(expect),
    }

    # ── 覆盖率自检打印（plan/04 §四 明确要求）────────────────────────────
    print(f"mask 覆盖率自检：格数 {coverage['cells_total']}"
          f" / land {coverage['land_cells']} / water {coverage['water_cells']}"
          f" / unknown {coverage['unknown_cells']}")
    print(f"  unknown_ratio = {coverage['unknown_ratio']}"
          f"   coastal_ratio = {coverage['coastal_ratio']}"
          f"   evaluable_cells = {coverage['evaluable_cells']}")

    # ── 自检（build() 末尾，--check 也走这里）──────────────────────────
    assert RESOLUTION_DEG <= 1.0, "§4.3 首期上限 1°，超限即拒绝加载"
    assert len(cells) == N_LON * N_LAT, "网格必须完整覆盖"
    assert set(cells.values()) <= {LAND, WATER, UNKNOWN}, "取值只能在 land/water/unknown"
    assert coverage["unknown_cells"] > 0, "unknown 必须真的出现，否则该纪律无从验证"
    assert coverage["coastal_cells"] > 0, "海岸带必须真的出现，否则该纪律无从验证"
    assert 0.0 < coverage["unknown_ratio"] < 1.0, "unknown 占比必须在合理区间"
    assert coverage["evaluable_cells"] < coverage["land_cells"] + coverage["water_cells"], (
        "海岸带已从可判定格中扣除——否则分母口径没实现"
    )
    # 抽样复算：几处已知块的取值必须与块定义一致
    for lon, lat, want in SAMPLES:
        row, col = _idx(lon, lat)
        assert cells[(row, col)] == want, f"({lon},{lat}) 期望 {want} 实得 {cells[(row, col)]}"
    assert len(files) == 2, f"产物应为网格 + 金标，实得 {sorted(files)}"
    return files


if __name__ == "__main__":
    raise SystemExit(FixtureRun(NAME, VERSION, build, here=_HERE).main())

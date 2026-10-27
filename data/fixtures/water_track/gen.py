#!/usr/bin/env python3
"""F5 · `water_track` —— D2 类场景：被 GCJ-02 偏移的陆上轨迹（`plan/04` §一 / F5）。

**场景**（`data/README.md` §1.4 的 D2 原话："people are not really running through lakes"）：
一条真实轨迹走在陆地上，但它以 **GCJ-02** 写入。若把这份数据直接当 WGS84，
轨迹就整条落到相邻的水面上；按 GCJ02 假设反解回去，落水率应当**归零**。

**为什么本 fixture 自带更细的掩膜**：GCJ-02 位移约 250–600 m，1° 网格里连格子边界都跨不过去，
"落水"就永远造不出来。`data/README.md` §4.3 的 **1° 是上限**（`MAX_RESOLUTION_DEG`），
更细的网格合法——本 fixture 用 `resolution_deg = 0.0008`（≈ 89 m）作为"用户自备 `--mask`"
的演示。它同样是**构造网格、非地理真值**，报告必须原样报出分辨率。

**海岸带纪律的影响**（`mask.MaskStats` / §4.2）：与异类相邻的格算 `coastal`、不进分母。
因此：陆带取 **3 格厚**、点落在**中间行**（中间行的四邻全是陆）；GCJ 落点必须离陆带
**≥ 2 行**，否则它自己是海岸带、被排除出分母，落水率会退化成 `undecidable`。
`_check_layering()` 用**与 `mask.Mask` 相同的格索引算式**逐点断言这三条——几何关系
是这份语料的前提，不是巧合。

跑法：

    py -3.12 data/fixtures/water_track/gen.py --out data/fixtures/water_track
    py -3.12 data/fixtures/water_track/gen.py --check
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
    raise SystemExit("water_track/gen.py: 向上找不到 data/_genlib.py")

from _genlib import FixtureRun, add_src_to_path, dumps_json  # noqa: E402

add_src_to_path()

from crsscope import algorithms  # noqa: E402

NAME = "water_track"
VERSION = "1"

# ── 掩膜几何（构造网格，约 89 m 一格）─────────────────────────────────────
RESOLUTION_DEG = 0.0008
LON_MIN = 110.000
LAT_MIN = 29.990
N_LON = 200  # → 110.000–110.160
N_LAT = 18  # → 29.990–30.0044

#: 陆带占 3 格厚，中间行 `LAND_MID` 是唯一"四邻全陆"的行。
LAND_MID = 11
LAND_ROWS = (LAND_MID - 1, LAND_MID, LAND_MID + 1)

#: 真值轨迹纬度 = 陆带中间行的**格中心**（离上下格线各半格，避开边界抖动）。
TRUE_LAT = LAT_MIN + (LAND_MID + 0.5) * RESOLUTION_DEG

#: 轨迹：真值经度 110.020 起、步长 0.004、共 31 点（≥ §4.3 的 30 点下限）。
TRACK_LON_START = 110.020
TRACK_LON_STEP = 0.004
TRACK_POINTS = 31


def _row(lat: float) -> int:
    """掩膜行号。与 `mask.Mask.index_of` 同一算式——金标因此可从坐标直接复算格子。"""
    return int((lat - LAT_MIN) // RESOLUTION_DEG)


def _col(lon: float) -> int:
    return int((lon - LON_MIN) // RESOLUTION_DEG)


def _value(row: int, col: int) -> str:
    if not (0 <= row < N_LAT and 0 <= col < N_LON):
        return "unknown"
    return "land" if LAND_ROWS[0] <= row <= LAND_ROWS[2] else "water"


def _is_coastal(row: int, col: int) -> bool:
    """四邻存在异类即海岸带（与 `mask.Mask.is_coastal` 同语义；`unknown` 邻格不算证据）。"""
    here = _value(row, col)
    if here not in ("land", "water"):
        return False
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        there = _value(row + dr, col + dc)
        if there in ("land", "water") and there != here:
            return True
    return False


def _landing(lon: float, lat: float) -> dict:
    row, col = _row(lat), _col(lon)
    return {
        "landing": [round(lon, 9), round(lat, 9)],
        "row": row,
        "col": col,
        "cell": _value(row, col),
        "coastal": _is_coastal(row, col),
    }


def _mask_cells() -> list[dict]:
    return [
        {"lat_idx": row, "lon_idx": col, "value": _value(row, col)}
        for row in range(N_LAT)
        for col in range(N_LON)
    ]


def _gpx(points: list[tuple[float, float]]) -> str:
    """最小 GPX：只有 trkpt。时间戳刻意缺席（时间只是从属输入，`plan/01` §一）。"""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="crsscope-fixture" xmlns="http://www.topografix.com/GPX/1/1">',
        "  <trk><name>demo-001</name><trkseg>",
    ]
    lines += [f'    <trkpt lat="{lat:.9f}" lon="{lon:.9f}"/>' for lon, lat in points]
    lines += ["  </trkseg></trk>", "</gpx>", ""]
    return "\n".join(lines)


def build() -> dict[str, str]:
    true_points = [(TRACK_LON_START + TRACK_LON_STEP * i, TRUE_LAT) for i in range(TRACK_POINTS)]
    # 语料 = 同一物理轨迹的 GCJ-02 表示（"厂商给的坐标就是 GCJ-02"）
    gcj_points = [algorithms.wgs84_to_gcj02(lon, lat) for lon, lat in true_points]
    bd_points = [algorithms.bd09_to_wgs84(*g) for g in gcj_points]

    mask = {
        "version": "water-track-v1",
        "resolution_deg": RESOLUTION_DEG,
        "lon_min": LON_MIN,
        "lat_min": LAT_MIN,
        "n_lon": N_LON,
        "n_lat": N_LAT,
        "kind": "constructed",
        "disclaimer": "掩膜为构造网格，非地理真值；仅用于固定落水启发式的口径",
        "cells": _mask_cells(),
    }

    hypotheses = {
        # 假设 WGS84：输入原样不动 → 落在水面上（这就是 D2 的故障形态）
        "WGS84": _landing(*gcj_points[0]),
        # 假设 GCJ02：反解回真值 → 落在陆带中线
        "GCJ02": _landing(*true_points[0]),
        # 假设 BD09：反解过了头 → 也落在水面（但与 WGS84 落点不同）
        "BD09": {**_landing(bd_points[0].lon, bd_points[0].lat), "converged": bd_points[0].converged},
    }

    files = {
        "out/water_track.gpx": _gpx(gcj_points),
        "out/water_track_mask.json": dumps_json(mask, indent=None),
    }

    expect = {
        "fixture": NAME,
        "generator_version": VERSION,
        "notes": (
            "真实轨迹在陆地上、以 GCJ-02 写入。掩膜为构造网格（0.0008°，约 89 m）："
            "§4.3 的 1° 是上限，更细合法。陆带 3 格厚使中间行不是海岸带；"
            "偏移落点离陆带 ≥ 2 行，否则会被当海岸带排除出分母。"
        ),
        "mask": {
            "path": "out/water_track_mask.json",
            "version": mask["version"],
            "resolution_deg": RESOLUTION_DEG,
            "land_rows": list(LAND_ROWS),
            "n_lon": N_LON,
            "n_lat": N_LAT,
        },
        "cases": [
            {
                "id": "case-001",
                "role": "water_track_d2",
                "encoding": "gcj02",
                "track": {
                    "path": "out/water_track.gpx",
                    "points": TRACK_POINTS,
                    "true_lat": round(TRUE_LAT, 9),
                    "lon_start": TRACK_LON_START,
                    "lon_step": TRACK_LON_STEP,
                },
                "expected": {
                    "evaluable_points": TRACK_POINTS,
                    # 落水率按 §4.2：可判定点 = 掩膜非 unknown 且非 coastal
                    "water_ratio": {"WGS84": 1.0, "GCJ02": 0.0, "BD09": 1.0},
                    "winner": "GCJ02",
                    "confidence": "high",  # 领先第二名 1.0 ≥ 0.15
                    "hypotheses": hypotheses,
                },
            }
        ],
    }
    files["expect.json"] = dumps_json(expect)

    # ── 自检（build() 末尾，--check 也走这里）──────────────────────────
    assert TRACK_POINTS >= 30, "§4.3 的可判定点下限是 30"
    _check_layering(true_points, gcj_points, bd_points)
    assert hypotheses["GCJ02"]["cell"] == "land" and not hypotheses["GCJ02"]["coastal"]
    assert hypotheses["WGS84"]["cell"] == "water" and not hypotheses["WGS84"]["coastal"]
    assert hypotheses["BD09"]["cell"] == "water" and not hypotheses["BD09"]["coastal"]
    assert hypotheses["BD09"]["converged"] is True
    # 位移幅度必须远大于网格分辨率，否则"落水"是浮点噪声造出来的
    assert abs(gcj_points[0][1] - true_points[0][1]) > 2 * RESOLUTION_DEG, "位移不足 2 格"
    assert len(files) == 3, f"产物应为 GPX + 掩膜 + 金标，实得 {sorted(files)}"
    return files

def _check_layering(true_points, gcj_points, bd_points) -> None:
    """逐点断言：真值在陆带中线且非海岸带；GCJ / BD09 落点在水域、离陆带 ≥ 2 行、非海岸带。"""
    for (tlon, tlat), (glon, glat), bd in zip(true_points, gcj_points, bd_points, strict=True):
        trow, tcol = _row(tlat), _col(tlon)
        assert trow == LAND_MID, f"真值行 {trow} 必须是陆带中线 {LAND_MID}"
        assert _value(trow, tcol) == "land"
        assert not _is_coastal(trow, tcol), f"真值格 ({trow},{tcol}) 被算成海岸带"
        # 整条轨迹都必须留在掩膜内（越界 = unknown = 退化成 undecidable）
        for lon, lat, tag in (
            (glon, glat, "GCJ02"),
            (bd.lon, bd.lat, "BD09"),
            (tlon, tlat, "true"),
        ):
            assert _value(_row(lat), _col(lon)) != "unknown", f"{tag} 落点越出掩膜"
        grow, gcol = _row(glat), _col(glon)
        assert _value(grow, gcol) == "water", f"GCJ 落点 ({grow},{gcol}) 应在水域"
        assert abs(grow - LAND_MID) >= 2, f"GCJ 落点行 {grow} 距陆带中线 {LAND_MID} 不足 2 行"
        assert not _is_coastal(grow, gcol), f"GCJ 落点 ({grow},{gcol}) 被算成海岸带"
        brow, bcol = _row(bd.lat), _col(bd.lon)
        assert _value(brow, bcol) == "water", f"BD09 落点 ({brow},{bcol}) 应在水域"
        assert abs(brow - LAND_MID) >= 2
        assert not _is_coastal(brow, bcol), f"BD09 落点 ({brow},{bcol}) 被算成海岸带"


if __name__ == "__main__":
    raise SystemExit(FixtureRun(NAME, VERSION, build, here=_HERE).main())

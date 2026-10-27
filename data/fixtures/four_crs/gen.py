#!/usr/bin/env python3
"""F1 · `four_crs` —— 同一个物理点写成四种坐标表示（`plan/04` §一）。

四份文件互为**同一地点的不同表示**：WGS84 / GCJ-02 / BD-09 / WebMercator(3857)。
金标记录**任两份之间的位移**（米，`data/README.md` §4.4 口径），以及**逆向收敛性**。

两条纪律：

1. 前向变换只在生成器里用（`plan/06` §六）：本工具不提供 `convert` 命令。
2. **`not_converged` 也要有金标**（`plan/04` §二）：`case-004` 在 gcoord 口径下定点迭代
   到上限仍不收敛——金标写 `inverse_converged: false` 与 `iterations: 100`。
   不允许"不收敛就悄悄给个看起来对的值"。

跑法：

    py -3.12 data/fixtures/four_crs/gen.py --out data/fixtures/four_crs
    py -3.12 data/fixtures/four_crs/gen.py --check
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in _HERE.parents:  # 向上找 data/_genlib.py（本文件在 data/fixtures/<name>/ 下）
    if (_p / "_genlib.py").is_file():
        sys.path.insert(0, str(_p))
        break
else:  # pragma: no cover - 目录被搬走才会到这里
    raise SystemExit("four_crs/gen.py: 向上找不到 data/_genlib.py")

from _genlib import (  # noqa: E402
    FixtureRun,
    add_src_to_path,
    dumps_geojson,
    dumps_json,
    feature_collection,
    point_feature,
)

add_src_to_path()

from crsscope import algorithms, geodesy  # noqa: E402

NAME = "four_crs"
VERSION = "1"

#: 构造用点：东海海面，半整数，两库边界框内（所以 GCJ / BD-09 都会真实偏移）。
POINTS = ((124.5, 32.0), (124.6, 32.1), (124.7, 32.2))

#: `case-004` 的不收敛输入（gcoord 闭区间内、coordTransform_py 开区间外）。
NON_CONVERGED = (72.05, 0.83)


def _r(value: float, digits: int = 9) -> float:
    return round(value, digits)


def _m(value: float) -> float:
    """距离金标：0.1 m（`data/README.md` §4.4）。"""
    return round(value, 1)


def build() -> dict[str, str]:
    wgs, gcj, bd09, merc = [], [], [], []
    for i, (lon, lat) in enumerate(POINTS, start=1):
        fid = f"demo-{i:03d}"
        g = algorithms.wgs84_to_gcj02(lon, lat)
        b = algorithms.wgs84_to_bd09(lon, lat)
        m = algorithms.wgs84_to_webmercator(lon, lat)
        wgs.append(point_feature(fid, _r(lon), _r(lat)))
        gcj.append(point_feature(fid, _r(g[0]), _r(g[1])))
        bd09.append(point_feature(fid, _r(b[0]), _r(b[1])))
        merc.append(point_feature(fid, _r(m[0], 6), _r(m[1], 6)))

    files = {
        "out/four_crs_wgs84.geojson": dumps_geojson(feature_collection(wgs)),
        "out/four_crs_gcj02.geojson": dumps_geojson(feature_collection(gcj)),
        "out/four_crs_bd09.geojson": dumps_geojson(feature_collection(bd09)),
        "out/four_crs_webmercator.geojson": dumps_geojson(feature_collection(merc)),
    }

    cases = []
    for i, (lon, lat) in enumerate(POINTS, start=1):
        g = algorithms.wgs84_to_gcj02(lon, lat)
        b = algorithms.wgs84_to_bd09(lon, lat)
        m = algorithms.wgs84_to_webmercator(lon, lat)
        inv = algorithms.gcj02_to_wgs84_iterative(*g)
        cases.append(
            {
                "id": f"case-{i:03d}",
                "role": "four_representations",
                "wgs84": [_r(lon), _r(lat)],
                "gcj02": [_r(g[0]), _r(g[1])],
                "bd09": [_r(b[0]), _r(b[1])],
                "webmercator": [_r(m[0], 6), _r(m[1], 6)],
                "expected": {
                    # 三对位移全部按 §4.4 的 haversine 口径（金标是"输入 + 期望"，不是观测）
                    "offset_m": {
                        "wgs84_to_gcj02": _m(geodesy.haversine_m(lon, lat, *g)),
                        "wgs84_to_bd09": _m(geodesy.haversine_m(lon, lat, *b)),
                        "gcj02_to_bd09": _m(geodesy.haversine_m(g[0], g[1], *b)),
                    },
                    "inverse_converged": inv.converged,
                    "inverse_iterations": inv.iterations,
                    "inverse_round_trip_m": _m(geodesy.haversine_m(inv.lon, inv.lat, lon, lat)),
                },
            }
        )

    nl = algorithms.gcj02_to_wgs84_iterative(*NON_CONVERGED, algorithms.PROFILE_GCOORD)
    cases.append(
        {
            "id": "case-004",
            "role": "not_converged",
            "gcj02": [_r(NON_CONVERGED[0]), _r(NON_CONVERGED[1])],
            "expected": {
                # 迭代到上限仍不收敛：结论必须显式报 not_converged，不得静默返回近似值
                "inverse_converged": nl.converged,
                "inverse_iterations": nl.iterations,
                "in_china": {
                    algorithms.PROFILE_CT_PY: algorithms.in_china(
                        *NON_CONVERGED, algorithms.PROFILE_CT_PY
                    ),
                    algorithms.PROFILE_GCOORD: algorithms.in_china(
                        *NON_CONVERGED, algorithms.PROFILE_GCOORD
                    ),
                },
            },
        }
    )

    expect = {
        "fixture": NAME,
        "generator_version": VERSION,
        "notes": (
            "四个表示是同一地点的不同写法；位移金标按 data/README.md §4.4 的 haversine 口径。"
            "case-004 的金标是 not_converged —— 不收敛是结论的一部分。"
        ),
        "cases": cases,
    }
    files["expect.json"] = dumps_json(expect)

    # ── 自检（必须在 build() 末尾：--check 不走 __main__）────────────────
    assert len(cases) == len(POINTS) + 1, "用例数与点数不符"
    for case in cases[: len(POINTS)]:
        offs = case["expected"]["offset_m"]
        assert offs["wgs84_to_gcj02"] > 0, "境内点必须发生 GCJ-02 偏移"
        assert offs["wgs84_to_bd09"] > offs["wgs84_to_gcj02"], "BD-09 应在 GCJ-02 之上再偏一次"
        assert case["expected"]["inverse_converged"] is True
        assert case["expected"]["inverse_round_trip_m"] <= 0.2, "迭代逆向往返应在 0.1 m 量级"
    assert cases[-1]["expected"]["inverse_converged"] is False, "不收敛样本必须落在金标里"
    assert cases[-1]["expected"]["inverse_iterations"] == algorithms.INVERSE_MAX_ITER
    assert cases[-1]["expected"]["in_china"][algorithms.PROFILE_CT_PY] is False
    assert cases[-1]["expected"]["in_china"][algorithms.PROFILE_GCOORD] is True
    assert len(files) == 5, f"产物应为 4 份语料 + 金标，实得 {sorted(files)}"
    return files


if __name__ == "__main__":
    raise SystemExit(FixtureRun(NAME, VERSION, build, here=_HERE).main())

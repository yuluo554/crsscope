#!/usr/bin/env python3
"""F7 · `geojson_struct` —— RFC 7946 结构面语料（`plan/04` §一 / F7）。

覆盖 `plan/03` §四的七项检查，其中**三项是 check-geojson README 明示不查的**
（环方向 / 坐标精度 / `crs` 成员）——题面 §M4 的验收就压在这三项上。

| 用例 | 内容 | 级别（`data/README.md` §4.6） |
|---|---|---|
| `case-001` | 外环顺时针（违反 R1） | `warning`（R2 决定级别；`--strict-ring` 才升 error） |
| `case-002` | 外环逆时针（合规对照） | 无发现 |
| `case-003` | 内环（洞）顺时针（合规） | 无发现 |
| `case-004` | `bbox = [177, -20, -178, -16]` 跨 180° | `info`（合法，R4） |
| `case-005` | `geometry: null` + `properties: null` | `info`（合法，R6） |
| `case-006` | 带 `crs` 成员 | `warning`，措辞 "no longer used"（R5） |
| `case-007` | 单分量小数位 12 位 | `warning`（precision，§4.6 阈值 > 9） |
| `case-008` | `GeometryCollection` 嵌套两层 | `info`（结构自洽） |
| `case-009` | 坐标对只有 1 个元素 | `error`（结构破碎） |

**环方向用 Shoelace 符号判定**，本文件**独立实现**一份（不复用 `crsscope.geojson`——
那还是没实现的骨架，更重要的是金标不许引用被测实现）。

`expect.json` 里只写"输入 + 期望级别"，不写任何 `observed` 字段。

跑法：

    py -3.12 data/fixtures/geojson_struct/gen.py --out data/fixtures/geojson_struct
    py -3.12 data/fixtures/geojson_struct/gen.py --check
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
    raise SystemExit("geojson_struct/gen.py: 向上找不到 data/_genlib.py")

from _genlib import FixtureRun, dumps_geojson, dumps_json  # noqa: E402

NAME = "geojson_struct"
VERSION = "1"

#: 精度阈值：单分量小数位 **> 9** → warning（`data/README.md` §4.6）。
PRECISION_WARN_DIGITS = 9

#: 合规的外环（逆时针 CCW，右手法则 R1 满足）。三个点必须不共线。
RING_CCW = [[112.0, 5.0], [113.0, 5.0], [112.5, 6.0], [112.0, 5.0]]
#: 违反 R1 的外环（顺时针 CW）= 把 CCW 的顶点次序反过来。
RING_CW = [[112.0, 5.0], [112.5, 6.0], [113.0, 5.0], [112.0, 5.0]]
#: 洞（内环必须顺时针 CW 才合规）
RING_HOLE_CW = [[112.2, 5.2], [112.3, 5.5], [112.4, 5.2], [112.2, 5.2]]


def shoelace_sign(ring: list[list[float]]) -> int:
    """环方向：`+1` 逆时针（CCW）/ `-1` 顺时针（CW）/ `0` 退化。

    标准 Shoelace 公式：`sum(x_i * y_{i+1} - x_{i+1} * y_i)`。正值 = CCW。
    独立实现（不复用生产模块），因为金标要与被测实现相互独立。
    """
    total = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i + 1][0], ring[i + 1][1]
        total += x1 * y2 - x2 * y1
    if total > 0:
        return 1
    if total < 0:
        return -1
    return 0


#: 与 `None` 区分开：`properties=None` 是**合法的 JSON null**（RFC 7946 §3.2 / case-005），
#: 不能被"省略参数就用默认 dict"的逻辑吞掉（2026-10-27 M5 实测修正）。
_UNSET = object()


def _feature(fid: str, geometry: object, properties: object = _UNSET) -> dict:
    return {
        "type": "Feature",
        "id": fid,
        "properties": {"id": fid} if properties is _UNSET else properties,
        "geometry": geometry,
    }


def _fc(features: list[dict], **extra: object) -> dict:
    fc: dict = {"type": "FeatureCollection", "features": features}
    fc.update(extra)
    return fc


def build() -> dict[str, str]:
    files: dict[str, str] = {}
    cases: list[dict] = []

    # case-001：外环顺时针 → 违反 R1 → warning（R2：解析器 SHOULD NOT 拒绝）
    files["out/case-001_ring_cw.geojson"] = dumps_geojson(
        _fc([_feature("demo-001", {"type": "Polygon", "coordinates": [RING_CW]})])
    )
    cases.append(
        {
            "id": "case-001",
            "role": "ring_order_violation",
            "file": "out/case-001_ring_cw.geojson",
            "expected": {
                "check": "ring_order",
                "status": "warning",  # 默认级别；--strict-ring 才升 error
                "status_with_strict_ring": "error",
                "ring_sign": shoelace_sign(RING_CW),
                "cites_r1": True,
                "cites_r2": True,
            },
        }
    )

    # case-002 / case-003：合规几何（外环 CCW + 洞 CW）→ 无发现
    files["out/case-002_ring_ccw.geojson"] = dumps_geojson(
        _fc([_feature("demo-002", {"type": "Polygon", "coordinates": [RING_CCW]})])
    )
    cases.append(
        {
            "id": "case-002",
            "role": "ring_order_ok",
            "file": "out/case-002_ring_ccw.geojson",
            "expected": {
                "check": "ring_order",
                "status": "consistent",
                "ring_sign": shoelace_sign(RING_CCW),
            },
        }
    )
    files["out/case-003_polygon_with_hole.geojson"] = dumps_geojson(
        _fc([_feature("demo-003", {"type": "Polygon", "coordinates": [RING_CCW, RING_HOLE_CW]})])
    )
    cases.append(
        {
            "id": "case-003",
            "role": "ring_order_ok_with_hole",
            "file": "out/case-003_polygon_with_hole.geojson",
            "expected": {
                "check": "ring_order",
                "status": "consistent",
                "exterior_sign": shoelace_sign(RING_CCW),
                "hole_sign": shoelace_sign(RING_HOLE_CW),
            },
        }
    )

    # case-004：bbox 跨 180°（west > east）—— R4 明确合法，只出 info
    files["out/case-004_bbox_antimeridian.geojson"] = dumps_geojson(
        _fc(
            [_feature("demo-004", {"type": "Point", "coordinates": [179.5, -18.0]})],
            bbox=[177.0, -20.0, -178.0, -16.0],
        )
    )
    cases.append(
        {
            "id": "case-004",
            "role": "bbox_antimeridian",
            "file": "out/case-004_bbox_antimeridian.geojson",
            "expected": {
                "check": "bbox",
                "status": "info",
                "west_greater_than_east": True,
                "is_error": False,  # R4：跨 180° 合法
            },
        }
    )

    # case-005：geometry: null + properties: null —— R6 明确合法，只出 info
    files["out/case-005_null_geometry.geojson"] = dumps_geojson(
        _fc([_feature("demo-005", None, properties=None)])
    )
    cases.append(
        {
            "id": "case-005",
            "role": "null_geometry",
            "file": "out/case-005_null_geometry.geojson",
            "expected": {
                "checks": ["null_geometry"],
                "status": "info",
                "geometry_is_null": True,
                "properties_is_null": True,
                "is_error": False,  # R6：unlocated feature 合法
            },
        }
    )

    # case-006：crs 成员存在 → warning，措辞 "no longer used"（**不是**强制禁用表述）
    files["out/case-006_crs_member.geojson"] = dumps_geojson(
        _fc(
            [_feature("demo-006", {"type": "Point", "coordinates": [112.0, 5.0]})],
            crs={"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        )
    )
    cases.append(
        {
            "id": "case-006",
            "role": "crs_member_present",
            "file": "out/case-006_crs_member.geojson",
            "expected": {
                "check": "crs_member",
                "status": "warning",
                "wording_must_contain": "no longer used",
                "wording_must_not_be_coercive": True,
            },
        }
    )

    # case-007：单分量 12 位小数 → 超 9 位阈值 → warning
    over_precise = [112.123456789012, 5.123456789012]
    files["out/case-007_precision.geojson"] = dumps_geojson(
        _fc([_feature("demo-007", {"type": "Point", "coordinates": over_precise})])
    )
    cases.append(
        {
            "id": "case-007",
            "role": "excess_precision",
            "file": "out/case-007_precision.geojson",
            "expected": {
                "check": "precision",
                "status": "warning",
                "fraction_digits": len("123456789012"),
                "threshold_digits": PRECISION_WARN_DIGITS,
            },
        }
    )

    # case-008：GeometryCollection 两层嵌套（结构自洽 → info）
    files["out/case-008_geometry_collection.geojson"] = dumps_geojson(
        _fc(
            [
                _feature(
                    "demo-008",
                    {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [112.0, 5.0]},
                            {
                                "type": "GeometryCollection",
                                "geometries": [
                                    {"type": "Point", "coordinates": [112.5, 5.5]},
                                    {"type": "LineString", "coordinates": [[112.0, 5.0], [112.5, 5.5]]},
                                ],
                            },
                        ],
                    },
                )
            ]
        )
    )
    cases.append(
        {
            "id": "case-008",
            "role": "geometry_collection_nested",
            "file": "out/case-008_geometry_collection.geojson",
            "expected": {"check": "nesting", "status": "info", "depth": 2, "is_error": False},
        }
    )

    # case-009：坐标对只有 1 个元素 → 结构破碎 → error
    files["out/case-009_bad_coord.geojson"] = dumps_geojson(
        _fc([_feature("demo-009", {"type": "Point", "coordinates": [112.0]})])
    )
    cases.append(
        {
            "id": "case-009",
            "role": "malformed_coordinate",
            "file": "out/case-009_bad_coord.geojson",
            "expected": {
                "check": "structure",
                "status": "error",
                "coordinate_length": 1,
                "min_length": 2,
            },
        }
    )

    expect = {
        "fixture": NAME,
        "generator_version": VERSION,
        "notes": (
            "覆盖 plan/03 §四 的七项检查。环方向由本文件独立实现 Shoelace 判定；"
            "case-001 的默认级别是 warning —— 级别由 R2（parsers SHOULD NOT reject）决定，"
            "--strict-ring 是唯一升级路径。"
        ),
        "rfc": {
            "r1": "A linear ring MUST follow the right-hand rule with respect to the area it bounds.",
            "r2": "For backwards compatibility, parsers SHOULD NOT reject Polygons that do not follow the right-hand rule.",
        },
        "cases": cases,
    }
    files["expect.json"] = dumps_json(expect)

    # ── 自检（build() 末尾，--check 也走这里）──────────────────────────
    assert shoelace_sign(RING_CCW) == 1, "合规外环必须判为逆时针"
    assert shoelace_sign(RING_CW) == -1, "违规外环必须判为顺时针"
    assert shoelace_sign(RING_HOLE_CW) == -1, "洞必须顺时针"
    assert RING_CW == list(reversed(RING_CCW)), "违规环就是合规环的顶点反转"
    assert len("123456789012") > PRECISION_WARN_DIGITS, "精度样本必须真的超阈值"
    assert cases[3]["expected"]["is_error"] is False, "跨 180° 不得报 error（R4）"
    assert cases[4]["expected"]["is_error"] is False, "null geometry 不得报错（R6）"
    assert cases[0]["expected"]["status"] == "warning", "环方向默认只能 warning（R2）"
    assert cases[0]["expected"]["status_with_strict_ring"] == "error"
    assert len(files) == 10, f"产物应为 9 份语料 + 金标，实得 {len(files)}"
    return files


if __name__ == "__main__":
    raise SystemExit(FixtureRun(NAME, VERSION, build, here=_HERE).main())

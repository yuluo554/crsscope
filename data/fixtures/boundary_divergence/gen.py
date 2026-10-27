#!/usr/bin/env python3
"""F4 · `boundary_divergence` —— 两库"中国边界框"结论不同的可复现样本（`plan/04` §一 / F4）。

**金标纪律（本文件最重要的一条）**：两套边界框常数**在这里照录**并**直接代入**判定，
**不 import `crsscope.algorithms`**。理由见 `plan/04` §二「参考实现三落点位」：
金标若复用生产实现，就是"用被测物证明被测物"，`--check` 绿灯不再有信息量。

常数出处（`data/README.md` §1.3，原样照录）：

- `coordTransform_py` 的 `out_of_china`：`lng ∈ (73.66, 135.05) ∧ lat ∈ (3.86, 53.55)` —— **开区间**
- `gcoord` 的 `isInChinaBbox`：`lon ∈ [72.004, 137.8347] ∧ lat ∈ [0.8293, 55.8271]` —— **闭区间**

四例（`plan/00` 决策 ⑥：**不编造分歧**——5°N 两库都判境内，只能作对照）：

| 用例 | 坐标 | 结论 |
|---|---|---|
| `case-001` | (73.2°E, 39.5°N) | 经向分歧：`73.2 < 73.66` → 开区间判境外；闭区间判境内 |
| `case-002` | (112.0°E, 2.0°N) | 纬向分歧：`2.0 < 3.86` → 开区间判境外；闭区间判境内 |
| `case-003` | (112.0°E, 5.0°N) | 一致对照：两库都判境内 |
| `case-004` | (112.0°E, 60.0°N) | 一致对照：两库都判境外 |

跑法：

    py -3.12 data/fixtures/boundary_divergence/gen.py --out data/fixtures/boundary_divergence
    py -3.12 data/fixtures/boundary_divergence/gen.py --check
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
    raise SystemExit("boundary_divergence/gen.py: 向上找不到 data/_genlib.py")

from _genlib import FixtureRun, dumps_geojson, dumps_json, feature_collection, point_feature  # noqa: E402

NAME = "boundary_divergence"
VERSION = "1"

# ── 两套常数（照录 data/README.md §1.3，**本文件独立持有，不 import 生产实现**）──
#: wandergis/coordTransform_py `out_of_china`：开区间
CT_PY_LON = (73.66, 135.05)
CT_PY_LAT = (3.86, 53.55)
#: hujiulong/gcoord `isInChinaBbox`：闭区间
GCOORD_LON = (72.004, 137.8347)
GCOORD_LAT = (0.8293, 55.8271)


def ct_py_in_china(lon: float, lat: float) -> bool:
    """开区间：端点算**境外**。"""
    return CT_PY_LON[0] < lon < CT_PY_LON[1] and CT_PY_LAT[0] < lat < CT_PY_LAT[1]


def gcoord_in_china(lon: float, lat: float) -> bool:
    """闭区间：端点算**境内**。"""
    return GCOORD_LON[0] <= lon <= GCOORD_LON[1] and GCOORD_LAT[0] <= lat <= GCOORD_LAT[1]


#: `(id, lon, lat, role)`。坐标取海洋或无人区、整数或半整数点（`data/README.md` §三.3）。
CASES = (
    ("case-001", 73.2, 39.5, "longitude_divergence"),
    ("case-002", 112.0, 2.0, "latitude_divergence"),
    ("case-003", 112.0, 5.0, "agreement_inside"),
    ("case-004", 112.0, 60.0, "agreement_outside"),
)


def _label(inside: bool) -> str:
    return "inside" if inside else "outside"


def build() -> dict[str, str]:
    features = []
    cases = []
    for cid, lon, lat, role in CASES:
        ct = ct_py_in_china(lon, lat)
        gc = gcoord_in_china(lon, lat)
        agree = ct is gc
        features.append(point_feature(cid, lon, lat))
        cases.append(
            {
                "id": cid,
                "lon": lon,
                "lat": lat,
                "coordTransform_py": _label(ct),
                "gcoord": _label(gc),
                "agree": agree,
                "expected": {
                    "role": role,
                    # 与 `xdiff` 的 boundary_table 行同形，M4 可直接逐字段对拍
                    "boundary_table_row": {
                        "lon": lon,
                        "lat": lat,
                        "coordTransform_py": _label(ct),
                        "gcoord": _label(gc),
                        "agree": agree,
                    },
                    # jump = 两库对"是否偏移"给出相反结论 → 同一坐标喂两个实现，输出不连续
                    "jump": not agree,
                },
            }
        )

    files = {"out/boundary_divergence.geojson": dumps_geojson(feature_collection(features))}
    expect = {
        "fixture": NAME,
        "generator_version": VERSION,
        "notes": (
            "两套边界框常数照录自 data/README.md §1.3，在本文件内独立代入判定，不复用 "
            "crsscope.algorithms。5°N 两库都判境内（决策 ⑥），只作一致对照，不构成分歧。"
        ),
        "cases": cases,
    }
    files["expect.json"] = dumps_json(expect)

    # ── 自检（build() 末尾，--check 也走这里）──────────────────────────
    by_id = {c["id"]: c for c in cases}
    assert by_id["case-001"]["coordTransform_py"] == "outside"
    assert by_id["case-001"]["gcoord"] == "inside"
    assert by_id["case-001"]["agree"] is False and by_id["case-001"]["expected"]["jump"] is True
    assert by_id["case-002"]["coordTransform_py"] == "outside", "2.0°N < 3.86°N 必须判境外"
    assert by_id["case-002"]["gcoord"] == "inside"
    assert by_id["case-002"]["agree"] is False
    assert by_id["case-003"]["agree"] is True and by_id["case-003"]["expected"]["jump"] is False
    assert by_id["case-004"]["agree"] is True and by_id["case-004"]["expected"]["jump"] is False
    # 分歧必须真的落在"两库都能判定"的域内，而不是被某一侧的 NaN / 边界噪声造出来
    assert all(abs(c["lon"]) <= 180 and abs(c["lat"]) <= 90 for c in cases)
    # 开/闭区间的差异必须在本文件里可观察（端点语义不是装饰）
    assert ct_py_in_china(CT_PY_LON[0], 39.5) is False, "开区间端点不算境内"
    assert gcoord_in_china(GCOORD_LON[0], 39.5) is True, "闭区间端点算境内"
    assert len(files) == 2, f"产物应为语料 + 金标，实得 {sorted(files)}"
    return files


if __name__ == "__main__":
    raise SystemExit(FixtureRun(NAME, VERSION, build, here=_HERE).main())

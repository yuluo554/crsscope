#!/usr/bin/env python3
"""F2 · `swapped_axis` —— `(lon, lat)` 被写成 `(lat, lon)`（`plan/04` §一）。

**必须是模块 M1「轴序」能单独命中**的样本：
- 至少 5 个**可判定样本**（`data/README.md` §4.1 的样本下限，`< 5` → `undecidable`）；
- 每个可判定样本满足 `|a| ≤ 180 ∧ |b| ≤ 180`，且 **`|b| > 90` 而 `|a| ≤ 90`**
  （第二分量越出纬度域、第一分量仍在经度域 → 呈 `(lat, lon)` 形态）；
- 这些点**量级全在度域**（`m ≤ 180`），所以量级判据不会误报——两条判据互不串扰。

金标记录"哪个点越界在哪个分量"与"纠正后的坐标"，纠正值 = 交换两分量（纯算术，可复算）。

跑法：

    py -3.12 data/fixtures/swapped_axis/gen.py --out data/fixtures/swapped_axis
    py -3.12 data/fixtures/swapped_axis/gen.py --check
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
    raise SystemExit("swapped_axis/gen.py: 向上找不到 data/_genlib.py")

from _genlib import (  # noqa: E402
    FixtureRun,
    dumps_geojson,
    dumps_json,
    feature_collection,
    point_feature,
)

NAME = "swapped_axis"
VERSION = "1"

#: 真值点（lon, lat）。全部取海洋/无人区的半整数点：|lon| > 90 使写反后一眼可判。
TRUE_POINTS = (
    (112.0, 5.0),
    (112.5, 5.5),
    (113.0, 6.0),
    (113.5, 6.5),
    (114.0, 7.0),
    (114.5, 7.5),
)


def build() -> dict[str, str]:
    features = []
    cases = []
    for i, (lon, lat) in enumerate(TRUE_POINTS, start=1):
        fid = f"demo-{i:03d}"
        # 写反：GeoJSON 的 [lon, lat] 位置放的是 lat，第二格放的是 lon
        written = [lat, lon]
        features.append(point_feature(fid, written[0], written[1]))
        cases.append(
            {
                "id": f"case-{i:03d}",
                "role": "swapped_axis",
                "input": written,
                "expected": {
                    # §4.1：第二分量越出纬度域而第一分量仍在经度域 → conflict/reason=axis
                    "decidable": True,
                    "second_component_out_of_lat_range": abs(written[1]) > 90,
                    "first_component_within_lon_range": abs(written[0]) <= 90,
                    "axis": "conflict",
                    "reason": "axis",
                    "corrected": [lon, lat],
                },
            }
        )

    files = {
        "out/swapped_axis.geojson": dumps_geojson(feature_collection(features)),
    }

    expect = {
        "fixture": NAME,
        "generator_version": VERSION,
        "notes": (
            "坐标以 [lat, lon] 写入 [lon, lat] 的位置；金标里的 corrected 是纯交换（可手算复算）。"
            "样本数 ≥ 5，满足 data/README.md §4.1 的可判定样本下限。"
        ),
        "cases": cases,
    }
    files["expect.json"] = dumps_json(expect)

    # ── 自检（build() 末尾，--check 也走这里）──────────────────────────
    assert len(TRUE_POINTS) >= 5, "可判定样本下限是 5（§4.1），语料必须够"
    for (lon, lat), case in zip(TRUE_POINTS, cases, strict=True):
        assert abs(lon) > 90, f"{lon} 必须在经度域外，否则写反后不可判"
        assert abs(lat) <= 90, f"{lat} 必须在纬度域内"
        a, b = case["input"]
        assert abs(a) <= 90 and abs(b) > 90, f"写反形态不成立: {case['input']}"
        assert max(abs(a), abs(b)) <= 180, "量级必须全在度域，否则与量级判据串扰"
        assert case["expected"]["corrected"] == [lon, lat]
    assert len(files) == 2, f"产物应为语料 + 金标，实得 {sorted(files)}"
    return files


if __name__ == "__main__":
    raise SystemExit(FixtureRun(NAME, VERSION, build, here=_HERE).main())

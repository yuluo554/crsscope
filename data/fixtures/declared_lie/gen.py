#!/usr/bin/env python3
"""F3 · `declared_lie` —— `crs` 声明 4326，但坐标量级是米（`plan/04` §一）。

**必须是模块 M1「量级」能单独命中**的样本：
- 每个坐标分量量级 `≥ 1_000_000`（米域，`data/README.md` §4.1）；
- 轴序判据**不参与**：米域样本不进"可判定样本"子集（该子集要求 `|a| ≤ 180 ∧ |b| ≤ 180`），
  所以本样本只会命中 `conflict/reason=magnitude`，不会被轴序判据串扰成 `axis`。

金标含两部分：语料里写的米值，以及"若按 3857 反解会回到哪些 WGS84 点"
（反解只用 `math` 与 §4.4 口径常量，不复用 `algorithms.py` 的实现——见 `plan/04` §二「参考实现三落点位」）。

跑法：

    py -3.12 data/fixtures/declared_lie/gen.py --out data/fixtures/declared_lie
    py -3.12 data/fixtures/declared_lie/gen.py --check
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in _HERE.parents:
    if (_p / "_genlib.py").is_file():
        sys.path.insert(0, str(_p))
        break
else:  # pragma: no cover
    raise SystemExit("declared_lie/gen.py: 向上找不到 data/_genlib.py")

from _genlib import FixtureRun, dumps_geojson, dumps_json, feature_collection, point_feature  # noqa: E402

NAME = "declared_lie"
VERSION = "1"

#: EPSG:3857 半周长（米）。**金标复算只用这一个常数**，不 import `algorithms`。
WEBMERCATOR_MAX = 20037508.342789244

#: 真值 WGS84 点（构造用：陆上无人区半整数点）。
TRUE_POINTS = ((100.0, 35.0), (100.5, 35.0), (101.0, 35.5), (101.5, 35.0), (101.0, 34.5))

#: 声明值：`crs` 成员写 CRS84/4326，但坐标是米。这正是"声明撒谎"。
DECLARED = {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}


def forward_m(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 → 3857（米）。**独立实现**：只用 `math`，不 import `algorithms`。

    与 `algorithms.wgs84_to_webmercator` 数学等价，但金标要能"独立复算"，
    复用生产实现就变成了自己证明自己（`plan/04` §二）。
    """
    x = lon * WEBMERCATOR_MAX / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) * WEBMERCATOR_MAX / math.pi
    return x, y


def inverse_m(x: float, y: float) -> tuple[float, float]:
    """3857（米）→ WGS84。独立实现，用于自检往返。"""
    lon = x / WEBMERCATOR_MAX * 180.0
    lat = 180.0 / math.pi * (2.0 * math.atan(math.exp(y * math.pi / WEBMERCATOR_MAX)) - math.pi / 2.0)
    return lon, lat


def build() -> dict[str, str]:
    features = []
    cases = []
    for i, (lon, lat) in enumerate(TRUE_POINTS, start=1):
        fid = f"demo-{i:03d}"
        x, y = forward_m(lon, lat)
        features.append(point_feature(fid, round(x, 6), round(y, 6)))
        cases.append(
            {
                "id": f"case-{i:03d}",
                "role": "declared_lie",
                "declared_crs": "4326",
                "input": [round(x, 6), round(y, 6)],
                "expected": {
                    # §4.1：declared 是度制 且 m > 180 → conflict/reason=magnitude
                    "magnitude_m": round(max(abs(x), abs(y)), 6),
                    "magnitude_band": "metre",
                    "axis_decidable": False,  # 米域样本不进轴序的可判定子集
                    "magnitude": "conflict",
                    "reason": "magnitude",
                    # 反解回去的真值（独立复算，供"若真是 3857 则原点在此"对照）
                    "if_3857_then_wgs84": [round(lon, 9), round(lat, 9)],
                },
            }
        )

    files = {
        "out/declared_lie.geojson": dumps_geojson(feature_collection(features, crs=DECLARED)),
    }

    expect = {
        "fixture": NAME,
        "generator_version": VERSION,
        "notes": (
            "crs 成员声明 4326/CRS84，坐标却是 3857 米域。金标里的 if_3857_then_wgs84 "
            "由 math 独立复算（不复用 algorithms.py）。"
        ),
        "cases": cases,
    }
    files["expect.json"] = dumps_json(expect)

    # ── 自检（build() 末尾，--check 也走这里）──────────────────────────
    assert len(TRUE_POINTS) >= 5, "样本数少于 5 会让下游判定退化成 undecidable"
    for (lon, lat), case in zip(TRUE_POINTS, cases, strict=True):
        x, y = case["input"]
        assert max(abs(x), abs(y)) >= 1_000_000, f"米域量级不足: {case['input']}"
        back = inverse_m(x, y)
        assert abs(back[0] - lon) < 1e-6 and abs(back[1] - lat) < 1e-6, "独立正反解往返失败"
        assert case["expected"]["magnitude_band"] == "metre"
        assert case["expected"]["axis_decidable"] is False
    # 声明与内容的矛盾必须真的存在（否则语料名不副实）
    assert '"crs"' in files["out/declared_lie.geojson"], "语料必须带 crs 成员"
    assert len(files) == 2, f"产物应为语料 + 金标，实得 {sorted(files)}"
    return files


if __name__ == "__main__":
    raise SystemExit(FixtureRun(NAME, VERSION, build, here=_HERE).main())

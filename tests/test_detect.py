"""模块 M2「GCJ-02 / BD-09 偏移检测与残差」的判定守门（`plan/03` §二 + `plan/05` §三 M3 DoD）。

**这批测试吃真实语料**（`data/fixtures/water_track/` 自带 0.0008° 细网格、
`data/fixtures/boundary_divergence/` 的两库分歧四例），不是内联玩具数据。

四条各自可证伪的判据：

1. **D2 复现**：被 GCJ-02 偏移的陆上轨迹，在正确假设（GCJ02）下把落水率压到 0，
   WGS84 / BD09 假设下落到水面（逐字段对拍入仓金标 `expect.json`）。
2. **边界外不硬判**：样本全在 `out_of_china` 域外 → `out_of_coverage` + `undecidable`，
   **不得**冒充 "WGS84 胜出"。
3. **残差三段是集合相等**（不是"至少存在一条"）：`formula_approximation` /
   `vendor_divergence` / `boundary_jump` 必须三个都在。
4. **两库边界框结论可不同**：`(73.2, 39.5)` 与 `(112.0, 2.0)` 两 profile 结论相反，
   `(112.0, 5.0)` / `(112.0, 60.0)` 一致——由本文件独立代入常数复算，不复用生产实现。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crsscope import detect
from crsscope.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "data" / "fixtures"

WATER_GPX = FIXTURES / "water_track" / "out" / "water_track.gpx"
WATER_MASK = FIXTURES / "water_track" / "out" / "water_track_mask.json"
DEFAULT_MASK = REPO_ROOT / "data" / "mask" / "out" / "mask_v1.json"


def _gold(name: str) -> dict:
    return json.loads((FIXTURES / name / "expect.json").read_text(encoding="utf-8"))


def _finding(result, check: str):
    hits = [f for f in result.findings if f.check == check]
    assert len(hits) == 1, f"{check} 项应恰好一条，实得 {[f.check for f in result.findings]}"
    return hits[0]


def _write_points(path: Path, pairs: list[list[float]]) -> Path:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"id": f"demo-{i:03d}"},
             "geometry": {"type": "Point", "coordinates": p}}
            for i, p in enumerate(pairs, start=1)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
    return path


def _hypothesis(payload: dict, name: str) -> dict:
    hits = [h for h in payload["hypotheses"] if h["name"] == name]
    assert len(hits) == 1, f"假设 {name} 应恰好一条"
    return hits[0]


# ── 零、契约常量与形态 ────────────────────────────────────────────────


def test_hypotheses_are_fixed_three_values() -> None:
    """候选假设固定三值，**不增不减**（`data/README.md` §4.2）。"""
    assert detect.HYPOTHESES == ("WGS84", "GCJ02", "BD09")


def test_residual_kinds_are_fixed_three_values() -> None:
    """残差三段固定枚举（§4.5）。少一个都不算齐全。"""
    assert detect.RESIDUAL_KINDS == ("formula_approximation", "vendor_divergence", "boundary_jump")


def test_boundary_profiles_are_two_libraries() -> None:
    assert detect.BOUNDARY_PROFILES == ("coordTransform_py", "gcoord")


def test_describe_shape() -> None:
    checks = [f.check for f in detect.describe()]
    assert checks == ["hypotheses", "residual_kinds", "boundary_profiles"]


def test_findings_follow_fixed_check_order() -> None:
    """判定顺序固定（`plan/03` §二）。一项一责：四条各答一件事。"""
    result = detect.run(WATER_GPX, None, mask_path=WATER_MASK)
    assert [f.check for f in result.findings] == [
        "coverage", "hypothesis", "residual", "boundary_profiles"
    ]


# ── 一、D2 复现（逐字段对拍金标）──────────────────────────────────────


def test_water_track_d2_reproduces_gold() -> None:
    """正确假设（GCJ02）把落水率压到近零，WGS84 / BD09 落到水面——对拍 `expect.json`。"""
    gold = _gold("water_track")["cases"][0]["expected"]
    result = detect.run(WATER_GPX, None, mask_path=WATER_MASK)
    payload = result.payload

    assert payload["winner"] == gold["winner"] == "GCJ02"
    assert payload["confidence"] == gold["confidence"] == "high"

    for name, ratio in gold["water_ratio"].items():
        hyp = _hypothesis(payload, name)
        assert hyp["water_ratio"] == pytest.approx(ratio, abs=1e-9), name
    # GCJ02 假设下落水率必须真的归零（这就是 D2 的判据落点）
    assert _hypothesis(payload, "GCJ02")["water_ratio"] == 0.0
    assert _hypothesis(payload, "WGS84")["water_ratio"] == 1.0

    assert payload["mask"]["evaluable_points"] == gold["evaluable_points"]
    # 偏移幅度是"在 GCJ02 假设下"的位移，量级应在 D1 锚点（几十~几百米）附近
    assert _hypothesis(payload, "GCJ02")["offset_m"] > 0.0
    assert _hypothesis(payload, "WGS84")["offset_m"] == 0.0

    assert result.exit_code == 0  # 判定成功、无灰区


def test_water_track_mask_block_reports_required_fields() -> None:
    """§4.3 必报字段：掩膜版本 / 上限分辨率 / 未知占比 / 海岸带占比 / 可判定点数。"""
    result = detect.run(WATER_GPX, None, mask_path=WATER_MASK)
    for key in ("mask_version", "mask_max_resolution_deg", "unknown_ratio",
                "coastal_ratio", "evaluable_points"):
        assert key in result.payload["mask"], key
        assert key in result.payload["header"], f"§4.10 报告头缺 {key}"
    gold_mask = _gold("water_track")["mask"]
    assert result.payload["mask"]["mask_version"] == gold_mask["version"]
    assert result.payload["mask"]["mask_max_resolution_deg"] == pytest.approx(
        gold_mask["resolution_deg"]
    )


def test_declared_crs_is_evidence_not_a_verdict() -> None:
    """声明 4326 时 GCJ02 仍胜出：声明只作 `declared(h)` 一项证据（§4.2），不替判定翻案。"""
    result = detect.run(WATER_GPX, "4326", mask_path=WATER_MASK)
    assert result.payload["winner"] == "GCJ02"
    assert _hypothesis(result.payload, "GCJ02")["declared_conflict"] == 1
    assert _hypothesis(result.payload, "WGS84")["declared_conflict"] == 0


# ── 二、边界外：不得硬判 WGS84 ────────────────────────────────────────


def test_all_outside_boundary_is_out_of_coverage(tmp_path: Path) -> None:
    """样本全在 `out_of_china` 域外 → `out_of_coverage`，**不**冒充 WGS84 胜出（`plan/01` §M2）。"""
    path = _write_points(tmp_path / "far.geojson", [[-100.0, 40.0], [-99.0, 41.0]])
    result = detect.run(path, None, mask_path=WATER_MASK)
    payload = result.payload

    assert payload["out_of_coverage"] is True
    assert payload["winner"] is None, "边界外不得硬判某个假设胜出，尤其不得判 WGS84"
    assert payload["confidence"] == "undecidable"
    cov = _finding(result, "coverage")
    assert cov.status == "undecidable"
    assert cov.reason == "out_of_coverage"
    # 必须附两份 boundary_profiles 各自的结论
    assert set(payload["boundary_profiles"]) == set(detect.BOUNDARY_PROFILES)


def test_out_of_coverage_exits_5(tmp_path: Path) -> None:
    path = _write_points(tmp_path / "far.geojson", [[-100.0, 40.0], [-99.0, 41.0]])
    out = tmp_path / "out"
    code = main(["detect", str(path), "--mask", str(WATER_MASK), "--json", "--out-dir", str(out)])
    assert code == 5
    assert main(["detect", str(path), "--mask", str(WATER_MASK), "--json",
                 "--allow-undecidable", "--out-dir", str(out)]) == 0


# ── 三、残差三段：集合相等 ────────────────────────────────────────────


def test_residual_kinds_are_set_equal() -> None:
    """断言**集合相等**而不是"存在"——少一段或多一段都必须红（§4.5）。"""
    result = detect.run(WATER_GPX, None, mask_path=WATER_MASK)
    kinds = [r["kind"] for r in result.payload["residual"]]
    assert set(kinds) == set(detect.RESIDUAL_KINDS)
    assert len(kinds) == len(detect.RESIDUAL_KINDS), "三段不许重复"
    for row in result.payload["residual"]:
        assert set(row) == {"kind", "detail", "affected_points"}
        assert "真实坐标" not in row["detail"], "禁止宣称'已还原为 WGS84 真实坐标'"


def test_residual_finding_lists_all_three() -> None:
    result = detect.run(WATER_GPX, None, mask_path=WATER_MASK)
    residual = _finding(result, "residual")
    assert residual.status == "info"
    assert set(residual.evidence["kinds"]) == set(detect.RESIDUAL_KINDS)


# ── 四、两库边界画像：结论可不同（独立代入常数复算）────────────────────

# 常数照录 `data/README.md` §1.3，**本文件独立持有**，不复用 crsscope.algorithms
CT_PY_LON = (73.66, 135.05)
CT_PY_LAT = (3.86, 53.55)
GCOORD_LON = (72.004, 137.8347)
GCOORD_LAT = (0.8293, 55.8271)


def _ct_py_inside(lon: float, lat: float) -> bool:
    return CT_PY_LON[0] < lon < CT_PY_LON[1] and CT_PY_LAT[0] < lat < CT_PY_LAT[1]


def _gcoord_inside(lon: float, lat: float) -> bool:
    return GCOORD_LON[0] <= lon <= GCOORD_LON[1] and GCOORD_LAT[0] <= lat <= GCOORD_LAT[1]


@pytest.mark.parametrize(
    ("lon", "lat", "differ"),
    [
        (73.2, 39.5, True),  # 经向分歧
        (112.0, 2.0, True),  # 纬向分歧（< 3.86°N）
        (112.0, 5.0, False),  # 一致：两库都境内
        (112.0, 60.0, False),  # 一致：两库都境外
    ],
)
def test_boundary_profiles_match_independent_computation(
    tmp_path: Path, lon: float, lat: float, differ: bool
) -> None:
    path = _write_points(tmp_path / "p.geojson", [[lon, lat]])
    result = detect.run(path, None, mask_path=WATER_MASK)
    profiles = result.payload["boundary_profiles"]

    got_ct = profiles["coordTransform_py"]["in_china"]
    got_gc = profiles["gcoord"]["in_china"]
    assert got_ct == _ct_py_inside(lon, lat)
    assert got_gc == _gcoord_inside(lon, lat)
    assert (got_ct != got_gc) is differ, f"({lon},{lat}) 两库结论差异应与独立复算一致"


def test_diverging_profiles_emit_explicit_warning(tmp_path: Path) -> None:
    """两库边界不一致要**显式警告**，且措辞不得说成某一方的 bug（决策 ④）。"""
    path = _write_points(tmp_path / "div.geojson", [[73.2, 39.5]])
    result = detect.run(path, None, mask_path=WATER_MASK)
    finding = _finding(result, "boundary_profiles")
    assert finding.status == "warning"
    assert finding.reason == "boundary_divergence"
    assert "不是任何一方的 bug" in finding.detail


# ── 五、失败路径与退出码（§4.9）───────────────────────────────────────


def test_missing_mask_is_environment_error(tmp_path: Path) -> None:
    """掩膜缺失 → exit 3（**不得**默认'全是陆地'，§4.3）。"""
    assert main(["detect", str(WATER_GPX), "--out-dir", str(tmp_path)]) == 3


def test_mask_resolution_above_cap_is_rejected(tmp_path: Path) -> None:
    """掩膜步长 > 1° → exit 3（`mask.MAX_RESOLUTION_DEG` 硬上限）。"""
    bad = {
        "version": "bad", "resolution_deg": 2.0, "lon_min": -180.0, "lat_min": -85.0,
        "n_lon": 180, "n_lat": 85, "cells": [{"lat_idx": 0, "lon_idx": 0, "value": "land"}],
    }
    mask_file = tmp_path / "coarse.json"
    mask_file.write_text(json.dumps(bad), encoding="utf-8", newline="\n")
    assert main(["detect", str(WATER_GPX), "--mask", str(mask_file), "--out-dir", str(tmp_path)]) == 3


def test_few_evaluable_points_exits_5(tmp_path: Path) -> None:
    """可判定点 `< 30` → `undecidable` + exit 5（§4.3）。单点样本即触发。"""
    path = _write_points(tmp_path / "one.geojson", [[112.0, 5.0]])
    out = tmp_path / "out"
    assert main(["detect", str(path), "--mask", str(WATER_MASK), "--json",
                 "--out-dir", str(out)]) == 5
    assert main(["detect", str(path), "--mask", str(WATER_MASK), "--json",
                 "--allow-undecidable", "--out-dir", str(out)]) == 0


def test_illegal_declared_crs_is_usage_error() -> None:
    """GCJ-02 没有 EPSG 代码，不是合法声明值 → `UsageError` → exit 2。"""
    from crsscope.errors import UsageError

    with pytest.raises(UsageError) as exc:
        detect.run(WATER_GPX, "gcj02", mask_path=WATER_MASK)
    assert exc.value.code == 2


def test_water_track_command_exits_0(tmp_path: Path, capsys) -> None:
    """真命令：判定成功、无灰区 → exit 0；`--json` 里 `winner` 为 GCJ02。"""
    code = main(["detect", str(WATER_GPX), "--mask", str(WATER_MASK), "--json",
                 "--out-dir", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["exit_code"] == 0
    assert payload["winner"] == "GCJ02"


def test_default_mask_rejects_gcj_offset_only_undecidable() -> None:
    """默认 1° 掩膜分辨不了 GCJ-02 位移（250–600 m ≪ 111 km）→ 只能落 `undecidable`。

    这是 `plan/05` §二之二 的实测结论：**复现 D2 必须用 fixture 自带的细网格**。
    """
    result = detect.run(WATER_GPX, None, mask_path=DEFAULT_MASK)
    assert result.payload["confidence"] == "undecidable"
    assert result.payload["winner"] is None
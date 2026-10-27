"""模块 M3「跨实现差分」的判定守门（`plan/03` §三 + `plan/05` §三 M4 DoD）。

**这批测试吃真实语料**（`data/fixtures/boundary_divergence/` 的两库分歧四例），
不是内联玩具数据。金标 `expect.json` 的 `expected.boundary_table_row` 与 `xdiff` 的
`boundary_table` 行**同形**，逐字段对拍。

五条各自可证伪的判据：

1. **两库分歧/一致**：`(73.2, 39.5)` 经向分歧、`(112.0, 2.0)` 纬向分歧，两库结论相反；
   `(112.0, 5.0)` / `(112.0, 60.0)` 一致——逐行对拍入仓金标。
2. **差分距离口径**：`pairwise` 给 `median_m` / `max_m` / `p95_m`，`max_m` 附该点坐标；
   距离只走 `geodesy.haversine_m`（禁止平面欧氏）。
3. **不收敛如实报出**：`(72.05, 0.83)` 在 gcoord 口径下迭代超上限 → `not_converged`
   出现在结果里（`undecidable` + exit 5），**不抛未捕获异常**，也**不静默**。
4. **退出码**：`target` 非法 → 2；文件缺失 → 3；灰区优先 → 5。
5. **常数与判据照录**：三个实现覆盖的坐标系与 `data/README.md` §1.3 一致；两库边界框独立复算。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crsscope import algorithms, xdiff
from crsscope.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "data" / "fixtures"
BOUNDARY_GEOJSON = FIXTURES / "boundary_divergence" / "out" / "boundary_divergence.geojson"
BOUNDARY_EXPECT = FIXTURES / "boundary_divergence" / "expect.json"


def _gold() -> dict:
    return json.loads(BOUNDARY_EXPECT.read_text(encoding="utf-8"))


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


# ── 零、契约常量与形态 ────────────────────────────────────────────────


def test_implementations_are_fixed_three_names() -> None:
    """三个对照实现固定，**不增不减**（`plan/03` §三 / `data/README.md` §1.3）。"""
    assert xdiff.IMPLEMENTATIONS == ("coordTransform_py", "gcoord", "proj4js_webmercator")


def test_target_choices_are_fixed_four_values() -> None:
    assert xdiff.TARGET_CHOICES == ("wgs84", "gcj02", "bd09", "webmercator")


def test_boundary_profiles_are_two_libraries() -> None:
    assert xdiff.BOUNDARY_PROFILES == ("coordTransform_py", "gcoord")


def test_describe_shape() -> None:
    checks = [f.check for f in xdiff.describe()]
    assert checks == ["ct_py_bbox", "gcoord_bbox", "implementations"]


def test_findings_follow_fixed_check_order() -> None:
    """判定顺序固定（`plan/03` §三）。一项一责：五条各答一件事。"""
    result = xdiff.run(BOUNDARY_GEOJSON, "gcj02")
    assert [f.check for f in result.findings] == [
        "implementations", "pairwise", "boundary_table", "jumps", "not_converged"
    ]


# ── 一、两库边界结论表：逐行对拍金标 ──────────────────────────────────


def test_boundary_table_matches_gold_row_by_row() -> None:
    """`boundary_table` 逐行对拍 `expect.json` 的 `boundary_table_row`（同形字段）。"""
    result = xdiff.run(BOUNDARY_GEOJSON, "gcj02")
    rows = result.payload["boundary_table"]

    gold_rows = {
        (c["lon"], c["lat"]): c["expected"]["boundary_table_row"] for c in _gold()["cases"]
    }
    assert len(rows) == len(gold_rows), "行数应与金标四例一致"
    for row in rows:
        expected = gold_rows[(row["lon"], row["lat"])]
        assert set(row) == set(expected), f"{row['lon']} 行字段集合应与金标同形"
        assert row == expected, f"{row['lon']} 行逐字段对拍金标失败：{row} != {expected}"


@pytest.mark.parametrize(
    ("lon", "lat", "differ"),
    [
        (73.2, 39.5, True),  # 经向分歧
        (112.0, 2.0, True),  # 纬向分歧（< 3.86°N）
        (112.0, 5.0, False),  # 一致：两库都境内
        (112.0, 60.0, False),  # 一致：两库都境外
    ],
)
def test_two_divergences_and_two_agreements(
    tmp_path: Path, lon: float, lat: float, differ: bool
) -> None:
    """两类分歧都报出、两个对照组都报一致（`plan/05` §三 M4 DoD）。"""
    path = _write_points(tmp_path / "p.geojson", [[lon, lat]])
    result = xdiff.run(path, "gcj02")
    row = result.payload["boundary_table"][0]
    assert (row["coordTransform_py"] != row["gcoord"]) is differ
    assert row["agree"] is (not differ)

    # 分歧即跳变点；一致则无跳变
    assert (len(result.payload["jumps"]) == 1) is differ
    if differ:
        assert result.payload["jumps"][0]["reason"] == "out_of_china 边界内外跳变"
        assert [result.payload["jumps"][0]["lon"], result.payload["jumps"][0]["lat"]] == [lon, lat]


def test_boundary_divergence_is_warning_not_bug_wording() -> None:
    """两库边界不一致要显式警告，措辞不得说成某一方的 bug（决策 ④）。"""
    finding = _finding(xdiff.run(BOUNDARY_GEOJSON, "gcj02"), "boundary_table")
    assert finding.status == "warning"
    assert finding.reason == "boundary_divergence"
    assert "不是任何一方的 bug" in finding.detail


def test_agreement_has_no_warning(tmp_path: Path) -> None:
    """两库一致时 `boundary_table` 应为 `consistent`，不得报警。"""
    path = _write_points(tmp_path / "same.geojson", [[112.0, 5.0], [112.0, 60.0]])
    result = xdiff.run(path, "gcj02")
    finding = _finding(result, "boundary_table")
    assert finding.status == "consistent"
    assert finding.reason is None
    assert result.payload["jumps"] == []


# ── 二、两两差分的距离口径（§4.4）─────────────────────────────────────


def test_pairwise_reports_median_max_p95_and_max_at() -> None:
    """`pairwise` 给 `median_m` / `max_m` / `p95_m`，且对 `max_m` 附该点坐标。"""
    result = xdiff.run(BOUNDARY_GEOJSON, "gcj02")
    pairwise = result.payload["pairwise"]
    assert len(pairwise) == 1  # gcj02 目标下适用两库 → 一对
    pair = pairwise[0]
    assert {pair["a"], pair["b"]} == {"coordTransform_py", "gcoord"}
    for key in ("median_m", "max_m", "p95_m"):
        assert key in pair, key
    assert pair["max_at"] is not None, "max_m 必须附该点坐标"
    # max_at 必是输入坐标之一（不是凭空造的）
    inputs = {(r["lon"], r["lat"]) for r in result.payload["boundary_table"]}
    assert (pair["max_at"][0], pair["max_at"][1]) in inputs


def test_pairwise_max_m_matches_independent_haversine() -> None:
    """`max_m` 与独立代入 `haversine_m` 复算一致（同一口径，禁止平面欧氏）。"""
    from crsscope import geodesy

    result = xdiff.run(BOUNDARY_GEOJSON, "gcj02")
    pair = result.payload["pairwise"][0]
    impl = {i["name"]: i["points"] for i in result.payload["implementations"]}
    rows = result.payload["boundary_table"]
    ct = impl["coordTransform_py"]
    gc = impl["gcoord"]

    expected = [
        geodesy.haversine_m(ct[i][0], ct[i][1], gc[i][0], gc[i][1])
        for i in range(len(rows))
    ]
    ordered = sorted(expected)
    mid = len(ordered) // 2
    expected_median = (
        ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
    )
    assert pair["max_m"] == pytest.approx(round(max(expected), 1))
    assert pair["median_m"] == pytest.approx(round(expected_median, 1))
    # 分歧点（两库一侧不偏移）贡献的是米级大差；一致点差异为 0 或近 0
    assert pair["max_m"] > 100.0, "分歧样本的差分应达数百米量级"


def test_all_implementations_are_local_and_fixed_for_webmercator() -> None:
    """WebMercator 目标下两库（gcoord / proj4js）对同一输入解出同一 WGS84。"""
    result = xdiff.run(BOUNDARY_GEOJSON, "webmercator")
    names = [i["name"] for i in result.payload["implementations"]]
    assert names == ["gcoord", "proj4js_webmercator"]
    pair = result.payload["pairwise"][0]
    assert pair["max_m"] == 0.0, "WebMercator 是闭式解析逆，两实现应逐点一致"


def test_wgs84_target_is_identity_all_zero() -> None:
    """`wgs84` 目标下 WGS84 本身就是恒等，三实现差分恒为 0。"""
    result = xdiff.run(BOUNDARY_GEOJSON, "wgs84")
    for pair in result.payload["pairwise"]:
        assert pair["max_m"] == 0.0
        assert pair["median_m"] == 0.0


# ── 三、不收敛如实报出（题面 §M3 纪律）────────────────────────────────


NON_CONVERGED = (72.05, 0.83)  # gcoord 闭区间内、coordTransform_py 开区间外（four_crs case-004）


def test_not_converged_is_reported_not_swallowed(tmp_path: Path) -> None:
    """迭代超上限 → `not_converged` 出现在结果里，**不抛未捕获异常**、不静默返回。"""
    path = _write_points(tmp_path / "nc.geojson", [list(NON_CONVERGED)])
    result = xdiff.run(path, "gcj02")

    rows = result.payload["not_converged"]
    assert len(rows) == 1, "不收敛点必须如实出现在结果里"
    row = rows[0]
    assert row["implementation"] == "gcoord"
    assert row["iterations"] == algorithms.INVERSE_MAX_ITER
    assert [row["lon"], row["lat"]] == list(NON_CONVERGED)

    # 整项按灰区处理（undecidable），不得伪装成"算出来了"
    finding = _finding(result, "not_converged")
    assert finding.status == "undecidable"
    assert finding.reason == "not_converged"


def test_not_converged_exits_5(tmp_path: Path) -> None:
    path = _write_points(tmp_path / "nc.geojson", [list(NON_CONVERGED)])
    out = tmp_path / "out"
    assert main(["xdiff", str(path), "--target", "gcj02", "--json", "--out-dir", str(out)]) == 5
    assert main(["xdiff", str(path), "--target", "gcj02", "--json",
                 "--allow-undecidable", "--out-dir", str(out)]) == 0


def test_converged_input_has_empty_not_converged() -> None:
    """正常语料不得报不收敛（否则判据空转）。"""
    result = xdiff.run(BOUNDARY_GEOJSON, "gcj02")
    assert result.payload["not_converged"] == []
    assert _finding(result, "not_converged").status == "consistent"


# ── 四、失败路径与退出码（§4.9）───────────────────────────────────────


def test_illegal_target_is_usage_error() -> None:
    from crsscope.errors import UsageError

    with pytest.raises(UsageError) as exc:
        xdiff.run(BOUNDARY_GEOJSON, "bogus")
    assert exc.value.code == 2


def test_illegal_target_exits_2(capsys) -> None:
    assert main(["xdiff", str(BOUNDARY_GEOJSON), "--target", "bogus"]) == 2
    capsys.readouterr()


def test_missing_file_is_environment_error(tmp_path: Path) -> None:
    assert main(["xdiff", str(tmp_path / "nope.geojson"), "--target", "wgs84",
                 "--out-dir", str(tmp_path)]) == 3


def test_agreeing_corpus_exits_0(tmp_path: Path) -> None:
    """全一致、全收敛、无冲突 → exit 0（`boundary_table` 一致不构成命中）。"""
    path = _write_points(tmp_path / "same.geojson", [[112.0, 5.0], [112.0, 60.0]])
    assert main(["xdiff", str(path), "--target", "gcj02", "--json",
                 "--out-dir", str(tmp_path / "o")]) == 0


def test_diverging_corpus_writes_reports(tmp_path: Path, capsys) -> None:
    """真命令：分歧语料产出报告且 `--json` 里的 `boundary_table` 与金标同形。"""
    out = tmp_path / "out"
    code = main(["xdiff", str(BOUNDARY_GEOJSON), "--target", "gcj02", "--json", "--out-dir", str(out)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["exit_code"] == 0
    assert len(payload["boundary_table"]) == 4
    assert (out / "report.json").is_file()
    assert (out / "report.md").is_file()


# ── 五、常数与判据照录（独立复算，不复用生产实现）──────────────────────

# 常数照录 `data/README.md` §1.3，**本文件独立持有**，不复用 crsscope.algorithms
CT_PY_LON = (73.66, 135.05)
CT_PY_LAT = (3.86, 53.55)
GCOORD_LON = (72.004, 137.8347)
GCOORD_LAT = (0.8293, 55.8271)


def _ct_py_inside(lon: float, lat: float) -> bool:
    return CT_PY_LON[0] < lon < CT_PY_LON[1] and CT_PY_LAT[0] < lat < CT_PY_LAT[1]


def _gcoord_inside(lon: float, lat: float) -> bool:
    return GCOORD_LON[0] <= lon <= GCOORD_LON[1] and GCOORD_LAT[0] <= lat <= GCOORD_LAT[1]


@pytest.mark.parametrize("lon,lat", [(73.2, 39.5), (112.0, 2.0), (112.0, 5.0), (112.0, 60.0)])
def test_boundary_table_matches_independent_computation(lon: float, lat: float) -> None:
    """`boundary_table` 的两库结论与独立代入常数复算一致（不复用生产实现）。"""
    rows = xdiff._boundary_table(_points([lon, lat]))  # noqa: SLF001
    row = rows[0]
    assert row["coordTransform_py"] == ("inside" if _ct_py_inside(lon, lat) else "outside")
    assert row["gcoord"] == ("inside" if _gcoord_inside(lon, lat) else "outside")


def _points(pair: list[float]):
    from crsscope import io

    return [io.Point(lon=pair[0], lat=pair[1], seq=0)]
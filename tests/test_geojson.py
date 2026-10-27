"""模块 M4「GeoJSON RFC 7946 结构与声明审计」的判定守门（`plan/03` §四 + `plan/05` §三 M5 DoD）。

**吃真实语料** `data/fixtures/geojson_struct/`（九个用例覆盖七项检查），不写内联玩具数据
（结构失败路径除外——那类样本在语料里有 `case-009`，我们只额外补 bbox / 类型两处）。

判据分五组，各自可证伪：

1. **check-geojson 不查的三项都查**：`ring_order` / `precision` / `crs_member` 各有一条真实命中；
2. **R1+R2 成对引用 + 级别由 R2 决定（变异靶子）**：把 `RFC_R2` 换成不含
   "SHOULD NOT reject" 的文本 → `ring_order` 必须升到 `error`。删掉 R2 分支这条测试就红；
3. **跨 180° bbox 不报 error、`geometry: null` 只 info**（R4 / R6）；
4. **结构失败路径**：坐标对非数值 / 未知 type / bbox 长度 → 逐条 `structure/error` → exit 4，
   **且失败路径零副作用**（不落报告）；
5. **退出码**：warning 默认不算命中（0）；`--strict-ring` 与 `--fail-on ring` 是显式升级路径。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crsscope import geojson
from crsscope.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "data" / "fixtures" / "geojson_struct"
OUT = FIXTURE / "out"


def _case_file(name: str) -> Path:
    return OUT / name


def _finding(result, check: str):
    hits = [f for f in result.findings if f.check == check]
    assert len(hits) == 1, f"{check} 项应恰好一条，实得 {[f.check for f in result.findings]}"
    return hits[0]


def _gold(case_id: str) -> dict:
    data = json.loads((FIXTURE / "expect.json").read_text(encoding="utf-8"))
    return next(case["expected"] for case in data["cases"] if case["id"] == case_id)


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
    return path


def _feature(geometry: object, properties: object = None, **extra: object) -> dict:
    feature: dict = {"type": "Feature", "properties": properties, "geometry": geometry}
    feature.update(extra)
    return feature


# ── 零、契约常量与形态 ────────────────────────────────────────────────


def test_checks_are_fixed_seven_in_order() -> None:
    """七项检查顺序固定（`plan/03` §四表）；模块常量不许改名（测试钉住）。"""
    assert geojson.CHECKS == (
        "ring_order",
        "axis",
        "bbox",
        "nesting",
        "null_geometry",
        "crs_member",
        "precision",
    )


def test_check_geojson_gaps_are_all_covered() -> None:
    """check-geojson 明示不查的三项，必须都在本工具的检查项里（题面 §M4 验收）。"""
    assert geojson.CHECK_GEOJSON_GAPS == ("ring_order", "precision", "crs_member")
    assert set(geojson.CHECK_GEOJSON_GAPS) <= set(geojson.CHECKS)


def test_findings_follow_fixed_check_order() -> None:
    result = geojson.run([_case_file("case-002_ring_ccw.geojson")])
    assert [f.check for f in result.findings] == list(geojson.CHECKS)


def test_describe_shape() -> None:
    checks = [f.check for f in geojson.describe()]
    assert checks == ["ring_order", "crs_member", "checked_gaps"]


# ── 一、check-geojson 不查的三项：都查，且各自单独命中 ─────────────────


def test_three_gaps_are_detected_in_one_run() -> None:
    result = geojson.run(
        [
            _case_file("case-001_ring_cw.geojson"),
            _case_file("case-006_crs_member.geojson"),
            _case_file("case-007_precision.geojson"),
        ]
    )
    statuses = {f.check: f.status for f in result.findings}
    assert statuses["ring_order"] == "warning"
    assert statuses["crs_member"] == "warning"
    assert statuses["precision"] == "warning"


def test_crs_member_wording_is_no_longer_used() -> None:
    """R5：措辞固定 "no longer used"，附 prior arrangement 活口，且**不含**强制禁用表述。"""
    finding = _finding(geojson.run([_case_file("case-006_crs_member.geojson")]), "crs_member")
    assert finding.status == "warning"
    assert _gold("case-006")["wording_must_contain"] in finding.detail
    assert "no longer used" in finding.detail
    assert "prior arrangement" in finding.detail
    assert "MUST NOT" not in finding.detail
    assert geojson.CRS_REMOVED_WORDING in finding.detail


def test_precision_threshold_is_nine_fraction_digits() -> None:
    finding = _finding(geojson.run([_case_file("case-007_precision.geojson")]), "precision")
    expected = _gold("case-007")
    assert finding.status == "warning"
    assert finding.evidence["max_fraction_digits"] == expected["fraction_digits"]
    assert finding.evidence["threshold_digits"] == expected["threshold_digits"]
    assert geojson.PRECISION_MAX_FRACTION_DIGITS == expected["threshold_digits"]


def test_precision_within_threshold_is_consistent() -> None:
    finding = _finding(geojson.run([_case_file("case-002_ring_ccw.geojson")]), "precision")
    assert finding.status == "consistent"


# ── 二、R1 + R2 成对引用；级别由 R2 决定（变异靶子）─────────────────────


def test_ring_order_violation_is_warning_by_default() -> None:
    result = geojson.run([_case_file("case-001_ring_cw.geojson")])
    finding = _finding(result, "ring_order")
    expected = _gold("case-001")
    assert finding.status == expected["status"] == "warning"
    assert finding.reason == "ring"
    # R1 + R2 成对引用：证据里两段原文都在，detail 里两句语义都在
    assert finding.evidence["r1"] == geojson.RFC_R1
    assert finding.evidence["r2"] == geojson.RFC_R2
    assert "R1" in finding.detail and "R2" in finding.detail
    assert "SHOULD NOT reject" in finding.detail
    # 违规环的 Shoelace 符号与金标一致
    assert result.payload["files"][0]["ring_violations"][0]["sign"] == expected["ring_sign"]


def test_ring_order_compliant_exterior_and_hole_are_consistent() -> None:
    exterior = _finding(geojson.run([_case_file("case-002_ring_ccw.geojson")]), "ring_order")
    assert exterior.status == "consistent"

    result = geojson.run([_case_file("case-003_polygon_with_hole.geojson")])
    finding = _finding(result, "ring_order")
    assert finding.status == "consistent"
    signs = {row["ring"]: row["sign"] for row in result.payload["files"][0]["rings"]}
    expected = _gold("case-003")
    assert signs["exterior"] == expected["exterior_sign"]
    assert signs["hole"] == expected["hole_sign"]


def test_strict_ring_escalates_to_error() -> None:
    result = geojson.run([_case_file("case-001_ring_cw.geojson")], strict_ring=True)
    expected = _gold("case-001")
    assert _finding(result, "ring_order").status == expected["status_with_strict_ring"] == "error"


def test_ring_level_is_derived_from_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    """**变异靶子**（决策 ②）：级别必须由 R2 的容忍语义推导，而不是写死。

    把 `RFC_R2` 换成不含 "SHOULD NOT reject" 的文本后，同一份违规语料必须升级为 `error`。
    代码里删掉 R2 判定分支 → 本断言立刻红（status 仍为 warning）；这就是"分级逻辑存在"的证据。
    """
    sample = [_case_file("case-001_ring_cw.geojson")]
    assert _finding(geojson.run(sample), "ring_order").status == "warning"

    monkeypatch.setattr(geojson, "RFC_R2", "（R2 被删去后的文本，不含容忍语义）")
    mutated = geojson.run(sample)
    assert _finding(mutated, "ring_order").status == "error", (
        "删掉 R2 → 环方向必须升级为 error；否则说明级别被写死、R2 只是装饰"
    )


# ── 三、R4 / R6：跨 180° bbox 与 null geometry 都不得报 error ───────────


def test_antimeridian_bbox_is_info_not_error() -> None:
    result = geojson.run([_case_file("case-004_bbox_antimeridian.geojson")])
    finding = _finding(result, "bbox")
    assert finding.status == _gold("case-004")["status"] == "info"
    assert finding.status != "error"
    assert finding.evidence["crossing"][0]["west_greater_than_east"] is True
    assert not any(f.status == "error" for f in result.findings)


def test_null_geometry_and_properties_are_info_only(tmp_path: Path) -> None:
    result = geojson.run([_case_file("case-005_null_geometry.geojson")])
    finding = _finding(result, "null_geometry")
    expected = _gold("case-005")
    assert finding.status == expected["status"] == "info"
    assert not any(f.status == "error" for f in result.findings)
    file_payload = result.payload["files"][0]
    assert file_payload["null_geometry"] == 1
    assert file_payload["null_properties"] == 1
    assert main(["geojson", str(_case_file("case-005_null_geometry.geojson")),
                 "--out-dir", str(tmp_path / "out")]) == 0


def test_nested_geometry_collection_depth_is_reported() -> None:
    result = geojson.run([_case_file("case-008_geometry_collection.geojson")])
    finding = _finding(result, "nesting")
    expected = _gold("case-008")
    assert finding.status == expected["status"] == "info"
    assert finding.evidence["max_depth"] == expected["depth"]
    assert finding.status != "error"


def test_bbox_not_containing_geometry_is_warning(tmp_path: Path) -> None:
    """bbox 与真实外包框不一致 → warning（§4.6），不是 error。"""
    path = _write(
        tmp_path,
        "mismatch.geojson",
        {
            "type": "FeatureCollection",
            "bbox": [0.0, 0.0, 1.0, 1.0],
            "features": [_feature({"type": "Point", "coordinates": [10.0, 10.0]}, {})],
        },
    )
    finding = _finding(geojson.run([path]), "bbox")
    assert finding.status == "warning"
    assert finding.reason == "bbox"


def test_axis_swapped_is_warning(tmp_path: Path) -> None:
    """第二分量越出纬度域 → 呈 (lat, lon) → warning（§4.6 / R3）。"""
    path = _write(
        tmp_path,
        "swapped.geojson",
        {
            "type": "FeatureCollection",
            "features": [_feature({"type": "Point", "coordinates": [39.9, 116.4]}, {})],
        },
    )
    finding = _finding(geojson.run([path]), "axis")
    assert finding.status == "warning"
    assert finding.reason == "axis"


# ── 四、结构失败路径：逐条记录 → 整体 exit 4，且零副作用 ────────────────


def test_malformed_coordinate_is_recorded_as_structure_error() -> None:
    audits, issues = geojson.audit([_case_file("case-009_bad_coord.geojson")])
    assert len(audits) == 1
    assert len(issues) == 1
    issue = issues[0]
    expected = _gold("case-009")
    assert issue.check == expected["check"] == "structure"
    assert issue.status == expected["status"] == "error"
    assert issue.evidence["coordinate_length"] == expected["coordinate_length"]
    assert issue.evidence["min_length"] == expected["min_length"]


def test_malformed_coordinate_exits_4_without_writing_reports(tmp_path: Path, capsys) -> None:
    from crsscope.errors import InvalidInput

    with pytest.raises(InvalidInput) as exc:
        geojson.run([_case_file("case-009_bad_coord.geojson")])
    assert exc.value.code == 4
    assert "坐标对只有 1 个元素" in (exc.value.detail or "")

    out_dir = tmp_path / "out"
    code = main(["geojson", str(_case_file("case-009_bad_coord.geojson")), "--json",
                 "--out-dir", str(out_dir)])
    capsys.readouterr()
    assert code == 4
    assert not out_dir.exists() or not list(out_dir.iterdir())


def test_unknown_type_is_structure_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "unknown.geojson", {"type": "Circle", "coordinates": [1.0, 2.0]})
    _, issues = geojson.audit([path])
    assert len(issues) == 1 and issues[0].check == "structure" and issues[0].status == "error"
    assert "未知 GeoJSON type" in issues[0].detail


def test_bbox_length_not_4_or_6_is_structure_error(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "bad_bbox.geojson",
        {
            "type": "FeatureCollection",
            "bbox": [0.0, 0.0, 1.0],
            "features": [_feature({"type": "Point", "coordinates": [0.5, 0.5]}, {})],
        },
    )
    _, issues = geojson.audit([path])
    assert len(issues) == 1
    assert issues[0].evidence["bbox_length"] == 3
    assert issues[0].evidence["allowed"] == [4, 6]
    assert main(["geojson", str(path), "--out-dir", str(tmp_path / "o")]) == 4


def test_invalid_json_exits_4(tmp_path: Path) -> None:
    path = tmp_path / "broken.geojson"
    path.write_text("{not json", encoding="utf-8", newline="\n")
    assert main(["geojson", str(path), "--out-dir", str(tmp_path / "o")]) == 4


def test_missing_file_exits_3(tmp_path: Path) -> None:
    assert main(["geojson", str(tmp_path / "nope.geojson"),
                 "--out-dir", str(tmp_path / "o")]) == 3


# ── 五、退出码与报告 ────────────────────────────────────────────────────


def test_warning_only_corpus_exits_zero(tmp_path: Path, capsys) -> None:
    """R1 违规默认 warning → **不**构成命中（否则历史数据会被判成失败，决策 ⑪）。"""
    out_dir = tmp_path / "out"
    code = main(["geojson", str(_case_file("case-001_ring_cw.geojson")), "--json",
                 "--out-dir", str(out_dir)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["exit_code"] == 0
    assert (out_dir / "report.json").is_file()
    assert (out_dir / "report.md").is_file()


def test_strict_ring_exits_one(tmp_path: Path) -> None:
    code = main(["geojson", str(_case_file("case-001_ring_cw.geojson")), "--strict-ring",
                 "--out-dir", str(tmp_path / "out")])
    assert code == 1


def test_fail_on_ring_exits_one(tmp_path: Path) -> None:
    """`--fail-on` 是 `--strict-ring` 之外的第二条显式升级通道（§4.9）。"""
    code = main(["geojson", str(_case_file("case-001_ring_cw.geojson")), "--fail-on", "ring",
                 "--out-dir", str(tmp_path / "out")])
    assert code == 1


def test_multiple_files_aggregate_into_one_finding_per_check() -> None:
    result = geojson.run(
        [_case_file("case-001_ring_cw.geojson"), _case_file("case-007_precision.geojson")]
    )
    assert len(result.findings) == len(geojson.CHECKS)
    assert result.payload["counts"]["files"] == 2
    assert _finding(result, "ring_order").status == "warning"
    assert _finding(result, "precision").status == "warning"


def test_run_is_deterministic() -> None:
    from crsscope import report

    files = [_case_file("case-002_ring_ccw.geojson"), _case_file("case-006_crs_member.geojson")]
    first = report.dumps_json(geojson.run(files).payload)
    second = report.dumps_json(geojson.run(files).payload)
    assert first == second

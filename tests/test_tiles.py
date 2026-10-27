"""模块 M5「瓦片 / 投影一致性」的判定守门（`plan/03` §五 + `plan/05` §三 M5 DoD）。

**吃真实语料** `data/fixtures/tile_flip/`（四组用例）。语料是纯 `z/x/y` 数字，不含任何地物、
不需要底图——这正是"静态检出"的含义（题面 §M5 验收）。

判据分四组，各自可证伪：

1. **`axis_flip` 静态检出**：同一 `z` / 同一 `x` 下 `y` 与 `2^z-1-y` 并存且指向同一 bbox →
   `conflict`，并给出具体的 `z/x/y`；反向样本（非互补行、无 bbox 且无 scheme 标签）不得误报。
2. **`y_range` 单点即判**：`y ∉ [0, 2^z-1]` → `error`（一枚就够）。
3. **`wrap`**：跨越日界线的 `x` 环绕必须显式 `wrap: true`；缺席 → `conflict` 且列出具体瓦片。
4. **`mixed_3857_4326`**：同一集合内度域与米域并存 → `conflict`，给出具体冲突坐标；
   另外 `zoom_bbox`（`z+1` ⊆ `z` 展开）与 z/x/y 非法 → exit 4 也各有断言。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crsscope import tiles
from crsscope.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "data" / "fixtures" / "tile_flip"
CORPUS = FIXTURE / "out" / "tile_flip.json"


def _corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def _case(case_id: str) -> dict:
    return next(case for case in _corpus()["cases"] if case["id"] == case_id)


def _gold(case_id: str) -> dict:
    data = json.loads((FIXTURE / "expect.json").read_text(encoding="utf-8"))
    return next(case["expected"] for case in data["cases"] if case["id"] == case_id)


def _write_case(tmp_path: Path, case_id: str) -> Path:
    """把金标里的一组建临时文件——金标把四组用例放在同一份语料里，逐组断言要拆开。"""
    path = tmp_path / f"{case_id}.json"
    payload = {"format": "z/x/y", "cases": [_case(case_id)]}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
    return path


def _write_tiles(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
    return path


def _finding(result, check: str):
    hits = [f for f in result.findings if f.check == check]
    assert len(hits) == 1, f"{check} 项应恰好一条，实得 {[f.check for f in result.findings]}"
    return hits[0]


# ── 零、契约常量与形态 ────────────────────────────────────────────────


def test_checks_are_fixed_five_in_order() -> None:
    assert tiles.CHECKS == ("axis_flip", "y_range", "zoom_bbox", "wrap", "mixed_3857_4326")


def test_findings_follow_fixed_check_order(tmp_path: Path) -> None:
    result = tiles.run(_write_case(tmp_path, "case-003"))
    assert [f.check for f in result.findings] == list(tiles.CHECKS)


def test_describe_shape() -> None:
    assert [f.check for f in tiles.describe()] == list(tiles.CHECKS)


def test_flip_formula_is_documented_constant() -> None:
    assert tiles.FLIP_FORMULA == "2**z - 1 - y"


# ── 一、axis_flip：静态检出（无需底图）────────────────────────────────


def test_axis_flip_is_detected_statically(tmp_path: Path) -> None:
    case = _case("case-001")
    expected = _gold("case-001")
    result = tiles.run(_write_case(tmp_path, "case-001"))
    group = result.payload["groups"][0]

    pair = group["axis_flip"][0]
    assert pair["z"] == case["tiles"][0]["z"]
    assert pair["x"] == case["tiles"][0]["x"]
    assert pair["y"] == sorted([tile["y"] for tile in case["tiles"]])
    assert pair["y"][1] == expected["flipped_y"]
    assert pair["row_span"] == expected["row_span"]
    assert pair["bbox"] == case["bbox"], "两枚瓦片必须指向同一 bbox"
    assert tuple(sorted(pair["schemes"])) == ("tms", "xyz")

    finding = _finding(result, "axis_flip")
    assert finding.status == "conflict"
    assert finding.reason == "axis_flip"
    # 冲突点必须具体到 z/x/y（不是"发现混用"一句空话）
    assert f"z={pair['z']}" in finding.detail
    assert f"x={pair['x']}" in finding.detail
    assert "y=3" in finding.detail and "28" in finding.detail


def test_axis_flip_needs_shared_bbox_or_scheme_labels(tmp_path: Path) -> None:
    """无 bbox、无 scheme 标签时不得凭"两行并存"臆断混用（§4.7 要求"同一 bbox"）。"""
    plain = _write_tiles(
        tmp_path,
        "plain.json",
        {"tiles": [{"z": 5, "x": 26, "y": 3}, {"z": 5, "x": 26, "y": 28}]},
    )
    assert _finding(tiles.run(plain), "axis_flip").status == "consistent"

    labelled = _write_tiles(
        tmp_path,
        "labelled.json",
        {
            "tiles": [
                {"z": 5, "x": 26, "y": 3, "scheme": "xyz"},
                {"z": 5, "x": 26, "y": 28, "scheme": "tms"},
            ]
        },
    )
    assert _finding(tiles.run(labelled), "axis_flip").status == "conflict"


def test_non_complementary_rows_are_not_flagged(tmp_path: Path) -> None:
    path = _write_tiles(
        tmp_path,
        "adjacent.json",
        {
            "bbox": [116.0, 39.0, 117.0, 40.0],
            "tiles": [{"z": 5, "x": 26, "y": 3}, {"z": 5, "x": 26, "y": 4}],
        },
    )
    result = tiles.run(path)
    assert _finding(result, "axis_flip").status == "consistent"
    assert result.payload["groups"][0]["axis_flip"] == []


# ── 二、y_range：单点即判 ─────────────────────────────────────────────


def test_y_out_of_range_is_error_with_single_point(tmp_path: Path) -> None:
    expected = _gold("case-002")
    result = tiles.run(_write_case(tmp_path, "case-002"))
    offenders = result.payload["groups"][0]["y_range_offenders"]
    assert len(offenders) == 1, "单点即判"
    assert offenders[0]["y"] == expected["offending_y"]
    assert offenders[0]["allowed"] == expected["allowed"]

    finding = _finding(result, "y_range")
    assert finding.status == expected["y_range"] == "error"
    assert finding.reason == "y_range"
    assert f"y={expected['offending_y']}" in finding.detail


def test_y_in_range_is_consistent(tmp_path: Path) -> None:
    result = tiles.run(_write_case(tmp_path, "case-001"))
    assert _finding(result, "y_range").status == "consistent"


# ── 三、wrap：x 环绕必须显式声明 ───────────────────────────────────────


def test_wrap_declared_passes(tmp_path: Path) -> None:
    expected = _gold("case-003")
    result = tiles.run(_write_case(tmp_path, "case-003"))
    group = result.payload["groups"][0]
    assert group["wrap_needed"] is True, "x=0 与 x=2^z-1 同时出现即构成环绕"
    assert group["wrap_missing"] == []
    # 金标用 "ok" 记"通过"；`Finding.status` 的固定枚举里对应值是 `consistent`（plan/03 开头）。
    assert expected["wrap"] == "ok"
    assert _finding(result, "wrap").status == "consistent"


def test_wrap_missing_is_conflict_with_specific_tiles(tmp_path: Path) -> None:
    expected = _gold("case-004")
    result = tiles.run(_write_case(tmp_path, "case-004"))
    missing = result.payload["groups"][0]["wrap_missing"]
    assert missing, "缺 wrap 时必须列出具体瓦片"
    assert {(item["z"], item["x"], item["y"]) for item in missing} == {(2, 0, 1), (2, 3, 1)}

    finding = _finding(result, "wrap")
    assert finding.status == expected["wrap"] == "conflict"
    assert finding.reason == "wrap"


def test_wrap_not_needed_is_consistent(tmp_path: Path) -> None:
    path = _write_tiles(tmp_path, "single.json", {"tiles": [{"z": 2, "x": 1, "y": 1}]})
    assert _finding(tiles.run(path), "wrap").status == "consistent"


# ── 四、zoom_bbox：z+1 ⊆ z 展开 ────────────────────────────────────────


def test_zoom_bbox_break_is_conflict(tmp_path: Path) -> None:
    path = _write_tiles(
        tmp_path,
        "zoom.json",
        {
            "tiles": [
                {"z": 2, "x": 0, "y": 0},
                {"z": 3, "x": 5, "y": 1},  # 父瓦片是 (2, 2)，不在 z=2 集合里
            ]
        },
    )
    result = tiles.run(path)
    breaks = result.payload["groups"][0]["zoom_breaks"]
    assert len(breaks) == 1
    assert breaks[0]["missing_parent"] == {"z": 2, "x": 2, "y": 0}

    finding = _finding(result, "zoom_bbox")
    assert finding.status == "conflict"
    assert finding.reason == "zoom_bbox"
    assert "z=3" in finding.detail


def test_zoom_bbox_nested_is_consistent(tmp_path: Path) -> None:
    path = _write_tiles(
        tmp_path,
        "nested.json",
        {"tiles": [{"z": 2, "x": 0, "y": 0}, {"z": 3, "x": 0, "y": 0}]},
    )
    assert _finding(tiles.run(path), "zoom_bbox").status == "consistent"


# ── 五、mixed_3857_4326：同一集合内量级分档冲突 ────────────────────────


def test_mixed_degree_and_metre_points_is_conflict(tmp_path: Path) -> None:
    path = _write_tiles(
        tmp_path,
        "mixed.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"id": "a"},
                 "geometry": {"type": "Point", "coordinates": [112.0, 5.0]}},
                {"type": "Feature", "properties": {"id": "b"},
                 "geometry": {"type": "Point", "coordinates": [12000000.0, 5000000.0]}},
            ],
        },
    )
    finding = _finding(tiles.run(path), "mixed_3857_4326")
    assert finding.status == "conflict"
    assert finding.reason == "mixed"
    # 具体冲突点：两个坐标都要出现在说明里（题面 §M5 验收）
    assert "112.0" in finding.detail
    assert "12000000.0" in finding.detail
    assert finding.evidence["bands"] == {"degree": 1, "metre": 1, "neither": 0}


def test_all_degree_points_is_consistent(tmp_path: Path) -> None:
    path = _write_tiles(
        tmp_path,
        "degree.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"id": "a"},
                 "geometry": {"type": "Point", "coordinates": [112.0, 5.0]}},
                {"type": "Feature", "properties": {"id": "b"},
                 "geometry": {"type": "Point", "coordinates": [113.0, 6.0]}},
            ],
        },
    )
    assert _finding(tiles.run(path), "mixed_3857_4326").status == "consistent"


def test_tile_listing_marks_mixed_as_not_applicable(tmp_path: Path) -> None:
    result = tiles.run(_write_case(tmp_path, "case-003"))
    finding = _finding(result, "mixed_3857_4326")
    assert finding.status == "info"
    assert result.payload["input_kind"] == "tiles"


# ── 六、CSV 输入 / 失败路径 / 退出码 ───────────────────────────────────


def test_csv_tile_listing_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "tiles.csv"
    path.write_text("z,x,y,wrap\n2,3,1,true\n2,0,1,true\n", encoding="utf-8", newline="\n")
    result = tiles.run(path)
    assert result.payload["input_kind"] == "tiles"
    assert result.payload["counts"]["tiles"] == 2
    assert _finding(result, "wrap").status == "consistent"


def test_csv_y_out_of_range_is_error(tmp_path: Path) -> None:
    path = tmp_path / "tiles.csv"
    path.write_text("z,x,y\n3,3,9\n", encoding="utf-8", newline="\n")
    assert _finding(tiles.run(path), "y_range").status == "error"


def test_non_integer_tile_field_exits_4(tmp_path: Path) -> None:
    from crsscope.errors import InvalidInput

    path = _write_tiles(tmp_path, "bad.json", {"tiles": [{"z": 3, "x": 3, "y": "9"}]})
    with pytest.raises(InvalidInput) as exc:
        tiles.run(path)
    assert exc.value.code == 4
    assert "必须是整数" in str(exc.value)

    out_dir = tmp_path / "out"
    assert main(["tiles", str(path), "--out-dir", str(out_dir)]) == 4
    assert not out_dir.exists() or not list(out_dir.iterdir())


def test_missing_file_exits_3(tmp_path: Path) -> None:
    assert main(["tiles", str(tmp_path / "nope.json"), "--out-dir", str(tmp_path / "o")]) == 3


def test_full_corpus_aggregates_all_four_cases() -> None:
    result = tiles.run(CORPUS)
    counts = result.payload["counts"]
    assert counts["groups"] == 4
    assert counts["axis_flip_pairs"] == 1  # case-001
    assert counts["y_range_offenders"] == 1  # case-002
    assert counts["wrap_missing"] == 2  # case-004 的两枚
    assert counts["zoom_breaks"] == 0
    statuses = {f.check: f.status for f in result.findings}
    assert statuses["axis_flip"] == "conflict"
    assert statuses["y_range"] == "error"
    assert statuses["wrap"] == "conflict"


def test_clean_case_exits_zero_and_writes_reports(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "out"
    code = main(["tiles", str(_write_case(tmp_path, "case-003")), "--json",
                 "--out-dir", str(out_dir)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["exit_code"] == 0
    assert (out_dir / "report.json").is_file()
    assert (out_dir / "report.md").is_file()


def test_axis_flip_corpus_exits_one(tmp_path: Path) -> None:
    assert main(["tiles", str(_write_case(tmp_path, "case-001")),
                 "--out-dir", str(tmp_path / "o")]) == 1


def test_y_range_corpus_exits_one(tmp_path: Path) -> None:
    assert main(["tiles", str(_write_case(tmp_path, "case-002")),
                 "--out-dir", str(tmp_path / "o")]) == 1


def test_fail_on_narrows_hit_set_to_named_check(tmp_path: Path) -> None:
    """`--fail-on axis_flip` 只认点名的检查项：同一份 case-002 语料不命中 → 0。"""
    assert main(["tiles", str(_write_case(tmp_path, "case-002")), "--fail-on", "axis_flip",
                 "--out-dir", str(tmp_path / "o1")]) == 0
    assert main(["tiles", str(_write_case(tmp_path, "case-001")), "--fail-on", "axis_flip",
                 "--out-dir", str(tmp_path / "o2")]) == 1


def test_payload_has_no_rendering_artifacts() -> None:
    """不做渲染 / 切片 / 图片（题面 §M5 三条纪律）：payload 里不得出现图像产物字段。"""
    result = tiles.run(CORPUS)
    forbidden = {"image", "png", "render", "tile_image", "preview", "map"}
    assert not (set(result.payload) & forbidden)
    assert all("image" not in key for key in result.payload)


def test_run_is_deterministic(tmp_path: Path) -> None:
    from crsscope import report

    path = _write_case(tmp_path, "case-001")
    assert report.dumps_json(tiles.run(path).payload) == report.dumps_json(tiles.run(path).payload)

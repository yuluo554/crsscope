"""模块 M1「声明-内容一致性」的判定守门（`plan/03` §一 + `plan/05` §三 M2 DoD）。

**这批测试吃的是真实语料**（`data/fixtures/*/out/*.geojson`，由 `tests/conftest.py`
在干净 clone 上先补齐），不是内联构造的玩具数据——金标已经把"哪一类样本命中哪一条判据"
写死在 `expect.json` 里，这里逐条对拍。

三条各自可证伪的判据：

1. **两类样本互不串扰**（`data/README.md` §4.1 末条）：`swapped_axis` 只命中 `axis`，
   `declared_lie` 只命中 `magnitude`——不是"同一份样本顺带把两条都点亮"。
2. **灰区必须 `undecidable`**：可判定样本 `< 5` 时不得凭少量点下结论，退出码 5
   （`--allow-undecidable` 才放行到 0）。
3. **退出码契约**（§4.9）：裸命令下 `conflict` 即命中 → exit 1；`--fail-on` 收窄命中面；
   非法 `--declared-crs` → exit 2。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crsscope import decl
from crsscope.cli import main
from crsscope.errors import UsageError, outcome_code, parse_fail_on

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "data" / "fixtures"

SWAPPED_AXIS = FIXTURES / "swapped_axis" / "out" / "swapped_axis.geojson"
DECLARED_LIE = FIXTURES / "declared_lie" / "out" / "declared_lie.geojson"


def _finding(result, check: str):
    hits = [f for f in result.findings if f.check == check]
    assert len(hits) == 1, f"{check} 项应恰好一条，实得 {[f.check for f in result.findings]}"
    return hits[0]


def _checks(result) -> list[str]:
    return [f.check for f in result.findings]


# ── 零、判定顺序与形态 ────────────────────────────────────────────────


def test_findings_follow_fixed_check_order() -> None:
    """判定顺序固定、不许重排（`plan/03` §一）。顺序错了，量级就压不住米域样本。"""
    result = decl.run(SWAPPED_AXIS, "4326")
    assert _checks(result) == list(decl.CHECKS)


def test_describe_lists_the_same_checks() -> None:
    """`describe()` 供 `--help` 与契约测试用，必须与 `CHECKS` 同源。"""
    assert [f.check for f in decl.describe()] == list(decl.CHECKS)


def test_illegal_declared_crs_raises_usage_error() -> None:
    """GCJ-02 没有 EPSG 代码，不是合法声明值（`data/README.md` §1.2）→ exit 2。"""
    with pytest.raises(UsageError) as exc:
        decl.run(SWAPPED_AXIS, "gcj02")
    assert exc.value.code == 2
    assert "3857" in (exc.value.detail or ""), "报错必须列出合法枚举"


# ── 一、两类样本各自命中（互不串扰）────────────────────────────────────


def test_swapped_axis_hits_axis_conflict_only() -> None:
    """轴序写反 → `conflict/axis`；量级必须留在度域，不许把 `magnitude` 一起点亮。"""
    result = decl.run(SWAPPED_AXIS, "4326")

    axis = _finding(result, "axis")
    assert axis.status == "conflict"
    assert axis.reason == "axis", "命中原因必须是 axis，不能靠 magnitude 串扰"
    assert result.payload["axis_decidable"] is True

    magnitude = _finding(result, "magnitude")
    assert magnitude.status == "consistent", "轴序样本全在度域，量级不得报冲突"
    assert magnitude.reason is None

    assert not [f for f in result.findings if f.status == "conflict" and f.check != "axis"], (
        "swapped_axis 只应命中 axis 一条 conflict"
    )
    assert not [f for f in result.findings if f.status == "undecidable"]


def test_swapped_axis_gold_matches_run() -> None:
    """逐对拍入仓金标：每个 case 的写反形态与纠正值都必须真的被本判定复现。"""
    gold = json.loads((FIXTURES / "swapped_axis" / "expect.json").read_text(encoding="utf-8"))
    result = decl.run(SWAPPED_AXIS, "4326")
    axis = _finding(result, "axis")

    assert len(gold["cases"]) >= decl.MIN_AXIS_SAMPLES
    for case in gold["cases"]:
        a, b = case["input"]
        case_expected = case["expected"]
        # 金标断言：第二分量越出纬度域、第一分量仍在经度域 → 判据必须成立
        assert abs(b) > 90 and abs(a) <= 90, case
        assert case_expected["corrected"] == [b, a], "金标纠正值应是纯交换"
    assert axis.evidence["decidable_samples"] == len(gold["cases"])
    assert axis.evidence["affected_samples"] == len(gold["cases"])
    assert axis.evidence["corrected_sample"] == gold["cases"][0]["expected"]["corrected"]


def test_declared_lie_hits_magnitude_conflict_only() -> None:
    """`crs` 声明 4326、坐标却是米域 → `conflict/magnitude`；轴序不得报 `conflict`。"""
    result = decl.run(DECLARED_LIE, "4326")

    magnitude = _finding(result, "magnitude")
    assert magnitude.status == "conflict"
    assert magnitude.reason == "magnitude", "命中原因必须是 magnitude，不能靠 axis 串扰"

    axis = _finding(result, "axis")
    assert axis.status == "undecidable", "米域样本不进轴序可判定子集 → 只能 undecidable"
    assert axis.reason == "insufficient_samples"
    assert axis.status != "conflict"
    assert result.payload["axis_decidable"] is False

    assert not [f for f in result.findings if f.status == "conflict" and f.check != "magnitude"], (
        "declared_lie 只应命中 magnitude 一条 conflict"
    )


def test_declared_lie_gold_matches_run() -> None:
    """金标里的 `magnitude_m` / `magnitude_band` / `axis_decidable` 必须逐字段对上。"""
    gold = json.loads((FIXTURES / "declared_lie" / "expect.json").read_text(encoding="utf-8"))
    result = decl.run(DECLARED_LIE, "4326")
    magnitude = _finding(result, "magnitude")

    assert gold["cases"], "金标不许为空"
    worst = max(c["expected"]["magnitude_m"] for c in gold["cases"])
    assert magnitude.evidence["magnitude_m"] == pytest.approx(worst, abs=1e-6)
    assert magnitude.evidence["bands"] == {"metre": len(gold["cases"])}
    for case in gold["cases"]:
        assert case["expected"]["magnitude_band"] == "metre"
        assert case["expected"]["axis_decidable"] is False
    assert result.payload["axis_decidable"] is False


def test_two_targets_do_not_light_each_other_up() -> None:
    """互不串扰的**对照**断言：把两类样本的命中集直接比一遍。"""
    axis_hits = {f.reason for f in decl.run(SWAPPED_AXIS, "4326").findings if f.reason}
    lie_hits = {f.reason for f in decl.run(DECLARED_LIE, "4326").findings if f.reason}
    assert "axis" in axis_hits and "axis" not in lie_hits
    assert "magnitude" in lie_hits and "magnitude" not in axis_hits


# ── 二、灰区：可判定样本不足必须 undecidable ────────────────────────────


def _write_geojson(path: Path, pairs: list[list[float]]) -> Path:
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


def test_too_few_decidable_samples_is_undecidable(tmp_path: Path) -> None:
    """4 个可判定样本（全部落在 ±90 内）→ `undecidable/insufficient_samples`，不得下结论。"""
    path = _write_geojson(tmp_path / "few.geojson", [[112.0, 5.0], [112.1, 5.1], [112.2, 5.2], [112.3, 5.3]])
    result = decl.run(path, "4326")
    axis = _finding(result, "axis")
    assert axis.status == "undecidable"
    assert axis.reason == "insufficient_samples"
    assert axis.evidence["decidable_samples"] == 4


def test_all_within_90_is_undecidable_even_with_enough_samples(tmp_path: Path) -> None:
    """可判定样本够多、但两分量都在 ±90 内 → 两种排列无法区分，仍须 `undecidable`（§4.1）。"""
    pairs = [[40.0 + i * 0.1, 5.0 + i * 0.1] for i in range(6)]
    result = decl.run(_write_geojson(tmp_path / "ambig.geojson", pairs), "4326")
    axis = _finding(result, "axis")
    assert axis.status == "undecidable"
    assert axis.reason is None
    assert result.payload["axis_decidable"] is False


def test_undecidable_exits_5_unless_allowed(tmp_path: Path) -> None:
    """`undecidable` 未获准 → exit 5；`--allow-undecidable` → exit 0（与 0 严格区分，§4.9）。"""
    path = _write_geojson(tmp_path / "few.geojson", [[112.0, 5.0], [112.1, 5.1], [112.2, 5.2]])
    out = tmp_path / "out"

    assert main(["decl", str(path), "--declared-crs", "4326", "--json",
                 "--out-dir", str(out)]) == 5
    assert main(["decl", str(path), "--declared-crs", "4326", "--json",
                 "--allow-undecidable", "--out-dir", str(out)]) == 0


def test_missing_file_is_environment_error(tmp_path: Path) -> None:
    assert main(["decl", str(tmp_path / "nope.geojson"), "--out-dir", str(tmp_path)]) == 3


# ── 三、其余检查项各自单独成立 ────────────────────────────────────────


def test_mixed_bands_conflict(tmp_path: Path) -> None:
    """前半段米、后半段度 → `conflict/mixed`（`plan/03` §一 测试点）。"""
    pairs = [[112.0e0, 5.0e0], [112.1, 5.1], [112.2e6, 500000.0], [112.3e6, 500001.0]]
    result = decl.run(_write_geojson(tmp_path / "mixed.geojson", pairs), "4326")
    mixed = _finding(result, "mixed")
    assert mixed.status == "conflict"
    assert mixed.reason == "mixed"
    assert mixed.evidence["bands"] == {"degree": 2, "metre": 2}


def test_unit_conflict_when_3857_declared_but_degree_coordinates(tmp_path: Path) -> None:
    """声明 3857 + 度域坐标 → `conflict/unit`（`plan/03` §一 测试点）。"""
    pairs = [[112.0 + i * 0.1, 5.0 + i * 0.1] for i in range(5)]
    result = decl.run(_write_geojson(tmp_path / "deg.geojson", pairs), "3857")
    unit = _finding(result, "unit")
    assert unit.status == "conflict"
    assert unit.reason == "unit"
    assert unit.evidence["degree_domain_samples"] == 5


def test_extent_suggests_candidate_when_framework_mismatches(tmp_path: Path) -> None:
    """声明地理坐标系但全在米域 → extent `undecidable` + **建议候选**（`plan/01` M1 第 3 条）。"""
    result = decl.run(DECLARED_LIE, "4326")
    extent = _finding(result, "extent")
    assert extent.status == "undecidable"
    assert extent.evidence["candidates"] == ["3857"]
    assert result.payload["candidates"] == ["3857"]


def test_extent_conflict_when_out_of_geographic_range(tmp_path: Path) -> None:
    """声明地理坐标系、轴序未反、外包框却越出 ±180/±90 → `conflict`（不是 warning）。"""
    pairs = [[179.0, 89.5], [179.1, 89.6], [179.2, 95.0], [179.3, 89.8], [179.4, 89.9]]
    result = decl.run(_write_geojson(tmp_path / "far.geojson", pairs), "4326")
    extent = _finding(result, "extent")
    assert extent.status == "conflict"
    assert extent.evidence["out_of_range_samples"] >= 1


def test_file_declared_crs_member_is_honoured_when_cli_is_silent() -> None:
    """CLI 不给声明时，文件内 `crs` 成员（CRS84）要参与判定，且来源记进报告头。"""
    result = decl.run(DECLARED_LIE, None)
    assert result.payload["header"]["declared_crs"] == "crs84"
    assert result.payload["header"]["declared_crs_source"] == "file"
    assert _finding(result, "magnitude").status == "conflict"


def test_unrecognised_crs_member_is_not_guessed(tmp_path: Path) -> None:
    """认不出的 `crs` 名字不许猜成某个枚举值（会把"没声明"伪装成"声明错了"）。"""
    payload = {
        "type": "Feature",
        "crs": {"properties": {"name": "urn:example:something-else"}, "type": "name"},
        "geometry": {"type": "Point", "coordinates": [112.0, 5.0]},
    }
    path = tmp_path / "weird.geojson"
    path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
    result = decl.run(path, None)
    assert result.payload["header"]["declared_crs"] == "none"
    assert result.payload["header"]["declared_crs_source"] == "file-unrecognised"
    assert "declaration_note" in result.payload


def test_strict_promotes_missing_declaration_to_undecidable(tmp_path: Path) -> None:
    """`--strict` 的唯一语义：没有声明值时不许"没得比"了事 → 升为 `undecidable`。"""
    path = _write_geojson(tmp_path / "nodecl.geojson", [[112.0 + i * 0.1, 5.0 + i * 0.1] for i in range(5)])
    lax = decl.run(path, None)
    strict = decl.run(path, None, strict=True)
    assert _finding(lax, "magnitude").status == "info"
    assert _finding(strict, "magnitude").status == "undecidable"


# ── 四、退出码契约（§4.9）────────────────────────────────────────────


def test_swapped_axis_command_exits_1_and_reports_axis(tmp_path: Path, capsys) -> None:
    """真命令：裸 `decl` 命中 `conflict` 即 exit 1；`--json` 里必须有 `check=axis`。"""
    code = main(["decl", str(SWAPPED_AXIS), "--declared-crs", "4326", "--json",
                 "--out-dir", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["exit_code"] == 1
    axis = [f for f in payload["findings"] if f["check"] == "axis"]
    assert axis and axis[0]["status"] == "conflict" and axis[0]["reason"] == "axis"


def test_fail_on_narrows_the_hit_set(tmp_path: Path) -> None:
    """`--fail-on` 给定时**收窄**：点错类别就不算命中（否则这个参数没有语义）。"""
    out = tmp_path / "out"
    base = ["decl", str(SWAPPED_AXIS), "--declared-crs", "4326", "--json", "--out-dir", str(out)]
    assert main([*base, "--fail-on", "axis"]) == 1
    assert main([*base, "--fail-on", "magnitude"]) == 0
    assert main([*base, "--fail-on", "conflict"]) == 1


def test_clean_data_exits_0(tmp_path: Path) -> None:
    """五项检查全绿（含允许轴序"无法区分"这一灰区）→ exit 0。否则"绿"就没有分界。"""
    pairs = [[111.0, 5.0], [112.0, 6.0], [113.0, 7.0], [114.0, 8.0], [115.0, 9.0]]
    path = _write_geojson(tmp_path / "clean.geojson", pairs)
    assert main(["decl", str(path), "--declared-crs", "4326", "--json",
                 "--out-dir", str(tmp_path), "--allow-undecidable"]) == 0


def test_outcome_code_default_states() -> None:
    """命中面：默认含 `conflict` / `error`，**不含 `warning`**（§4.6 的 R1 分级纪律）。"""
    from crsscope.report import Finding

    clean = [Finding(check="axis", status="consistent", detail="ok")]
    conflicted = [Finding(check="axis", status="conflict", reason="axis", detail="x")]
    warned = [Finding(check="ring_order", status="warning", reason="ring", detail="x")]
    undecided = [Finding(check="axis", status="undecidable", reason="insufficient_samples", detail="x")]

    assert outcome_code(clean) == 0
    assert outcome_code(conflicted) == 1
    assert outcome_code(warned) == 0, "warning 默认不算命中（--strict-ring 才升级）"
    assert outcome_code(warned, fail_on="ring") == 1, "--fail-on 是 warning 的升级路径"
    assert outcome_code(undecided) == 5
    assert outcome_code(undecided, allow_undecidable=True) == 0


def test_parse_fail_on_trims_and_dedupes() -> None:
    assert parse_fail_on(" conflict , axis ,,conflict ") == ("conflict", "axis")
    assert parse_fail_on("") == ()
    assert parse_fail_on(None) == ()
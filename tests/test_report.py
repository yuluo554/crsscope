"""`report` 子命令的判定守门（HANDOFF-M6 §三A + `plan/03` §七）。

**聚合测试吃真实产物**：先在 tmp_path 里真跑五个判定子命令拿它们落盘的
`report.json`，再喂给 `report` 汇总——不造假报告，与 test_decl / test_detect
吃真实语料是同一条纪律（跑命令一律传 `--out-dir tmp_path`，不污染仓库根）。

判据分五组，各自可证伪：

1. **聚合**：五份真实报告的 findings 原样并入，逐条标 `evidence.source`；
   `sources` 汇总每份的 `command` / `exit_code` / 条数；`counts` 与 findings 一致。
2. **退出码优先级**：聚合集里有 `undecidable` → 5（灰区优先），即便另有 conflict；
   `--allow-undecidable` 放行后回落到命中 → 1。折算只走 `errors.outcome_code`。
3. **`--fail-on` 收窄**：默认不算命中的 `warning`，点名后才算；点名没命中的类别保持 0。
4. **失败路径**：缺文件 → 3；坏 JSON / 顶层缺 `findings` / findings 元素缺 status → 4。
5. **确定性**：同一组输入跑两遍，聚合 payload 逐字节相等（不读时钟）。
"""

from __future__ import annotations

import json
from pathlib import Path

from crsscope import report
from crsscope.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "data" / "fixtures"

#: 五个子命令各跑一条真实语料（与 HANDOFF-M6 §七 命令速查同源）。
#: `detect` 必须带 `--mask`：§4.3 禁止默认"全是陆地"，掩膜缺失会以 exit 3 拒跑。
FIVE_RUNS: list[tuple[list[str], str]] = [
    (
        [
            "decl",
            str(FIXTURES / "geojson_struct/out/case-002_ring_ccw.geojson"),
            "--declared-crs",
            "4326",
        ],
        "decl",
    ),
    (
        ["detect", str(FIXTURES / "four_crs/out/four_crs_wgs84.geojson"), "--mask",
         str(REPO_ROOT / "data" / "mask" / "out" / "mask_v1.json")],
        "detect",
    ),
    (
        ["xdiff", str(FIXTURES / "four_crs/out/four_crs_wgs84.geojson"), "--target", "gcj02"],
        "xdiff",
    ),
    (
        ["geojson", str(FIXTURES / "geojson_struct/out/case-001_ring_cw.geojson"), "--strict-ring"],
        "geojson",
    ),
    (["tiles", str(FIXTURES / "tile_flip/out/tile_flip.json")], "tiles"),
]


def _produce_reports(tmp_path: Path) -> list[Path]:
    """真跑五个子命令，返回各自 report.json 的路径（顺带断言都真的落盘了）。"""
    paths: list[Path] = []
    for argv, name in FIVE_RUNS:
        out_dir = tmp_path / name
        main([*argv, "--json", "--out-dir", str(out_dir)])
        path = out_dir / "report.json"
        assert path.is_file(), f"{name} 未落盘 report.json"
        paths.append(path)
    return paths


def _write_report(tmp_path: Path, name: str, findings: list[dict], *, exit_code: int = 0) -> Path:
    path = tmp_path / name
    payload = {
        "header": {"tool": "crsscope", "command": "synthetic", "generated_at": "1970-01-01T00:00:00Z"},
        "findings": findings,
        "exit_code": exit_code,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
    return path


# ── 一、聚合 ──────────────────────────────────────────────────────────


def test_aggregates_five_real_reports(tmp_path: Path) -> None:
    paths = _produce_reports(tmp_path)
    out_dir = tmp_path / "agg"
    code = main(["report", *[str(p) for p in paths], "--json", "--out-dir", str(out_dir)])
    # decl 那份报告含 insufficient_samples → undecidable；灰区优先于 geojson/tiles 的命中。
    assert code == 5

    summary = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert len(summary["sources"]) == 5
    assert {s["command"] for s in summary["sources"]} == {"decl", "detect", "xdiff", "geojson", "tiles"}
    # 五份输入同名 report.json → 标签按出现序消歧；不存绝对路径
    assert {s["file"] for s in summary["sources"]} == {
        "report.json",
        "report.json#2",
        "report.json#3",
        "report.json#4",
        "report.json#5",
    }
    counts = summary["counts"]
    assert sum(counts.values()) == len(summary["findings"])
    assert counts.get("undecidable", 0) >= 1
    assert summary["header"]["command"] == "report"
    assert summary["header"]["report_count"] == 5


def test_each_finding_is_attributed_to_its_source_report(tmp_path: Path) -> None:
    paths = _produce_reports(tmp_path)
    result = report.run(paths)
    labels = {s["file"] for s in result.payload["sources"]}
    by_source: dict[str, int] = {}
    for f in result.findings:
        assert f.evidence.get("source") in labels
        by_source[f.evidence["source"]] = by_source.get(f.evidence["source"], 0) + 1
    assert sum(by_source.values()) == len(result.findings)
    # 每份输入报告的条数与 sources 汇总对得上（同名输入靠 #k 标签区分）
    for src in result.payload["sources"]:
        assert src["findings"] == by_source[src["file"]]
    assert len(labels) == 5


def test_source_summary_records_original_exit_codes(tmp_path: Path) -> None:
    paths = _produce_reports(tmp_path)
    result = report.run(paths)
    codes = {s["command"]: s["exit_code"] for s in result.payload["sources"]}
    # 三份已知金标：decl → 5（轴序样本不足）、geojson → 1（--strict-ring 下环方向 error）、
    # tiles → 1（axis_flip conflict）。聚合层原样转抄，不改写。
    assert codes["decl"] == 5
    assert codes["geojson"] == 1
    assert codes["tiles"] == 1


def test_gate_verdict_mirrors_outcome_priority(tmp_path: Path) -> None:
    good = _write_report(tmp_path, "good.json", [{"check": "axis", "status": "consistent", "detail": "ok"}])
    assert report.gate_verdict({"consistent": 1}).startswith("门禁通过")
    result = report.run([good])
    assert result.payload["verdict"].startswith("门禁通过")


# ── 二、退出码优先级（只走 errors.outcome_code，不另写映射）──────────────


def test_undecidable_beats_conflict_then_allow_flag_falls_back_to_hit(tmp_path: Path) -> None:
    paths = _produce_reports(tmp_path)
    argv = ["report", *[str(p) for p in paths]]
    out_dir = tmp_path / "gate"
    assert main([*argv, "--json", "--out-dir", str(out_dir)]) == 5
    assert main([*argv, "--allow-undecidable", "--json", "--out-dir", str(out_dir)]) == 1


def test_pass_gate_exits_zero(tmp_path: Path) -> None:
    good = _write_report(tmp_path, "a.json", [{"check": "axis", "status": "consistent", "detail": "ok"}])
    info = _write_report(tmp_path, "b.json", [{"check": "bbox", "status": "info", "detail": "no bbox"}])
    out_dir = tmp_path / "out"
    assert main(["report", str(good), str(info), "--json", "--out-dir", str(out_dir)]) == 0


# ── 三、--fail-on 收窄 ────────────────────────────────────────────────


def test_fail_on_narrows_to_named_category(tmp_path: Path) -> None:
    warn = _write_report(
        tmp_path,
        "w.json",
        [{"check": "ring_order", "status": "warning", "reason": "ring", "detail": "R1 违规"}],
    )
    clean = _write_report(tmp_path, "c.json", [{"check": "bbox", "status": "info", "detail": "ok"}])
    argv = ["report", str(warn), str(clean)]
    out_dir = tmp_path / "out"
    # 默认：warning 不算命中（§4.9 / K16）→ 0；点名 ring 后才算 → 1；
    # 点名一个没有负向发现的类别（bbox 只有 info）→ 仍 0。
    assert main([*argv, "--json", "--out-dir", str(out_dir)]) == 0
    assert main([*argv, "--fail-on", "ring", "--json", "--out-dir", str(out_dir)]) == 1
    assert main([*argv, "--fail-on", "bbox", "--json", "--out-dir", str(out_dir)]) == 0


# ── 四、失败路径（§4.9：缺文件 3，输入无效 4）──────────────────────────


def test_missing_file_exits_3(tmp_path: Path) -> None:
    assert main(["report", str(tmp_path / "nope.json")]) == 3


def test_bad_json_exits_4(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{oops", encoding="utf-8")
    assert main(["report", str(path)]) == 4


def test_top_level_missing_findings_exits_4(tmp_path: Path) -> None:
    path = tmp_path / "no_findings.json"
    path.write_text('{"header": {}}', encoding="utf-8")
    assert main(["report", str(path)]) == 4


def test_finding_without_status_exits_4(tmp_path: Path) -> None:
    path = _write_report(tmp_path, "bad_shape.json", [{"check": "axis", "detail": "缺 status"}])
    assert main(["report", str(path)]) == 4


def test_no_args_is_usage_error() -> None:
    assert main(["report"]) == 2


# ── 五、确定性 ────────────────────────────────────────────────────────


def test_same_inputs_aggregate_byte_identical(tmp_path: Path) -> None:
    warn = _write_report(
        tmp_path,
        "w.json",
        [{"check": "ring_order", "status": "warning", "reason": "ring", "detail": "R1 违规"}],
    )
    a = report.run([warn, warn])
    b = report.run([warn, warn])
    from crsscope.report import dumps_json

    pa = dict(a.payload)
    pb = dict(b.payload)
    pa.setdefault("findings", [f.as_dict() for f in a.findings])
    pb.setdefault("findings", [f.as_dict() for f in b.findings])
    assert dumps_json(pa) == dumps_json(pb)

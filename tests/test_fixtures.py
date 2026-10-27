"""语料契约守门（`plan/04` §1.1 / §二 + `plan/05` §三 M1 DoD）。

四条判据，各自可证伪：

1. **每份生成器 `--check` exit 0**（重生成与冻结产物逐字节一致）；
2. **`expect.json` 的键集合符合 `plan/04` §2.1**（`fixture` / `generator_version` / `cases`）；
3. **金标里没有 `observed` 一类字段**（真值纪律：只存"输入 + 期望"）；
4. **边界分歧三例的数值与 `data/README.md` §1.3 对照表逐格一致**（且由常数直接代入算出，
   **不复用** `crsscope.algorithms`）。

第 4 条是本题最容易被写成"循环论证"的地方：金标若从生产实现取数，
`--check` 绿灯只证明"实现没变"，不证明"实现正确"。因此这里**另写一份**判定式。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "data" / "fixtures"
MASK_DIR = REPO_ROOT / "data" / "mask"

#: `plan/04` §一 的七份 fixture（F1–F7）。少一份 = M1 没做完。
FIXTURE_NAMES = (
    "four_crs",
    "swapped_axis",
    "declared_lie",
    "boundary_divergence",
    "water_track",
    "tile_flip",
    "geojson_struct",
)

#: `plan/04` §2.1 的顶层键（多一个都算偏离）。
EXPECT_TOP_KEYS = {"fixture", "generator_version", "cases"}
#: 允许的附加顶层键（说明性字段，不影响判据）。
EXPECT_OPTIONAL_KEYS = {"notes", "track", "mask", "coverage", "expected", "rfc"}

#: 金标里禁止出现的键名（`plan/04` §二：真值只存"输入 + 期望"，不存"观测"）。
FORBIDDEN_KEYS = {"observed", "observed_value", "actual", "actual_value", "measured"}


def _generators() -> list[Path]:
    gens = [FIXTURES_DIR / name / "gen.py" for name in FIXTURE_NAMES]
    gens.append(MASK_DIR / "gen.py")
    return gens


def _gen_id(gen: Path) -> str:
    return gen.parent.name if gen.parent.parent.name == "fixtures" else "mask"


def test_all_fixture_generators_exist() -> None:
    """阳性对照：七份 fixture + 掩膜，一个都不能少。"""
    missing = [str(g.relative_to(REPO_ROOT)) for g in _generators() if not g.is_file()]
    assert not missing, f"缺生成器: {missing}"


def test_shared_genlib_exists() -> None:
    """共用框架必须在位，否则各生成器会各自复制一份 `--check` 实现（口径必然漂移）。"""
    assert (REPO_ROOT / "data" / "_genlib.py").is_file()


@pytest.mark.parametrize("gen", _generators(), ids=_gen_id)
def test_generator_check_is_byte_identical(gen: Path) -> None:
    """`--check` 必须 exit 0：重生成结果与冻结产物逐字节一致。"""
    proc = subprocess.run(
        [sys.executable, str(gen), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, f"{gen.parent.name} --check 失败：\n{proc.stdout}\n{proc.stderr}"
    assert "逐字节一致" in proc.stdout or "CHECK" in proc.stdout


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_expect_json_has_required_keys(name: str) -> None:
    """金标顶层键必须是 `plan/04` §2.1 的形状（缺键与多键都红）。"""
    path = FIXTURES_DIR / name / "expect.json"
    assert path.is_file(), f"{name}/expect.json 是入仓金标，不许缺"
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = set(data)
    assert EXPECT_TOP_KEYS <= keys, f"{name} 缺顶层键 {sorted(EXPECT_TOP_KEYS - keys)}"
    extra = keys - EXPECT_TOP_KEYS - EXPECT_OPTIONAL_KEYS
    assert not extra, f"{name} 出现未登记的顶层键 {sorted(extra)}"
    assert data["fixture"] == name, f"{name} 的 fixture 字段写成 {data['fixture']!r}"
    assert isinstance(data["generator_version"], str) and data["generator_version"]
    assert isinstance(data["cases"], list) and data["cases"], "cases 必须是非空数组"


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_case_ids_match_pattern(name: str) -> None:
    """`id` 形如 `case-\\d{3}`——不出现真实地名 / 真实用户（`data/README.md` §三.3）。"""
    import re

    path = FIXTURES_DIR / name / "expect.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    pattern = re.compile(r"^(case|demo)-\d{3}$")
    bad = [c.get("id") for c in data["cases"] if not pattern.match(str(c.get("id", "")))]
    assert not bad, f"{name} 的 id 不合规: {bad}"


def _walk_keys(node: object, path: str = "") -> list[str]:
    """递归收集所有键名（含数组内元素），带路径前缀便于定位。"""
    out: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            out.append(key)
            out.extend(_walk_keys(value, f"{path}/{key}"))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            out.extend(_walk_keys(value, f"{path}[{i}]"))
    return out


@pytest.mark.parametrize("name", [*FIXTURE_NAMES, "mask"])
def test_expect_json_has_no_observed_fields(name: str) -> None:
    """真值纪律：金标里出现 `observed` 一类字段即违规（`plan/04` §二）。"""
    base = FIXTURES_DIR / name if name != "mask" else MASK_DIR
    data = json.loads((base / "expect.json").read_text(encoding="utf-8"))
    found = sorted({k for k in _walk_keys(data) if k.lower() in FORBIDDEN_KEYS})
    assert not found, f"{name}/expect.json 出现观测类字段 {found}（只允许'输入 + 期望'）"


def test_observed_field_detector_sees_planted_sample() -> None:
    """探活：判据必须能抓到阳性样本，否则"零命中"只是判据没工作。"""
    planted = {"cases": [{"id": "case-001", "observed": 1.0, "expected": {}}]}
    found = {k for k in _walk_keys(planted) if k.lower() in FORBIDDEN_KEYS}
    assert found == {"observed"}


# ── 边界分歧三例：常数直接代入，**不复用** crsscope.algorithms ─────────────
# 常数照录 `data/README.md` §1.3（开区间 / 闭区间是实质差异，不是浮点噪声）
CT_PY_LON = (73.66, 135.05)
CT_PY_LAT = (3.86, 53.55)
GCOORD_LON = (72.004, 137.8347)
GCOORD_LAT = (0.8293, 55.8271)


def _ct_py_inside(lon: float, lat: float) -> bool:
    return CT_PY_LON[0] < lon < CT_PY_LON[1] and CT_PY_LAT[0] < lat < CT_PY_LAT[1]


def _gcoord_inside(lon: float, lat: float) -> bool:
    return GCOORD_LON[0] <= lon <= GCOORD_LON[1] and GCOORD_LAT[0] <= lat <= GCOORD_LAT[1]


@pytest.mark.parametrize(
    ("lon", "lat", "ct", "gc", "agree"),
    [
        (73.2, 39.5, "outside", "inside", False),  # 经向分歧
        (112.0, 2.0, "outside", "inside", False),  # 纬向分歧（< 3.86°N）
        (112.0, 5.0, "inside", "inside", True),  # 一致对照（决策 ⑥：5°N 不是分歧）
        (112.0, 60.0, "outside", "outside", True),  # 一致对照（都不偏移）
    ],
)
def test_boundary_divergence_matches_data_ledger(
    lon: float, lat: float, ct: str, gc: str, agree: bool
) -> None:
    """`data/README.md` §1.3 对照表逐格对拍——用本文件自己的常数，不用生产实现。"""
    got_ct = "inside" if _ct_py_inside(lon, lat) else "outside"
    got_gc = "inside" if _gcoord_inside(lon, lat) else "outside"
    assert (got_ct, got_gc) == (ct, gc), f"({lon},{lat}) 代入常数得 ({got_ct},{got_gc})"
    assert (got_ct == got_gc) is agree


def test_boundary_divergence_fixture_matches_independent_computation() -> None:
    """语料里的金标必须与"独立代入"的结果逐字段相等（金标不许来自生产实现）。"""
    path = FIXTURES_DIR / "boundary_divergence" / "expect.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["cases"]) == 4
    for case in data["cases"]:
        lon, lat = case["lon"], case["lat"]
        want = ("inside" if _ct_py_inside(lon, lat) else "outside",
                "inside" if _gcoord_inside(lon, lat) else "outside")
        got = (case["coordTransform_py"], case["gcoord"])
        assert got == want, f"{case['id']} 金标 {got} 与独立复算 {want} 不符"
        assert case["expected"]["boundary_table_row"]["agree"] == (want[0] == want[1])


def test_open_vs_closed_interval_semantics() -> None:
    """开/闭区间的差异必须能被观察到（端点语义是本题的审计发现点之一）。"""
    assert _ct_py_inside(CT_PY_LON[0], 39.5) is False, "开区间端点算境外"
    assert _gcoord_inside(GCOORD_LON[0], 39.5) is True, "闭区间端点算境内"


# ── M1 出口判据：语料与掩膜真的落盘了 ──────────────────────────────────
def test_fixture_artifacts_present() -> None:
    """`--check` 允许生成物缺席（干净 clone 常态），但**跑完补齐后**必须都在。"""
    for name in FIXTURE_NAMES:
        out_dir = FIXTURES_DIR / name / "out"
        assert out_dir.is_dir(), f"{name}/out 缺失 —— session fixture 应已补齐"
        assert any(p.is_file() for p in out_dir.rglob("*")), f"{name}/out 是空目录"


def test_mask_artifacts_present() -> None:
    assert (MASK_DIR / "out" / "mask_v1.json").is_file(), "掩膜网格缺失（session fixture 应已补齐）"


def test_mask_expect_declares_resolution_cap() -> None:
    """§4.3：分辨率上限 1°；掩膜必须自带版本与分辨率，供报告原样报出。"""
    data = json.loads((MASK_DIR / "expect.json").read_text(encoding="utf-8"))
    assert data["mask"]["resolution_deg"] <= 1.0, "首期上限 1°"
    assert data["mask"]["version"], "掩膜必须有版本号"
    for field in (
        "mask_version",
        "mask_max_resolution_deg",
        "unknown_ratio",
        "coastal_ratio",
        "evaluable_points",
    ):
        assert field in data["expected"]["required_header_fields"], f"§4.3 必报字段缺 {field}"
    # unknown 与 coastal 必须真的出现过，否则两条分母纪律在掩膜上无从验证
    assert data["coverage"]["unknown_cells"] > 0
    assert data["coverage"]["coastal_cells"] > 0
    assert data["expected"]["has_unknown_cells"] is True
    assert data["expected"]["has_coastal_cells"] is True


def test_water_track_fixture_supports_d2_scenario() -> None:
    """D2 复现的前提必须真的成立：反解落陆、原样落水、位移远大于格距。"""
    data = json.loads((FIXTURES_DIR / "water_track" / "expect.json").read_text(encoding="utf-8"))
    assert len(data["cases"]) == 1
    case = data["cases"][0]
    expected = case["expected"]
    assert case["encoding"] == "gcj02"
    assert expected["winner"] == "GCJ02"
    assert expected["water_ratio"]["GCJ02"] == 0.0
    assert expected["water_ratio"]["WGS84"] == 1.0
    assert expected["evaluable_points"] >= 30, "§4.3 的可判定点下限"
    assert expected["hypotheses"]["GCJ02"]["cell"] == "land"
    assert expected["hypotheses"]["GCJ02"]["coastal"] is False
    assert expected["hypotheses"]["WGS84"]["cell"] == "water"
    assert data["mask"]["resolution_deg"] <= 1.0
    assert case["track"]["points"] >= 30


def test_swapped_axis_and_declared_lie_are_independent_targets() -> None:
    """两类样本必须**各自**成立（`data/README.md` §4.1 末条：互不串扰）。"""
    axis = json.loads((FIXTURES_DIR / "swapped_axis" / "expect.json").read_text(encoding="utf-8"))
    lie = json.loads((FIXTURES_DIR / "declared_lie" / "expect.json").read_text(encoding="utf-8"))

    # 轴序样本：全在度域（量级判据不会误报），且写反形态成立
    assert len(axis["cases"]) >= 5
    for case in axis["cases"]:
        a, b = case["input"]
        assert max(abs(a), abs(b)) <= 180, "轴序样本必须全在度域"
        assert abs(b) > 90 and abs(a) <= 90, "写反形态不成立"

    # 量级样本：全部在米域（轴序判据的可判定子集排除它们）
    for case in lie["cases"]:
        x, y = case["input"]
        assert max(abs(x), abs(y)) >= 1_000_000, "量级样本必须在米域"
        assert case["expected"]["axis_decidable"] is False, "米域样本不进轴序可判定子集"
        assert case["expected"]["reason"] == "magnitude"

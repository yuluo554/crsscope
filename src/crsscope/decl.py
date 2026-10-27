"""模块 M1 · 声明-内容一致性（`plan/03` §一）。

判定顺序固定为 `CHECKS` 的顺序，不许并行、不许重排：
量级先判可以把"米域 vs 度域"一次性定性，后续轴序判定才不会被米域样本污染。

**一项一责**（否则五条判据会互相串扰，`data/README.md` §4.1 末条的验收就失效）：

| 检查项 | 只回答 | 不回答 |
|---|---|---|
| `magnitude` | 声明是度制而量级越出度域？ | 声明 3857 时的单位矛盾（归 `unit`） |
| `axis` | 在可判定样本子集上，`(lon, lat)` 还是 `(lat, lon)`？ | 米域样本（不进可判定子集） |
| `unit` | 声明 3857 而量级在度域？ | 其余任何情况 |
| `mixed` | 同一批数据内是否同时出现度域与米域？ | 声明对不对 |
| `extent` | 外包框是否落在声明 CRS 的定义域内；判不出时给候选 | 逐分量的纬度越界（归 `axis`） |

退出码不在这里算：`decl.run()` 只产出 `findings`，命中判定与退出码折算走
`errors.outcome_code`（`data/README.md` §4.9 的全序只在一处实现）。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import io
from .algorithms import WEBMERCATOR_MAX
from .errors import UsageError
from .report import Finding, ModuleResult, build_header

#: 检查项顺序（`plan/03` §一「判定顺序」）。代码与文档必须一致。
CHECKS: tuple[str, ...] = ("magnitude", "axis", "unit", "mixed", "extent")

#: `--declared-crs` 的合法枚举（`data/README.md` §1.2）。
#: **GCJ-02 / BD-09 不在其中**：它们没有 EPSG 代码，只能作为 `detect` 的检测假设。
DECLARED_CRS_CHOICES: tuple[str, ...] = ("4326", "3857", "4490", "crs84")

MILESTONE = "M2"

# ── 口径阈值（`data/README.md` §4.1 定义，此处只引用不复制第二份口径）──────
#: 度域上限：`m ≤ 180` 为度域（§4.1）
DEGREE_MAX = 180.0
#: 米域下限：`m ≥ 1_000_000` 为米域（§4.1）；两者之间是"中间带"
METRE_MIN = 1_000_000.0
#: 纬度域上限：轴序判据里"第二分量越出 ±90"即呈 `(lat, lon)`（§4.1）
LAT_RANGE_MAX = 90.0
#: 可判定样本下限：`< 5` → `undecidable(insufficient_samples)`（§4.1）
MIN_AXIS_SAMPLES = 5

#: 度制声明族（§4.1「与 `declared ∈ {4326, 4490, crs84}` 相容」）
DEGREE_DECLARED: tuple[str, ...] = ("4326", "4490", "crs84")

BAND_DEGREE = "degree"
BAND_METRE = "metre"
BAND_NEITHER = "neither"

#: 文件里 `crs` 成员的名字 → 本工具的声明枚举。**只认已登记的名字**，
#: 认不出的不猜（会把"没声明"伪装成"声明错了"）。
_FILE_CRS_ALIASES: dict[str, str] = {
    "crs84": "crs84",
    "ogc:crs84": "crs84",
    "urn:ogc:def:crs:ogc:1.3:crs84": "crs84",
    "urn:ogc:def:crs:ogc::crs84": "crs84",
    "urn:ogc:def:crs:epsg::4326": "4326",
    "urn:ogc:def:crs:epsg:6.6:4326": "4326",
    "epsg:4326": "4326",
    "wgs84": "4326",
    "urn:ogc:def:crs:epsg::3857": "3857",
    "epsg:3857": "3857",
    "epsg:900913": "3857",
    "urn:ogc:def:crs:epsg::4490": "4490",
    "epsg:4490": "4490",
    "cgcs2000": "4490",
}

SOURCE_CLI = "cli"
SOURCE_FILE = "file"
SOURCE_FILE_UNRECOGNISED = "file-unrecognised"
SOURCE_NONE = "none"


@dataclass(frozen=True)
class _Sample:
    """一对坐标。`a`/`b` 保持**文件里的分量顺序**——轴序判定正是要判这个顺序。"""

    seq: int
    a: float
    b: float

    @property
    def magnitude(self) -> float:
        """`m = max(|a|, |b|)`（§4.1）。"""
        return max(abs(self.a), abs(self.b))

    @property
    def band(self) -> str:
        if self.magnitude <= DEGREE_MAX:
            return BAND_DEGREE
        if self.magnitude >= METRE_MIN:
            return BAND_METRE
        return BAND_NEITHER

    @property
    def pair(self) -> list[float]:
        return [self.a, self.b]


def normalize_declared(raw: str | None) -> str | None:
    """把声明值归一成本工具的四值枚举；认不出返回 `None`（**不猜**）。"""
    if raw is None:
        return None
    key = raw.strip().lower()
    if key in DECLARED_CRS_CHOICES:
        return key
    return _FILE_CRS_ALIASES.get(key)


def _resolve_declared(cli_value: str | None, file_value: str | None) -> tuple[str | None, str]:
    """CLI 声明优先于文件内 `crs` 成员；两者都给的矛盾留给调用方看 `source`。

    返回 `(归一后的声明, 来源)`。来源是报告头的一部分——读者必须知道
    "这个声明是命令行说的，还是文件自称的"。

    非法 CLI 值在这里也拦一道（不只是 argparse 的 `choices`）：`decl.run()` 是公开接口，
    直接调用时同样必须是 `UsageError` → exit 2（`plan/03` §一 失败路径）。
    """
    if cli_value is not None:
        if cli_value not in DECLARED_CRS_CHOICES:
            raise UsageError(
                f"非法的 --declared-crs: {cli_value!r}",
                detail=(
                    "合法枚举: " + " / ".join(DECLARED_CRS_CHOICES)
                    + "；GCJ-02 与 BD-09 没有 EPSG 代码，只能作为 detect 的检测假设"
                ),
            )
        return cli_value, SOURCE_CLI
    if file_value is not None:
        normalised = normalize_declared(file_value)
        if normalised is None:
            return None, SOURCE_FILE_UNRECOGNISED
        return normalised, SOURCE_FILE
    return None, SOURCE_NONE


# ── 五个检查项：每个只回答一件事 ──────────────────────────────────────


def _bands(samples: list[_Sample]) -> dict[str, int]:
    return dict(sorted(Counter(s.band for s in samples).items()))


def _check_magnitude(samples: list[_Sample], declared: str | None) -> Finding:
    """量级（§4.1）：声明是度制而 `m > 180` → `conflict/magnitude`。"""
    if not samples:
        return Finding(
            check="magnitude",
            status="undecidable",
            reason="insufficient_samples",
            detail="没有任何坐标样本，量级无从判定",
            evidence={"rule": "data/README.md §4.1", "samples": 0},
        )
    bands = _bands(samples)
    worst = max(s.magnitude for s in samples)
    evidence: dict[str, Any] = {
        "rule": "data/README.md §4.1",
        "declared_crs": declared or "none",
        "magnitude_m": round(worst, 6),
        "bands": bands,
        "degree_max": DEGREE_MAX,
        "metre_min": METRE_MIN,
    }

    if declared is None:
        return Finding(
            check="magnitude",
            status="info",
            detail=f"无声明值可比；最大量级 {worst:g}，分档 {bands}",
            evidence=evidence,
        )

    if declared in DEGREE_DECLARED:
        if worst > DEGREE_MAX:
            return Finding(
                check="magnitude",
                status="conflict",
                reason="magnitude",
                detail=(
                    f"声明为度制（{declared}），但最大量级 {worst:g} 超过度域上限 {DEGREE_MAX:g}"
                ),
                evidence=evidence,
            )
        return Finding(
            check="magnitude",
            status="consistent",
            detail=f"声明为度制（{declared}），最大量级 {worst:g} 在度域内",
            evidence=evidence,
        )

    # declared == "3857"：单位矛盾归 `unit`，混用归 `mixed`，这里只报量级事实。
    if bands.get(BAND_METRE) and len(bands) == 1:
        return Finding(
            check="magnitude",
            status="consistent",
            detail="声明 3857（米制），全部样本量级在米域",
            evidence=evidence,
        )
    if bands.get(BAND_NEITHER) and len(bands) == 1:
        return Finding(
            check="magnitude",
            status="undecidable",
            detail=f"声明 3857，但全部样本落在中间带（{DEGREE_MAX:g} < m < {METRE_MIN:g}）",
            evidence=evidence,
        )
    return Finding(
        check="magnitude",
        status="info",
        detail=f"声明 3857；量级分档 {bands}，矛盾由 unit / mixed 项给出",
        evidence=evidence,
    )


def _decidable_samples(samples: list[_Sample]) -> list[_Sample]:
    """可判定样本 = 两分量都在 ±180 内（§4.1）。米域样本天然被排除。"""
    return [s for s in samples if abs(s.a) <= DEGREE_MAX and abs(s.b) <= DEGREE_MAX]


def _check_axis(samples: list[_Sample], declared: str | None) -> tuple[Finding, bool]:
    """轴序（§4.1）：只用可判定样本；`< 5` → `undecidable(insufficient_samples)`。"""
    decidable = _decidable_samples(samples)
    evidence: dict[str, Any] = {
        "rule": "data/README.md §4.1",
        "total_samples": len(samples),
        "decidable_samples": len(decidable),
        "min_decidable_samples": MIN_AXIS_SAMPLES,
    }

    if declared == "3857":
        return (
            Finding(
                check="axis",
                status="info",
                detail="声明为投影坐标系（3857），经度/纬度域判据不适用",
                evidence=evidence,
            ),
            False,
        )
    if len(decidable) < MIN_AXIS_SAMPLES:
        return (
            Finding(
                check="axis",
                status="undecidable",
                reason="insufficient_samples",
                detail=(
                    f"可判定样本 {len(decidable)} 个，低于下限 {MIN_AXIS_SAMPLES}，不得凭少量点下结论"
                ),
                evidence=evidence,
            ),
            False,
        )

    swapped = [s for s in decidable if abs(s.b) > LAT_RANGE_MAX and abs(s.a) <= LAT_RANGE_MAX]
    if swapped:
        first = swapped[0]
        return (
            Finding(
                check="axis",
                status="conflict",
                reason="axis",
                detail=(
                    f"{len(swapped)}/{len(decidable)} 个可判定样本的第二分量越出纬度域（±{LAT_RANGE_MAX:g}），"
                    "而第一分量仍在经度域内 → 呈 (lat, lon) 排列"
                ),
                evidence={
                    **evidence,
                    "affected_samples": len(swapped),
                    "sample": first.pair,
                    "corrected_sample": [first.b, first.a],
                },
            ),
            True,
        )

    normal = [s for s in decidable if abs(s.a) > LAT_RANGE_MAX and abs(s.b) <= LAT_RANGE_MAX]
    if normal:
        return (
            Finding(
                check="axis",
                status="consistent",
                detail=(
                    f"{len(normal)} 个可判定样本的第一分量越出纬度域 → 只能是经度，轴序呈 (lon, lat)"
                ),
                evidence={**evidence, "affected_samples": len(normal), "sample": normal[0].pair},
            ),
            True,
        )

    return (
        Finding(
            check="axis",
            status="undecidable",
            detail="全部可判定样本都落在 ±90 内，无法区分 (lon, lat) 与 (lat, lon)",
            evidence=evidence,
        ),
        False,
    )


def _check_unit(samples: list[_Sample], declared: str | None) -> Finding:
    """单位（§4.1）：`declared = 3857` 且量级在度域 → `conflict/unit`。"""
    evidence: dict[str, Any] = {"rule": "data/README.md §4.1", "declared_crs": declared or "none"}
    if declared != "3857":
        return Finding(
            check="unit",
            status="info",
            detail="unit 项只对 `--declared-crs 3857` 生效；本次声明不是 3857",
            evidence=evidence,
        )
    if not samples:
        return Finding(
            check="unit",
            status="undecidable",
            reason="insufficient_samples",
            detail="没有任何坐标样本，单位无从判定",
            evidence=evidence,
        )
    degree_pts = [s for s in samples if s.band == BAND_DEGREE]
    evidence["degree_domain_samples"] = len(degree_pts)
    evidence["samples"] = len(samples)
    if degree_pts:
        return Finding(
            check="unit",
            status="conflict",
            reason="unit",
            detail=(
                f"声明 3857（米），但有 {len(degree_pts)}/{len(samples)} 个样本量级 ≤ {DEGREE_MAX:g}"
                "（度域），单位与声明不相容"
            ),
            evidence=evidence,
        )
    return Finding(
        check="unit",
        status="consistent",
        detail=f"声明 3857，没有样本落在度域（分档 {_bands(samples)}）",
        evidence=evidence,
    )


def _check_mixed(samples: list[_Sample]) -> Finding:
    """混用（§4.1 末条 / §4.8）：同一批数据内量级分档冲突 → `conflict/mixed`。"""
    bands = _bands(samples)
    evidence: dict[str, Any] = {"rule": "data/README.md §4.1", "bands": bands}
    if not samples:
        return Finding(
            check="mixed",
            status="info",
            detail="没有任何坐标样本，无混用可判",
            evidence=evidence,
        )
    if bands.get(BAND_DEGREE) and bands.get(BAND_METRE):
        return Finding(
            check="mixed",
            status="conflict",
            reason="mixed",
            detail=(
                f"同一批数据内同时出现度域（{bands[BAND_DEGREE]} 个）与米域（{bands[BAND_METRE]} 个）样本，"
                "量级分档冲突"
            ),
            evidence=evidence,
        )
    return Finding(
        check="mixed",
        status="consistent",
        detail=f"量级分档一致：{bands}",
        evidence=evidence,
    )


def _bbox(samples: list[_Sample]) -> list[float] | None:
    if not samples:
        return None
    aa = [s.a for s in samples]
    bb = [s.b for s in samples]
    return [round(min(aa), 9), round(min(bb), 9), round(max(aa), 9), round(max(bb), 9)]


def _decode(s: _Sample, axis_orientation: str | None) -> tuple[float, float]:
    """按已判定的轴序把一对分量读成 `(lon, lat)`；轴序未定时保持文件顺序。"""
    return (s.b, s.a) if axis_orientation == "lat_lon" else (s.a, s.b)


def _check_extent(
    samples: list[_Sample], declared: str | None, axis_orientation: str | None
) -> tuple[Finding, list[str]]:
    """分布范围（`plan/01` M1 第 3 条）：外包框与声明 CRS 的定义域是否相容。

    判不出时**必须**给出候选建议（`plan/01`：`undecidable` + 建议候选），不得硬判。

    **一项一责**：分量是不是 `lon, lat` 由 `axis` 项判（这里只按它的结论读数）；
    这里只回答"外包框落不落在声明的定义域里"。
    """
    candidates: list[str] = []
    evidence: dict[str, Any] = {"rule": "data/README.md §4.1", "declared_crs": declared or "none"}
    if axis_orientation:
        evidence["axis_orientation"] = axis_orientation

    if declared is None:
        evidence["bbox"] = _bbox(samples)
        return (
            Finding(
                check="extent",
                status="info",
                detail=f"无声明值；外包框 {evidence['bbox']}" if samples else "无声明值且无样本",
                evidence=evidence,
            ),
            candidates,
        )

    if declared in DEGREE_DECLARED:
        degree_pts = [s for s in samples if s.band == BAND_DEGREE]
        evidence["degree_domain_samples"] = len(degree_pts)
        if not degree_pts:
            candidates = ["3857"]
            evidence["bbox"] = _bbox(samples)
            return (
                Finding(
                    check="extent",
                    status="undecidable",
                    detail=(
                        "声明为地理坐标系，但没有任何样本落在度域；外包框与声明不相容，"
                        "量级上看更像 3857 米域"
                    ),
                    evidence={**evidence, "candidates": candidates},
                ),
                candidates,
            )
        pairs = [_decode(s, axis_orientation) for s in degree_pts]
        lons = [p[0] for p in pairs]
        lats = [p[1] for p in pairs]
        bbox = [
            round(min(lons), 9),
            round(min(lats), 9),
            round(max(lons), 9),
            round(max(lats), 9),
        ]
        evidence["bbox_lon_lat"] = bbox
        out_of_range = [
            p for p in pairs if abs(p[0]) > 180.0 or abs(p[1]) > LAT_RANGE_MAX
        ]
        if out_of_range:
            evidence["out_of_range_samples"] = len(out_of_range)
            return (
                Finding(
                    check="extent",
                    status="conflict",
                    detail=(
                        f"声明为地理坐标系（{declared}），但按当前轴序读出的外包框 {bbox} "
                        f"越出 ±180 / ±{LAT_RANGE_MAX:g}，有 {len(out_of_range)} 个样本越界"
                    ),
                    evidence=evidence,
                ),
                candidates,
            )
        note = (
            f"（按 axis 项判定的 {axis_orientation} 顺序读取）"
            if axis_orientation
            else "（轴序未定，按文件顺序读取）"
        )
        return (
            Finding(
                check="extent",
                status="consistent",
                detail=f"度域样本外包框 {bbox} 落在 ±180 / ±{LAT_RANGE_MAX:g} 内{note}",
                evidence=evidence,
            ),
            candidates,
        )

    # declared == "3857"
    metre_pts = [s for s in samples if s.band == BAND_METRE]
    evidence["metre_domain_samples"] = len(metre_pts)
    evidence["bbox"] = _bbox(metre_pts)
    if not metre_pts:
        candidates = list(DEGREE_DECLARED)
        return (
            Finding(
                check="extent",
                status="undecidable",
                detail="声明 3857（米），但没有任何样本落在米域；外包框与声明不相容，量级上看更像度制",
                evidence={**evidence, "candidates": candidates},
            ),
            candidates,
        )
    if any(abs(s.a) > WEBMERCATOR_MAX or abs(s.b) > WEBMERCATOR_MAX for s in metre_pts):
        return (
            Finding(
                check="extent",
                status="conflict",
                detail=(
                    f"声明 3857，但外包框 {evidence['bbox']} 越出 Web Mercator 全球范围 "
                    f"±{WEBMERCATOR_MAX:g} m"
                ),
                evidence={**evidence, "webmercator_max_m": WEBMERCATOR_MAX},
            ),
            candidates,
        )
    return (
        Finding(
            check="extent",
            status="consistent",
            detail=f"米域样本外包框 {evidence['bbox']} 落在 Web Mercator 全球范围内",
            evidence=evidence,
        ),
        candidates,
    )


def _verdict(findings: list[Finding]) -> str:
    conflicts = [f.check for f in findings if f.status == "conflict"]
    if conflicts:
        return "声明与内容不一致：" + "、".join(conflicts)
    undecided = [f.check for f in findings if f.status == "undecidable"]
    if undecided:
        return "结论不可判定（需人工介入）：" + "、".join(undecided)
    return "声明与内容相容（五项检查均未命中）"


def run(path: Path, declared_crs: str | None, *, strict: bool = False) -> ModuleResult:
    """判定入口。**判定顺序固定为 `CHECKS` 的顺序**（`plan/03` §一）。

    `strict`：无声明值（命令行与文件都没给）时，把"没得比"从 `info` 升为 `undecidable`——
    严格模式下"没有声明"不是一个可以放过的结论。这是 `--strict` 的**唯一**语义，
    不引入任何新阈值。
    """
    point_set = io.read_points(path)
    declared, source = _resolve_declared(declared_crs, point_set.declared_crs)
    samples = [_Sample(seq=p.seq, a=p.lon, b=p.lat) for p in point_set.points]

    findings: list[Finding] = []
    findings.append(_check_magnitude(samples, declared))
    axis_finding, axis_decidable = _check_axis(samples, declared)
    findings.append(axis_finding)
    findings.append(_check_unit(samples, declared))
    findings.append(_check_mixed(samples))
    # axis 项先判，extent 按它给出的顺序读分量（判定顺序不可倒）。
    axis_orientation: str | None = None
    if axis_finding.status == "conflict":
        axis_orientation = "lat_lon"
    elif axis_finding.status == "consistent":
        axis_orientation = "lon_lat"
    extent_finding, candidates = _check_extent(samples, declared, axis_orientation)
    findings.append(extent_finding)

    if strict and declared is None:
        steered: list[Finding] = []
        for f in findings:
            if f.status == "info" and f.check in {"magnitude", "unit", "extent"}:
                steered.append(
                    Finding(
                        check=f.check,
                        status="undecidable",
                        reason=None,
                        detail=f"--strict：无声明值即不可判定（原判：{f.detail}）",
                        evidence=dict(f.evidence, strict=True),
                    )
                )
            else:
                steered.append(f)
        findings = steered

    payload: dict[str, Any] = {
        "header": build_header(
            "decl",
            declared_crs=declared,
            declared_crs_source=source,
            source_kind=point_set.source_kind,
        ),
        "verdict": _verdict(findings),
        "axis_decidable": axis_decidable,
        "sample_counts": {
            "total": len(samples),
            "decidable": len(_decidable_samples(samples)),
            "bands": _bands(samples),
        },
        "candidates": candidates,
    }
    if source == SOURCE_FILE_UNRECOGNISED:
        payload["declaration_note"] = (
            f"文件内 crs 成员为 {point_set.declared_crs!r}，未登记于本工具的声明枚举，"
            "未按声明参与判定（不猜）"
        )

    return ModuleResult(command="decl", findings=findings, payload=payload)


def describe() -> list[Finding]:
    """返回检查项清单（供 `--help` 与该模块的契约测试使用，不读数据）。"""
    return [Finding(check=name, status="info", detail=f"检查项 {name}") for name in CHECKS]

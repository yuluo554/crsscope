"""模块 M2 · GCJ-02 / BD-09 偏移检测与残差（`plan/03` §二）。

判定顺序**固定、不许并行**（`plan/03` §二）：
逆变换 → 覆盖检查 → 三路评分 → 排序与置信 → 残差三段 → 边界画像。

**一项一责**（照 `decl.py` 的形状；后判项可读先判项的结论，但不许重复判同一件事）：

| 检查项 | 只回答 | 不回答 |
|---|---|---|
| `coverage` | 样本是否整个落在 `out_of_china` 域外？ | 落在域内时哪个假设赢 |
| `hypothesis` | 三个候选假设谁得分最高、置信多少？ | 残差是什么、边界画像是哪两库 |
| `residual` | 三条不可消解残差是否齐全？ | 残差的具体数值（那是 `affected_points`） |
| `boundary_profiles` | 两库边界框对这些样本的结论是否一致？ | 谁赢（归 `hypothesis`） |

**退出码不在这里算**：`detect.run()` 只产出 `findings` + `payload`；命中判定与退出码折算走
`errors.outcome_code`（`data/README.md` §4.9 的全序只在一处实现）。
本模块**不认识** `--fail-on` / `--allow-undecidable`。

**诚实边界**（`plan/00` 决策 ③）：结论永远是"**在某组假设下的残差与置信**"，
**禁止**宣称"已还原为 WGS84 真实坐标"。`residual.kind` 三段固定输出。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import algorithms, decl, geodesy, io, mask as mask_mod
from .errors import EnvironmentMissing, UsageError
from .report import Finding, ModuleResult, build_header

#: 候选假设固定三值（`data/README.md` §4.2）。**不增不减。**
HYPOTHESES = algorithms.HYPOTHESES

#: 残差三段固定枚举（`data/README.md` §4.5）。**必须齐全**，不是"至少一条"。
RESIDUAL_KINDS = ("formula_approximation", "vendor_divergence", "boundary_jump")

#: 边界画像双份（两库边界不同是审计发现点，必须分别输出）。
BOUNDARY_PROFILES = (algorithms.PROFILE_CT_PY, algorithms.PROFILE_GCOORD)

MILESTONE = "M3"

# ── 口径常量：唯一权威 = `data/README.md` §4.2 / §4.3，此处只引用不复述数值 ──────
#: 评分权重（§4.2 的 `score` 式）。
WEIGHT_BOUNDARY = 0.25
WEIGHT_DECLARED = 0.30
#: 置信档位分界（§4.2 的 `confidence` 表）。
CONFIDENCE_HIGH_MARGIN = 0.15
CONFIDENCE_MEDIUM_MARGIN = 0.05
#: 可判定点下限（§4.3）。
MIN_EVALUABLE_POINTS = 30
#: 边界带角距上限（§4.2 的 `boundary_jump` 标记）。
BOUNDARY_BAND_DEG = 0.05
#: `unknown + coastal` 占比上限（§4.2 的 `undecidable` 条件）。
UNKNOWN_COASTAL_MAX_RATIO = 0.8

CONFIDENCE_UNDECIDABLE = "undecidable"

#: 结论原因（`Finding.reason`）的固定枚举，供 `--fail-on` 点名。
REASON_OUT_OF_COVERAGE = "out_of_coverage"
REASON_INSUFFICIENT = "insufficient_samples"
REASON_TIE = "tie"
REASON_BOUNDARY_DIVERGENCE = "boundary_divergence"


def _resolve_declared(cli_value: str | None, file_value: str | None) -> tuple[str | None, str]:
    """CLI 声明优先；认不出的文件 `crs` 名字**不猜**（会被当"没声明"）。

    与 `decl._resolve_declared` 同口径，但只返回本模块要用的 `(声明, 来源)`：
    `detect` 里声明只作评分式里的 `declared(h)` 一项证据，不参与量级/轴序判定。
    """
    if cli_value is not None:
        if cli_value not in decl.DECLARED_CRS_CHOICES:
            raise UsageError(
                f"非法的 --declared-crs: {cli_value!r}",
                detail=(
                    "合法枚举: " + " / ".join(decl.DECLARED_CRS_CHOICES)
                    + "；GCJ-02 与 BD-09 没有 EPSG 代码，只能作为检测假设"
                ),
            )
        return cli_value, decl.SOURCE_CLI
    if file_value is not None:
        normalised = decl.normalize_declared(file_value)
        if normalised is None:
            return None, decl.SOURCE_FILE_UNRECOGNISED
        return normalised, decl.SOURCE_FILE
    return None, decl.SOURCE_NONE


def _declared_conflict(hypothesis: str, declared: str | None) -> int:
    """`declared(h)`（§4.2）：`--declared-crs` 与假设 `h` 矛盾的**强证据** → 1。

    - 无声明 → 0（没有可比对象）。
    - 声明为投影坐标系（3857）：三个地理假设都与声明矛盾 → 一律 1（对排序无差，但如实扣分）。
    - 声明为度制族（4326 / 4490 / crs84）：`WGS84` 相容（0），`GCJ02` / `BD09` 与声明矛盾（1）
      ——  声明本身是不是真的，由 `hypothesis` 的分数与 `confidence` 如实呈现，不在这里替它翻案。
    """
    if declared is None:
        return 0
    if declared == "3857":
        return 1
    return 0 if hypothesis == "WGS84" else 1


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    idx = math.ceil(0.95 * len(ordered)) - 1
    return ordered[max(0, idx)]


def _compass(east: float, north: float) -> str | None:
    """8 方位罗盘方向。零位移返回 `None`（不是 `"N"`——没有位移就没有方向）。"""
    if east == 0.0 and north == 0.0:
        return None
    bearing = math.degrees(math.atan2(east, north)) % 360.0
    dirs = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return dirs[int((bearing + 22.5) % 360.0 // 45.0)]


# ── 环节 2：覆盖检查（两库边界画像各一份）──────────────────────────────


@dataclass(frozen=True)
class _Boundary:
    """边界画像的逐点分析结果 + 两库汇总（§4.2 / §4.5 的 `boundary_profiles`）。"""

    profiles: dict[str, dict[str, Any]]
    covered: bool  # 至少一个点在某一库的 out_of_china 域内
    disagree: bool  # 存在点使两库"是否境内"结论相反
    near_band: bool  # 存在点距某库边界 < BOUNDARY_BAND_DEG
    per_point_disagree: tuple[bool, ...]
    per_point_near: tuple[bool, ...]


def _boundary_analysis(points: list[io.Point]) -> _Boundary:
    """两库边界框对这些样本的独立判定。**不合并、不取并集**——差异本身就是发现点。"""
    profiles: dict[str, dict[str, Any]] = {}
    inside: dict[str, list[bool]] = {}
    dists: dict[str, list[float]] = {}
    for profile in BOUNDARY_PROFILES:
        bbox = algorithms.CT_PY_BBOX if profile == algorithms.PROFILE_CT_PY else algorithms.GCOORD_BBOX
        inside[profile] = [algorithms.in_bbox(p.lon, p.lat, bbox) for p in points]
        dists[profile] = [algorithms.distance_to_bbox_deg(p.lon, p.lat, bbox) for p in points]
        profiles[profile] = {
            "in_china": bool(inside[profile]) and all(inside[profile]),
            "distance_to_boundary_deg": round(min(dists[profile]), 6) if dists[profile] else None,
            "points_inside": sum(inside[profile]),
            "points_total": len(points),
        }

    ct, gc = algorithms.PROFILE_CT_PY, algorithms.PROFILE_GCOORD
    per_disagree = tuple(a != b for a, b in zip(inside[ct], inside[gc], strict=True))
    per_near = tuple(
        min(dc, dg) < BOUNDARY_BAND_DEG
        for dc, dg in zip(dists[ct], dists[gc], strict=True)
    )
    covered = any(inside[ct]) or any(inside[gc])
    return _Boundary(
        profiles=profiles,
        covered=covered,
        disagree=any(per_disagree),
        near_band=any(per_near),
        per_point_disagree=per_disagree,
        per_point_near=per_near,
    )


# ── 环节 1 / 3：逆变换 + 三路评分（§4.2）──────────────────────────────


@dataclass(frozen=True)
class _Hypothesis:
    """一个候选假设的完整评分（§4.2）。`score=None` 表示**没有任何可判定点**，无从打分。"""

    name: str
    score: float | None
    water_ratio: float | None
    stats: mask_mod.MaskStats
    offset_m: float
    p95_offset_m: float
    direction: str | None
    boundary: int
    declared: int
    not_converged: int

    @property
    def evaluable_points(self) -> int:
        return self.stats.evaluable

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": None if self.score is None else round(self.score, 6),
            "water_ratio": None if self.water_ratio is None else round(self.water_ratio, 6),
            "offset_m": round(self.offset_m, 1),
            "p95_offset_m": round(self.p95_offset_m, 1),
            "direction": self.direction,
            "evaluable_points": self.evaluable_points,
            "boundary": self.boundary,
            "declared_conflict": self.declared,
            "not_converged": self.not_converged,
        }


def _evaluate(
    name: str, points: list[io.Point], mask: mask_mod.Mask, declared: str | None, boundary: int
) -> _Hypothesis:
    """对一个假设做完整逆变换并评分。

    "若 `h` 为上文的假设，则真实坐标 = `inverse_h(p)`"——落水率判的是**逆变换后的落点**，
    不是原始点（`data/README.md` §4.2）。分母规则**只走 `mask.MaskStats`**
    （`unknown` 与海岸带不进分母）。
    """
    stats = mask_mod.MaskStats()
    offsets: list[float] = []
    east = north = 0.0
    not_converged = 0
    for p in points:
        inv = algorithms.inverse_for(name, p.lon, p.lat)
        if not inv.converged:
            not_converged += 1
        stats.add(mask, inv.lon, inv.lat)
        offsets.append(geodesy.haversine_m(p.lon, p.lat, inv.lon, inv.lat))
        east += inv.lon - p.lon
        north += inv.lat - p.lat

    ratio = stats.water_ratio
    conflict = _declared_conflict(name, declared)
    score = None
    if ratio is not None:
        score = (1.0 - ratio) - WEIGHT_BOUNDARY * boundary - WEIGHT_DECLARED * conflict
    return _Hypothesis(
        name=name,
        score=score,
        water_ratio=ratio,
        stats=stats,
        offset_m=_median(offsets),
        p95_offset_m=_p95(offsets),
        direction=None if not offsets else _compass(east, north),
        boundary=boundary,
        declared=conflict,
        not_converged=not_converged,
    )


def _rank(hypotheses: list[_Hypothesis]) -> list[_Hypothesis]:
    """排序：`score` 降序；同分按假设名**字典序**（`BD09` < `GCJ02` < `WGS84`）；无分者殿后。"""
    return sorted(
        hypotheses,
        key=lambda h: (h.score is None, -(h.score if h.score is not None else 0.0), h.name),
    )


def _confidence(
    scorable: list[_Hypothesis], boundary: _Boundary
) -> tuple[str, float | None, str | None]:
    """置信档位（§4.2）+ 灰区（§4.8）。

    返回 `(confidence, margin, gray_reason)`；`gray_reason` 非 None 即整项 `undecidable`。
    **灰区优先**：可判定点不足 / 并列第一 / 覆盖率过差都是灰区，不硬判。
    """
    if not scorable:
        return CONFIDENCE_UNDECIDABLE, None, REASON_INSUFFICIENT
    top = scorable[0]
    total = top.stats.water + top.stats.land + top.stats.unknown + top.stats.coastal
    if top.evaluable_points < MIN_EVALUABLE_POINTS:
        return CONFIDENCE_UNDECIDABLE, None, REASON_INSUFFICIENT
    if total and (top.stats.unknown + top.stats.coastal) / total > UNKNOWN_COASTAL_MAX_RATIO:
        return CONFIDENCE_UNDECIDABLE, None, REASON_INSUFFICIENT
    second_score = scorable[1].score if len(scorable) >= 2 else None
    margin = top.score - second_score if second_score is not None else top.score
    assert margin is not None
    if margin <= 0.0:
        return CONFIDENCE_UNDECIDABLE, margin, REASON_TIE
    if margin >= CONFIDENCE_HIGH_MARGIN:
        confidence = "high"
    elif margin >= CONFIDENCE_MEDIUM_MARGIN:
        confidence = "medium"
    else:
        confidence = "low"
    # 边界带（§4.2）：任一点距某库边界过近时把置信上限压到 medium。
    if boundary.near_band and confidence == "high":
        confidence = "medium"
    return confidence, margin, None


# ── 环节 5：残差三段（§4.5，固定枚举齐全）─────────────────────────────


def _residual(
    winner: _Hypothesis | None, boundary: _Boundary, points: list[io.Point]
) -> list[dict[str, Any]]:
    """三段残差**固定齐全**。`affected_points` 按"该不确定性实际影响到几个点"计数。

    措辞纪律（决策 ③ / ④）：只说"在某实现假设下的位移"，不说"已还原为真实坐标"；
    两库边界不同是**审计发现点**，不表述为任何一方的 bug。
    """
    offset_points = 0
    if winner is not None and winner.offset_m > 0.0:
        offset_points = sum(
            1
            for p in points
            if algorithms.inverse_for(winner.name, p.lon, p.lat).lon != p.lon
            or algorithms.inverse_for(winner.name, p.lon, p.lat).lat != p.lat
        )
    jump_points = sum(
        1
        for dis, near in zip(boundary.per_point_disagree, boundary.per_point_near, strict=True)
        if dis or near
    )
    return [
        {
            "kind": "formula_approximation",
            "detail": (
                "上述偏移是民间公开公式下的近似，不保证等价于未公开的实现；"
                "结论只表述为'在某实现假设下的残差与置信'。"
            ),
            "affected_points": offset_points,
        },
        {
            "kind": "vendor_divergence",
            "detail": (
                "高德 / Google 中国 / 腾讯等实现的同一坐标可能对应不同的'真值'，"
                "实现差异可达米级；本工具不指定唯一真值。"
            ),
            "affected_points": offset_points,
        },
        {
            "kind": "boundary_jump",
            "detail": (
                "out_of_china 是硬边界，边界两侧的输出不连续；且 coordTransform_py 与 gcoord "
                "的边界框不同（data/README.md §1.3）——这是审计发现点，不是任何一方的 bug。"
            ),
            "affected_points": jump_points,
        },
    ]


# ── 入口 ──────────────────────────────────────────────────────────────


def run(path: Path, declared_crs: str | None, mask_path: Path | None = None) -> ModuleResult:
    """判定入口。**判定顺序固定**（`plan/03` §二）。

    `mask_path` 缺失即 `EnvironmentMissing`（exit 3）——**不得**默认"全是陆地"（§4.3）。
    """
    point_set = io.read_points(path)
    declared, source = _resolve_declared(declared_crs, point_set.declared_crs)
    points = point_set.points

    if mask_path is None:
        raise EnvironmentMissing(
            "掩膜缺失（未提供 --mask）",
            detail="按 data/README.md §4.3 不得默认'全是陆地'；用 data/mask/gen.py 生成或 --mask 指定",
        )
    mask = mask_mod.load_mask(mask_path)

    # 环节 2：覆盖检查（绑定两库边界画像）。
    boundary = _boundary_analysis(points)
    out_of_coverage = not boundary.covered

    # 环节 1 + 3：逆变换与三路评分。`boundary(h)` 对所有假设同值（两库分歧与边界带是样本属性）。
    boundary_flag = 1 if (boundary.disagree or boundary.near_band) else 0
    hypotheses = [_evaluate(name, points, mask, declared, boundary_flag) for name in HYPOTHESES]

    # 环节 4：排序与置信。
    scorable = [h for h in hypotheses if h.score is not None]
    ranked = _rank(hypotheses)
    ordered_scorable = [h for h in ranked if h.score is not None]
    if out_of_coverage:
        confidence, margin, gray_reason = CONFIDENCE_UNDECIDABLE, None, REASON_OUT_OF_COVERAGE
    else:
        confidence, margin, gray_reason = _confidence(ordered_scorable, boundary)
    undecidable = gray_reason is not None
    winner = ordered_scorable[0] if (ordered_scorable and not undecidable) else None

    # 环节 5：残差三段（固定齐全）。
    residual = _residual(winner, boundary, points)

    header_hypothesis = winner or (ordered_scorable[0] if ordered_scorable else hypotheses[0])
    mask_header = header_hypothesis.stats.as_header(mask)

    # ── findings：一项一责（`plan/03` §二 / `handoff` §三.8）────────────────
    coverage_status = "undecidable" if out_of_coverage else "consistent"
    coverage_detail = (
        "样本全部落在两库的 out_of_china 域外 → 无从比较偏移假设，不硬判 WGS84"
        if out_of_coverage
        else (
            f"样本有覆盖：coordTransform_py 境内 {boundary.profiles['coordTransform_py']['points_inside']}"
            f"/{len(points)}，gcoord 境内 {boundary.profiles['gcoord']['points_inside']}/{len(points)}"
        )
    )
    coverage_finding = Finding(
        check="coverage",
        status=coverage_status,
        reason=REASON_OUT_OF_COVERAGE if out_of_coverage else None,
        detail=coverage_detail,
        evidence={
            "rule": "data/README.md §4.2",
            "points_total": len(points),
            "covered": boundary.covered,
        },
    )

    if undecidable:
        hypothesis_status = "undecidable"
        reason = gray_reason
    else:
        hypothesis_status = "consistent"
        reason = None
    if winner is not None:
        hypothesis_detail = (
            f"假设 {winner.name} 得分最高（{winner.score:.3f}），置信 {confidence}；"
            f"落水率 {winner.water_ratio}，偏移中位数 {winner.offset_m:.1f} m"
        )
    else:
        hypothesis_detail = f"三个假设无法分出唯一胜者（灰区：{gray_reason}）"
    hypothesis_finding = Finding(
        check="hypothesis",
        status=hypothesis_status,
        reason=reason,
        detail=hypothesis_detail,
        evidence={
            "rule": "data/README.md §4.2",
            "confidence": confidence,
            "margin": None if margin is None else round(margin, 6),
            "ranking": [h.name for h in ranked],
            "min_evaluable_points": MIN_EVALUABLE_POINTS,
        },
    )

    residual_finding = Finding(
        check="residual",
        status="info",
        detail="残差三段固定输出：" + "、".join(r["kind"] for r in residual),
        evidence={"rule": "data/README.md §4.5", "kinds": [r["kind"] for r in residual]},
    )

    diverge = boundary.profiles[algorithms.PROFILE_CT_PY]["in_china"] != boundary.profiles[
        algorithms.PROFILE_GCOORD
    ]["in_china"]
    boundary_finding = Finding(
        check="boundary_profiles",
        status="warning" if diverge else "consistent",
        reason=REASON_BOUNDARY_DIVERGENCE if diverge else None,
        detail=(
            "两库边界框对本批样本结论不同（coordTransform_py 开区间 / gcoord 闭区间）"
            "——这是审计发现点，不是任何一方的 bug"
            if diverge
            else "两库边界框对本批样本结论一致"
        ),
        evidence={"rule": "data/README.md §1.3", "profiles": boundary.profiles},
    )

    findings = [coverage_finding, hypothesis_finding, residual_finding, boundary_finding]

    verdict = (
        f"最可能是 {winner.name}（置信 {confidence}）"
        if winner is not None
        else f"不可判定（灰区：{gray_reason}）"
    )

    payload: dict[str, Any] = {
        "header": build_header(
            "detect",
            declared_crs=declared,
            declared_crs_source=source,
            **mask_header,
        ),
        "verdict": verdict,
        "winner": None if winner is None else winner.name,
        "confidence": confidence,
        "out_of_coverage": out_of_coverage,
        "gray_reason": gray_reason,
        "hypotheses": [h.as_dict() for h in ranked],
        "boundary_profiles": boundary.profiles,
        "residual": residual,
        "mask": mask_header,
        "sample_counts": {
            "total": len(points),
            "covered": boundary.covered,
        },
    }

    return ModuleResult(command="detect", findings=findings, payload=payload)


def describe() -> list[Finding]:
    return [
        Finding(check="hypotheses", status="info", detail=",".join(HYPOTHESES)),
        Finding(check="residual_kinds", status="info", detail=",".join(RESIDUAL_KINDS)),
        Finding(check="boundary_profiles", status="info", detail=",".join(BOUNDARY_PROFILES)),
    ]
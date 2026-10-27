"""模块 M3 · 跨实现差分（`plan/03` §三）。

把**同一批坐标**分别喂给三个**本地重实现**（不调用外部服务、不引入第三方运行时依赖），
报告：每个实现输出的绝对坐标 / 两两差异（米，§4.4）/ 跳变点 / 两库边界结论表。

三个对照实现的常数与判据照录自 `data/README.md` §1.3，本模块**不新增**任何常数：

- `coordTransform_py`：逆向**一步线性近似** `[lng*2 - mglng, lat*2 - mglat]`，边界框**开区间**；
- `gcoord`：逆向**定点迭代**，容差 `1e-6°`，边界框**闭区间**；
- `proj4js_webmercator`：WebMercator 解析逆。

**方向**：输入坐标被读作 `--target` 指定的坐标系，每个实现把它转成 **WGS84**——
这是三者唯一可比的公共参照系；差分在 WGS84 输出之间做。

**诚实边界（题面 §M3 纪律 / 决策 ③）**：迭代超上限即 `converged=False`，本模块**必须**把
`not_converged` 报进结果（`undecidable` + `reason: not_converged`），**不得**静默返回一个
"看起来对"的值。两库边界框不同是**审计发现点**，**不表述为任何一方的 bug**（决策 ④）。

**退出码不在这里算**：`xdiff.run()` 只产出 `findings` + `payload`；命中判定与退出码折算走
`errors.outcome_code`（`data/README.md` §4.9 的全序只在一处实现）。本模块**不认识**
`--fail-on` / `--allow-undecidable`。
"""

from __future__ import annotations

import math
from itertools import combinations
from pathlib import Path
from typing import Any

from . import algorithms, geodesy, io
from .errors import UsageError
from .report import Finding, ModuleResult, build_header

#: 参与差分的本地实现（**全量**，顺序固定）。
IMPLEMENTATIONS = ("coordTransform_py", "gcoord", "proj4js_webmercator")

#: `--target` 的合法枚举：输入坐标被读作哪一个坐标系。
TARGET_CHOICES = ("wgs84", "gcj02", "bd09", "webmercator")

#: 每个目标坐标系下**适用**的实现（顺序固定）。不适用的实现在该次运行中不参与差分——
#: 三个实现覆盖的坐标系不同（`data/README.md` §1.5），把不适用者塞进来只会造出虚假差分。
TARGET_IMPLEMENTATIONS: dict[str, tuple[str, ...]] = {
    "wgs84": IMPLEMENTATIONS,
    "gcj02": (algorithms.PROFILE_CT_PY, algorithms.PROFILE_GCOORD),
    "bd09": (algorithms.PROFILE_CT_PY, algorithms.PROFILE_GCOORD),
    "webmercator": ("gcoord", "proj4js_webmercator"),
}

#: 两库边界画像（`boundary_table` / `jumps` 只涉及这两库，§1.3）。
BOUNDARY_PROFILES = (algorithms.PROFILE_CT_PY, algorithms.PROFILE_GCOORD)

#: 结论原因（`Finding.reason`）的固定枚举，供 `--fail-on` 点名。
REASON_BOUNDARY_DIVERGENCE = "boundary_divergence"
REASON_NOT_CONVERGED = "not_converged"

#: 跳变点的固定文案（`plan/03` §三）。
JUMP_REASON = "out_of_china 边界内外跳变"

MILESTONE = "M4"


# ── 差分距离统计（§4.4：输出米、保留 0.1 m；与 `detect` 同口径，独立持有）──────


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


# ── 三个实现：输入（`target` 坐标系）→ WGS84 ────────────────────────────────


def _identity(lon: float, lat: float) -> algorithms.InverseResult:
    return algorithms.InverseResult(lon, lat, True, 0)


def _coord_transform_py_to_wgs84(
    target: str, lon: float, lat: float
) -> algorithms.InverseResult:
    """`wandergis/coordTransform_py` 口径（§1.3 CT-PY-BBOX / CT-PY-INV）：开区间 + 一步线性近似。"""
    if target == "wgs84":
        return _identity(lon, lat)
    if target == "gcj02":
        return algorithms.gcj02_to_wgs84_linear(lon, lat, algorithms.PROFILE_CT_PY)
    if target == "bd09":
        g_lon, g_lat = algorithms.bd09_to_gcj02(lon, lat)
        return algorithms.gcj02_to_wgs84_linear(g_lon, g_lat, algorithms.PROFILE_CT_PY)
    raise UsageError(
        f"coordTransform_py 不覆盖 target={target!r}",
        detail="该实现对 BD-09/GCJ-02/WGS84 有效，WebMercator 由 gcoord / proj4js 覆盖",
    )


def _gcoord_to_wgs84(target: str, lon: float, lat: float) -> algorithms.InverseResult:
    """`hujiulong/gcoord` 口径（§1.3 GCOORD-BBOX / GCOORD-INV）：闭区间 + 定点迭代，容差 `1e-6`。"""
    if target == "wgs84":
        return _identity(lon, lat)
    if target == "gcj02":
        return algorithms.gcj02_to_wgs84_iterative(lon, lat, algorithms.PROFILE_GCOORD)
    if target == "bd09":
        g_lon, g_lat = algorithms.bd09_to_gcj02(lon, lat)
        return algorithms.gcj02_to_wgs84_iterative(g_lon, g_lat, algorithms.PROFILE_GCOORD)
    if target == "webmercator":
        w_lon, w_lat = algorithms.webmercator_to_wgs84(lon, lat)
        return algorithms.InverseResult(w_lon, w_lat, True, 1)
    raise UsageError(f"gcoord 不覆盖 target={target!r}")


def _proj4js_webmercator_to_wgs84(
    target: str, lon: float, lat: float
) -> algorithms.InverseResult:
    """`proj4js` 等价 WebMercator 解析逆（§1.3；EPSG:3857 ↔ WGS84 的闭式解）。"""
    if target == "wgs84":
        return _identity(lon, lat)
    if target == "webmercator":
        w_lon, w_lat = algorithms.webmercator_to_wgs84(lon, lat)
        return algorithms.InverseResult(w_lon, w_lat, True, 1)
    raise UsageError(
        f"proj4js_webmercator 不覆盖 target={target!r}",
        detail="该实现对 WGS84 / EPSG:3857 有效；GCJ-02 / BD-09 由两库覆盖",
    )


#: `{实现名: 转换函数}`（顺序即 `IMPLEMENTATIONS`）。
_CONVERTERS = {
    algorithms.PROFILE_CT_PY: _coord_transform_py_to_wgs84,
    "gcoord": _gcoord_to_wgs84,
    "proj4js_webmercator": _proj4js_webmercator_to_wgs84,
}


def _label(inside: bool) -> str:
    return "inside" if inside else "outside"


def _round9(value: float) -> float:
    return round(value, 9)


# ── 环节：边界结论表与跳变点（两库独立判定，**不合并、不取并集**）──────────────


def _boundary_table(points: list[io.Point]) -> list[dict[str, Any]]:
    """逐点对拍 `data/fixtures/boundary_divergence/expect.json` 的 `boundary_table_row`。

    用**输入坐标**直接代入两库边界框（不复用 WGS84 输出）——金标就是这么算的（`gen.py`）：
    §1.3 的对照表也是按源坐标判定的（"经度 73.2 < 73.66 → 境外、不偏移"）。
    """
    ct_bbox = algorithms.CT_PY_BBOX
    gc_bbox = algorithms.GCOORD_BBOX
    rows: list[dict[str, Any]] = []
    for p in points:
        ct = algorithms.in_bbox(p.lon, p.lat, ct_bbox)
        gc = algorithms.in_bbox(p.lon, p.lat, gc_bbox)
        rows.append(
            {
                "lon": p.lon,
                "lat": p.lat,
                algorithms.PROFILE_CT_PY: _label(ct),
                "gcoord": _label(gc),
                "agree": ct is gc,
            }
        )
    return rows


def _jumps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """两库对"是否偏移"给出**相反**结论的坐标 → 输出不连续（`plan/03` §三 jumps）。"""
    return [
        {"lon": r["lon"], "lat": r["lat"], "reason": JUMP_REASON}
        for r in rows
        if not r["agree"]
    ]


# ── 入口 ────────────────────────────────────────────────────────────────


def run(path: Path, target: str) -> ModuleResult:
    """差分入口。`target` 非法 → exit 2（`UsageError`）；文件缺失 → exit 3（`EnvironmentMissing`）。

    `run()` 是公开接口，直接调用时不经过 `argparse` 的 `choices`，所以这里**自己也要拦一道**。
    """
    if target not in TARGET_CHOICES:
        raise UsageError(
            f"非法的 --target: {target!r}",
            detail="合法枚举: " + " / ".join(TARGET_CHOICES),
        )

    point_set = io.read_points(path)
    points = point_set.points
    applicable = TARGET_IMPLEMENTATIONS[target]

    # 每个实现把输入坐标转成 WGS84；迭代不收敛**如实收集**（不得静默）。
    outputs: dict[str, list[tuple[float, float]]] = {}
    not_converged: list[dict[str, Any]] = []
    per_impl_not_converged: dict[str, int] = {}
    for name in applicable:
        convert = _CONVERTERS[name]
        lons: list[tuple[float, float]] = []
        failures = 0
        for p in points:
            inv = convert(target, p.lon, p.lat)
            if not inv.converged:
                failures += 1
                not_converged.append(
                    {
                        "lon": p.lon,
                        "lat": p.lat,
                        "implementation": name,
                        "iterations": inv.iterations,
                    }
                )
            lons.append((_round9(inv.lon), _round9(inv.lat)))
        outputs[name] = lons
        per_impl_not_converged[name] = failures

    # 两两差异（§4.4：haversine，米，保留 0.1 m；`max_m` 附该点坐标）。
    pairwise: list[dict[str, Any]] = []
    for a, b in combinations(applicable, 2):
        oa, ob = outputs[a], outputs[b]
        dists = [
            geodesy.haversine_m(pa[0], pa[1], pb[0], pb[1])
            for pa, pb in zip(oa, ob, strict=True)
        ]
        if dists:
            max_idx = max(range(len(dists)), key=lambda i: (dists[i], -i))
            max_at = [points[max_idx].lon, points[max_idx].lat]
            max_m = round(dists[max_idx], 1)
        else:
            max_at = None
            max_m = 0.0
        pairwise.append(
            {
                "a": a,
                "b": b,
                "median_m": round(_median(dists), 1),
                "max_m": max_m,
                "p95_m": round(_p95(dists), 1),
                "max_at": max_at,
                "points_compared": len(dists),
            }
        )

    boundary_rows = _boundary_table(points)
    jumps = _jumps(boundary_rows)
    diverge = [r for r in boundary_rows if not r["agree"]]

    # ── findings：一项一责（`plan/03` §三 / handoff §三.7）───────────────────
    impl_finding = Finding(
        check="implementations",
        status="info",
        detail=f"target={target}；适用实现：" + "、".join(applicable),
        evidence={
            "rule": "data/README.md §1.3",
            "implementations": list(IMPLEMENTATIONS),
            "applicable": list(applicable),
            "input_points": len(points),
        },
    )

    if pairwise:
        worst = max(pairwise, key=lambda r: r["max_m"])
        pairwise_detail = (
            f"{len(pairwise)} 对实现差分，最大 {worst['a']} vs {worst['b']} "
            f"= {worst['max_m']:.1f} m（@ {worst['max_at']}）"
        )
    else:
        pairwise_detail = "无可比较的实现对"
    pairwise_finding = Finding(
        check="pairwise",
        status="info",
        detail=pairwise_detail,
        evidence={
            "rule": "data/README.md §4.4",
            "pairs": [f"{r['a']}/{r['b']}" for r in pairwise],
            "max_m": round(max((r["max_m"] for r in pairwise), default=0.0), 1),
        },
    )

    boundary_finding = Finding(
        check="boundary_table",
        status="warning" if diverge else "consistent",
        reason=REASON_BOUNDARY_DIVERGENCE if diverge else None,
        detail=(
            f"两库 out_of_china 结论不同的点：{len(diverge)}/{len(boundary_rows)}"
            "（coordTransform_py 开区间 / gcoord 闭区间）——这是审计发现点，不是任何一方的 bug"
            if diverge
            else "两库 out_of_china 对本批坐标结论一致"
        ),
        evidence={
            "rule": "data/README.md §1.3",
            "rows": len(boundary_rows),
            "disagree": len(diverge),
        },
    )

    jumps_finding = Finding(
        check="jumps",
        status="info",
        detail=f"边界内外跳变点 {len(jumps)} 个（两库对'是否偏移'结论相反）",
        evidence={
            "rule": "plan/03 §三",
            "jumps": len(jumps),
            "reason": JUMP_REASON,
        },
    )

    if not_converged:
        nc_status = "undecidable"
        nc_reason = REASON_NOT_CONVERGED
        nc_detail = (
            f"gcoord 定点迭代在 {len(not_converged)} 个点上超上限未收敛（容差 "
            f"{algorithms.INVERSE_TOLERANCE_DEG}°）——这些点的差分不可信，按灰区处理"
        )
    else:
        nc_status = "consistent"
        nc_reason = None
        nc_detail = "所有适用实现的逆向均在容差内收敛"
    not_converged_finding = Finding(
        check="not_converged",
        status=nc_status,
        reason=nc_reason,
        detail=nc_detail,
        evidence={
            "rule": "plan/03 §三",
            "tolerance_deg": algorithms.INVERSE_TOLERANCE_DEG,
            "max_iter": algorithms.INVERSE_MAX_ITER,
            "points": len(not_converged),
        },
    )

    findings = [
        impl_finding,
        pairwise_finding,
        boundary_finding,
        jumps_finding,
        not_converged_finding,
    ]

    if not points:
        verdict = "无样本可比较（输入点集为空）"
    elif not_converged:
        verdict = (
            f"两库边界结论 {len(diverge)} 点不同、{len(jumps)} 处跳变；"
            f"另有 {len(not_converged)} 点迭代未收敛（不可判定）"
        )
    elif diverge:
        verdict = f"两库边界结论 {len(diverge)} 点不同；其余一致"
    else:
        verdict = "两库边界结论对全部坐标一致"

    payload: dict[str, Any] = {
        "header": build_header("xdiff"),
        "verdict": verdict,
        "target": target,
        "input_points": len(points),
        "implementations": [
            {
                "name": name,
                "points": [list(coord) for coord in outputs[name]],
                "not_converged": per_impl_not_converged[name],
            }
            for name in applicable
        ],
        "pairwise": pairwise,
        "boundary_table": boundary_rows,
        "jumps": jumps,
        "not_converged": not_converged,
    }

    return ModuleResult(command="xdiff", findings=findings, payload=payload)


def describe() -> list[Finding]:
    ct, gc = algorithms.CT_PY_BBOX, algorithms.GCOORD_BBOX
    return [
        Finding(
            check="ct_py_bbox",
            status="info",
            detail=f"lon {ct['lon']} lat {ct['lat']}（开区间）",
            evidence={"source": "data/README.md §1.3 CT-PY-BBOX"},
        ),
        Finding(
            check="gcoord_bbox",
            status="info",
            detail=f"lon {gc['lon']} lat {gc['lat']}（闭区间）",
            evidence={"source": "data/README.md §1.3 GCOORD-BBOX"},
        ),
        Finding(
            check="implementations",
            status="info",
            detail=",".join(IMPLEMENTATIONS),
            evidence={"tolerance_deg": algorithms.INVERSE_TOLERANCE_DEG},
        ),
    ]
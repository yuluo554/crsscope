"""模块 M4 · GeoJSON RFC 7946 结构与声明审计（`plan/03` §四）。

**两条不可动摇的纪律**：

1. **R1 与 R2 必须成对引用**（`data/README.md` §1.1）：
   R1 = 外环逆时针 MUST；R2 = "parsers SHOULD NOT reject…"。级别由 **R2** 决定 → 默认 `warning`，
   `--strict-ring` 是唯一升级路径。只引 R1 会做出"拒绝合法历史数据"的校验器。
2. **`crs` 成员只表述为 "no longer used"**（RFC 7946 §4 与 Appendix B.1 **没有**任何强制禁用条款；
   `plan/00` 决策 ①）。任何强制禁用式措辞都是违规——`tests/test_wording.py` 会扫 `src/`、`README.md`
   与 `AGENTS.md`，命中即红。

**判定顺序固定**为 `CHECKS`（`plan/03` §四表）：环方向 → 轴序 → bbox → 嵌套 → null → `crs` → 精度。
每项一条 `Finding`（一项一责），跨文件聚合；结构性问题（非法 JSON / 未知 `type` / 坐标对非数值 /
bbox 长度不为 4/6）记为 `structure` 的 `error`，最终由 `run()` 抛 `InvalidInput` → exit 4
（`data/README.md` §4.9："逐条记录但整体按 4 退出"）。

退出码不在这里算：`run()` 只产出 `findings`，命中判定与退出码折算走 `errors.outcome_code`。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import io
from .errors import InvalidInput
from .report import Finding, ModuleResult, build_header

#: 检查项顺序固定（`plan/03` §四）。
CHECKS: tuple[str, ...] = (
    "ring_order",
    "axis",
    "bbox",
    "nesting",
    "null_geometry",
    "crs_member",
    "precision",
)

#: check-geojson 明示不查的三项——本工具**必须**都查（题面 §M4 验收）。
CHECK_GEOJSON_GAPS = ("ring_order", "precision", "crs_member")

#: `crs` 成员的固定措辞。断言用常量比对，防止文案漂移回强制式。
CRS_REMOVED_WORDING = "RFC 7946 已不再使用（no longer used）该成员"

#: R5 的活口（"prior arrangement"一句）——`crs_member` 文案必须附上，避免读成"禁用"。
CRS_PRIOR_ARRANGEMENT = (
    "where all involved parties have a prior arrangement, "
    "alternative coordinate reference systems can be used"
)

#: R1 / R2 原文（照录，用于报告证据字段）。
RFC_R1 = (
    "A linear ring MUST follow the right-hand rule with respect to the area it bounds, "
    "i.e., exterior rings are counterclockwise, and holes are clockwise."
)
RFC_R2 = (
    "For backwards compatibility, parsers SHOULD NOT reject Polygons that do not follow "
    "the right-hand rule."
)

#: 精度阈值（`data/README.md` §4.6）：单分量小数位 **> 9** → `precision` warning。
PRECISION_MAX_FRACTION_DIGITS = 9

#: `ring_order` 的默认级别与升级级别（`data/README.md` §4.6 / 决策 ②）。
RING_ORDER_DEFAULT_STATUS = "warning"
RING_ORDER_STRICT_STATUS = "error"

#: R2 的容忍语义标记。**级别由它决定**——见 `_ring_order_status()` 的变异靶子说明。
R2_TOLERANCE_MARKER = "SHOULD NOT reject"

MILESTONE = "M5"

#: `reason` 固定枚举（供 `--fail-on` 点名）。
REASON_RING = "ring"
REASON_AXIS = "axis"
REASON_BBOX = "bbox"
REASON_STRUCTURE = "structure"

#: GeoJSON 几何类型 → 坐标数组的嵌套层数（`coordinates` 到单个坐标对的距离）。
_GEOMETRY_DIMS: dict[str, int] = {
    "Point": 0,
    "MultiPoint": 1,
    "LineString": 1,
    "MultiLineString": 2,
    "Polygon": 2,
    "MultiPolygon": 3,
}

_GEOMETRY_TYPES: frozenset[str] = frozenset({"GeometryCollection", *_GEOMETRY_DIMS})
_TOP_TYPES: frozenset[str] = frozenset({"Feature", "FeatureCollection"}) | _GEOMETRY_TYPES

_MISSING = object()

#: 坐标精度样本的保留上限（只影响证据体积，不影响 `max_fraction_digits` 判定）。
_PRECISION_SAMPLES_CAP = 10


# ── 单个文件的审计中间表示 ──────────────────────────────────────────────


@dataclass
class FileAudit:
    """一个 GeoJSON 文件的审计事实（**只记录，不判定**；判定在 `_check_*` 里）。"""

    name: str
    top_type: str | None = None
    has_crs: bool = False
    geometry_types: list[str] = field(default_factory=list)
    points: list[tuple[float, float]] = field(default_factory=list)
    ring_signs: list[dict[str, Any]] = field(default_factory=list)
    ring_violations: list[dict[str, Any]] = field(default_factory=list)
    bbox_members: list[dict[str, Any]] = field(default_factory=list)
    max_fraction_digits: int = 0
    precision_samples: list[dict[str, Any]] = field(default_factory=list)
    null_geometries: int = 0
    null_properties: int = 0
    nesting_depth: int = 0
    #: 结构性问题（非法 JSON / 未知 type / 坐标对非数值 …）。非空即 exit 4。
    issues: list[Finding] = field(default_factory=list)


def _issue(audit: FileAudit, message: str, **evidence: Any) -> None:
    """记录一条结构性问题。级别固定 `error`，`check` 固定 `structure`（§4.6）。"""
    audit.issues.append(
        Finding(
            check="structure",
            status="error",
            reason=REASON_STRUCTURE,
            detail=f"{audit.name}: {message}",
            evidence={"file": audit.name, "rule": "data/README.md §4.6", **evidence},
        )
    )


# ── 数值与精度 ──────────────────────────────────────────────────────────


def _number(value: object) -> float | None:
    """JSON 数值 → float；布尔、字符串与非有限值一律 `None`（由调用方记结构错误）。

    JSON 用 `parse_float=Decimal` 读入，这里换算成 float 只用于几何判定；
    精度检查直接读 Decimal 的十进制指数，**不经过 float 往返**。
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
    elif isinstance(value, float):
        if not math.isfinite(value):
            return None
    elif not isinstance(value, int):
        return None
    result = float(value)  # type: ignore[arg-type]
    return result if math.isfinite(result) else None


def _fraction_digits(value: object) -> int:
    """单分量的十进制小数位（`112.123456789012` → 12）。整数为 0。"""
    if isinstance(value, Decimal):
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int):
            return max(0, -exponent)
    return 0


# ── 结构与坐标收集 ──────────────────────────────────────────────────────


def _leaf(node: object, audit: FileAudit) -> tuple[float, float] | None:
    """一个坐标对。长度 < 2 / 非数值 → 结构错误（§4.6 的 `error`）。"""
    if not isinstance(node, list):
        _issue(audit, "坐标对必须是数组", value_type=type(node).__name__)
        return None
    if len(node) < 2:
        _issue(
            audit,
            f"坐标对只有 {len(node)} 个元素（至少需要 2 个）",
            coordinate_length=len(node),
            min_length=2,
        )
        return None
    lon, lat = _number(node[0]), _number(node[1])
    if lon is None or lat is None:
        _issue(audit, f"坐标对含非数值或非有限分量: {node[:2]!r}")
        return None

    for index, component in enumerate(node):
        digits = _fraction_digits(component)
        if digits > audit.max_fraction_digits:
            audit.max_fraction_digits = digits
        if digits > PRECISION_MAX_FRACTION_DIGITS and len(audit.precision_samples) < _PRECISION_SAMPLES_CAP:
            audit.precision_samples.append(
                {"component": index, "value": str(component), "fraction_digits": digits}
            )

    audit.points.append((lon, lat))
    return (lon, lat)


def _collect(node: object, depth: int, audit: FileAudit) -> Any:
    """按几何维度把 `coordinates` 收成嵌套列表；叶子是坐标对（或 `None`）。"""
    if depth == 0:
        return _leaf(node, audit)
    if not isinstance(node, list):
        _issue(audit, "坐标数组形态非法（该层级应为数组）", expected_depth=depth)
        return None
    return [_collect(child, depth - 1, audit) for child in node]


def _flatten_pairs(node: Any) -> list[tuple[float, float]]:
    if node is None:
        return []
    if isinstance(node, tuple):
        return [node]
    out: list[tuple[float, float]] = []
    for child in node:
        out.extend(_flatten_pairs(child))
    return out


def _shoelace_sign(pairs: list[tuple[float, float]]) -> int:
    """环方向：`+1` 逆时针（CCW）/ `-1` 顺时针（CW）/ `0` 退化。

    闭式 Shoelace：`sum(x_i * y_{i+1} - x_{i+1} * y_i)`，首尾自动闭合。
    """
    if len(pairs) < 3:
        return 0
    total = 0.0
    for index, (x1, y1) in enumerate(pairs):
        x2, y2 = pairs[(index + 1) % len(pairs)]
        total += x1 * y2 - x2 * y1
    if total > 0:
        return 1
    if total < 0:
        return -1
    return 0


def _polygons(tree: Any, geometry_type: str) -> list[list[Any]]:
    if geometry_type == "Polygon":
        return [tree] if isinstance(tree, list) else []
    if geometry_type == "MultiPolygon":
        return [poly for poly in tree if isinstance(poly, list)] if isinstance(tree, list) else []
    return []


def _audit_rings(tree: Any, geometry_type: str, audit: FileAudit) -> None:
    """Polygon / MultiPolygon 的环方向判定（R1）；违规**只记录**，级别在 `_check_ring_order`。"""
    for polygon_index, polygon in enumerate(_polygons(tree, geometry_type)):
        rings = polygon if isinstance(polygon, list) else []
        for ring_index, ring in enumerate(rings):
            if not isinstance(ring, list):
                continue
            pairs = [pair for pair in ring if isinstance(pair, tuple)]
            if len(pairs) != len(ring):  # 有结构错误的分量，环方向无从判定
                continue
            role = "exterior" if ring_index == 0 else "hole"
            sign = _shoelace_sign(pairs)
            record: dict[str, Any] = {
                "file": audit.name,
                "geometry": geometry_type,
                "polygon": polygon_index,
                "ring": role,
                "index": ring_index,
                "sign": sign,
            }
            audit.ring_signs.append(record)
            if sign == 0:
                _issue(
                    audit,
                    f"环退化（Shoelace 面积为 0）：{role} ring #{ring_index}",
                    polygon=polygon_index,
                    ring=role,
                )
                continue
            expected = 1 if role == "exterior" else -1
            if sign != expected:
                audit.ring_violations.append({**record, "expected": expected})


def _bbox_contains(
    west: float, south: float, east: float, north: float, lon: float, lat: float
) -> bool:
    """bbox 包含判定。`west > east` 时按**跨 180°** 解读（RFC 7946 §7.1 / §5.2）。"""
    if not (south <= lat <= north):
        return False
    if west <= east:
        return west <= lon <= east
    return lon >= west or lon <= east


def _audit_bbox(raw: object, points: list[tuple[float, float]], audit: FileAudit, where: str) -> None:
    """bbox 成员：长度 / 顺序 / 与真实外包框一致 / 跨 180° 合法性（§4.6 / R4）。"""
    if not isinstance(raw, list) or len(raw) not in (4, 6):
        length = len(raw) if isinstance(raw, list) else None
        _issue(audit, "bbox 长度必须为 4 或 6", bbox_length=length, allowed=[4, 6], where=where)
        return
    values = [_number(item) for item in raw]
    if any(value is None for value in values):
        _issue(audit, "bbox 含非数值或非有限分量", where=where)
        return
    numeric = [float(value) for value in values if value is not None]
    if len(numeric) == 4:
        west, south, east, north = numeric
        extra: dict[str, Any] = {}
    else:
        west, south, minz, east, north, maxz = numeric
        extra = {"minz": minz, "maxz": maxz}

    problems: list[str] = []
    if south > north:
        problems.append("south > north，违反 [west, south, east, north] 顺序")
    outside = [
        point for point in points if not _bbox_contains(west, south, east, north, point[0], point[1])
    ]
    if points and outside:
        problems.append(
            f"{len(outside)}/{len(points)} 个坐标落在声明 bbox 之外（bbox 与几何真实外包框不一致）"
        )

    record: dict[str, Any] = {
        "file": audit.name,
        "where": where,
        "bbox": numeric,
        "west_greater_than_east": west > east,
        "problems": problems,
        **extra,
    }
    if outside:
        record["outside_sample"] = list(outside[0])
    audit.bbox_members.append(record)


def _geometry(geom: object, audit: FileAudit, depth: int = 0) -> list[tuple[float, float]]:
    """递归审计一个几何对象，返回它覆盖的坐标点。"""
    if geom is None:
        return []
    if not isinstance(geom, dict):
        _issue(audit, "几何对象必须是 JSON object 或 null", value_type=type(geom).__name__)
        return []

    geometry_type = geom.get("type")
    if not isinstance(geometry_type, str) or geometry_type not in _GEOMETRY_TYPES:
        _issue(audit, f"未知几何类型: {geometry_type!r}", geometry_type=geometry_type)
        return []
    audit.geometry_types.append(geometry_type)

    points: list[tuple[float, float]] = []
    if geometry_type == "GeometryCollection":
        children = geom.get("geometries")
        if not isinstance(children, list):
            _issue(audit, "GeometryCollection.geometries 必须是数组")
            children = []
        audit.nesting_depth = max(audit.nesting_depth, depth + 1)
        for child in children:
            points.extend(_geometry(child, audit, depth + 1))
    else:
        coordinates = geom.get("coordinates")
        if coordinates is None:
            _issue(audit, f"{geometry_type} 缺少 coordinates 成员", geometry_type=geometry_type)
        else:
            tree = _collect(coordinates, _GEOMETRY_DIMS[geometry_type], audit)
            points = _flatten_pairs(tree)
            if geometry_type in {"Polygon", "MultiPolygon"}:
                _audit_rings(tree, geometry_type, audit)

    if "bbox" in geom:
        _audit_bbox(geom["bbox"], points, audit, f"geometry:{geometry_type}")
    return points


def _feature(feature: object, audit: FileAudit, index: int) -> list[tuple[float, float]]:
    if not isinstance(feature, dict):
        _issue(audit, f"features[{index}] 必须是 JSON object", feature_index=index)
        return []
    if feature.get("type") != "Feature":
        _issue(
            audit,
            f"features[{index}].type 应为 Feature（实得 {feature.get('type')!r}）",
            feature_index=index,
        )
        return []

    properties = feature.get("properties", _MISSING)
    if properties is _MISSING:
        _issue(audit, "Feature 缺少 properties 成员（RFC 7946 §3.2：可为 null）", feature_index=index)
    elif properties is None:
        audit.null_properties += 1
    elif not isinstance(properties, dict):
        _issue(audit, "Feature.properties 必须是 JSON object 或 null", feature_index=index)

    if "geometry" not in feature:
        _issue(audit, "Feature 缺少 geometry 成员（RFC 7946 §3.2：可为 null）", feature_index=index)
        return []
    geometry = feature.get("geometry")
    if geometry is None:
        audit.null_geometries += 1
        return []

    points = _geometry(geometry, audit)
    if "bbox" in feature:
        _audit_bbox(feature["bbox"], points, audit, f"feature[{index}]")
    return points


def _audit_path(path: Path) -> FileAudit:
    """读入并审计一个文件。文件缺失 → exit 3（由 `io.read_text` 抛出）。"""
    audit = FileAudit(name=path.name)
    text = io.read_text(path)
    try:
        data = json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        _issue(audit, f"JSON 不可解析: {exc.msg}（行 {exc.lineno} 列 {exc.colno}）")
        return audit

    if not isinstance(data, dict):
        _issue(audit, "顶层应为 GeoJSON object")
        return audit

    top_type = data.get("type")
    audit.top_type = top_type if isinstance(top_type, str) else None
    if top_type not in _TOP_TYPES:
        _issue(audit, f"未知 GeoJSON type: {top_type!r}", type=top_type)
        return audit
    audit.has_crs = "crs" in data

    points: list[tuple[float, float]] = []
    if top_type == "FeatureCollection":
        features = data.get("features")
        if not isinstance(features, list):
            _issue(audit, "FeatureCollection.features 必须是数组")
            features = []
        for index, feature in enumerate(features):
            points.extend(_feature(feature, audit, index))
    elif top_type == "Feature":
        points.extend(_feature(data, audit, 0))
    else:
        points.extend(_geometry(data, audit))

    if "bbox" in data:
        _audit_bbox(data["bbox"], points, audit, top_type)
    return audit


# ── 七个检查项（顺序固定，一项一责）────────────────────────────────────


def _ring_order_status(strict_ring: bool) -> str:
    """R1 违规的级别**由 R2 决定**：R2 的容忍语义在 → `warning`；不在 → `error`。

    **变异靶子**（决策 ②）：删掉 `R2_TOLERANCE_MARKER not in RFC_R2` 这一支，
    `tests/test_geojson.py::test_ring_level_is_derived_from_r2` 立刻变红——
    它把 `RFC_R2` 换成不含 "SHOULD NOT reject" 的文本，并要求级别升到 `error`。
    """
    if strict_ring:
        return RING_ORDER_STRICT_STATUS
    if R2_TOLERANCE_MARKER not in RFC_R2:
        return RING_ORDER_STRICT_STATUS
    return RING_ORDER_DEFAULT_STATUS


def _check_ring_order(audits: list[FileAudit], strict_ring: bool) -> Finding:
    violations = [record for audit in audits for record in audit.ring_violations]
    signs = [record for audit in audits for record in audit.ring_signs]
    evidence: dict[str, Any] = {
        "rule": "RFC 7946 §3.1.6",
        "r1": RFC_R1,
        "r2": RFC_R2,
        "strict_ring": strict_ring,
        "rings_checked": len(signs),
        "violations": len(violations),
    }
    if violations:
        status = _ring_order_status(strict_ring)
        first = violations[0]
        detail = (
            f"{len(violations)} 个环违反 R1（右手法则：外环逆时针、洞顺时针；"
            f"首个为 {first['file']} 的 {first['ring']} ring，Shoelace 符号 {first['sign']}）；"
            "按 R2（for backwards compatibility, parsers SHOULD NOT reject…）报告不放弃、"
            f"但级别默认为 {RING_ORDER_DEFAULT_STATUS}，--strict-ring 是唯一升 error 的路径"
        )
        evidence["samples"] = violations[:_PRECISION_SAMPLES_CAP]
        return Finding(
            check="ring_order",
            status=status,
            reason=REASON_RING,
            detail=detail,
            evidence=evidence,
        )
    if not signs:
        return Finding(
            check="ring_order",
            status="info",
            detail="没有 Polygon / MultiPolygon 环可判（R1 不适用）",
            evidence=evidence,
        )
    return Finding(
        check="ring_order",
        status="consistent",
        detail=f"{len(signs)} 个环全部符合 R1（外环逆时针、洞顺时针）",
        evidence=evidence,
    )


def _check_axis(audits: list[FileAudit]) -> Finding:
    points = [point for audit in audits for point in audit.points]
    evidence: dict[str, Any] = {"rule": "RFC 7946 §3.1.1", "coordinates": len(points)}
    if not points:
        return Finding(check="axis", status="info", detail="没有坐标对可判轴序", evidence=evidence)

    swapped = [point for point in points if abs(point[1]) > 90 and abs(point[0]) <= 90]
    if swapped:
        evidence["sample"] = list(swapped[0])
        evidence["affected"] = len(swapped)
        return Finding(
            check="axis",
            status="warning",
            reason=REASON_AXIS,
            detail=(
                f"{len(swapped)}/{len(points)} 个坐标对的第二分量越出纬度域（> 90°）而第一分量仍在经度域"
                f"（样本 {list(swapped[0])}）→ 呈 (lat, lon) 排列，RFC 7946 要求 (lon, lat)"
            ),
            evidence=evidence,
        )

    lon_clear = [point for point in points if abs(point[0]) > 90]
    if lon_clear:
        evidence["sample"] = list(lon_clear[0])
        return Finding(
            check="axis",
            status="consistent",
            detail=f"{len(lon_clear)} 个坐标对的第一分量越出纬度域 → 只能是经度，轴序呈 (lon, lat)",
            evidence=evidence,
        )
    return Finding(
        check="axis",
        status="info",
        detail="全部坐标分量都落在 ±90 内，无法区分 (lon, lat) 与 (lat, lon)",
        evidence=evidence,
    )


def _check_bbox(audits: list[FileAudit]) -> Finding:
    members = [record for audit in audits for record in audit.bbox_members]
    evidence: dict[str, Any] = {
        "rule": "RFC 7946 §7.1 / §5.2",
        "bbox_members": len(members),
        "members": members,
    }
    if not members:
        return Finding(check="bbox", status="info", detail="没有 bbox 成员", evidence=evidence)

    warned = [record for record in members if record["problems"]]
    if warned:
        first = warned[0]
        return Finding(
            check="bbox",
            status="warning",
            reason=REASON_BBOX,
            detail=(
                f"{len(warned)}/{len(members)} 个 bbox 成员与几何不一致："
                f"{first['where']} —— {'；'.join(first['problems'])}"
            ),
            evidence={**evidence, "problems": warned[:_PRECISION_SAMPLES_CAP]},
        )

    crossing = [record for record in members if record["west_greater_than_east"]]
    if crossing:
        return Finding(
            check="bbox",
            status="info",
            detail=(
                f"{len(crossing)} 个 bbox 呈 west > east（跨 180°）——RFC 7946 §7.1 / §5.2（R4）明确合法，"
                "不是错误"
            ),
            evidence={**evidence, "crossing": crossing[:_PRECISION_SAMPLES_CAP]},
        )
    return Finding(
        check="bbox",
        status="consistent",
        detail=f"{len(members)} 个 bbox 成员与几何外包框一致",
        evidence=evidence,
    )


def _check_nesting(audits: list[FileAudit]) -> Finding:
    depth = max((audit.nesting_depth for audit in audits), default=0)
    evidence: dict[str, Any] = {
        "rule": "RFC 7946 §3.1",
        "max_depth": depth,
        "geometry_collections": sum(
            1 for audit in audits for kind in audit.geometry_types if kind == "GeometryCollection"
        ),
    }
    if depth:
        return Finding(
            check="nesting",
            status="info",
            detail=f"GeometryCollection 最大嵌套深度 {depth}，类型自洽",
            evidence=evidence,
        )
    return Finding(
        check="nesting", status="consistent", detail="没有 GeometryCollection 嵌套", evidence=evidence
    )


def _check_null_geometry(audits: list[FileAudit]) -> Finding:
    null_geometries = sum(audit.null_geometries for audit in audits)
    null_properties = sum(audit.null_properties for audit in audits)
    evidence: dict[str, Any] = {
        "rule": "RFC 7946 §3.2",
        "null_geometries": null_geometries,
        "null_properties": null_properties,
    }
    if null_geometries or null_properties:
        return Finding(
            check="null_geometry",
            status="info",
            detail=(
                f"geometry: null 的 Feature {null_geometries} 个、properties: null 的 {null_properties} 个"
                "——RFC 7946 §3.2 明确合法（unlocated feature），只做提示，不进 exit 4"
            ),
            evidence=evidence,
        )
    return Finding(
        check="null_geometry",
        status="consistent",
        detail="没有 geometry: null / properties: null 的 Feature",
        evidence=evidence,
    )


def _check_crs_member(audits: list[FileAudit]) -> Finding:
    files = [audit.name for audit in audits if audit.has_crs]
    evidence: dict[str, Any] = {
        "rule": "RFC 7946 §4 与 Appendix B.1",
        "source": "RFC 7946 §4 / Appendix B.1",
        "files": files,
        "wording": CRS_REMOVED_WORDING,
    }
    if files:
        return Finding(
            check="crs_member",
            status="warning",
            reason="crs",
            detail=(
                f"{len(files)} 个文件声明了 crs 成员：{CRS_REMOVED_WORDING}；"
                f"RFC 7946 §4 同时留了活口：{CRS_PRIOR_ARRANGEMENT}"
            ),
            evidence=evidence,
        )
    return Finding(
        check="crs_member",
        status="consistent",
        detail="没有文件使用 crs 成员",
        evidence=evidence,
    )


def _check_precision(audits: list[FileAudit]) -> Finding:
    max_digits = max((audit.max_fraction_digits for audit in audits), default=0)
    samples = [sample for audit in audits for sample in audit.precision_samples]
    evidence: dict[str, Any] = {
        "rule": "data/README.md §4.6",
        "max_fraction_digits": max_digits,
        "threshold_digits": PRECISION_MAX_FRACTION_DIGITS,
        "samples": samples[:_PRECISION_SAMPLES_CAP],
    }
    if max_digits > PRECISION_MAX_FRACTION_DIGITS:
        return Finding(
            check="precision",
            status="warning",
            reason="precision",
            detail=(
                f"单分量小数位最多 {max_digits} 位，超过阈值 {PRECISION_MAX_FRACTION_DIGITS} 位"
                "（9 位十进制 ≈ 0.1 mm，对任何地表坐标无意义）"
            ),
            evidence=evidence,
        )
    return Finding(
        check="precision",
        status="consistent",
        detail=f"单分量小数位最多 {max_digits} 位，未超阈值 {PRECISION_MAX_FRACTION_DIGITS} 位",
        evidence=evidence,
    )


def _verdict(findings: list[Finding]) -> str:
    errors = [finding.check for finding in findings if finding.status == "error"]
    if errors:
        return "结构错误：" + "、".join(errors)
    warnings = [finding.check for finding in findings if finding.status == "warning"]
    if warnings:
        return "结构与声明审计有提示项：" + "、".join(warnings)
    infos = [finding.check for finding in findings if finding.status == "info"]
    if infos:
        return "结构自洽（信息项：" + "、".join(infos) + "）"
    return "结构自洽（七项检查均未命中）"


# ── 入口 ────────────────────────────────────────────────────────────────


def audit(paths: list[Path]) -> tuple[list[FileAudit], list[Finding]]:
    """逐文件收集事实与结构性问题，**不抛异常**（供测试与 `run()` 共用）。

    返回 `(每个文件的审计事实, 全部结构性问题)`。结构性问题非空即整体 exit 4。
    """
    audits = [_audit_path(path) for path in paths]
    issues = [finding for audit_result in audits for finding in audit_result.issues]
    return audits, issues


def run(paths: list[Path], *, strict_ring: bool = False) -> ModuleResult:
    """GeoJSON 审计入口。

    - 结构性问题（非法 JSON / 未知 `type` / 坐标对非数值 / bbox 长度不为 4/6）→
      逐条记录后整体 `InvalidInput` → exit 4（§4.9）；
    - `geometry: null` / `properties: null` **不进** exit 4（R6，只出 info）；
    - 跨 180° bbox **不报 error**（R4，只出 info）；
    - R1 违规默认 `warning`，`--strict-ring` 是唯一升级到 `error` 的路径。
    """
    audits, issues = audit(paths)
    if issues:
        detail = "；".join(finding.detail for finding in issues)
        raise InvalidInput(
            f"{len(issues)} 处结构错误（共 {len(audits)} 个文件）",
            detail=detail,
        )

    findings = [
        _check_ring_order(audits, strict_ring),
        _check_axis(audits),
        _check_bbox(audits),
        _check_nesting(audits),
        _check_null_geometry(audits),
        _check_crs_member(audits),
        _check_precision(audits),
    ]

    payload: dict[str, Any] = {
        "header": build_header("geojson"),
        "verdict": _verdict(findings),
        "strict_ring": strict_ring,
        "files": [
            {
                "name": audit_result.name,
                "type": audit_result.top_type,
                "geometry_types": sorted(set(audit_result.geometry_types)),
                "coordinates": len(audit_result.points),
                "rings": audit_result.ring_signs,
                "ring_violations": audit_result.ring_violations,
                "bbox_members": audit_result.bbox_members,
                "max_fraction_digits": audit_result.max_fraction_digits,
                "null_geometry": audit_result.null_geometries,
                "null_properties": audit_result.null_properties,
                "nesting_depth": audit_result.nesting_depth,
                "has_crs": audit_result.has_crs,
            }
            for audit_result in audits
        ],
        "counts": {
            "files": len(audits),
            "coordinates": sum(len(audit_result.points) for audit_result in audits),
            "rings": sum(len(audit_result.ring_signs) for audit_result in audits),
            "ring_violations": sum(len(audit_result.ring_violations) for audit_result in audits),
        },
    }

    return ModuleResult(command="geojson", findings=findings, payload=payload)


def describe() -> list[Finding]:
    return [
        Finding(
            check="ring_order",
            status="info",
            detail="默认 warning（R2）；--strict-ring 升 error",
            evidence={"r1": RFC_R1, "r2": RFC_R2},
        ),
        Finding(
            check="crs_member",
            status="info",
            detail=CRS_REMOVED_WORDING,
            evidence={"source": "RFC 7946 §4 与 Appendix B.1"},
        ),
        Finding(check="checked_gaps", status="info", detail=",".join(CHECK_GEOJSON_GAPS)),
    ]

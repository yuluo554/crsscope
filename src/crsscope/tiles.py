"""模块 M5 · 瓦片 / 投影一致性（`plan/03` §五）。

**不做地图渲染、不产出图片、不做切片**；输出只有布尔 / 数值判定与证据（题面 §M5）。

输入两态（题面 §M5 "瓦片坐标清单（`z/x/y`）或 3857/4326 混用的点集"）：

1. **瓦片清单**：JSON（`{"tiles": [...]}` / `{"cases": [{"tiles": [...]}]}` / `[{"z","x","y"}]`）
   或 CSV（表头含 `z,x,y`）。可选字段：`bbox`（组级或单枚）、`wrap: true`、`scheme`。
2. **点集**：GeoJSON / CSV(lon,lat)，交给 `io.read_points` 归一；只做 3857/4326 量级分档判定。

检查项顺序固定为 `CHECKS`（`plan/03` §五表）：
`axis_flip` → `y_range` → `zoom_bbox` → `wrap` → `mixed_3857_4326`。

- `axis_flip` 是**静态**判定：同一 `z` / 同一 `x` 下同时出现 `y` 与 `2^z - 1 - y`，
  且两者指向同一 bbox（组级 bbox 或两枚各自声明同一 bbox，或 scheme 明写 xyz/tms）→ 混用。
  **不需要任何底图**（题面 §M5 验收）。
- `y_range`：`y ∉ [0, 2^z - 1]` → `error`，**单点即判**。
- 不做渲染 / 切片 / 图片——本模块的 `payload` 里不含任何图像产物字段。

退出码不在这里算：`run()` 只产出 `findings`，命中判定与退出码折算走 `errors.outcome_code`。
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import io
from .errors import EnvironmentMissing, InvalidInput
from .report import Finding, ModuleResult, build_header

CHECKS: tuple[str, ...] = ("axis_flip", "y_range", "zoom_bbox", "wrap", "mixed_3857_4326")

MILESTONE = "M5"

#: `y` 轴翻转公式（§4.7：`2^z - 1 - y`）。
FLIP_FORMULA = "2**z - 1 - y"

#: 量级分档阈值（**引用** `data/README.md` §4.1，本模块不另立口径）。
#: `mixed_3857_4326` 只用这两条分档，权重与评分一概不涉及。
DEGREE_MAX = 180.0
METRE_MIN = 1_000_000.0

BAND_DEGREE = "degree"
BAND_METRE = "metre"
BAND_NEITHER = "neither"

#: `reason` 固定枚举（供 `--fail-on` 点名）。
REASON_AXIS_FLIP = "axis_flip"
REASON_Y_RANGE = "y_range"
REASON_ZOOM_BBOX = "zoom_bbox"
REASON_WRAP = "wrap"
REASON_MIXED = "mixed"


# ── 输入模型 ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Tile:
    z: int
    x: int
    y: int
    wrap: bool = False
    scheme: str | None = None
    bbox: tuple[float, float, float, float] | None = None

    @property
    def rows(self) -> int:
        """该 `z` 下的行数 `2^z`。"""
        return 2**self.z

    @property
    def key(self) -> dict[str, int]:
        return {"z": self.z, "x": self.x, "y": self.y}

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"z": self.z, "x": self.x, "y": self.y, "wrap": self.wrap}
        if self.scheme is not None:
            data["scheme"] = self.scheme
        if self.bbox is not None:
            data["bbox"] = list(self.bbox)
        return data


@dataclass
class TileGroup:
    id: str
    tiles: list[Tile] = field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class GroupAudit:
    """一组的判定事实（只记录，判定在 `_check_*` 里）。"""

    id: str
    bbox: tuple[float, float, float, float] | None = None
    tiles: list[Tile] = field(default_factory=list)
    axis_flip_pairs: list[dict[str, Any]] = field(default_factory=list)
    y_range_offenders: list[dict[str, Any]] = field(default_factory=list)
    zoom_breaks: list[dict[str, Any]] = field(default_factory=list)
    wrap_missing: list[dict[str, Any]] = field(default_factory=list)
    wrap_needed: bool = False


# ── 读取与校验 ──────────────────────────────────────────────────────────


def _int_field(obj: dict[str, Any], key: str, path: Path) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidInput(
            f"{path.name}: 瓦片字段 {key} 必须是整数（实得 {value!r}）",
            detail="z/x/y 为瓦片编号，不接受浮点或字符串（§4.9 输入无效 → exit 4）",
        )
    return value


def _bbox_field(obj: dict[str, Any], path: Path) -> tuple[float, float, float, float] | None:
    if "bbox" not in obj:
        return None
    raw = obj["bbox"]
    if not isinstance(raw, list) or len(raw) != 4:
        raise InvalidInput(
            f"{path.name}: 瓦片 bbox 必须是长度 4 的数组 [west, south, east, north]",
            detail="§4.9 结构破碎 → exit 4",
        )
    try:
        west, south, east, north = (float(value) for value in raw)
    except (TypeError, ValueError) as exc:
        raise InvalidInput(f"{path.name}: 瓦片 bbox 含非数值分量") from exc
    return (west, south, east, north)


def _tile_from_dict(obj: object, path: Path) -> Tile:
    if not isinstance(obj, dict):
        raise InvalidInput(f"{path.name}: 瓦片条目必须是 JSON object")
    z = _int_field(obj, "z", path)
    x = _int_field(obj, "x", path)
    y = _int_field(obj, "y", path)
    if z < 0:
        raise InvalidInput(
            f"{path.name}: 瓦片 z 不能为负（实得 {z}）",
            detail="§4.9 输入无效 → exit 4",
        )
    scheme = obj.get("scheme")
    return Tile(
        z=z,
        x=x,
        y=y,
        wrap=obj.get("wrap") is True,
        scheme=scheme if isinstance(scheme, str) else None,
        bbox=_bbox_field(obj, path),
    )


def _tiles_from_list(items: object, path: Path, where: str) -> list[Tile]:
    if not isinstance(items, list):
        raise InvalidInput(f"{path.name}: {where} 必须是数组")
    return [_tile_from_dict(item, path) for item in items]


def _groups_from_json(data: dict[str, Any], path: Path) -> list[TileGroup]:
    if "cases" in data:
        cases = data["cases"]
        if not isinstance(cases, list):
            raise InvalidInput(f"{path.name}: cases 必须是数组")
        groups: list[TileGroup] = []
        for index, case in enumerate(cases):
            if not isinstance(case, dict):
                raise InvalidInput(f"{path.name}: cases[{index}] 必须是 JSON object")
            case_id = case.get("id")
            groups.append(
                TileGroup(
                    id=str(case_id) if case_id is not None else f"case-{index + 1:03d}",
                    tiles=_tiles_from_list(case.get("tiles"), path, f"cases[{index}].tiles"),
                    bbox=_bbox_field(case, path),
                )
            )
        return groups
    return [
        TileGroup(
            id="tiles",
            tiles=_tiles_from_list(data.get("tiles"), path, "tiles"),
            bbox=_bbox_field(data, path),
        )
    ]


def _tiles_from_csv(rows: list[list[str]], header: list[str], path: Path) -> list[Tile]:
    index = {name: header.index(name) for name in ("z", "x", "y")}
    i_wrap = header.index("wrap") if "wrap" in header else None
    tiles: list[Tile] = []
    body = rows[1:]
    while body and not any(cell.strip() for cell in body[-1]):
        body.pop()
    for line_number, row in enumerate(body, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        try:
            z = int(row[index["z"]])
            x = int(row[index["x"]])
            y = int(row[index["y"]])
        except (IndexError, ValueError) as exc:
            raise InvalidInput(
                f"{path.name}: CSV 第 {line_number} 行的 z/x/y 不是整数",
                detail="§4.9 输入无效 → exit 4",
            ) from exc
        if z < 0:
            raise InvalidInput(f"{path.name}: CSV 第 {line_number} 行 z 为负")
        wrap = False
        if i_wrap is not None and i_wrap < len(row):
            wrap = row[i_wrap].strip().lower() in {"1", "true", "yes", "y"}
        tiles.append(Tile(z=z, x=x, y=y, wrap=wrap))
    return tiles


def _load(path: Path) -> tuple[str, list[TileGroup], list[io.Point]]:
    """按**形态**分派：瓦片清单（JSON / CSV）或点集（GeoJSON / CSV）。"""
    text = io.read_text(path)
    stripped = text.lstrip()

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise InvalidInput(
                f"{path.name}: JSON 不可解析: {exc.msg}（行 {exc.lineno} 列 {exc.colno}）",
                detail="§4.9 输入无效 → exit 4",
            ) from exc
        if isinstance(data, dict) and ("tiles" in data or "cases" in data):
            return "tiles", _groups_from_json(data, path), []
        if isinstance(data, list):
            return "tiles", [TileGroup(id="tiles", tiles=_tiles_from_list(data, path, "顶层数组"))], []
        return "points", [], io.read_points(path).points

    if path.suffix.lower() in {".csv", ".tsv"}:
        rows = list(csv.reader(text.splitlines()))
        if not rows:
            raise InvalidInput(f"{path.name}: CSV 为空", detail="§4.9 输入无效 → exit 4")
        header = [cell.strip().lower() for cell in rows[0]]
        if {"z", "x", "y"} <= set(header):
            return "tiles", [TileGroup(id="csv", tiles=_tiles_from_csv(rows, header, path))], []
        return "points", [], io.read_points(path).points

    raise EnvironmentMissing(
        f"不支持的瓦片输入形态: {path.name}",
        detail="支持：z/x/y 清单（JSON / CSV）或 GeoJSON / CSV(lon,lat) 点集",
    )


# ── 五项判定的事实收集 ──────────────────────────────────────────────────


def _row_limit(tile: Tile) -> int:
    return tile.rows - 1


def _same_bbox(group: TileGroup, first: Tile, second: Tile) -> bool:
    """两枚瓦片是否"指向同一 bbox"（§4.7 的静态判据之一）。"""
    if group.bbox is not None:
        return True
    if first.bbox is not None and second.bbox is not None and first.bbox == second.bbox:
        return True
    schemes = {first.scheme, second.scheme}
    return schemes == {"xyz", "tms"}


def _audit_group(group: TileGroup) -> GroupAudit:
    audit = GroupAudit(id=group.id, bbox=group.bbox, tiles=list(group.tiles))

    # 1) y 越界：单点即判（§4.7）
    for tile in group.tiles:
        limit = _row_limit(tile)
        if tile.y < 0 or tile.y > limit:
            audit.y_range_offenders.append(
                {**tile.key, "allowed": [0, limit], "scheme": tile.scheme}
            )

    # 2) y 轴翻转：同一 z / 同一 x 下 y 与 2^z-1-y 并存，且指向同一 bbox
    by_column: dict[tuple[int, int], list[Tile]] = {}
    for tile in group.tiles:
        limit = _row_limit(tile)
        if 0 <= tile.y <= limit:
            by_column.setdefault((tile.z, tile.x), []).append(tile)
    for (z, x), column in sorted(by_column.items()):
        by_y = {tile.y: tile for tile in column}
        limit = 2**z - 1
        seen: set[tuple[int, int]] = set()
        for y, tile in sorted(by_y.items()):
            flipped = limit - y
            if flipped == y or flipped not in by_y:
                continue
            pair_key = (min(y, flipped), max(y, flipped))
            if pair_key in seen:
                continue
            other = by_y[flipped]
            if not _same_bbox(group, tile, other):
                continue
            seen.add(pair_key)
            audit.axis_flip_pairs.append(
                {
                    "group": group.id,
                    "z": z,
                    "x": x,
                    "y": [y, flipped],
                    "flip_formula": FLIP_FORMULA,
                    "bbox": list(group.bbox) if group.bbox is not None else None,
                    "schemes": [tile.scheme, other.scheme],
                    "row_span": [0, limit],
                }
            )

    # 3) zoom ↔ bbox：z+1 的父瓦片必须出现在 z 的集合里（否则覆盖不单调）
    by_zoom: dict[int, list[Tile]] = {}
    for tile in group.tiles:
        if 0 <= tile.y <= _row_limit(tile):
            by_zoom.setdefault(tile.z, []).append(tile)
    for z, parent_tiles in sorted(by_zoom.items()):
        children = by_zoom.get(z + 1)
        if not children:
            continue
        parents = {(tile.x, tile.y) for tile in parent_tiles if 0 <= tile.x < 2**z}
        for child in sorted(children, key=lambda t: (t.x, t.y)):
            if not 0 <= child.x < 2 ** (z + 1):
                continue
            parent = (child.x // 2, child.y // 2)
            if parent not in parents:
                audit.zoom_breaks.append(
                    {
                        "group": group.id,
                        "z": child.z,
                        "x": child.x,
                        "y": child.y,
                        "missing_parent": {"z": z, "x": parent[0], "y": parent[1]},
                    }
                )

    # 4) wrap：x 环绕必须显式 wrap: true（§4.7）
    crossing_bbox = group.bbox is not None and group.bbox[2] < group.bbox[0]
    for z, tiles in sorted(by_zoom.items()):
        limit_x = 2**z - 1
        columns = {tile.x for tile in tiles}
        out_of_range = [tile for tile in tiles if tile.x < 0 or tile.x > limit_x]
        edge_pair = z > 0 and 0 in columns and limit_x in columns
        if not (edge_pair or out_of_range or (crossing_bbox and z > 0)):
            continue
        audit.wrap_needed = True
        if crossing_bbox:
            required = tiles
        else:
            required = [tile for tile in tiles if tile.x in (0, limit_x) or tile.x < 0 or tile.x > limit_x]
        for tile in required:
            if not tile.wrap:
                audit.wrap_missing.append({**tile.key, "group": group.id})

    return audit


def _band(point: io.Point) -> str:
    magnitude = max(abs(point.lon), abs(point.lat))
    if magnitude <= DEGREE_MAX:
        return BAND_DEGREE
    if magnitude >= METRE_MIN:
        return BAND_METRE
    return BAND_NEITHER


# ── 五项检查（顺序固定，一项一责）─────────────────────────────────────


def _check_axis_flip(audits: list[GroupAudit]) -> Finding:
    pairs = [pair for audit in audits for pair in audit.axis_flip_pairs]
    evidence: dict[str, Any] = {
        "rule": "data/README.md §4.7",
        "flip_formula": FLIP_FORMULA,
        "pairs": pairs,
    }
    if pairs:
        first = pairs[0]
        return Finding(
            check="axis_flip",
            status="conflict",
            reason=REASON_AXIS_FLIP,
            detail=(
                f"{len(pairs)} 组 y 轴混用（XYZ 与 TMS 同时出现）：首个为 z={first['z']} x={first['x']} "
                f"y={first['y'][0]} ↔ {first['y'][1]}（{FLIP_FORMULA}），"
                f"bbox={first['bbox']}——同一 bbox 被两种 y 轴语义同时声明，静态可判，无需底图"
            ),
            evidence=evidence,
        )
    return Finding(
        check="axis_flip",
        status="consistent",
        detail=f"未发现 y 与 {FLIP_FORMULA} 同时指向同一 bbox 的混用",
        evidence=evidence,
    )


def _check_y_range(audits: list[GroupAudit]) -> Finding:
    offenders = [offender for audit in audits for offender in audit.y_range_offenders]
    evidence: dict[str, Any] = {"rule": "data/README.md §4.7", "offenders": offenders}
    if offenders:
        first = offenders[0]
        return Finding(
            check="y_range",
            status="error",
            reason=REASON_Y_RANGE,
            detail=(
                f"{len(offenders)} 枚瓦片的 y 越界（单点即判）：首个为 z={first['z']} x={first['x']} "
                f"y={first['y']}，该 z 的合法范围是 [{first['allowed'][0]}, {first['allowed'][1]}]"
            ),
            evidence=evidence,
        )
    return Finding(
        check="y_range", status="consistent", detail="全部瓦片的 y 都在 [0, 2^z - 1] 内", evidence=evidence
    )


def _check_zoom_bbox(audits: list[GroupAudit]) -> Finding:
    breaks = [item for audit in audits for item in audit.zoom_breaks]
    evidence: dict[str, Any] = {"rule": "data/README.md §4.7", "breaks": breaks}
    if breaks:
        first = breaks[0]
        parent = first["missing_parent"]
        return Finding(
            check="zoom_bbox",
            status="conflict",
            reason=REASON_ZOOM_BBOX,
            detail=(
                f"{len(breaks)} 处 z+1 覆盖集合不嵌套：z={first['z']} x={first['x']} y={first['y']} 的父瓦片 "
                f"z={parent['z']} x={parent['x']} y={parent['y']} 不在集合里"
            ),
            evidence=evidence,
        )
    return Finding(
        check="zoom_bbox",
        status="consistent",
        detail="z+1 的覆盖集合都嵌套在 z 的集合里（或输入只有单一 zoom）",
        evidence=evidence,
    )


def _check_wrap(audits: list[GroupAudit]) -> Finding:
    missing = [item for audit in audits for item in audit.wrap_missing]
    needed = any(audit.wrap_needed for audit in audits)
    evidence: dict[str, Any] = {
        "rule": "data/README.md §4.7",
        "wrap_required": needed,
        "missing": missing,
    }
    if missing:
        first = missing[0]
        return Finding(
            check="wrap",
            status="conflict",
            reason=REASON_WRAP,
            detail=(
                f"x 环绕未显式声明 wrap：{len(missing)} 枚（首个为 z={first['z']} x={first['x']} "
                f"y={first['y']}）——跨日界线的 x 环绕必须显式记录 wrap: true"
            ),
            evidence=evidence,
        )
    if not needed:
        return Finding(
            check="wrap",
            status="consistent",
            detail="输入未出现跨日界线的 x 环绕",
            evidence=evidence,
        )
    return Finding(
        check="wrap",
        status="consistent",
        detail="跨日界线的 x 环绕已全部显式声明 wrap: true",
        evidence=evidence,
    )


def _check_mixed(kind: str, points: list[io.Point]) -> Finding:
    evidence: dict[str, Any] = {"rule": "data/README.md §4.1", "input_kind": kind}
    if kind != "points":
        return Finding(
            check="mixed_3857_4326",
            status="info",
            detail="输入为 z/x/y 瓦片编号，没有 3857/4326 坐标量级可比（本项不适用）",
            evidence=evidence,
        )
    if not points:
        return Finding(
            check="mixed_3857_4326", status="info", detail="点集为空，量级无从判定", evidence=evidence
        )

    bands = {band: 0 for band in (BAND_DEGREE, BAND_METRE, BAND_NEITHER)}
    first_degree: io.Point | None = None
    first_metre: io.Point | None = None
    for point in points:
        band = _band(point)
        bands[band] += 1
        if band == BAND_DEGREE and first_degree is None:
            first_degree = point
        if band == BAND_METRE and first_metre is None:
            first_metre = point
    evidence["bands"] = bands
    evidence["degree_max"] = DEGREE_MAX
    evidence["metre_min"] = METRE_MIN

    if first_degree is not None and first_metre is not None:
        evidence["samples"] = [
            {"lon": first_degree.lon, "lat": first_degree.lat, "band": BAND_DEGREE},
            {"lon": first_metre.lon, "lat": first_metre.lat, "band": BAND_METRE},
        ]
        return Finding(
            check="mixed_3857_4326",
            status="conflict",
            reason=REASON_MIXED,
            detail=(
                f"同一集合内度域与米域并存：{bands[BAND_DEGREE]} 个度域样本（如 "
                f"[{first_degree.lon}, {first_degree.lat}]）与 {bands[BAND_METRE]} 个米域样本（如 "
                f"[{first_metre.lon}, {first_metre.lat}]）——3857 与 4326 混用"
            ),
            evidence=evidence,
        )
    if bands[BAND_DEGREE]:
        label = "全部在度域（与 4326 相容）"
    elif bands[BAND_METRE]:
        label = "全部在米域（与 3857 相容）"
    else:
        label = "全部落在中间带（180 < m < 1e6，量级无法归档）"
    return Finding(
        check="mixed_3857_4326",
        status="consistent",
        detail=f"量级分档一致：{label}（{bands}）",
        evidence=evidence,
    )


def _verdict(findings: list[Finding], kind: str) -> str:
    hits = [finding.check for finding in findings if finding.status in {"conflict", "error"}]
    if hits:
        return "瓦片/投影片不一致：" + "、".join(hits)
    if kind == "points":
        return "点集量级一致；瓦片轴序项不适用"
    return "瓦片轴序 / 范围 / 嵌套 / 环绕均未命中"


# ── 入口 ────────────────────────────────────────────────────────────────


def run(path: Path) -> ModuleResult:
    """瓦片 / 投影一致性入口。文件缺失 → exit 3；z/x/y 非法 → exit 4（§4.9）。"""
    kind, groups, points = _load(path)
    audits = [_audit_group(group) for group in groups]

    findings = [
        _check_axis_flip(audits),
        _check_y_range(audits),
        _check_zoom_bbox(audits),
        _check_wrap(audits),
        _check_mixed(kind, points),
    ]

    payload: dict[str, Any] = {
        "header": build_header("tiles"),
        "verdict": _verdict(findings, kind),
        "input_kind": kind,
        "input_name": path.name,
        "groups": [
            {
                "id": audit.id,
                "bbox": list(audit.bbox) if audit.bbox is not None else None,
                "tiles": [tile.as_dict() for tile in audit.tiles],
                "axis_flip": [pair for pair in audit.axis_flip_pairs],
                "y_range_offenders": audit.y_range_offenders,
                "zoom_breaks": audit.zoom_breaks,
                "wrap_needed": audit.wrap_needed,
                "wrap_missing": audit.wrap_missing,
            }
            for audit in audits
        ],
        "counts": {
            "groups": len(audits),
            "tiles": sum(len(audit.tiles) for audit in audits),
            "points": len(points),
            "axis_flip_pairs": sum(len(audit.axis_flip_pairs) for audit in audits),
            "y_range_offenders": sum(len(audit.y_range_offenders) for audit in audits),
            "zoom_breaks": sum(len(audit.zoom_breaks) for audit in audits),
            "wrap_missing": sum(len(audit.wrap_missing) for audit in audits),
        },
    }

    return ModuleResult(command="tiles", findings=findings, payload=payload)


def describe() -> list[Finding]:
    return [Finding(check=name, status="info", detail=f"检查项 {name}") for name in CHECKS]

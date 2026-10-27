"""输入读取与归一（GeoJSON / GPX / CSV / `.prj`）→ 统一中间表示。

纪律（`plan/02` §1.1）：本层只做"读进来 + 归一"，**不做判定**。判定顺序在各子命令模块里固定。
缺失态一律抛 `InvalidInput` / `EnvironmentMissing`，**不静默补零、不猜字段**。

**XML 安全（零依赖加固）**：GPX 是不可信输入。标准库 `ElementTree` 会接受内部 DTD 实体，
恶意文件可借此做实体扩展 / 资源耗尽。因此解析前**显式拒绝 `<!DOCTYPE` 与 `<!ENTITY`**，
并对输入体积设上限。引入 `defusedxml` 会破坏"零运行时依赖"承诺，故不用。
"""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .errors import EnvironmentMissing, InvalidInput

#: 单文件体积上限（字节）。GPX 轨迹正常不超过几十 MB；超限即拒，不下注式解析。
MAX_INPUT_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class Point:
    """统一坐标点。`lon`/`lat` 的语义由声明或判定决定，读取层不解释轴序。"""

    lon: float
    lat: float
    seq: int


@dataclass
class PointSet:
    """一次读入的结果。`source_kind` 记录判别依据（按**文件形态**而不是目录名）。"""

    points: list[Point] = field(default_factory=list)
    source_kind: str = "unknown"
    declared_crs: str | None = None
    raw_geometry_types: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.points)


def _fail(path: Path, exc: Exception) -> InvalidInput:
    return InvalidInput(f"{path.name} 无法解析: {exc}", detail="按 data/README.md §4.9 以 exit 4 退出")


def read_text(path: Path) -> str:
    if not path.is_file():
        raise EnvironmentMissing(f"文件不存在: {path.name}", detail="按 §4.9 以 exit 3 退出")
    size = path.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise InvalidInput(
            f"{path.name} 体积 {size} 字节超过上限 {MAX_INPUT_BYTES}",
            detail="超限输入直接拒收，不做流式下注式解析",
        )
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _fail(path, exc) from exc


def _reject_xml_danger(text: str, path: Path) -> None:
    """拒绝 DTD / 实体声明（XXE 与 billion-laughs 的入口）。大小写与空白都被归一后再判。"""
    probe = text[:MAX_INPUT_BYTES].lower()
    for token in ("<!doctype", "<!entity"):
        if token in probe:
            raise InvalidInput(
                f"{path.name}: 含 XML {token.upper()} 声明，已拒绝解析",
                detail="GPX 不允许 DTD/实体声明（防实体扩展与外部实体引用）",
            )


def detect_kind(path: Path) -> str:
    """按**文件形态**判别归属，不看目录名（`plan/02` §1.1）。

    形态优先于内容嗅探：`{"type": ...}` → GeoJSON，`<gpx` → GPX，`.csv` / `.tsv` → 点表，
    `.prj` → 声明文件。**其余一律 `unknown`**（→ 退出码 3 并列出支持面），
    不把任意文本当 CSV 猜着解析——那会把"格式不支持"报成"表头缺 lon"。
    """
    text = read_text(path)
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return "json"
        if isinstance(data, dict) and data.get("type") in {
            "FeatureCollection",
            "Feature",
            "Point",
            "MultiPoint",
            "LineString",
            "MultiLineString",
            "Polygon",
            "MultiPolygon",
            "GeometryCollection",
        }:
            return "geojson"
        if isinstance(data, dict) and {"version", "resolution_deg", "cells"} <= set(data):
            return "mask"
        return "json"
    if stripped.startswith("<"):
        _reject_xml_danger(stripped, path)
        return "gpx" if "<gpx" in stripped[:4096].lower() else "xml"
    suffix = path.suffix.lower()
    if suffix == ".prj":
        return "prj"
    if suffix in {".csv", ".tsv"}:
        return "csv"
    return "unknown"


def _coord_pair(node: object, path: Path) -> tuple[float, float]:
    if not isinstance(node, (list, tuple)) or len(node) < 2:
        raise InvalidInput(f"{path.name}: 坐标对形态非法: {node!r}")
    try:
        return float(node[0]), float(node[1])  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise _fail(path, exc) from exc


def _walk_geometry(geom: object, out: list[tuple[float, float]], path: Path, depth: int = 0) -> None:
    """递归收集坐标。`null` 几何合法（RFC 7946 §3.2），直接跳过。"""
    if geom is None:
        return
    if not isinstance(geom, dict):
        raise InvalidInput(f"{path.name}: 几何对象应为 JSON object 或 null")
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "GeometryCollection":
        if depth > 8:
            raise InvalidInput(f"{path.name}: 几何嵌套过深（>8），疑似结构异常")
        for child in geom.get("geometries") or []:
            _walk_geometry(child, out, path, depth + 1)
        return

    def rec(node: object, d: int) -> None:
        if d == 0:
            out.append(_coord_pair(node, path))
            return
        if not isinstance(node, (list, tuple)):
            raise InvalidInput(f"{path.name}: 坐标数组形态非法")
        for child in node:
            rec(child, d - 1)

    dims = {
        "Point": 0,
        "MultiPoint": 1,
        "LineString": 1,
        "MultiLineString": 2,
        "Polygon": 2,
        "MultiPolygon": 3,
    }
    if gtype not in dims:
        raise InvalidInput(f"{path.name}: 未知几何类型 {gtype!r}")
    if coords is None:
        raise InvalidInput(f"{path.name}: {gtype} 缺少 coordinates")
    rec(coords, dims[gtype])


def read_geojson(path: Path) -> PointSet:
    text = read_text(path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _fail(path, exc) from exc
    result = PointSet(source_kind="geojson")
    if isinstance(data, dict) and "crs" in data:
        crs = data.get("crs")
        name = None
        if isinstance(crs, dict):
            props = crs.get("properties") or {}
            name = props.get("name") if isinstance(props, dict) else None
        result.declared_crs = str(name) if name is not None else "declared"

    raw: list[tuple[float, float]] = []
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                raise InvalidInput(f"{path.name}: features 元素应为 object")
            geom = feat.get("geometry")
            if isinstance(geom, dict):
                result.raw_geometry_types.append(str(geom.get("type")))
            _walk_geometry(geom, raw, path)
    elif isinstance(data, dict) and data.get("type") == "Feature":
        geom = data.get("geometry")
        if isinstance(geom, dict):
            result.raw_geometry_types.append(str(geom.get("type")))
        _walk_geometry(geom, raw, path)
    elif isinstance(data, dict):
        result.raw_geometry_types.append(str(data.get("type")))
        _walk_geometry(data, raw, path)
    else:
        raise InvalidInput(f"{path.name}: 顶层应为 GeoJSON object")

    result.points = [Point(lon=a, lat=b, seq=i) for i, (a, b) in enumerate(raw)]
    return result


def read_gpx(path: Path) -> PointSet:
    text = read_text(path)
    _reject_xml_danger(text, path)
    try:
        # 已排除 DTD/实体；禁用外部实体解析是 ElementTree 的默认行为（不解析外部实体）。
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise _fail(path, exc) from exc
    result = PointSet(source_kind="gpx")
    pts: list[Point] = []
    if root.tag.split("}")[-1] != "gpx":
        raise InvalidInput(f"{path.name}: 根元素不是 <gpx>")
    for elem in root.iter():
        if elem.tag.split("}")[-1] not in {"trkpt", "wpt", "rtept"}:
            continue
        try:
            lon = float(elem.attrib["lon"])
            lat = float(elem.attrib["lat"])
        except (KeyError, ValueError) as exc:
            raise _fail(path, exc) from exc
        pts.append(Point(lon=lon, lat=lat, seq=len(pts)))
    result.points = pts
    return result


def read_csv_points(path: Path) -> PointSet:
    text = read_text(path)
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        raise InvalidInput(f"{path.name}: CSV 为空")
    header = [c.strip().lower() for c in rows[0]]
    try:
        i_lon = header.index("lon")
        i_lat = header.index("lat")
    except ValueError as exc:
        raise InvalidInput(
            f"{path.name}: CSV 表头需含 lon 与 lat（实得 {header}）",
            detail="列名不符是硬错，不做模糊匹配",
        ) from exc
    pts: list[Point] = []
    body = rows[1:]
    while body and not any(c.strip() for c in body[-1]):
        body.pop()
    for i, row in enumerate(body, start=1):
        if not row or all(not c.strip() for c in row):
            continue
        try:
            pts.append(Point(lon=float(row[i_lon]), lat=float(row[i_lat]), seq=i))
        except (IndexError, ValueError) as exc:
            raise _fail(path, exc) from exc
    return PointSet(points=pts, source_kind="csv")


def read_points(path: Path) -> PointSet:
    """按形态分派读取器。未知形态 → exit 3（列支持面），不做内容嗅探兜底。"""
    kind = detect_kind(path)
    if kind == "geojson":
        return read_geojson(path)
    if kind == "gpx":
        return read_gpx(path)
    if kind == "prj":
        text = read_text(path).strip()
        return PointSet(points=[], source_kind="prj", declared_crs=text)
    if kind == "csv":
        return read_csv_points(path)
    raise EnvironmentMissing(
        f"不支持的文件形态: {kind}（{path.name}）",
        detail="支持：GeoJSON / GPX / CSV(lon,lat) / .prj",
    )

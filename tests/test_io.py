"""输入层守门：按形态分派、缺失态不兜底、XML 安全（`plan/02` §1.1 / `io.py` 文档串）。

`io.py` 的 XML 加固是安全项：GPX 是不可信输入，标准库 ElementTree 会接受内部 DTD 实体。
本文件把"拒绝 DOCTYPE / ENTITY"落成可跑红的断言——没有它，加固代码只是注释。
"""

from __future__ import annotations

import json

import pytest

from crsscope import io as crsio
from crsscope.errors import EnvironmentMissing, InvalidInput


def test_missing_file_is_environment_error(tmp_path) -> None:
    with pytest.raises(EnvironmentMissing) as exc:
        crsio.read_points(tmp_path / "nope.geojson")
    assert exc.value.code == 3


def test_geojson_pointset_is_read_in_file_order(write_file) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [112.0, 5.0]}},
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [112.5, 5.5]}},
        ],
    }
    path = write_file("a.geojson", json.dumps(payload))
    pts = crsio.read_points(path)
    assert pts.source_kind == "geojson"
    assert [(p.lon, p.lat) for p in pts.points] == [(112.0, 5.0), (112.5, 5.5)]


def test_null_geometry_is_legal_and_skipped(write_file) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": None, "geometry": None}],
    }
    path = write_file("null.geojson", json.dumps(payload))
    pts = crsio.read_points(path)
    assert pts.points == [], "null geometry 合法（RFC 7946 §3.2），不得报错"


def test_crs_member_is_surfaced(write_file) -> None:
    payload = {"type": "Feature", "crs": {"properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}, "geometry": None}
    path = write_file("crs.geojson", json.dumps(payload))
    assert crsio.read_points(path).declared_crs == "urn:ogc:def:crs:OGC:1.3:CRS84"


def test_non_numeric_coordinate_is_invalid_input(write_file) -> None:
    payload = {"type": "Point", "coordinates": ["a", "b"]}
    path = write_file("bad.geojson", json.dumps(payload))
    with pytest.raises(InvalidInput) as exc:
        crsio.read_points(path)
    assert exc.value.code == 4


def test_csv_requires_lon_lat_header(write_file) -> None:
    path = write_file("p.csv", "x,y\n1,2\n")
    with pytest.raises(InvalidInput) as exc:
        crsio.read_points(path)
    assert exc.value.code == 4
    assert "lon" in exc.value.message


def test_csv_reads_points(write_file) -> None:
    path = write_file("ok.csv", "lon,lat\n112.0,5.0\n112.5,5.5\n")
    pts = crsio.read_points(path)
    assert len(pts.points) == 2


def test_gpx_reads_trackpoints(write_file) -> None:
    text = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="t"><trk><trkseg>'
        '<trkpt lat="5.0" lon="112.0"></trkpt>'
        '<trkpt lat="5.5" lon="112.5"></trkpt>'
        "</trkseg></trk></gpx>"
    )
    path = write_file("t.gpx", text)
    pts = crsio.read_points(path)
    assert [(p.lon, p.lat) for p in pts.points] == [(112.0, 5.0), (112.5, 5.5)]


@pytest.mark.parametrize(
    "payload",
    [
        '<!DOCTYPE gpx [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><gpx>&xxe;</gpx>',
        '<!doctype gpx><gpx></gpx>',
        '<!ENTITY lol "x"><gpx></gpx>',
    ],
)
def test_xml_with_dtd_or_entity_is_rejected(write_file, payload: str) -> None:
    path = write_file("evil.gpx", payload)
    with pytest.raises(InvalidInput) as exc:
        crsio.read_points(path)
    # 报错文案里两个 token 都是大写形式（`<!DOCTYPE` / `<!ENTITY`）——否则区分不了是哪一个触发的
    assert "<!DOCTYPE" in exc.value.message or "<!ENTITY" in exc.value.message


def test_xml_guard_detector_sees_planted_token() -> None:
    """守门自证：加固函数必须真的能抓到 token（否则拒绝分支从没跑过）。"""
    from pathlib import Path

    with pytest.raises(InvalidInput):
        crsio._reject_xml_danger('<!DOCTYPE x><gpx/>', Path("x.gpx"))
    crsio._reject_xml_danger("<gpx/>", Path("x.gpx"))  # 干净输入必须放行


def test_unsupported_shape_is_environment_error(write_file) -> None:
    path = write_file("notes.txt", "just some text\n")
    with pytest.raises(EnvironmentMissing) as exc:
        crsio.read_points(path)
    assert exc.value.code == 3

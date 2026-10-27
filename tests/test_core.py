"""共享层契约：距离口径、算法常数、掩膜分母规则（`plan/03` §一–§五）。

这三块是"一处定义"的地方，测试要钉住**唯一性**与**边界语义**，而不只是"函数能跑"。
"""

from __future__ import annotations

import math

import pytest

from crsscope import algorithms, geodesy, mask


# ── geodesy ────────────────────────────────────────────────────────────
def test_haversine_zero_for_same_point() -> None:
    assert geodesy.haversine_m(112.0, 5.0, 112.0, 5.0) == 0.0


def test_haversine_one_degree_latitude_is_about_111km() -> None:
    d = geodesy.haversine_m(112.0, 5.0, 112.0, 6.0)
    assert 110_000 < d < 112_500, d


def test_haversine_is_symmetric_and_crosses_antimeridian() -> None:
    a = geodesy.haversine_m(179.9, 0.0, -179.9, 0.0)
    b = geodesy.haversine_m(-179.9, 0.0, 179.9, 0.0)
    assert a == pytest.approx(b)
    assert a < 25_000, "跨日界线必须走近路，不能绕地球"


def test_normalize_lon_wraps() -> None:
    assert geodesy.normalize_lon(190.0) == pytest.approx(-170.0)
    assert geodesy.normalize_lon(-190.0) == pytest.approx(170.0)


# ── algorithms: 两套边界框不许被合并 ───────────────────────────────────
def test_ct_py_uses_open_interval() -> None:
    lo, _hi = algorithms.CT_PY_BBOX["lon"]
    assert not algorithms.in_china(lo, 39.5, algorithms.PROFILE_CT_PY), "开区间端点不算境内"


def test_gcoord_uses_closed_interval() -> None:
    lo, _hi = algorithms.GCOORD_BBOX["lon"]
    assert algorithms.in_china(lo, 39.5, algorithms.PROFILE_GCOORD), "闭区间端点算境内"


def test_xinjiang_73_2_diverges() -> None:
    """题面 M3 验收点：73.2°E 对两库结论不同。"""
    ct = algorithms.in_china(73.2, 39.5, algorithms.PROFILE_CT_PY)
    gc = algorithms.in_china(73.2, 39.5, algorithms.PROFILE_GCOORD)
    assert ct is False and gc is True


@pytest.mark.parametrize(
    ("lon", "lat", "ct", "gc"),
    [
        (112.0, 2.0, False, True),  # 纬向分歧：< 3.86°N
        (112.0, 5.0, True, True),  # 两库一致（都境内）
        (112.0, 60.0, False, False),  # 两库一致（都境外）
    ],
)
def test_boundary_cases_match_data_ledger(lon, lat, ct, gc) -> None:
    assert algorithms.in_china(lon, lat, algorithms.PROFILE_CT_PY) is ct
    assert algorithms.in_china(lon, lat, algorithms.PROFILE_GCOORD) is gc


def test_krasovsky_constants_are_verbatim() -> None:
    assert algorithms.KRASOVSKY_A == 6378245.0
    assert algorithms.KRASOVSKY_EE == 0.006693421622965823
    assert algorithms.INVERSE_TOLERANCE_DEG == 1e-6


def test_forward_then_inverse_round_trips_within_tolerance() -> None:
    lon, lat = 116.397, 39.909
    g_lon, g_lat = algorithms.wgs84_to_gcj02(lon, lat)
    assert (g_lon, g_lat) != (lon, lat), "北京必须发生偏移"
    inv = algorithms.gcj02_to_wgs84_iterative(g_lon, g_lat)
    assert inv.converged
    assert abs(inv.lon - lon) < 1e-5 and abs(inv.lat - lat) < 1e-5


def test_linear_inverse_is_less_accurate_than_iterative() -> None:
    """两种逆向必须可区分——否则 xdiff 的两两差分就没有信息量。"""
    lon, lat = 116.397, 39.909
    g_lon, g_lat = algorithms.wgs84_to_gcj02(lon, lat)
    lin = algorithms.gcj02_to_wgs84_linear(g_lon, g_lat)
    itr = algorithms.gcj02_to_wgs84_iterative(g_lon, g_lat)
    d_lin = geodesy.haversine_m(lin.lon, lin.lat, lon, lat)
    d_itr = geodesy.haversine_m(itr.lon, itr.lat, lon, lat)
    assert d_lin > d_itr, f"线性近似应比迭代更差：lin={d_lin:.3f} itr={d_itr:.3f}"


def test_out_of_china_point_is_not_shifted() -> None:
    lon, lat = 2.0, 48.0  # 巴黎
    assert algorithms.wgs84_to_gcj02(lon, lat) == (lon, lat)


def test_not_converged_is_reported_not_swallowed() -> None:
    """超迭代上限必须返回 `converged=False`——不许静默给一个"看起来对"的值。"""
    original = algorithms.INVERSE_MAX_ITER
    algorithms.INVERSE_MAX_ITER = 0
    try:
        result = algorithms.gcj02_to_wgs84_iterative(116.4, 39.9)
    finally:
        algorithms.INVERSE_MAX_ITER = original
    assert result.converged is False


def test_webmercator_round_trip() -> None:
    x, y = algorithms.wgs84_to_webmercator(112.0, 5.0)
    assert abs(x) > 1e6 and abs(y) > 1e5, "3857 是米域"
    back = algorithms.webmercator_to_wgs84(x, y)
    assert back[0] == pytest.approx(112.0, abs=1e-9)
    assert back[1] == pytest.approx(5.0, abs=1e-9)


def test_webmercator_latitude_clamped() -> None:
    _x, y = algorithms.wgs84_to_webmercator(0.0, 89.0)
    assert math.isfinite(y)


# ── mask: 分母规则 ─────────────────────────────────────────────────────
def _tiny_mask(**overrides) -> mask.Mask:
    kwargs = dict(
        version="test",
        resolution_deg=1.0,
        lon_min=0.0,
        lat_min=0.0,
        n_lon=5,
        n_lat=1,
        # 同格之间留空档（未设置的格按 unknown 处理），避免无意造出海岸带——
        # coastal 会从分母里扣掉，把"unknown 不计分母"这条断言污染成别的结论。
        cells={(0, 0): "land", (0, 2): "water", (0, 4): "unknown"},
    )
    kwargs.update(overrides)
    return mask.Mask(**kwargs)


def test_mask_rejects_resolution_above_cap() -> None:
    with pytest.raises(mask.EnvironmentMissing):
        _tiny_mask(resolution_deg=2.0)


def test_unknown_cell_not_counted_in_denominator() -> None:
    m = _tiny_mask()
    stats = mask.MaskStats()
    for lon in (0.5, 2.5, 4.5):
        stats.add(m, lon, 0.5)
    assert stats.unknown == 1
    assert stats.coastal == 0
    assert stats.evaluable == 2, "unknown 不得进落水分母"
    assert stats.water_ratio == pytest.approx(0.5)


def test_coastal_cell_not_counted_in_denominator() -> None:
    m = _tiny_mask(cells={(0, 0): "land", (0, 1): "water", (0, 4): "land"})
    stats = mask.MaskStats()
    for lon in (0.5, 1.5, 4.5):
        stats.add(m, lon, 0.5)
    assert stats.coastal == 2, "与异类相邻的两格算海岸带"
    assert stats.evaluable == 1


def test_water_ratio_is_none_when_nothing_evaluable() -> None:
    """无可判定点必须返回 None（→ undecidable），绝不能用 0.0 冒充"全陆上"。"""
    m = _tiny_mask(cells={(0, 0): "unknown"})
    stats = mask.MaskStats()
    stats.add(m, 0.5, 0.5)
    assert stats.water_ratio is None


def test_mask_header_fields_present() -> None:
    m = _tiny_mask()
    stats = mask.MaskStats()
    for lon in (0.5, 1.5, 2.5):
        stats.add(m, lon, 0.5)
    header = stats.as_header(m)
    for key in ("mask_version", "mask_max_resolution_deg", "unknown_ratio", "coastal_ratio", "evaluable_points"):
        assert key in header

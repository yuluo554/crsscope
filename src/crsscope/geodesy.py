"""角度 / 距离换算的**唯一实现处**（`data/README.md` §4.4）。

其他模块一律调用本文件，不得自己写 haversine——否则度与米混算会静默产生错误量级。
"""

from __future__ import annotations

import math

#: 地球平均半径（米），`data/README.md` §4.4。
EARTH_RADIUS_M = 6371008.8


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """球面大圆距离（米）。输入为十进制度。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def normalize_lon(lon: float) -> float:
    """归一到 [-180, 180)。跨日界线的几何/包围框计算要用它，而不是直接比较大小。"""
    return (lon + 180.0) % 360.0 - 180.0


def lon_delta(a: float, b: float) -> float:
    """两个经度之间的最短角差，落在 [-180, 180]。"""
    return normalize_lon(a - b)


def approx_meters_per_degree_lat(lat: float) -> float:
    """纬度 1° 的近似弧长（米），仅用于"像素/瓦片量级"这类粗判，不得用于残差输出。"""
    return math.pi * EARTH_RADIUS_M / 180.0


def approx_meters_per_degree_lon(lat: float) -> float:
    """经度 1° 的近似弧长（米，随纬度收缩）。"""
    return math.pi * EARTH_RADIUS_M * math.cos(math.radians(lat)) / 180.0

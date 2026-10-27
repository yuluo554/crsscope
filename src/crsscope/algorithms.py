"""GCJ-02 / BD-09 / WebMercator 常数与算法的**唯一落点**（`data/README.md` §1.3）。

纪律（题面 §三 M3、§七 算法纪律）：

- 常数**原样照录**并注明来源；两套 `out_of_china` 边界各留一份，**不合并、不取并集**——
  它们不同这件事本身就是本工具的审计发现点（`data/README.md` §1.3 对照表）。
- **不复制任何未公开实现**，不声称逆向出官方算法。本文件里的前向/逆向都是民间公开公式，
  因此结论只能表述为"在某实现假设下的残差"（§4.5 三段残差）。
- 前向变换**只服务 fixture 生成器**，不作为产品能力对外（题面 §七：不提供 `convert`）。

来源标注：`a`、`ee`、两套边界框与迭代容差全部来自 `data/README.md` §1.3 的实测台账。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ── 常数（照录，来源：data/README.md §1.3）───────────────────────────────
KRASOVSKY_A = 6378245.0
KRASOVSKY_EE = 0.006693421622965823
X_PI = math.pi * 3000.0 / 180.0
WEBMERCATOR_MAX = 20037508.342789244  # EPSG:3857 半周长（米）
INVERSE_TOLERANCE_DEG = 1e-6  # gcoord 定点迭代容差（≈0.1 m）
INVERSE_MAX_ITER = 100

# ── 两套边界框（**不合并**：差异是审计发现点）───────────────────────────
#: wandergis/coordTransform_py 的 `out_of_china`：开区间。
CT_PY_BBOX = {"lon": (73.66, 135.05), "lat": (3.86, 53.55), "closed": False}
#: hujiulong/gcoord 的 `isInChinaBbox`：闭区间。
GCOORD_BBOX = {"lon": (72.004, 137.8347), "lat": (0.8293, 55.8271), "closed": True}

PROFILE_CT_PY = "coordTransform_py"
PROFILE_GCOORD = "gcoord"


def in_bbox(lon: float, lat: float, bbox: dict) -> bool:
    """按给定边界框判定；`closed` 决定端点是否算"境内"。

    端点差异对本项目是**实质差异**而不是浮点噪声：`coordTransform_py` 用开区间，
    所以恰好落在 73.66°E 的点被判"境外"。本函数据此不把两套边界"统一"成同一形态。
    """
    (lon_lo, lon_hi), (lat_lo, lat_hi) = bbox["lon"], bbox["lat"]
    if bbox["closed"]:
        return lon_lo <= lon <= lon_hi and lat_lo <= lat <= lat_hi
    return lon_lo < lon < lon_hi and lat_lo < lat < lat_hi


def in_china(lon: float, lat: float, profile: str = PROFILE_GCOORD) -> bool:
    """按指定实现的口径判定"是否在中国境内（需要偏移）"。"""
    if profile == PROFILE_CT_PY:
        return in_bbox(lon, lat, CT_PY_BBOX)
    if profile == PROFILE_GCOORD:
        return in_bbox(lon, lat, GCOORD_BBOX)
    raise ValueError(f"未知边界画像: {profile}")


def distance_to_bbox_deg(lon: float, lat: float, bbox: dict) -> float:
    """到边界框的近似角距（度）；在框内时返回 0，框外返回最近边的距离。

    用途只有一处：`detect` 的 `boundary_jump` 边界带标记（§4.2 的 0.05° 阈值）。
    这是"角度空间"的距离，**不是**米——需要米时由调用方经 `geodesy` 换算。
    """
    (lon_lo, lon_hi), (lat_lo, lat_hi) = bbox["lon"], bbox["lat"]
    dlon = max(lon_lo - lon, 0.0, lon - lon_hi)
    dlat = max(lat_lo - lat, 0.0, lat - lat_hi)
    return math.hypot(dlon, dlat)


# ── GCJ-02 前向（公开公式，服务 fixture 生成与对照实现）─────────────────
def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def _delta(lon: float, lat: float) -> tuple[float, float]:
    """返回 (dlon, dlat)，单位度。"""
    dlat_rad = _transform_lat(lon - 105.0, lat - 35.0)
    dlon_rad = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = math.radians(lat)
    magic = 1.0 - KRASOVSKY_EE * math.sin(radlat) ** 2
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat_rad * 180.0) / ((KRASOVSKY_A * (1.0 - KRASOVSKY_EE)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon_rad * 180.0) / (KRASOVSKY_A / sqrtmagic * math.cos(radlat) * math.pi)
    return dlon, dlat


def wgs84_to_gcj02(lon: float, lat: float, profile: str = PROFILE_GCOORD) -> tuple[float, float]:
    """WGS84 → GCJ-02。境外按 `profile` 的边界框原样返回（不偏移）。"""
    if not in_china(lon, lat, profile):
        return lon, lat
    dlon, dlat = _delta(lon, lat)
    return lon + dlon, lat + dlat


@dataclass(frozen=True)
class InverseResult:
    """逆向结果。`converged=False` 时调用方**必须**把 `not_converged` 报出来（不得静默返回）。"""

    lon: float
    lat: float
    converged: bool
    iterations: int


def gcj02_to_wgs84_iterative(
    lon: float, lat: float, profile: str = PROFILE_GCOORD
) -> InverseResult:
    """gcoord 口径：定点迭代，容差 `1e-6°`（`data/README.md` §1.3 / §4.4）。

    超迭代上限即返回 `converged=False`——**不抛异常、也不静默给一个"看起来对"的值**，
    因为"没收敛"是结论的一部分（题面 §M3 纪律）。
    """
    if not in_china(lon, lat, profile):
        return InverseResult(lon, lat, True, 0)
    cur_lon, cur_lat = lon, lat
    for i in range(1, INVERSE_MAX_ITER + 1):
        fwd_lon, fwd_lat = wgs84_to_gcj02(cur_lon, cur_lat, profile)
        dx, dy = fwd_lon - lon, fwd_lat - lat
        cur_lon -= dx
        cur_lat -= dy
        if abs(dx) <= INVERSE_TOLERANCE_DEG and abs(dy) <= INVERSE_TOLERANCE_DEG:
            return InverseResult(cur_lon, cur_lat, True, i)
    return InverseResult(cur_lon, cur_lat, False, INVERSE_MAX_ITER)


def gcj02_to_wgs84_linear(lon: float, lat: float, profile: str = PROFILE_CT_PY) -> InverseResult:
    """coordTransform_py 口径：**一步线性近似** `[lng*2 - mglng, lat*2 - mglat]`。

    这是近似，不是迭代收敛——所以残差比迭代法大，"收敛"在这里恒为 True 但**不代表精确**。
    该差异必须在 `xdiff` 的 `pairwise` 里如实体现（两实现两两差分）。
    """
    if not in_china(lon, lat, profile):
        return InverseResult(lon, lat, True, 0)
    mg_lon, mg_lat = wgs84_to_gcj02(lon, lat, profile)
    return InverseResult(lon * 2.0 - mg_lon, lat * 2.0 - mg_lat, True, 1)


# ── BD-09 ──────────────────────────────────────────────────────────────
def gcj02_to_bd09(lon: float, lat: float) -> tuple[float, float]:
    z = math.sqrt(lon * lon + lat * lat) + 0.00002 * math.sin(lat * X_PI)
    theta = math.atan2(lat, lon) + 0.000003 * math.cos(lon * X_PI)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def bd09_to_gcj02(lon: float, lat: float) -> tuple[float, float]:
    x, y = lon - 0.0065, lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    return z * math.cos(theta), z * math.sin(theta)


def wgs84_to_bd09(lon: float, lat: float, profile: str = PROFILE_GCOORD) -> tuple[float, float]:
    g_lon, g_lat = wgs84_to_gcj02(lon, lat, profile)
    return gcj02_to_bd09(g_lon, g_lat)


def bd09_to_wgs84(lon: float, lat: float, profile: str = PROFILE_GCOORD) -> InverseResult:
    g_lon, g_lat = bd09_to_gcj02(lon, lat)
    return gcj02_to_wgs84_iterative(g_lon, g_lat, profile)


# ── WebMercator (EPSG:3857) ─────────────────────────────────────────────
def wgs84_to_webmercator(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 → EPSG:3857（米）。纬度在 ±85.05112878° 处截止。"""
    lat = max(min(lat, 85.05112878), -85.05112878)
    x = lon * WEBMERCATOR_MAX / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) * WEBMERCATOR_MAX / math.pi
    return x, y


def webmercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
    lon = x / WEBMERCATOR_MAX * 180.0
    lat = 180.0 / math.pi * (2.0 * math.atan(math.exp(y * math.pi / WEBMERCATOR_MAX)) - math.pi / 2.0)
    return lon, lat


# ── 假设枚举（detect 的候选，固定三值）────────────────────────────────
HYPOTHESES = ("WGS84", "GCJ02", "BD09")


def inverse_for(hypothesis: str, lon: float, lat: float, profile: str = PROFILE_GCOORD) -> InverseResult:
    """给定假设 `h`，求"若输入是 h 则真实 WGS84 坐标"（`data/README.md` §4.2 第 1 步）。"""
    if hypothesis == "WGS84":
        return InverseResult(lon, lat, True, 0)
    if hypothesis == "GCJ02":
        return gcj02_to_wgs84_iterative(lon, lat, profile)
    if hypothesis == "BD09":
        return bd09_to_wgs84(lon, lat, profile)
    raise ValueError(f"未知假设: {hypothesis}")

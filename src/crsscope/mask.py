"""离线陆水掩膜（`data/README.md` §2.1 / §4.3）。

**三条硬纪律**：

1. 首期分辨率上限 **1°**；超出即拒绝加载（exit 3），**不得静默降采样**。
2. 掩膜是**构造**的低分辨率网格，**不是地理真值**——报告必须同时输出 `mask_version` 与
   `mask_max_resolution_deg`，并声明这一点。
3. `unknown` 与海岸带（`coastal`）**不计入落水分母**：避免"掩膜看不见的湖"被当作"陆上正确"。

运行期**不下载**任何数据；需要地理准确性时由用户 `--mask <file>` 提供自己的网格。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import EnvironmentMissing, InvalidInput

#: 首期分辨率上限（度），`data/README.md` §4.3。
MAX_RESOLUTION_DEG = 1.0

LAND = "land"
WATER = "water"
UNKNOWN = "unknown"

#: 与异类相邻的格在评分时单独计数，不进分母。
COASTAL = "coastal"


@dataclass(frozen=True)
class Mask:
    """构造网格。`cells` 以 `(lat_idx, lon_idx)` 为键，值为 `land` / `water` / `unknown`。"""

    version: str
    resolution_deg: float
    lon_min: float
    lat_min: float
    n_lon: int
    n_lat: int
    cells: dict[tuple[int, int], str]

    def __post_init__(self) -> None:
        if self.resolution_deg > MAX_RESOLUTION_DEG + 1e-12:
            raise EnvironmentMissing(
                f"掩膜步长 {self.resolution_deg}° 超过首期上限 {MAX_RESOLUTION_DEG}°",
                detail="按 data/README.md §4.3 拒绝加载；不得静默降采样",
            )

    @property
    def max_resolution_deg(self) -> float:
        return self.resolution_deg

    def index_of(self, lon: float, lat: float) -> tuple[int, int] | None:
        i_lon = int((lon - self.lon_min) // self.resolution_deg)
        i_lat = int((lat - self.lat_min) // self.resolution_deg)
        if not (0 <= i_lon < self.n_lon and 0 <= i_lat < self.n_lat):
            return None
        return i_lat, i_lon

    def cell_at(self, lon: float, lat: float) -> str:
        idx = self.index_of(lon, lat)
        if idx is None:
            return UNKNOWN
        return self.cells.get(idx, UNKNOWN)

    def is_coastal(self, lon: float, lat: float) -> bool:
        """四邻中存在异类（land vs water）即算海岸带；`unknown` 邻格不算证据。"""
        idx = self.index_of(lon, lat)
        if idx is None:
            return False
        here = self.cells.get(idx, UNKNOWN)
        if here not in (LAND, WATER):
            return False
        i_lat, i_lon = idx
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = self.cells.get((i_lat + di, i_lon + dj), UNKNOWN)
            if neighbor in (LAND, WATER) and neighbor != here:
                return True
        return False


def load_mask(path: Path) -> Mask:
    """从 JSON 读取掩膜。任何形态问题都落 `EnvironmentMissing` / `InvalidInput`，不兜底造数据。"""
    if not path.is_file():
        raise EnvironmentMissing(f"掩膜不存在: {path.name}", detail="用 data/mask/gen.py 生成，或 --mask 指定")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidInput(f"掩膜不可解析: {exc}") from exc
    try:
        cells = {
            (int(c["lat_idx"]), int(c["lon_idx"])): str(c["value"]) for c in raw["cells"]
        }
        mask = Mask(
            version=str(raw["version"]),
            resolution_deg=float(raw["resolution_deg"]),
            lon_min=float(raw["lon_min"]),
            lat_min=float(raw["lat_min"]),
            n_lon=int(raw["n_lon"]),
            n_lat=int(raw["n_lat"]),
            cells=cells,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidInput(f"掩膜字段缺失或类型错误: {exc}") from exc
    bad = {v for v in mask.cells.values()} - {LAND, WATER, UNKNOWN}
    if bad:
        raise InvalidInput(f"掩膜含未知取值: {sorted(bad)}")
    return mask


class MaskStats:
    """落水评分的累计器。分母规则**只在这里实现一次**（§4.2 / §4.3）。"""

    def __init__(self) -> None:
        self.water = 0
        self.land = 0
        self.unknown = 0
        self.coastal = 0

    def add(self, mask: Mask, lon: float, lat: float) -> None:
        value = mask.cell_at(lon, lat)
        if value == UNKNOWN:
            self.unknown += 1
            return
        if mask.is_coastal(lon, lat):
            self.coastal += 1
            return
        if value == WATER:
            self.water += 1
        else:
            self.land += 1

    @property
    def evaluable(self) -> int:
        return self.water + self.land

    @property
    def water_ratio(self) -> float | None:
        """无可判定点时返回 `None`（→ 调用方必须落 `undecidable`，不许拿 0.0 冒充"全陆上"）。"""
        if self.evaluable == 0:
            return None
        return self.water / self.evaluable

    def as_header(self, mask: Mask) -> dict:
        total = self.water + self.land + self.unknown + self.coastal
        return {
            "mask_version": mask.version,
            "mask_max_resolution_deg": mask.max_resolution_deg,
            "unknown_ratio": round(self.unknown / total, 6) if total else 0.0,
            "coastal_ratio": round(self.coastal / total, 6) if total else 0.0,
            "evaluable_points": self.evaluable,
        }

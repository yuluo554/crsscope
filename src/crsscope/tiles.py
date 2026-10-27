"""模块 M5 · 瓦片 / 投影一致性（`plan/03` §五）。

**不做地图渲染、不产出图片、不做切片**；输出只有布尔 / 数值判定与证据（题面 §M5）。
"""

from __future__ import annotations

from pathlib import Path

from .errors import UnimplementedFeature
from .report import Finding, ModuleResult

CHECKS: tuple[str, ...] = ("axis_flip", "y_range", "zoom_bbox", "wrap", "mixed_3857_4326")

MILESTONE = "M5"


def run(path: Path) -> ModuleResult:
    raise UnimplementedFeature(
        f"tiles 判定尚未实现（计划里程碑 {MILESTONE}）",
        detail="y 轴翻转须静态检出（无需底图）；口径见 data/README.md §4.7",
    )


def describe() -> list[Finding]:
    return [Finding(check=name, status="info", detail=f"检查项 {name}") for name in CHECKS]

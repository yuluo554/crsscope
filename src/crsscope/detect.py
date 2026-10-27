"""模块 M2 · GCJ-02 / BD-09 偏移检测与残差（`plan/03` §二）。

判定顺序固定：逆变换 → 覆盖检查 → 三路评分 → 排序与置信 → 残差三段 → 边界画像。
"""

from __future__ import annotations

from pathlib import Path

from . import algorithms
from .errors import UnimplementedFeature
from .report import Finding, ModuleResult

#: 候选假设固定三值（`data/README.md` §4.2）。不增不减。
HYPOTHESES = algorithms.HYPOTHESES

#: 残差三段固定枚举（`data/README.md` §4.5）。**必须齐全**，不是"至少一条"。
RESIDUAL_KINDS = ("formula_approximation", "vendor_divergence", "boundary_jump")

#: 边界画像双份（两库边界不同是审计发现点，必须分别输出）。
BOUNDARY_PROFILES = (algorithms.PROFILE_CT_PY, algorithms.PROFILE_GCOORD)

MILESTONE = "M3"


def run(path: Path, declared_crs: str | None, mask_path: Path | None = None) -> ModuleResult:
    raise UnimplementedFeature(
        f"detect 判定尚未实现（计划里程碑 {MILESTONE}）",
        detail="评分公式见 data/README.md §4.2；掩膜与残差契约见 plan/03 §二",
    )


def describe() -> list[Finding]:
    return [
        Finding(check="hypotheses", status="info", detail=",".join(HYPOTHESES)),
        Finding(check="residual_kinds", status="info", detail=",".join(RESIDUAL_KINDS)),
        Finding(check="boundary_profiles", status="info", detail=",".join(BOUNDARY_PROFILES)),
    ]

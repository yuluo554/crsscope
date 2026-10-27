"""模块 M4 · GeoJSON RFC 7946 结构与声明审计（`plan/03` §四）。

**两条不可动摇的纪律**：

1. **R1 与 R2 必须成对引用**（`data/README.md` §1.1）：
   R1 = 外环逆时针 MUST；R2 = "parsers SHOULD NOT reject…"。级别由 **R2** 决定 → 默认 `warning`，
   `--strict-ring` 是唯一升级路径。只引 R1 会做出"拒绝合法历史数据"的校验器。
2. **`crs` 成员只表述为 "no longer used"**（RFC 7946 §4 与 Appendix B.1 **没有**任何强制禁用条款；
   `plan/00` 决策 ①）。任何强制禁用式措辞都是违规——`tests/test_wording.py` 会扫 `src/`、`README.md`
   与 `AGENTS.md`，命中即红。
"""

from __future__ import annotations

from pathlib import Path

from .errors import UnimplementedFeature
from .report import Finding, ModuleResult

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

#: R1 / R2 原文（照录，用于报告证据字段）。
RFC_R1 = (
    "A linear ring MUST follow the right-hand rule with respect to the area it bounds, "
    "i.e., exterior rings are counterclockwise, and holes are clockwise."
)
RFC_R2 = (
    "For backwards compatibility, parsers SHOULD NOT reject Polygons that do not follow "
    "the right-hand rule."
)

MILESTONE = "M5"


def run(paths: list[Path], *, strict_ring: bool = False) -> ModuleResult:
    raise UnimplementedFeature(
        f"geojson 审计尚未实现（计划里程碑 {MILESTONE}）",
        detail="R1+R2 分级与 crs 措辞见 plan/03 §四；--strict-ring 是唯一升级路径",
    )


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

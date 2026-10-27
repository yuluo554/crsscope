"""模块 M1 · 声明-内容一致性（`plan/03` §一）。

判定顺序固定为 `CHECKS` 的顺序，不许并行、不许重排：
量级先判可以把"米域 vs 度域"一次性定性，后续轴序判定才不会被米域样本污染。
"""

from __future__ import annotations

from pathlib import Path

from .errors import UnimplementedFeature
from .report import Finding, ModuleResult

#: 检查项顺序（`plan/03` §一「判定顺序」）。代码与文档必须一致。
CHECKS: tuple[str, ...] = ("magnitude", "axis", "unit", "mixed", "extent")

#: `--declared-crs` 的合法枚举（`data/README.md` §1.2）。
#: **GCJ-02 / BD-09 不在其中**：它们没有 EPSG 代码，只能作为 `detect` 的检测假设。
DECLARED_CRS_CHOICES: tuple[str, ...] = ("4326", "3857", "4490", "crs84")

MILESTONE = "M2"


def run(path: Path, declared_crs: str | None, *, strict: bool = False) -> ModuleResult:
    """判定入口。骨架阶段显式抛未实现——**绝不返回空结果冒充"无问题"**。"""
    raise UnimplementedFeature(
        f"decl 判定尚未实现（计划里程碑 {MILESTONE}）",
        detail="参数面与检查项顺序已定；判定逻辑见 plan/03 §一",
    )


def describe() -> list[Finding]:
    """返回检查项清单（供 `--help` 与该模块的契约测试使用，不读数据）。"""
    return [Finding(check=name, status="info", detail=f"检查项 {name}") for name in CHECKS]

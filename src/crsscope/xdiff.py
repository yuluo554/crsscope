"""模块 M3 · 跨工具差分（`plan/03` §三）。

三个对照实现**全部本地重实现**，常数与两套边界框照录自 `data/README.md` §1.3。
本模块**不提供转换命令**——差分只用于"报出分歧"，不对外承诺 API 稳定性（题面 §七）。
"""

from __future__ import annotations

from pathlib import Path

from . import algorithms
from .errors import UnimplementedFeature
from .report import Finding, ModuleResult

#: 参与差分的本地实现（顺序固定，输出按此顺序排列）。
IMPLEMENTATIONS = ("coordTransform_py", "gcoord", "proj4js_webmercator")

#: `--target` 的合法枚举。
TARGET_CHOICES = ("wgs84", "gcj02", "bd09", "webmercator")

MILESTONE = "M4"


def run(path: Path, target: str) -> ModuleResult:
    raise UnimplementedFeature(
        f"xdiff 差分尚未实现（计划里程碑 {MILESTONE}）",
        detail="两库常数与边界框见 data/README.md §1.3；不收敛须报 not_converged",
    )


def describe() -> list[Finding]:
    ct, gc = algorithms.CT_PY_BBOX, algorithms.GCOORD_BBOX
    return [
        Finding(
            check="ct_py_bbox",
            status="info",
            detail=f"lon {ct['lon']} lat {ct['lat']}（开区间）",
            evidence={"source": "data/README.md §1.3 CT-PY-BBOX"},
        ),
        Finding(
            check="gcoord_bbox",
            status="info",
            detail=f"lon {gc['lon']} lat {gc['lat']}（闭区间）",
            evidence={"source": "data/README.md §1.3 GCOORD-BBOX"},
        ),
        Finding(
            check="implementations",
            status="info",
            detail=",".join(IMPLEMENTATIONS),
            evidence={"tolerance_deg": algorithms.INVERSE_TOLERANCE_DEG},
        ),
    ]

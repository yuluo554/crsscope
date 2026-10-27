"""错误类型 → 退出码的唯一映射（`data/README.md` §4.9）。

**为什么集中在这里**：§4.9 的优先级是全序（`2 → 3 → 4 → 5 → 1 → 0`）。若每个子命令自己
`sys.exit(...)`，同一情况会在不同入口答出不同码——这正是"两处口径必然漂移"的经典形态。
`cli.main()` 是唯一把异常翻译成退出码的地方。
"""

from __future__ import annotations

from collections.abc import Iterable

#: 退出码优先级（数值越小越优先）。**不存在其他退出码**；新增语义先改 §4.9 再加进这里。
_PRIORITY: dict[int, int] = {2: 0, 3: 1, 4: 2, 5: 3, 1: 4, 0: 5}


class CrsscopeError(Exception):
    """所有可预期失败的基类。子类只声明 `code` 与默认文案。"""

    code: int = 1
    label: str = "error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - 简单拼接
        return f"{self.label}: {self.message}" if self.label else self.message


class FindingsHit(CrsscopeError):
    """判定命中（`--fail-on`）。"""

    code = 1
    label = "findings"


class UsageError(CrsscopeError):
    """参数缺失 / 互斥 / 非法枚举。"""

    code = 2
    label = "usage"


class EnvironmentMissing(CrsscopeError):
    """文件不存在、掩膜缺失或步长超限、算法常数未加载。"""

    code = 3
    label = "environment"


class UnimplementedFeature(EnvironmentMissing):
    """能力尚未就绪（本仓库骨架阶段用）。

    归入 3（环境不满足）而不是 0/1：**未实现的命令绝不能用"成功且无命中"退出**，
    否则下游 CI 会把"没跑"读成"跑过且没问题"（§4.9 明确"与 0 严格区分"）。
    """

    code = 3
    label = "not implemented"


class InvalidInput(CrsscopeError):
    """JSON/GPX 不可解析、坐标对非数值、结构破碎。"""

    code = 4
    label = "invalid-input"


class Undecidable(CrsscopeError):
    """结论不可判定（灰区）。"""

    code = 5
    label = "undecidable"


def most_severe(codes: Iterable[int]) -> int:
    """按 §4.9 的全序取最严重的一个；空集视为 0。"""
    ordered = [c for c in codes if c in _PRIORITY]
    if not ordered:
        return 0
    return min(ordered, key=lambda c: _PRIORITY[c])

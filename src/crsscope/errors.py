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


#: 负向状态集：只有这些状态的发现项才可能构成"命中"。
#:
#: `warning` 在列：它本身默认不失败（见上），但 `--fail-on ring` 这类点名正是它的升级路径
#: （§4.6 的 `--strict-ring` 之外的第二条显式通道）。`consistent` / `info` 不在列——
#: 否则 `--fail-on axis` 会在"轴序正确"的数据上报失败，正好反了。
NEGATIVE_STATUSES: frozenset[str] = frozenset({"conflict", "error", "warning"})

#: 默认视为"判定命中"的状态集（`data/README.md` §4.9 的 1 行）。
#:
#: **刻意不含 `warning`**：`warning` 是本项目对"合法但值得提示"的固定级别（§4.6 —— R1 环方向
#: 违规默认就是 warning，因为 RFC 7946 §3.1.6 的第二句要求解析器容忍它）。若 warning 默认
#: 让命令 exit 1，CI 就会把历史数据判成失败，正好违反"分级而非拒绝"这条纪律。
#: 需要看 warning 时用 `--fail-on` 点名（如 `--fail-on ring`）。
DEFAULT_HIT_STATUSES: frozenset[str] = frozenset({"conflict", "error"})

#: 不计入"命中"、但影响退出码的状态（走 5 分支）。
UNDECIDABLE_STATUS = "undecidable"


def parse_fail_on(raw: str | None) -> tuple[str, ...]:
    """`--fail-on conflict,axis` → `("conflict", "axis")`。空串与重复项都被去掉（保序）。"""
    if not raw:
        return ()
    seen: list[str] = []
    for part in raw.split(","):
        name = part.strip()
        if name and name not in seen:
            seen.append(name)
    return tuple(seen)


def finding_categories(finding: object) -> frozenset[str]:
    """一条结果项可用于 `--fail-on` 面名的名字集合：状态 / 原因 / 检查项 id。

    三种都收：`--fail-on conflict`（按级别）、`--fail-on magnitude`（按原因）、
    `--fail-on axis_flip`（按检查项）在文档里都是合法写法。**但只有负向状态**的结果项
    会被计入命中——`consistent` 的 `axis` 项不该因为 `--fail-on axis` 就成了命中
    （否则 `--fail-on axis` 会在"轴序正确"的数据上报失败，正好反了）。
    """
    status = str(getattr(finding, "status", ""))
    if status not in NEGATIVE_STATUSES and status != UNDECIDABLE_STATUS:
        return frozenset()
    names = {status}
    reason = getattr(finding, "reason", None)
    if reason:
        names.add(str(reason))
    check = getattr(finding, "check", None)
    if check:
        names.add(str(check))
    return frozenset(names)


def outcome_code(
    findings: Iterable[object],
    *,
    fail_on: str | None = "",
    allow_undecidable: bool = False,
) -> int:
    """把一份判定结果折算成退出码（§4.9 的全序 `2→3→4→5→1→0` 的 `5→1→0` 段）。

    `2/3/4` 走异常（`CrsscopeError` 的子类），**不经过这里**：它们代表"结果集本身不可信"，
    在判定阶段就该中断。这里只回答"结果集已经产出，命令该怎么退出"。

    - 存在 `undecidable` 且未开 `--allow-undecidable` → `5`；
    - 命中 → `1`：`--fail-on` 为空时按 `DEFAULT_HIT_STATUSES`（`conflict` / `error`），
      给定时**收窄**为只认点名的类别；
    - 其余 → `0`。
    """
    statuses = [str(getattr(f, "status", "")) for f in findings]

    if not allow_undecidable and UNDECIDABLE_STATUS in statuses:
        return 5

    named = frozenset(parse_fail_on(fail_on))
    for finding, status in zip(findings, statuses):
        if status == UNDECIDABLE_STATUS:
            continue  # 已由上面处理；--allow-undecidable 下它就是"不再拦"
        categories = finding_categories(finding)
        if not categories:
            continue
        if named:
            if categories & named:  # --fail-on 给定时：收窄为只认点名的类别
                return 1
        elif status in DEFAULT_HIT_STATUSES:
            return 1
    return 0

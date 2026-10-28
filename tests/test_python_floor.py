"""Python 下限门（`requires-python >=3.11`）的本地判据（D5）。

**为什么不靠解释器**：本机只有 3.12（`py -3.11` → `Requested Python version (3.11) not
installed`，exit 103，2026-10-28 实测），所以"3.11 能不能跑"这件事在本地**永远发现不了**；
CI 的 3.11 腿能兜住，但它报出来的是 `SyntaxError` 的 collection error，而不是
"你写了 3.12 才能写的语法"。

**判据形态**：`ast.parse(source, feature_version=(3, 11))` 逐文件解析。CPython 的
`feature_version` 会在**解析期**拒绝高于该版本的新语法——这正是我们要的信号，且
3.12 的解释器就够用，不需要装 3.11。

实测（2026-10-28，本机 3.12.10）两种 3.12 专有语法在 `feature_version=(3,11)` 下都抛
`SyntaxError: Type statement is only supported in Python 3.12 and greater`：

    type Alias = dict[str, int]          # PEP 695 类型别名
    def probe[T](v: T) -> T: ...         # PEP 695 泛型参数

**范围**：`src/` 与 `tests/` 下全部 `.py`（含 `tools/`？不含——`tools/` 是门脚本，
它跑在**发布者的机器**上，与包的 `requires-python` 不是同一个契约）。判据的靶子是
"会被装进 wheel 的代码 + 随源码分发的测试"。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOOR = (3, 11)
SCAN_DIRS = ("src", "tests")


def _sources() -> list[Path]:
    """扫描面：`src/` 与 `tests/` 下的全部 `.py`。

    扫描面为空的判据是空跑——`_sources()` 返回空列表时 `test_every_source_file_parses`
    会因为没有参数化项而**静默通过**，所以另有一条 `test_scan_surface_is_not_empty`
    把这件事钉住。
    """
    found: list[Path] = []
    for name in SCAN_DIRS:
        base = REPO_ROOT / name
        if base.is_dir():
            found.extend(sorted(base.rglob("*.py")))
    return found


def _parse(source: str) -> None:
    """按项目下限解析；语法超出下限即抛 SyntaxError（这是**唯一**的判据）。"""
    ast.parse(source, filename="<floor-probe>", feature_version=FLOOR)


def test_every_source_file_parses() -> None:
    """仓内每个 `.py` 都必须能按 3.11 语法解析通过。

    **先守空跑**：本仓的布局门有同款纪律（"全部门加起来 0 行 = 判据空跑 = FAIL"）——
    一个扫 0 个文件的语法门比没有门更糟，它会给出"3.11 兼容"这个假结论。

    **一次遍历、聚合报错**：不按文件参数化，是为了让"全量测试条数"不随源文件增减而
    漂移（`tests/test_reported_counts.py` 会拿真实 collected 去核对 plan/ 里自述的数字，
    判据条数一动，文档就假红）。红的时候把所有违规文件一次列全。
    """
    sources = _sources()
    assert len(sources) >= 20, f"扫描面只有 {len(sources)} 个文件，判据在空跑"
    assert any(p.parent.name == "crsscope" for p in sources), "扫描面没覆盖 src/crsscope/"

    violations: list[str] = []
    for path in sources:
        source = path.read_text(encoding="utf-8")
        try:
            _parse(source)
        except SyntaxError as exc:
            violations.append(
                f"{path.relative_to(REPO_ROOT).as_posix()}:{exc.lineno}: "
                f"超出 Python {FLOOR[0]}.{FLOOR[1]} 下限 —— {exc.msg}"
            )
    assert not violations, "以下文件用了高于下限的语法：\n" + "\n".join(violations)


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param("type Alias = dict[str, int]\n", id="pep695-type-alias"),
        pytest.param("def f[T](v: T) -> T:\n    return v\n", id="pep695-generic-function"),
    ],
)
def test_floor_gate_sees_312_only_syntax(snippet: str) -> None:
    """阳性对照：两种 3.12 专有语法必须被判出（否则判据就是永远绿的装饰）。"""
    with pytest.raises(SyntaxError):
        _parse(snippet)


def test_floor_gate_accepts_legal_311_code() -> None:
    """阴性对照：合法的 3.11 代码不许红（判据不能靠"什么都红"来通过阳性对照）。

    覆盖本项目实际用到的几类 3.11 语法：`X | Y` 类型联合、内置泛型注解、
    `from __future__ import annotations`、模式匹配、`Self`。
    """
    legal = """
from __future__ import annotations

from typing import Self


class Probe:
    def clone(self) -> Self:
        return self


def judge(values: list[dict[str, float]] | None) -> tuple[bool, str]:
    match values:
        case None:
            return False, "缺值"
        case []:
            return False, "空表"
        case _:
            return True, f"{len(values)} 条"
"""
    _parse(legal)  # 不抛即通过

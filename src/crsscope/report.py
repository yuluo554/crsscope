"""报告组装与渲染（`plan/03` §六）。

**两轨同源**：`report.json` 与 `report.md` 由**同一份 payload** 渲染两次，不允许各走一条取数路径。
**确定性**：`sort_keys=True`、浮点统一格式化、不写绝对路径 / 主机名 / 用户名、只允许一个时间戳。
"""

from __future__ import annotations

import json
import os
import platform
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .errors import CrsscopeError, EnvironmentMissing, InvalidInput, UNDECIDABLE_STATUS, UsageError

#: `generated_at` 的兜底值（无 `SOURCE_DATE_EPOCH` 时）。固定值 = 双跑可逐字节比对。
FALLBACK_TIMESTAMP = "1970-01-01T00:00:00Z"

#: 报告中允许的时间戳字段白名单（`data/README.md` §4.10）。其余字段出现时间形态即视为越界。
TIMESTAMP_FIELD = "generated_at"

_ABS_WIN_PATH = re.compile(r"[A-Za-z]:[\\/][^\s\"']*")
_ABS_POSIX_PATH = re.compile(r"(?<![\w.-])/(?:home|Users|root|tmp|var|opt)/[^\s\"']*")


def generated_at_from_env(env: dict[str, str] | None = None) -> str:
    """唯一允许取"时间"的入口。

    优先 `SOURCE_DATE_EPOCH`（可复现构建的标准约定）；否则退回固定值。
    **不读系统时钟**——`data/README.md` §四要求"两次运行字节级一致"。
    """
    source = os.environ if env is None else env
    raw = source.get("SOURCE_DATE_EPOCH")
    if raw is None:
        return FALLBACK_TIMESTAMP
    try:
        ts = int(raw)
    except ValueError as exc:
        raise CrsscopeError(f"SOURCE_DATE_EPOCH 不是整数: {raw!r}") from exc
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrub(text: str) -> str:
    """去掉绝对路径与用户名/主机名痕迹（`plan/02` §四）。"""
    text = _ABS_WIN_PATH.sub("<path>", text)
    text = _ABS_POSIX_PATH.sub("<path>", text)
    for leak in (platform.node(), os.environ.get("USERNAME", ""), os.environ.get("USER", "")):
        if leak and len(leak) >= 3:
            text = text.replace(leak, "<redacted>")
    return text


def fmt_float(value: float | None, digits: int = 1) -> str | None:
    """全项目唯一的浮点格式化入口（§4.4：距离保留 0.1 m）。"""
    if value is None:
        return None
    return f"{value:.{digits}f}"


@dataclass
class Finding:
    """统一结果项。所有模块的每条结论都长这个形状（`plan/03` 开头）。"""

    check: str
    status: str  # consistent | conflict | undecidable | info | warning | error
    detail: str
    reason: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "status": self.status,
            "reason": self.reason,
            "detail": scrub(self.detail),
            "evidence": self.evidence,
        }


@dataclass
class ModuleResult:
    """一个子命令的完整结果。`payload` 是额外模块字段（如 `detect` 的 `winner`）。"""

    command: str
    findings: list[Finding] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    exit_code: int = 0

    def has_status(self, *statuses: str) -> bool:
        return any(f.status in statuses for f in self.findings)


def build_header(command: str, *, declared_crs: str | None = None, **extra: Any) -> dict[str, Any]:
    """报告头（§4.10 缺一不可）。`extra` 只放模块必填字段（如掩膜坐标）。"""
    header: dict[str, Any] = {
        "tool": "crsscope",
        "tool_version": __version__,
        "command": command,
        "declared_crs": declared_crs or "none",
        TIMESTAMP_FIELD: generated_at_from_env(),
    }
    header.update(extra)
    return header


def dumps_json(payload: dict[str, Any]) -> str:
    """唯一的 JSON 序列化入口：键序固定、中文不转义、末尾带换行（diff 友好）。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _status_icon(status: str) -> str:
    return {
        "consistent": "✅",
        "conflict": "❌",
        "undecidable": "⚠️",
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
    }.get(status, "·")


#: 报告末节固定声明（`plan/03` §六：人读面必须自带已知边界）。
KNOWN_LIMITS = """\
## 已知边界

- **掩膜分辨率**：首期离线掩膜步长上限 1°（`data/README.md` §4.3）；掩膜为**构造网格**，
  不是地理真值，`unknown` 与海岸带不计入落水分母。分辨率不足时结论为 `undecidable`。
- **不可消解残差**：GCJ-02 / BD-09 的逆向只给出"在某实现假设下的残差与置信"。
  三段固定不确定性（民间公式近似 / 厂商米级差异 / 边界两侧跳变）见 `residual` 字段。
- **不做渲染**：本工具不产出地图、切片或图片，输出只有判定与证据。
"""


def render_markdown(result: ModuleResult) -> str:
    """人读面。与 `dumps_json` 共用同一份 `ModuleResult`（两轨同源）。"""
    head = result.payload.get("header", {})
    lines: list[str] = [
        f"# crsscope · {result.command}",
        "",
        f"- 工具版本：`{head.get('tool_version', __version__)}`",
        f"- 声明 CRS：`{head.get('declared_crs', 'none')}`",
        f"- 生成时间：`{head.get(TIMESTAMP_FIELD, FALLBACK_TIMESTAMP)}`",
    ]
    for key in ("mask_version", "mask_max_resolution_deg", "evaluable_points", "unknown_ratio"):
        if key in head:
            lines.append(f"- {key}：`{head[key]}`")
    lines.append("")

    verdict = result.payload.get("verdict")
    if verdict:
        lines += [f"**结论**：{verdict}", ""]

    if result.findings:
        lines += ["| 检查项 | 状态 | 原因 | 说明 |", "|---|---|---|---|"]
        for f in result.findings:
            lines.append(
                f"| `{f.check}` | {_status_icon(f.status)} {f.status} | {f.reason or '—'} | {scrub(f.detail)} |"
            )
        lines.append("")
        evidence_rows = [(f.check, f.evidence) for f in result.findings if f.evidence]
        if evidence_rows:
            lines += ["## 证据", ""]
            for check, ev in evidence_rows:
                pairs = ", ".join(f"`{k}`={v!r}" for k, v in sorted(ev.items()))
                lines.append(f"- `{check}`：{pairs}")
            lines.append("")
    else:
        lines += ["（无检查项）", ""]

    lines += [KNOWN_LIMITS, f"退出码：`{result.exit_code}`", ""]
    return scrub("\n".join(lines))


def write_reports(
    result: ModuleResult,
    *,
    out_dir: Path | None = None,
    want_json: bool = True,
    want_md: bool = True,
) -> dict[str, str]:
    """渲染并落盘。返回 `{文件名: 绝对路径字符串}` 供 CLI 打印提示。

    **失败路径零副作用**：本函数只被 `cli` 在判定成功之后调用；判定阶段抛错时一个字节都不写。
    """
    payload: dict[str, Any] = dict(result.payload)
    payload.setdefault("findings", [f.as_dict() for f in result.findings])
    payload["exit_code"] = result.exit_code

    written: dict[str, str] = {}
    target_dir = out_dir or Path.cwd()
    target_dir.mkdir(parents=True, exist_ok=True)
    if want_json:
        path = target_dir / "report.json"
        path.write_text(dumps_json(payload), encoding="utf-8", newline="\n")
        written["report.json"] = str(path)
    if want_md:
        path = target_dir / "report.md"
        path.write_text(render_markdown(result), encoding="utf-8", newline="\n")
        written["report.md"] = str(path)
    return written


# ── `report` 子命令：多份 report.json 的汇总与门禁（HANDOFF-M6 §三A）────────
#
# 聚合只产出 findings 与汇总事实；退出码折算交回 `cli._emit` → `errors.outcome_code`
#（§4.9 的全序只在一处实现）——**本模块不另写第二份退出码映射**。
# 失败路径按 §4.9：缺文件 → 3（EnvironmentMissing）；JSON 不可解析 / 顶层缺
# `findings` → 4（InvalidInput）。这三者都在判定阶段抛出，一个字节都不落盘。

REPORT_COMMAND = "report"

#: `header.command` 缺失时的兜底值。真实的五类报告都有该字段；兜底只为直调 `run()` 时不炸。
_UNKNOWN_COMMAND = "unknown"


def _load_report(path: Path) -> dict[str, Any]:
    """读入并校验一份 report.json。结构不合法走 exit 4，与文件不存在（exit 3）分层。"""
    if not path.is_file():
        raise EnvironmentMissing(
            f"文件不存在: {path.name}",
            detail="report 子命令吃的是此前各子命令落盘的 report.json",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidInput(f"JSON 不可解析: {path.name}（{exc}）") from exc
    if not isinstance(payload, dict) or "findings" not in payload:
        raise InvalidInput(
            f"顶层缺 findings 成员: {path.name}",
            detail="report.json 顶层必须是含 findings 数组的对象",
        )
    if not isinstance(payload["findings"], list):
        raise InvalidInput(f"findings 不是数组: {path.name}")
    return payload


def _finding_from_dict(raw: Any, source: str) -> Finding:
    """把 JSON 里的一条结果项还原成 `Finding`；形状不对按输入无效处理（exit 4）。"""
    if not isinstance(raw, dict) or not isinstance(raw.get("status"), str):
        raise InvalidInput(f"findings 元素缺 status 字符串: {source}")
    evidence = raw.get("evidence")
    evidence = dict(evidence) if isinstance(evidence, dict) else {}
    evidence["source"] = source  # 逐条标出它来自哪份输入报告（basename，无绝对路径）
    reason = raw.get("reason")
    return Finding(
        check=str(raw.get("check", "")),
        status=raw["status"],
        detail=str(raw.get("detail", "")),
        reason=reason if isinstance(reason, str) else None,
        evidence=evidence,
    )


def gate_verdict(counts: dict[str, int]) -> str:
    """门禁结论（人读面）。

    只**描述**聚合内容的结论文案，语序刻意与 `errors.outcome_code` 的优先级一致
    （灰区优先于命中）；退出码数值仍由 `outcome_code` 折算，这里不出现数字。
    """
    undecided = counts.get(UNDECIDABLE_STATUS, 0)
    if undecided:
        return (
            f"存在不可判定结果 {undecided} 项（灰区优先：需人工介入，"
            "默认以退出码 5 报出，--allow-undecidable 可显式放行）"
        )
    hits = counts.get("conflict", 0) + counts.get("error", 0)
    if hits:
        return f"门禁命中：conflict / error 共 {hits} 项"
    return "门禁通过：聚合结果无 conflict / error / undecidable"


def run(paths: Sequence[Path]) -> ModuleResult:
    """`report` 子命令入口（`plan/03` §七：汇总与门禁）。

    聚合规则：每份输入的 findings **原样并入**（逐条加 `evidence.source` 标明出处），
    汇总层不重判、不改级别——重判是各判定子命令的事，这里只回答"合在一起看怎么样"。

    输入标签 = basename（报告里不许出现绝对路径）；同名输入按出现序追加 `#2`/`#3`
    消歧——五份输入可以都叫 `report.json`，归属必须仍然可证。
    """
    path_list = list(paths)
    if not path_list:
        raise UsageError("report 需要至少一份 report.json")

    seen: dict[str, int] = {}
    labels: list[str] = []
    for path in path_list:
        name = path.name
        seen[name] = seen.get(name, 0) + 1
        labels.append(name if seen[name] == 1 else f"{name}#{seen[name]}")

    findings: list[Finding] = []
    sources: list[dict[str, Any]] = []
    for path, label in zip(path_list, labels):
        payload = _load_report(path)
        header = payload.get("header")
        header = header if isinstance(header, dict) else {}
        command = header.get("command")
        if not isinstance(command, str) or not command:
            command = _UNKNOWN_COMMAND
        module_findings = [_finding_from_dict(raw, label) for raw in payload["findings"]]
        findings.extend(module_findings)
        raw_exit = payload.get("exit_code")
        sources.append(
            {
                "file": label,
                "command": command,
                "exit_code": raw_exit if isinstance(raw_exit, int) else None,
                "findings": len(module_findings),
            }
        )

    counts: dict[str, int] = dict(sorted(Counter(f.status for f in findings).items()))
    return ModuleResult(
        command=REPORT_COMMAND,
        findings=findings,
        payload={
            "header": build_header(REPORT_COMMAND, report_count=len(path_list)),
            "verdict": gate_verdict(counts),
            "sources": sources,
            "counts": counts,
        },
    )

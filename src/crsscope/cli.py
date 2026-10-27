"""命令行入口（`plan/03` §七）。

**唯一**把异常翻译成退出码的地方（`data/README.md` §4.9 的优先级 `2→3→4→5→1→0`）。
未实现的子命令一律 exit 3 并打印 `not implemented`——**绝不以 0 退出**，
否则下游 CI 会把"没跑"读成"跑过且没问题"。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from . import __version__, decl, detect, geojson, report, tiles, xdiff
from .errors import CrsscopeError

PROG = "crsscope"

EPILOG = """\
数值口径唯一权威：data/README.md §四（阈值 / 评分 / 残差格式 / 灰区 / 退出码）。
本工具只做判定，不提供坐标转换命令，不做地图渲染，运行期零网络。

退出码：0 无命中 / 1 判定命中 / 2 用法错误 / 3 环境不满足 / 4 输入无效 / 5 不可判定
"""


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="把 report.json 打到 stdout")
    parser.add_argument("--out-dir", type=Path, default=None, help="报告落盘目录（默认当前目录）")
    parser.add_argument(
        "--fail-on",
        default="",
        help="命中即 exit 1 的类别，逗号分隔（conflict,axis,magnitude,ring,axis_flip…）",
    )
    parser.add_argument(
        "--allow-undecidable",
        action="store_true",
        help="存在 undecidable 时仍 exit 0（默认把'判不出来'当作需人工介入）",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="空间参考语义审计器：判定坐标参考系、量化偏移与不可消解残差。",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_decl = sub.add_parser("decl", help="判定声明 CRS 与数据内容是否一致")
    p_decl.add_argument("file", type=Path)
    p_decl.add_argument(
        "--declared-crs",
        choices=decl.DECLARED_CRS_CHOICES,
        default=None,
        help="声明值；GCJ-02 / BD-09 无 EPSG 代码，不是合法声明值",
    )
    p_decl.add_argument("--strict", action="store_true", help="严格模式")
    _add_common(p_decl)

    p_detect = sub.add_parser("detect", help="检测 WGS84 / GCJ02 / BD09 偏移假设并报残差")
    p_detect.add_argument("file", type=Path)
    p_detect.add_argument("--declared-crs", choices=decl.DECLARED_CRS_CHOICES, default=None)
    p_detect.add_argument("--mask", type=Path, default=None, help="离线陆水掩膜 JSON（步长 ≤ 1°）")
    _add_common(p_detect)

    p_xdiff = sub.add_parser("xdiff", help="同一批坐标喂给本地三个实现并报两两差异")
    p_xdiff.add_argument("file", type=Path)
    p_xdiff.add_argument("--target", choices=xdiff.TARGET_CHOICES, required=True)
    _add_common(p_xdiff)

    p_geo = sub.add_parser("geojson", help="GeoJSON RFC 7946 结构与声明审计")
    p_geo.add_argument("files", type=Path, nargs="+")
    p_geo.add_argument(
        "--strict-ring",
        action="store_true",
        help="把 R1 环方向违规从 warning 升为 error（默认不升级：R2 要求解析器容忍）",
    )
    _add_common(p_geo)

    p_tiles = sub.add_parser("tiles", help="瓦片轴序 / zoom-bbox / 跨 180° 一致性")
    p_tiles.add_argument("file", type=Path)
    _add_common(p_tiles)

    p_report = sub.add_parser("report", help="汇总已有 report.json 并做门禁")
    p_report.add_argument("files", type=Path, nargs="+")
    _add_common(p_report)

    return parser


def _run_decl(args: argparse.Namespace) -> report.ModuleResult:
    return decl.run(args.file, args.declared_crs, strict=args.strict)


def _run_detect(args: argparse.Namespace) -> report.ModuleResult:
    return detect.run(args.file, args.declared_crs, mask_path=args.mask)


def _run_xdiff(args: argparse.Namespace) -> report.ModuleResult:
    return xdiff.run(args.file, args.target)


def _run_geojson(args: argparse.Namespace) -> report.ModuleResult:
    return geojson.run(args.files, strict_ring=args.strict_ring)


def _run_tiles(args: argparse.Namespace) -> report.ModuleResult:
    return tiles.run(args.file)


def _run_report(args: argparse.Namespace) -> report.ModuleResult:
    from .errors import UnimplementedFeature

    raise UnimplementedFeature(
        "report 汇总尚未实现（随 M6 发布门一起落位）",
        detail="语义见 plan/03 §六：多份 report.json 汇总 + --fail-on 门禁",
    )


_HANDLERS: dict[str, Callable[[argparse.Namespace], report.ModuleResult]] = {
    "decl": _run_decl,
    "detect": _run_detect,
    "xdiff": _run_xdiff,
    "geojson": _run_geojson,
    "tiles": _run_tiles,
    "report": _run_report,
}


def _emit(result: report.ModuleResult, args: argparse.Namespace) -> int:
    payload = dict(result.payload)
    payload.setdefault("findings", [f.as_dict() for f in result.findings])
    payload["exit_code"] = result.exit_code
    if args.json:
        sys.stdout.write(report.dumps_json(payload))
    else:
        sys.stdout.write(report.render_markdown(result))
    written = report.write_reports(result, out_dir=args.out_dir)
    if not args.json:
        for name, path in written.items():
            sys.stderr.write(f"wrote {name}\n")
    return result.exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse 对用法错误是 SystemExit(2)，统一成整数返回
        return int(exc.code or 0)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    handler = _HANDLERS[args.command]
    try:
        result = handler(args)
    except CrsscopeError as exc:
        sys.stderr.write(f"{PROG}: {exc}\n")
        if exc.detail:
            sys.stderr.write(f"  hint: {exc.detail}\n")
        return exc.code
    except BrokenPipeError:  # 管道提前关闭（如 | head）不是错误
        return 0
    return _emit(result, args)


if __name__ == "__main__":
    raise SystemExit(main())

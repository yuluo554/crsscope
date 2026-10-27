#!/usr/bin/env python3
"""布局门（方法论装订第②件）：把"项目还长在方法论上"变成可跑红的断言。

判据一律落**仓库内文件**，不读 git 元数据（浅克隆下 tag / 历史深度会翻转判据）。
退出码：0 全绿 / 1 有 FAIL / 2 用法错误。

配置区（§一）是本文件唯一需要随项目改的地方；判据（§二）与报告（§三）不要跟着改。

派生说明：判据集按 `ai-tool-project-sprint/references/templates/check-sprint-layout.mjs`
移植为 Python（Python 项目在 CI 里不必装 Node）。移植时保留原模板的三条纪律：
  ① **判据不许自我参照**（真值不取自任何一个副本）；
  ② **每份副本的命中行数必须可见**，全部门加起来 0 行 = 判据空跑 = FAIL；
  ③ 匹配里程碑号前**剥掉行内代码与文件名**（否则 `plan/RELEASE-M6.md` 里的 `M6` 被当状态引用）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ─────────────────────────────── §一 配置区 ───────────────────────────────

REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "LICENSE",
    "data/README.md",
    "plan/00-README总览.md",
    "plan/01-题目文档.md",
    "plan/02-架构与技术选型.md",
    "plan/03-模块详设.md",
    "plan/04-数据计划.md",
    "plan/05-里程碑与发布.md",
    "plan/06-交付对标与决策.md",
]

REQUIRED_SECTIONS = {
    "plan/00-README总览.md": ["文档索引", "决策记录", "承诺-证据台账", "里程碑"],
    "plan/01-题目文档.md": ["任务要求", "评分标准", "边界与非目标"],
    "plan/02-架构与技术选型.md": ["分层", "构建"],
    "plan/03-模块详设.md": ["接口", "判定顺序", "失败路径", "测试点"],
    "plan/04-数据计划.md": ["数据清单", "真值纪律", "数值口径"],
    "plan/05-里程碑与发布.md": ["状态表", "DoD", "已知未验证项"],
    "plan/06-交付对标与决策.md": ["评分对标", "风险登记", "缺口"],
    "data/README.md": ["依据查证记录", "数值口径"],
}

HANDOFF_SECTIONS = ["当前进度", "当前事实", "待办", "既定口径", "环境坑", "DoD", "命令速查"]

# 已声明豁免（不要求交接单的里程碑号）。出题阶段不按 M 编号，故此处为空。
EXEMPT_MILESTONES: list[int] = []
HANDOFF_FORMAT_FROM = 1
HANDOFF_EXEMPT_LAST = False

# 状态副本：同一里程碑在这几处的状态必须互相一致。README 刻意不参与（见 AGENTS.md §二）。
STATUS_COPIES = [
    ("plan/00-README总览.md", "里程碑表"),
    ("plan/05-里程碑与发布.md", "状态表"),
]

STATUS_LINE = re.compile(r"^\|\s*\*{0,2}M(\d+)\b")
PENDING_MARKERS = ("⬜", "🟡", "未开始", "未执行", "待执行", "待确认", "未开工")

# 文档已点名、但所属里程碑未完成的脚本：{相对路径: 里程碑号}
# M6 已落位：tools/check-release.py 实物在仓，登记项按纪律删除（登记过期即红的反向面）。
PENDING_TOOLS: dict[str, int] = {}
# 确实不打算实现的脚本（理由写在这里）
EXEMPT_TOOLS: set[str] = set()

RELEASE_MILESTONE: int | None = None
CI_GATE_TOKEN = "check-sprint-layout.py"
CI_MUTATION_TOKEN = "mutate-layout-gate.py"

FILE_EXT_RE = re.compile(r"[\w./-]+\.(?:md|py|mjs|js|json|toml|txt|yml|yaml)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
TOOLS_REF_RE = re.compile(r"tools/[\w.-]+\.(?:py|mjs|js|cjs|sh|ps1)")


# ─────────────────────────────── §二 判据 ───────────────────────────────

class Gate:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.checks: list[tuple[str, bool, str]] = []
        self.scanned = {
            "docs": 0,
            "handoffs": 0,
            "copies": 0,
            "status_rows": 0,
            "doc_tools": 0,
            "gap_rows": 0,
            "ledger_rows": 0,
            "release": 0,
        }

    # -- 基础工具 --------------------------------------------------------
    def path(self, rel: str) -> Path:
        return self.root / rel

    def read(self, rel: str) -> str | None:
        p = self.path(rel)
        if not p.is_file():
            return None
        return p.read_text(encoding="utf-8", errors="replace")

    def add(self, cid: str, ok: bool, detail: str) -> None:
        self.checks.append((cid, ok, detail))

    # -- ① 必备文件 ------------------------------------------------------
    def check_files(self) -> None:
        missing = [rel for rel in REQUIRED_FILES if not self.path(rel).is_file()]
        self.scanned["docs"] = len(REQUIRED_FILES) - len(missing)
        self.add(
            "LAYOUT.FILES",
            not missing,
            f"缺: {','.join(missing)}" if missing else f"{self.scanned['docs']} 份齐备",
        )

    # -- ② 装订行（plan/00 顶部，三锚点同现于一行）------------------------
    def check_binding(self) -> None:
        text = self.read("plan/00-README总览.md") or ""
        pattern = re.compile(
            r"^>(?=.*ai-tool-project-sprint)(?=.*check-sprint-layout)(?=.*20\d{2}-\d{2}-\d{2}).*$",
            re.MULTILINE,
        )
        ok = bool(pattern.search(text))
        self.add(
            "LAYOUT.BINDING_HEAD",
            ok,
            "plan/00 顶部有装订行（三锚点齐）"
            if ok
            else "plan/00 顶部缺装订行（需同现：方法论名 + 布局门命令 + 装订日期）",
        )

    # -- ③ 必需小节 ------------------------------------------------------
    def check_sections(self) -> None:
        """判据 = **标题行**含关键词，不是"全文出现过该词"。

        全文匹配是假门族②的变体：正文里随便提一句"分层"就能让判据恒绿，
        而真正的小节被删掉时**没有任何东西会红**（本项目 2026-10-27 变异实测：
        把 `## 一、分层架构` 改成 `## 一、结构`，全文匹配仍绿）。
        """
        title_re = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
        bad: list[str] = []
        for rel, needles in REQUIRED_SECTIONS.items():
            text = self.read(rel)
            if text is None:
                continue
            titles = "\n".join(title_re.findall(text))
            missing = [n for n in needles if n not in titles]
            if missing:
                bad.append(f"{rel}: 标题缺 {'/'.join(missing)}")
        self.add(
            "LAYOUT.SECTIONS",
            not bad,
            "；".join(bad) if bad else f"{len(REQUIRED_SECTIONS)} 份小节齐备（按标题行判）",
        )

    # -- ④ 状态副本一致 --------------------------------------------------
    def collect_states(self) -> tuple[dict[int, set[str]], dict[str, int]]:
        states: dict[int, set[str]] = {}
        rows_by_copy: dict[str, int] = {}
        for rel, _kind in STATUS_COPIES:
            text = self.read(rel)
            if text is None:
                continue
            self.scanned["copies"] += 1
            rows = 0
            for line in text.splitlines():
                m = STATUS_LINE.match(line)
                if not m:
                    continue
                rows += 1
                pending = any(mark in line for mark in PENDING_MARKERS)
                states.setdefault(int(m.group(1)), set()).add("pending" if pending else "done")
            rows_by_copy[rel] = rows
            self.scanned["status_rows"] += rows
        return states, rows_by_copy

    def check_status(self, states: dict[int, set[str]], rows_by_copy: dict[str, int]) -> None:
        conflicts = [
            f"M{k} 在副本间状态不一致（{' vs '.join(sorted(v))}）"
            for k, v in sorted(states.items())
            if len(v) > 1
        ]
        total = sum(rows_by_copy.values())
        per_copy = " ".join(f"{Path(f).name}:{n}" for f, n in sorted(rows_by_copy.items()))
        if not conflicts and total == 0:
            self.add("LAYOUT.STATUS", False, f"所有副本合计 0 行状态行（判据空跑）：{per_copy}")
            return
        self.add(
            "LAYOUT.STATUS",
            not conflicts,
            "；".join(conflicts)
            if conflicts
            else f"{self.scanned['copies']} 处副本 × {len(states)} 个里程碑 状态全一致（行数 {per_copy}）",
        )

    # -- ⑤ 交接单 --------------------------------------------------------
    def check_handoffs(self, done: list[int], all_ms: list[int]) -> None:
        last = max(all_ms) if all_ms else 0
        missing: list[str] = []
        for k in sorted(done):
            if k in EXEMPT_MILESTONES:
                continue
            if HANDOFF_EXEMPT_LAST and k == last:
                continue
            rel = f"plan/HANDOFF-M{k}.md"
            text = self.read(rel)
            if text is None:
                missing.append(f"{rel}(缺)")
                continue
            self.scanned["handoffs"] += 1
            if k < HANDOFF_FORMAT_FROM:
                continue
            lack = [n for n in HANDOFF_SECTIONS if n not in text]
            if lack:
                missing.append(f"{rel}(缺节: {'/'.join(lack)})")
        self.add(
            "LAYOUT.HANDOFFS",
            not missing,
            "；".join(missing)
            if missing
            else f"{self.scanned['handoffs']} 份交接单齐（已 ✅ 里程碑 {len(done)} 个）",
        )

    # -- ⑥ 缺口列 --------------------------------------------------------
    def check_gaps(self, done: list[int]) -> None:
        lines = (self.read("plan/06-交付对标与决策.md") or "").splitlines()
        header_idx = next(
            (i for i, l in enumerate(lines) if l.startswith("|") and "缺口" in l), None
        )
        if header_idx is None:
            self.add("LAYOUT.GAPS", False, "plan/06 找不到含『缺口』表头的表（判据表搬走了？）")
            return
        header = [c.strip() for c in lines[header_idx].split("|")]
        col = next((i for i, c in enumerate(header) if "缺口" in c), None)
        if col is None:
            self.add("LAYOUT.GAPS", False, "plan/06 缺口表头无法定位列号")
            return
        stale: list[str] = []
        rows = 0
        for line in lines[header_idx + 2 :]:
            if not line.startswith("|"):
                break
            rows += 1
            cells = [c.strip() for c in line.split("|")]
            cell = cells[col] if col < len(cells) else ""
            # 剥掉行内代码与文件名：`plan/RELEASE-M6.md` 里的 M6 是标识符，不是状态引用
            cell = FILE_EXT_RE.sub(" ", INLINE_CODE_RE.sub(" ", cell))
            for k in done:
                if re.search(rf"(^|[^0-9A-Za-z])M{k}([^0-9]|$)", cell):
                    stale.append(f"plan/06 缺口列仍提 M{k}: {cell.strip()[:60]}")
        self.scanned["gap_rows"] = rows
        self.add(
            "LAYOUT.GAPS",
            not stale,
            "；".join(stale) if stale else f"plan/06 缺口列扫了 {rows} 行，无已 ✅ 里程碑",
        )

    # -- ⑦ 承诺-证据台账（第三份状态副本）--------------------------------
    def check_ledger(self, done: list[int]) -> None:
        lines = (self.read("plan/00-README总览.md") or "").splitlines()
        # 表头必须同现「承诺」与「状态」两列。**不要**要求「证据」也出现在表头行：
        # 本项目的台账表头是 `承诺项 | 素材来源 | 交付物内可达性 | 核验方式 | 状态`，
        # 「证据」只在它上面的小节标题「## 承诺-证据台账」里——按表头行断言三词会**假红**
        # （本仓 2026-10-27 实测：门报"找不到台账表头"而台账明明在）。
        header_idx = next(
            (
                i
                for i, l in enumerate(lines)
                if l.startswith("|") and "承诺" in l and "状态" in l
            ),
            None,
        )
        if header_idx is None:
            self.add("LAYOUT.LEDGER", False, "plan/00 找不到『承诺-证据台账』表头")
            return
        header = [c.strip() for c in lines[header_idx].split("|")]
        col = next((i for i, c in enumerate(header) if "状态" in c), None)
        if col is None:
            self.add("LAYOUT.LEDGER", False, "台账表头无『状态』列")
            return
        bad: list[str] = []
        rows = 0
        for line in lines[header_idx + 2 :]:
            if not line.startswith("|"):
                break
            rows += 1
            cells = [c.strip() for c in line.split("|")]
            status = cells[col] if col < len(cells) else ""
            if not re.search(r"[⬜🟡]|未开始|待 M\d|待开工|未开工", status):
                continue
            for k in done:
                if re.search(rf"(^|[^0-9A-Za-z])M{k}([^0-9]|$)", status):
                    bad.append(f"台账行仍挂未完成: {status[:60]}")
        self.scanned["ledger_rows"] = rows
        if rows == 0:
            self.add("LAYOUT.LEDGER", False, "台账表 0 行——判据空跑")
            return
        self.add(
            "LAYOUT.LEDGER",
            not bad,
            "；".join(bad) if bad else f"台账 {rows} 行，已成 ✅ 的里程碑无未完成标记",
        )

    # -- ⑧ 发布留档 ------------------------------------------------------
    def check_release(self, done: list[int], all_ms: list[int]) -> None:
        release_ms = RELEASE_MILESTONE if RELEASE_MILESTONE is not None else (max(all_ms) if all_ms else 0)
        if release_ms == 0 or release_ms not in done:
            self.add(
                "LAYOUT.RELEASE",
                True,
                f"发布里程碑 M{release_ms} 未完成，收尾记录尚不适用（已 ✅ {len(done)} 个）",
            )
            return
        self.scanned["release"] += 1
        release = self.read(f"plan/RELEASE-M{release_ms}.md")
        wrapup = self.read(f"plan/WRAPUP-M{release_ms}.md")
        if release is None and wrapup is None:
            self.add("LAYOUT.RELEASE", False, f"缺 plan/RELEASE-M{release_ms}.md 或 plan/WRAPUP-M{release_ms}.md")
            return
        if release is None:
            self.add("LAYOUT.RELEASE", True, "WRAPUP 形态")
            return
        cols = bool(re.search(r"^##\s*一、tag 前事实", release, re.MULTILINE)) and bool(
            re.search(r"^##\s*二、tag 后追加", release, re.MULTILINE)
        )
        heading = bool(re.search(r"^#{2,3}.*覆盖对账", release, re.MULTILINE))
        rows = len(re.findall(r"^\|.*(?:实现|不适用|待首推).*\|$", release, re.MULTILINE))
        self.add(
            "LAYOUT.RELEASE",
            cols and heading and rows >= 3,
            f"两栏:{cols} 覆盖对账小节:{heading} 三态行数:{rows}",
        )

    # -- ⑨ 文档点名的 tools/ 脚本必须有实物 ------------------------------
    def check_doc_tools(self, done: list[int]) -> None:
        docs = ["AGENTS.md"]
        plan_dir = self.root / "plan"
        if plan_dir.is_dir():
            docs += [f"plan/{p.name}" for p in sorted(plan_dir.glob("*.md"))]
        referenced: set[str] = set()
        for rel in docs:
            text = self.read(rel)
            if text is None:
                continue
            referenced.update(TOOLS_REF_RE.findall(text))
        if not referenced:
            self.add(
                "LAYOUT.DOC_TOOLS",
                False,
                f"扫了 {len(docs)} 份文档，0 处 tools/ 引用——判据是空的（阳性对照失败）",
            )
            return
        self.scanned["doc_tools"] = len(referenced)
        missing: list[str] = []
        deferred: list[str] = []
        stale: list[str] = []
        for rel in sorted(referenced):
            if self.path(rel).is_file() or rel in EXEMPT_TOOLS:
                continue
            milestone = PENDING_TOOLS.get(rel)
            if milestone is None:
                missing.append(rel)
            elif milestone in done:
                stale.append(f"{rel}（M{milestone} 已 ✅，登记项必须清理）")
            else:
                deferred.append(f"{rel}(M{milestone})")
        problems = missing + stale
        detail = f"{len(referenced)} 个文档点名的 tools/ 脚本"
        if problems:
            detail += f"；问题: {','.join(problems)}"
        elif deferred:
            detail += f"；{len(deferred)} 个待里程碑落位: {','.join(deferred)}"
        else:
            detail += " 全部在位"
        self.add("LAYOUT.DOC_TOOLS", not problems, detail)

    # -- ⑩ 门自身在 CI 里（两条步骤：门 + 变异验证）-----------------------
    def check_ci(self) -> None:
        wf_dir = self.root / ".github" / "workflows"
        texts: list[tuple[str, str]] = []
        if wf_dir.is_dir():
            for p in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
                texts.append((p.name, p.read_text(encoding="utf-8", errors="replace")))
        for cid, token, label in (
            ("LAYOUT.CI_STEP", CI_GATE_TOKEN, "布局门步骤"),
            ("LAYOUT.CI_MUTATION", CI_MUTATION_TOKEN, "门变异验证步骤"),
        ):
            hits = [name for name, text in texts if token in text]
            self.add(
                cid,
                bool(hits),
                f"{label}在 CI：{','.join(hits)}" if hits else f"{len(texts)} 个 workflow 文件里找不到 {token}",
            )

    # -- 汇总 ------------------------------------------------------------
    def run(self) -> int:
        for fn in (self.check_files, self.check_binding, self.check_sections):
            try:
                fn()
            except Exception as exc:  # 门自己崩掉也要落成 FAIL，不许无结论退出
                self.add(fn.__name__, False, f"判据异常: {exc}")
        try:
            states, rows_by_copy = self.collect_states()
        except Exception as exc:
            self.add("LAYOUT.STATUS", False, f"判据异常: {exc}")
            states, rows_by_copy = {}, {}
        done = sorted(k for k, v in states.items() if "done" in v)
        all_ms = sorted(states)
        for fn in (
            lambda: self.check_status(states, rows_by_copy),
            lambda: self.check_handoffs(done, all_ms),
            lambda: self.check_gaps(done),
            lambda: self.check_ledger(done),
            lambda: self.check_release(done, all_ms),
            lambda: self.check_doc_tools(done),
            self.check_ci,
        ):
            try:
                fn()
            except Exception as exc:
                self.add(getattr(fn, "__name__", "LAYOUT.CHECK"), False, f"判据异常: {exc}")
        return self.report()

    # ───────────────────────── §三 报告 ─────────────────────────
    def report(self) -> int:
        failed = [c for c in self.checks if not c[1]]
        out = [
            "布局门（方法论装订） · 判据只落仓库内文件",
            "=" * 56,
        ]
        out += [f"{'PASS' if ok else 'FAIL'}  {cid}  {detail}" for cid, ok, detail in self.checks]
        out += [
            "=" * 56,
            "这轮扫到：文档 {docs} / 交接单 {handoffs} / 状态副本 {copies}（状态行 {status_rows}）"
            " / 点名脚本 {doc_tools} / 缺口行 {gap_rows} / 台账行 {ledger_rows} / 发布留档 {release}".format(
                **self.scanned
            ),
            f"结论: {'全绿' if not failed else f'{len(failed)} 项 FAIL'}",
        ]
        sys.stdout.write("\n".join(out) + "\n")
        return 0 if not failed else 1


def _ensure_utf8_stdio() -> None:
    """中文控制台（cp936 / cp1252 管道）下不许因编码崩，也不把编码问题伪装成判据失败。"""
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", "") or "").lower()
        if enc.replace("-", "") in {"utf8", "utf_8"}:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check-sprint-layout",
        description="布局门：断言仓库仍长在 ai-tool-project-sprint 的强制布局上。",
    )
    parser.add_argument(
        "--root",
        default=str(REPO_ROOT),
        help="被检查仓库根（默认：本脚本上一级）。变异验证用，不要写进文档。",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write(f"用法错误：--root 不是目录：{args.root}\n")
        return 2
    _ensure_utf8_stdio()
    return Gate(root).run()


if __name__ == "__main__":
    raise SystemExit(main())

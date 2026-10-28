# RELEASE-M7 · crsscope v0.1.2 发布留档

> **两栏结构**（与 `RELEASE-M6.md` 同构）：`§一` 写"tag 时点仓库内**已有**的事实"，写进 tag 树
> 也不自指失效；`§二` 只写 tag **之后**才产生的事实（tag 对象 OID / 包 sha256 / CI run id）。
> 纪律来源：`plan/05` §五 时序纪律 3 —— **tag 树内不写字面值**。

---

## 一、tag 前事实

tag 名 `v0.1.2`；注释式 tag（annotated）。版本单点 `src/crsscope/__init__.py` 的
`__version__ = "0.1.2"`（`pyproject` 用 `dynamic`，`tests/test_version.py` 4 条守门）。

### 1.1 本版做了什么（相对 `v0.1.1`）

这一版**不碰任何判定逻辑**（`src/crsscope/` 的 13 个判定/IO 模块全部零改动，唯一改动是
`__init__.py` 的版本字面量）。它是"把已经发现的缺陷修掉 + 给它们各配一道门"的一版。

| # | 项 | 修法 | 守门 |
|---|---|---|---|
| 1 | `v0.1.1` 的 Release **正文**写错版本号（写 `crsscope-0.1.0-*.whl`，附件是 `0.1.1`；照抄 `pip install` 直接 `No such file or directory`） | `gh release edit v0.1.1 --notes-file` 就地改 4 处（附件与 tag 一字节未动）；`--online` 新增判据 `REL.BODY_VERSION` | `tests/test_release_gate.py` 3 条（错版红 / 0 处红 / 全对绿） |
| 2 | `addopts = "-q"` 与读者敲的 `pytest -q` 叠加成 `-qq`，**汇总行被吞** | 删 `pyproject.toml` 的 `addopts`（`testpaths` 保留） | 无独立门：`pytest -q` 能打出汇总行本身就是证据（`grep -c passed` = 1） |
| 3 | README 最小复现把 `report.json` / `report.md` 落在仓库根，二者未被忽略 → 任何人照跑一遍得到脏树 | `.gitignore` 加 `/report.json` / `/report.md`（前导斜杠只锚仓库根） | `git check-ignore -v --no-index report.json report.md` rc=0 且两条各自命中 |
| 4 | 无 Python 下限的本地判据（`requires-python >=3.11` 只靠 CI 的 3.11 腿守；本机无 3.11，本地永远发现不了） | 新增 `tests/test_python_floor.py`：`ast.parse(source, feature_version=(3,11))` 逐文件解析 `src/` + `tests/` | 4 条：遍历（聚合报错 + 空跑守卫）、2 条 3.12 语法阳性对照、1 条合法 3.11 阴性对照 |
| 5 | 自述测试数三处漂移（文档写 321 / 318 / 16 / 30，实测 322 / 13 / 28），且错值随 sdist 发布 | 按实测改写 `plan/05` / `plan/06` / 本仓 `plan/RELEASE-M6.md`；HANDOFF-M1..M6 的 102/146/168/191/218/273 加时点限定（不改数字） | 新增 `tests/test_reported_counts.py` 3 条（对撞实测 / 禁 321·318 复活 / 文件读不到时必须红） |
| 6 | actions 落后两个大版本，每条 check-run 带 `Node.js 20 is deprecated` 注解 | `checkout@v4 → @v7`、`setup-python@v5 → @v7`（最新 v7.0.1 / v7.1.0） | CI 真跑（本地门只断言步骤名，不判 `uses` 版本） |
| 7 | GitHub topics 为空 | 一次 PUT 给全 8 个（PUT 是替换语义）：`geojson` `gcj02` `bd09` `crs` `gis` `python` `cli` `rfc7946` | `gh api repos/yuluo554/crsscope --jq '.topics'` 非空 |
| 8 | 外部事实无"何时复核"锚（D11） | `data/README.md` §5.1 登记 `review_interval = annual`、`next_review = 2027-10-28` + 四类到期必核对象（RFC 7946 / EPSG / 两库 `out_of_china`） | 无门（登记型）；纪律写在 §5.1 |

**D6 / D7 / D8 如实不修**（理由见 `update/00-诊断报告.md`，本轮定案）：

- **D6**：`MANIFEST.in` 的 `recursive-include .github *.yml *.yaml` 会打 4 条 `no files found` 告警。
  **不能简单删 `*.yaml`**：将来加 `.yaml` 工作流会静默漏进 sdist，而 `tests/test_layout_gate.py`
  要求"发布包形态下门必须能跑"。告警无害，保留容忍。
- **D7**：离线档在 `dist/` 在场时不核对"dist 与当前源码树一致"。`--online` 能抓"tag 树 ≠ 附件"，
  抓不到"工作树 ≠ 附件"。判据 P2：只在"发布者本机同时有旧 dist 与已改源码"时触发，本轮按
  时序纪律（构建晚于交付面定稿）规避，不改门。
- **D8**：遗留本地分支 `m5-geojson-tiles`（已完全合入 `main`、无远程对应）。**删不删是用户的决定**，
  执行方不自行删除。

### 1.2 tag 前的门禁事实

以下每条都是"tag 时点在本仓库上可复跑"的，不涉及任何 tag 后字面值。

| 项 | 事实 | 复核方式 |
|---|---|---|
| 全量测试 | `332 passed / 2 skipped`（334 collected；2 条 skip 是 `test_unimplemented_contract.py` 的 `empty parameter set`，刻意保留） | `py -3.12 -m pytest -o addopts=""` |
| `pytest -q` 可见汇总行 | 输出含 `332 passed, 2 skipped`（B1-1 之后） | `py -3.12 -m pytest -q` |
| 布局门 | 11 条判据全绿（文档 11 / 交接单 6 / 状态副本 2（状态行 12）/ 点名脚本 3 / 缺口行 5 / 台账行 21 / 发布留档 1） | `py -3.12 tools/check-sprint-layout.py` |
| 门变异 | 符合预期 10 / 不符 0 / 跳过 0 | `py -3.12 tools/mutate-layout-gate.py` |
| 发布门（离线） | 5 条判据全 PASS（`REL.DIST` 2 份产物文件名含 `0.1.2`；`REL.SUMS` 复核 2/2） | `py -3.12 tools/check-release.py` |
| 发布门（`--pre-tag`） | 判据全 PASS，含 `REL.TAG_ABSENT`："目标 tag `v0.1.2` 尚未创建" | `py -3.12 tools/check-release.py --pre-tag` |
| Python 下限 | `src/` + `tests/` 全部 `.py` 按 `feature_version=(3,11)` 解析通过（**本机无 3.11 解释器**，见 §三 未验证项） | `py -3.12 -m pytest -o addopts="" tests/test_python_floor.py` |
| 自述数字 | 三份现役文档的每个"数字 + passed"与"`test_xxx.py`（N 项）"都等于实测；`321 passed` / `318 passed` 零命中 | `py -3.12 -m pytest -o addopts="" tests/test_reported_counts.py` |
| 旧版正文 | `v0.1.1` 正文 4 处产物名已全为 `0.1.1`；`--online --tag v0.1.1` 9 条判据全 PASS | `py -3.12 tools/check-release.py --online --tag v0.1.1` |
| 语料可重建 | 8 份生成器 `--check` 全部逐字节一致 | `data/fixtures/*/gen.py --check` |

**构建产物**（tag 时点已在本地 `dist/`，附件由其上传）：

- `crsscope-0.1.2-py3-none-any.whl`
- `crsscope-0.1.2.tar.gz`
- `SHA256SUMS`（**不入仓**——包哈希是发布事实，写进 tag 树会自指失效；`.gitignore` 第 105 行）

---

## 二、tag 后追加

以下字面值**只能**出现在 tag 之后（本文件所在的提交晚于 `v0.1.2`）。

（待发布后填写：annotated tag OID / tag 指向的 commit / Release URL / 两个产物的 sha256 /
真下载复核结果 / 各次 CI run id 与结论 / `--online --tag v0.1.2` 的 9 条判据输出）

---

## 三、覆盖对账表（M7 出口判据）

| # | 出口判据 | 三态 | 证据 / 理由 |
|---|---|---|---|
| 1 | Release 正文与附件同版本，且有机器判据守着 | 实现 | `REL.BODY_VERSION`（`--online` 第 6 条判据）；守门 3 条在 `tests/test_release_gate.py` |
| 2 | `pytest -q` 能看见汇总行，且与 `-o addopts=""` 一致 | 实现 | 删 `addopts` 后两者都输出 `332 passed, 2 skipped` |
| 3 | 照 README 跑完最小复现，仓库根仍是干净树 | 实现 | `/report.json` `/report.md` 已入 `.gitignore`；`git status --porcelain` 为空 |
| 4 | 自述数字零漂移且有门 | 实现 | `tests/test_reported_counts.py` 3 条 + 真负控（改 999 → 红 → 还原） |
| 5 | 3.11 语法兼容有本地判据 | 实现（经 AST，非解释器） | `tests/test_python_floor.py` 4 条；**本机无 3.11，未实跑 3.11**（见未验证项） |
| 6 | 附件 sha256 三方一致，`--online` 9 条判据全 PASS | 待首推 | tag 后追加（§二） |
| 7 | CI 四组矩阵全绿且 Node20 弃用注解消失 | 待首推 | tag 后追加（§二） |
| 8 | topics 非空 | 实现 | `gh api repos/yuluo554/crsscope --jq '.topics'` → 8 个 |
| 9 | 外部事实有复核锚 | 实现 | `data/README.md` §5.1（`annual` / `2027-10-28`）+ `plan/00` 决策 ⑭ |

**三态统计**：实现 7 行 / 不适用 0 行 / 待首推 2 行（合计 9 行）。第七、八行在本版发布后填实。

### 未验证项（不许写成 PASS）

| # | 项 | 状态 | 原因 |
|---|---|---|---|
| U1 | Python 3.11 实跑 | **未验证** | 本机 `py -3.11` 不存在（实测 exit 103）。3.11 兼容性由 AST 判据（`feature_version=(3,11)`）+ CI 的 3.11 腿两处守，**都不是"本机 3.11 跑过"** |
| U2 | `actions/checkout@v7` / `setup-python@v7` 能否装 3.11 | **未验证（发布前）** | 升完必须真推一次看 CI；若 v7 装不上 3.11 则回退 `setup-python` 到 v5 并记录 |
| U3 | `v0.1.1` 的 `HANDOFF-M1..M5` 历史数字是否精确 | **只验两端点** | 实测 `0c5127f`（v0.1.0）=318、`556cf99`（v0.1.1）=322；中间 4 个里程碑提交未逐个 checkout 重跑（语义是"当时真值"，已加时点限定） |
| U4 | Ubuntu 26 迁移后 CI 是否仍绿 | **未验证** | 注解里只有 notice；未确认 runner 镜像版本 |
| U5 | 真实 GPS 轨迹 / 真实地理掩膜下的行为 | **不适用（项目形态）** | 仓库明确不做（见 `RELEASE-M6.md` §三 #9） |
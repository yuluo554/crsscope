# RELEASE-M6 · crsscope v0.1.1 发布留档

> **两栏结构**：`§一` 写"tag 时点仓库内**已有**的事实"（写进 tag 树也不自指失效的内容）；
> `§二` 总写 tag **之后**才产生的事实（tag 对象 OID / 包 sha256 / CI run id / Release URL）。
> 纪律来源：`plan/05` §五 时序纪律 3 —— **tag 树内不写字面值**。
>
> **两版事实**：`v0.1.0` 是先发的一版；其后发现 tag 树里的 `tools/check-release.py` 缺少归档
> 布局归一化（`--online` 档会报"共有文件 0 个"——判据读不懂 wheel/sdist 的目录形态），
> 故发布修订版 `v0.1.1`。`v0.1.0` 保留为历史 tag（不删除、不移动），`v0.1.1` 是**当前发布版**。

---

## 一、tag 前事实

tag 名 `v0.1.1`；注释式 tag（annotated）。以下事实在打 tag 的**那一刻**就已成立，可由 tag 树自身复核。

| 项 | 事实 | 复核方式 |
|---|---|---|
| 交付面 | 六个子命令全部落位：`decl` / `detect` / `xdiff` / `geojson` / `tiles` / `report` | `crsscope --help`；`tests/test_cli.py` |
| `report` | 多份 `report.json` 聚合 + 门禁；缺文件 → 3、坏 JSON/缺 `findings` → 4、灰区 → 5 | `tests/test_report.py`（13 项） |
| 契约表 | `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 已清空，并保留显式空表断言 | 该文件 |
| 发布门 | `tools/check-release.py` 三档在位（离线默认 / `--pre-tag` / `--online`） | `tests/test_release_gate.py`（v0.1.1 tag 时点 28 条用例；二次迭代加 `REL.BODY_VERSION` 后 **31** 项，见 §二 2.3） |
| 发布门归一化 | wheel（安装态 `crsscope/x.py`）与 sdist（`crsscope-<ver>/src/…`）都归一化到源树路径再比 | `test_wheel_layout_is_normalised_to_source_paths` / `test_sdist_container_directory_is_stripped` |
| 登记清理 | 布局门 `PENDING_TOOLS` 已删 `tools/check-release.py`；`AGENTS.md` §六同步 | `py -3.12 tools/check-sprint-layout.py` |
| 全量测试 | `332 passed / 2 skipped`（本机 3.12；**v0.1.1 tag 时点是 322**，二次迭代新增 10 条守门后为 332，加法见 §二 2.3） | `py -3.12 -m pytest -o addopts=""` |
| 布局门 | 11 条判据全绿（文档 11 / 交接单 6 / 状态副本 2 / 台账 21 行 / 发布留档 1） | `py -3.12 tools/check-sprint-layout.py` |
| 门变异 | 10 / 10 全部如期变红，0 SKIP | `py -3.12 tools/mutate-layout-gate.py` |
| 语料可重建 | 8 份生成器 `--check` 全部 exit 0（逐字节一致） | `data/fixtures/*/gen.py --check` |
| tag 前发布门 | `--pre-tag` 判据全 PASS（含"tag 尚未创建"前置事实） | `py -3.12 tools/check-release.py --pre-tag` |
| 离线发布门 | 5 条判据全 PASS（`SHA256SUMS` 复核 2/2） | `py -3.12 tools/check-release.py` |
| 零网络 | 运行时断网实跑：`sitecustomize` 审计钩子拦截 socket，三子命令 + `report` 行为不变 | `tests/test_offline_runtime.py`（6 项） |
| 双装态 | wheel 与 sdist 各装一次，跑同两条真命令 → 退出码相同，`report.json` / `report.md` 逐字节一致 | 见 §二 的复现命令 |

**构建产物**（tag 时点已在本地 `dist/`，附件由其上传）：

- `crsscope-0.1.1-py3-none-any.whl`
- `crsscope-0.1.1.tar.gz`
- `SHA256SUMS`（两条 `<sha256>  <文件名>`；**不入仓**——包哈希是发布事实，写进 tag 树会自指失效）

**v0.1.0 的已知缺陷**（本版修正，如实留档）：

- `v0.1.0` 树内的 `tools/check-release.py` 在比较"附件 × tag 树共有文件"时未做归档布局归一化：
  wheel 是安装态布局（`crsscope/x.py`），sdist 多一层 `crsscope-0.1.0/`，两者的相对路径与源树
  （`src/crsscope/x.py`）都对不上 → 交集恒为 0 → 判据以"共有文件 0 个（下限 5）"变红。
  该档当时在同一台机器上"通过"是因为修复发生在 tag 之后——**这正是发布门必须能在自己的
  tag 树上跑通的原因**：产物必须包含能核对自身的判据。

---

## 二、tag 后追加

以下字面值**只能**出现在 tag 之后（本文件所在的提交晚于 `v0.1.1`）。

### 2.1 当前发布版 `v0.1.1`

| 项 | 字面值 |
|---|---|
| annotated tag OID | `b521957847752359e8bf4b58ac984abab8b5115c` |
| tag 指向的 commit | `556cf990b82d7ea1eb43bdc25a380c9f02585c30`（`fix(release): v0.1.1 …`） |
| Release URL | <https://github.com/yuluo554/crsscope/releases/tag/v0.1.1> |
| Release 附件 | 3 份：wheel、sdist、`SHA256SUMS` |
| wheel sha256 | `bc07efb7850e7e3110421740a9776eaf991748001f7fc45d40c18d9588788315` |
| sdist sha256 | `616168b91fea4ed3fc8b7d7fe644a0d4d9baee7f8b84e77072fd9a1e8628ac93` |
| 真下载复核 | `gh release download v0.1.1` → `sha256sum -c SHA256SUMS` 两条 OK → 与原产物 `cmp` 三项逐字节一致 |
| 干净 venv 装下载件 | 全新 venv 装**下载来的** wheel → `0.1.1`；`geojson` / `tiles` / `report` 各跑一条真命令，退出码与源码态一致 |
| 在线发布门 | `py -3.12 tools/check-release.py --online --tag v0.1.1` → 8 条判据全 PASS（共有文件 76 个、逐字节不一致 0 个） |
| CI run（main push `556cf99`） | `40540733469` — success（windows/ubuntu × 3.11/3.12 四组全绿） |
| CI run（tag push `v0.1.1`） | `40540763666` — success（四组矩阵；日志含布局门 11 PASS、发布门 `REL.FILES` PASS / `REL.DIST` 0 份产物显式跳过、`smoke ok`、`contract ok (rc=2)`） |
| CI run（留档提交 `7930e2f`） | `40541180524` — success |

> **构建与 tag 的时序教训（第三版才做对）**：`v0.1.1` 第一次上传的附件是在**最后一次改码之前**
> 构建的——`--online` 档随即报出 3 个共有文件逐字节不一致（`tools/check-release.py`、
> `tests/test_release_gate.py`、`plan/05-里程碑与发布.md`）。这正是 `plan/05` §五 时序纪律 1
> 的实证：**构建必须晚于交付面定稿**。处置：把 tag 指向的提交 `556cf99` 从干净工作树重新构建
> 一次，再用 `gh release upload --clobber` 替换附件，重跑 `--online` 得 8/8。

### 2.2 历史版 `v0.1.0`（保留，不删除、不移动）

| 项 | 字面值 |
|---|---|
| annotated tag OID | `89caeffd8866946273bd669da7043cf64bef7f07` |
| tag 指向的 commit | `0c5127f08d2f2312ea9c7d5208be3ef74e3a006a`（`feat(report+release): M6 …`） |
| Release URL | <https://github.com/yuluo554/crsscope/releases/tag/v0.1.0> |
| wheel sha256 | `cb0c06bf2074680e090b2e67945270e1fbfba8475ef4f113cfcd613bd50878b4` |
| sdist sha256 | `2daed2d75d13e0b1e70e6137ed5363948698ba9590b385e0b2de8ebae74b5007` |
| 已知缺陷 | 树内 `tools/check-release.py` 缺归档布局归一化（`--online` 档报"共有文件 0 个"）；`--pre-tag` 档守的是"仓库里一个 tag 都没有"（发布过一版后永远无法通过）。两者均在 `v0.1.1` 修正 |
| CI run（main push） | `40537982093` — success（windows/ubuntu × 3.11/3.12 四组全绿） |
| CI run（tag push） | `40537994706` — success |

**复现双装态对拍**（在仓库外做，避免污染源树）：

```bash
py -3.12 -m venv /tmp/v-wheel && py -3.12 -m venv /tmp/v-sdist
/tmp/v-wheel/Scripts/pip install --no-index --find-links dist crsscope
/tmp/v-sdist/Scripts/pip install dist/crsscope-0.1.1.tar.gz      # 需 setuptools>=77（build isolation）
# 两态各跑同一组命令，再对拍报告字节
crsscope geojson data/fixtures/geojson_struct/out/case-001_ring_cw.geojson --strict-ring --out-dir /tmp/o
crsscope tiles   data/fixtures/tile_flip/out/tile_flip.json --out-dir /tmp/o
cmp /tmp/w/report.json /tmp/s/report.json && cmp /tmp/w/report.md /tmp/s/report.md
```

### 2.3 二次迭代（2026-10-28）对 `v0.1.1` 的追溯修正

`v0.1.1` 的**附件与 tag 一个字节未动**；以下是发布之后才发现、且可以在不重发的前提下修掉的部分。

| 项 | 事实 |
|---|---|
| Release 正文版本号 | §二 2.1 的正文原写 `crsscope-0.1.0-py3-none-any.whl` / `crsscope-0.1.0.tar.gz`（4 处），实际附件是 `0.1.1`——照抄 `pip install` 会 `No such file or directory`。**已用 `gh release edit v0.1.1 --notes-file` 就地改正文**，现 4 处全为 `0.1.1`；附件未动 |
| 新增判据 `REL.BODY_VERSION` | `--online` 档由 8 条判据变 **9** 条：抓正文里全部 `crsscope-<x.y.z>` 形态的产物名，要求**全部**等于 `read_version(root)` 且**至少命中 1 处**（0 处 = 判据空跑 = FAIL）。守门 3 条（错版红 / 0 处红 / 全对绿）在 `tests/test_release_gate.py` |
| 判据形态的一处修正 | 最初按"版本后紧跟 `-`"写正则，**实测只命中 2/4 处**（sdist 的 `crsscope-0.1.1.tar.gz` 版本号后是 `.`）。已放宽为"版本后紧跟 `-` 或 `.`"——这是**加严**（多抓不是少抓），不是放宽 |
| 自述测试数字的口径 | 本表 §一 的 `321` / `16` / `30` 与 `plan/05` / `plan/06` 的 `318` 均为错值；实测 v0.1.1 tag 时点是 **322 条用例**（13 / 28 两个分文件数同实测），二次迭代加 10 条守门后为 **332 passed**（+3 `REL.BODY_VERSION`、+4 `test_python_floor`、+3 `test_reported_counts`）。现已全部按实测改写，并新增 `tests/test_reported_counts.py` 三条自指守门 |
| 为什么留 `v0.1.1` 不改 tag | 错值在 tag 树与 sdist 里，但改 tag 会让已下载者手上的 sha256 失效；**新版本 `v0.1.2` 承载修正后的树**（见 `plan/RELEASE-M7.md`） |

---

## 三、阶段 7 覆盖对账表

对账对象 = M6 出口判据（`plan/05` §三「M6 发布」）逐条 ↔ 证据。**三态**：
`实现`（有可复跑证据）/ `不适用`（该判据在本项目形态下不成立，须给出理由）/ `待首推`（尚无远端证据）。

| # | M6 出口判据 | 三态 | 证据 / 理由 |
|---|---|---|---|
| 1 | `tools/check-release.py` 三档：`--pre-tag` / 离线默认 / `--online` | 实现 | `tests/test_release_gate.py` 31 项（v0.1.1 tag 时点是 28 条用例，二次迭代加 3 条 `REL.BODY_VERSION` 守门）；三档各实跑：`--pre-tag` 6 PASS、离线 5 PASS、`--online` **9** PASS（新增 `REL.BODY_VERSION`） |
| 2 | 干净环境：真下载附件 → 中立目录解包 → 逐条敲 README | 实现 | §二 2.1「真下载复核」+「干净 venv 装下载件」；`sha256sum -c` 两条 OK、`cmp` 三项一致 |
| 3 | 附件与 `git archive <tag>` 解包树的共有文件逐字节相等（不是 `diff -r` 零差异） | 实现 | `--online --tag v0.1.1` 的 `REL.COMMON_FILES`：共有文件 76 个（下限 5）、不一致 0 个；归一化逻辑由 `test_wheel_layout_is_normalised_to_source_paths` / `test_sdist_container_directory_is_stripped` / `test_normalised_common_file_mismatch_is_still_caught` 守 |
| 4 | 断网跑通（`docker run --network none` 或用 `--offline` 冒烟） | 实现（`--offline` 冒烟通道） | 本机无 docker（`docker: command not found`，2026-10-27 实测）→ 走 PLAN 允许的第二通道并加强：`sitecustomize` 审计钩子拦截全部 `socket.*`，含阳性探活；`tests/test_offline_runtime.py` 6 项 |
| 5 | `plan/RELEASE-M6.md` 两栏 + 阶段 7 覆盖对账表 | 实现 | 本文件 §一 / §二 / §三 |
| 6 | GitHub **公开**仓库 + tag + Release 附产物 | 实现 | <https://github.com/yuluo554/crsscope>（public）；annotated tag `v0.1.1`；Release 3 份附件 |
| 7 | CI 首推全绿（`plan/05` §四"CI 实跑"翻 ✅ 的前提） | 实现 | run `40537982093`（main）/ `40537994706`（tag），四组矩阵 success；日志含布局门 11 PASS、发布门 5 PASS、`smoke ok`、`contract ok (rc=2)` |
| 8 | 跨 Python 版本行为（3.11 与 3.12） | 实现（经 CI） | 本机只有 3.12 参与验证；CI 矩阵在 3.11 与 3.12 上各跑全量测试，均 success |
| 9 | 真实地理掩膜 / 真实 GPS 轨迹回归 | 不适用 | 项目形态决定：首期掩膜是 1° 构造网格（不承诺海岸线准确性）；真实轨迹属隐私红线（脱敏不可验证），永不接受 |
| 10 | 地图渲染 / 切片 / 图片产出 | 不适用 | 形态唯一：本工具只做判定与证据输出，不做渲染（`plan/01` §边界与非目标） |
| 11 | Release 正文与附件同版本（二次迭代新增的出口判据） | 实现 | `REL.BODY_VERSION`（`--online` 第 6 条判据）：正文 4 处产物名全为当前版本；守门 3 条在 `tests/test_release_gate.py`；`v0.1.1` 原错版已就地修正，见 §二 2.3 |

**三态统计**：实现 9 行 / 不适用 2 行 / 待首推 0 行（合计 11 行）。

---

## 四、遗留与下一轮入口

- **无未完成里程碑**：M1–M6 全部 ✅。不需要 `plan/HANDOFF-M7.md`。
- **本机未验证项**（如实记录，不得写成绿）：
  - `docker run --network none` 通道未用过（本机无 docker）；断网证据来自审计钩子通道。
  - 真实地理掩膜与真实 GPS 轨迹回归：项目形态决定不做（见 §三 #9）。
- **发布门重跑入口**：任何时候可跑离线档；`--pre-tag` 在**目标 tag** 已存在后会**必红**（这是设计，
  目标名缺省按版本推 `v<version>`，也可 `--tag` 显式给），核对已发布事实请用 `--online --tag v0.1.1`。
- **两次时序教训**（都记在这里，避免下一棒重犯）：
  1. 产物必须**能核对自身**：`v0.1.0` 的 tag 树里带着有缺陷的发布门，判据在自身上跑不通。
  2. 构建必须**晚于交付面定稿**：`v0.1.1` 首次上传的附件是在最后一次改码前构建的，`--online`
     立刻报出 3 个文件字节不一致；重建并 `--clobber` 替换后才得 8/8。

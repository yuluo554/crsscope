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
| `report` | 多份 `report.json` 聚合 + 门禁；缺文件 → 3、坏 JSON/缺 `findings` → 4、灰区 → 5 | `tests/test_report.py`（16 项） |
| 契约表 | `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 已清空，并保留显式空表断言 | 该文件 |
| 发布门 | `tools/check-release.py` 三档在位（离线默认 / `--pre-tag` / `--online`） | `tests/test_release_gate.py`（30 项） |
| 发布门归一化 | wheel（安装态 `crsscope/x.py`）与 sdist（`crsscope-<ver>/src/…`）都归一化到源树路径再比 | `test_wheel_layout_is_normalised_to_source_paths` / `test_sdist_container_directory_is_stripped` |
| 登记清理 | 布局门 `PENDING_TOOLS` 已删 `tools/check-release.py`；`AGENTS.md` §六同步 | `py -3.12 tools/check-sprint-layout.py` |
| 全量测试 | `321 passed / 2 skipped`（本机 3.12） | `py -3.12 -m pytest -o addopts=""` |
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

以下字面值**只能**出现在 tag 之后（本文件所在的提交晚于 `v0.1.0`）。

| 项 | 字面值 |
|---|---|
| annotated tag OID | `89caeffd8866946273bd669da7043cf64bef7f07` |
| tag 指向的 commit | `0c5127f08d2f2312ea9c7d5208be3ef74e3a006a`（`feat(report+release): M6 …`） |
| Release URL | <https://github.com/yuluo554/crsscope/releases/tag/v0.1.0> |
| Release 附件 | 3 份：wheel、sdist、`SHA256SUMS` |
| wheel sha256 | `cb0c06bf2074680e090b2e67945270e1fbfba8475ef4f113cfcd613bd50878b4` |
| sdist sha256 | `2daed2d75d13e0b1e70e6137ed5363948698ba9590b385e0b2de8ebae74b5007` |
| CI run（main push） | `40537982093` — success（windows/ubuntu × 3.11/3.12 四组全绿） |
| CI run（tag push） | `40537994706` — success |
| 真下载复核 | `gh release download` → `sha256sum -c SHA256SUMS` 两条 OK → 与原产物 `cmp` 三项逐字节一致 |
| 干净 venv 装下载件 | 全新 venv 装下载来的 wheel → `0.1.0`；`geojson` / `tiles` / `report` 各跑一条真命令，退出码与源码态一致 |
| 在线发布门 | `py -3.12 tools/check-release.py --online --tag v0.1.0` → 8 条判据全 PASS（共有文件 74 个、逐字节不一致 0 个） |

**复现双装态对拍**（在仓库外做，避免污染源树）：

```bash
py -3.12 -m venv /tmp/v-wheel && py -3.12 -m venv /tmp/v-sdist
/tmp/v-wheel/Scripts/pip install --no-index --find-links dist crsscope
/tmp/v-sdist/Scripts/pip install dist/crsscope-0.1.0.tar.gz      # 需 setuptools>=77（build isolation）
# 两态各跑同一组命令，再对拍报告字节
crsscope geojson data/fixtures/geojson_struct/out/case-001_ring_cw.geojson --strict-ring --out-dir /tmp/o
crsscope tiles   data/fixtures/tile_flip/out/tile_flip.json --out-dir /tmp/o
cmp /tmp/w/report.json /tmp/s/report.json && cmp /tmp/w/report.md /tmp/s/report.md
```

---

## 三、阶段 7 覆盖对账表

对账对象 = M6 出口判据（`plan/05` §三「M6 发布」）逐条 ↔ 证据。**三态**：
`实现`（有可复跑证据）/ `不适用`（该判据在本项目形态下不成立，须给出理由）/ `待首推`（尚无远端证据）。

| # | M6 出口判据 | 三态 | 证据 / 理由 |
|---|---|---|---|
| 1 | `tools/check-release.py` 三档：`--pre-tag` / 离线默认 / `--online` | 实现 | `tests/test_release_gate.py` 27 项；三档各实跑：`--pre-tag` 6 PASS、离线 5 PASS、`--online` 8 PASS |
| 2 | 干净环境：真下载附件 → 中立目录解包 → 逐条敲 README | 实现 | §二「真下载复核」+「干净 venv 装下载件」；`sha256sum -c` 两条 OK、`cmp` 三项一致 |
| 3 | 附件与 `git archive <tag>` 解包树的共有文件逐字节相等（不是 `diff -r` 零差异） | 实现 | `--online` 档 `REL.COMMON_FILES`：共有文件 74 个（下限 5）、不一致 0 个；归一化逻辑由 `test_wheel_layout_is_normalised_to_source_paths` / `test_sdist_container_directory_is_stripped` 守 |
| 4 | 断网跑通（`docker run --network none` 或用 `--offline` 冒烟） | 实现（`--offline` 冒烟通道） | 本机无 docker（`docker: command not found`，2026-10-27 实测）→ 走 PLAN 允许的第二通道并加强：`sitecustomize` 审计钩子拦截全部 `socket.*`，含阳性探活；`tests/test_offline_runtime.py` 6 项 |
| 5 | `plan/RELEASE-M6.md` 两栏 + 阶段 7 覆盖对账表 | 实现 | 本文件 §一 / §二 / §三 |
| 6 | GitHub **公开**仓库 + tag + Release 附产物 | 实现 | <https://github.com/yuluo554/crsscope>（public）；annotated tag `v0.1.0`；Release 3 份附件 |
| 7 | CI 首推全绿（`plan/05` §四"CI 实跑"翻 ✅ 的前提） | 实现 | run `40537982093`（main）/ `40537994706`（tag），四组矩阵 success；日志含布局门 11 PASS、发布门 5 PASS、`smoke ok`、`contract ok (rc=2)` |
| 8 | 跨 Python 版本行为（3.11 与 3.12） | 实现（经 CI） | 本机只有 3.12 参与验证；CI 矩阵在 3.11 与 3.12 上各跑全量测试，均 success |
| 9 | 真实地理掩膜 / 真实 GPS 轨迹回归 | 不适用 | 项目形态决定：首期掩膜是 1° 构造网格（不承诺海岸线准确性）；真实轨迹属隐私红线（脱敏不可验证），永不接受 |
| 10 | 地图渲染 / 切片 / 图片产出 | 不适用 | 形态唯一：本工具只做判定与证据输出，不做渲染（`plan/01` §边界与非目标） |

**三态统计**：实现 8 行 / 不适用 2 行 / 待首推 0 行（合计 10 行）。

---

## 四、遗留与下一轮入口

- **无未完成里程碑**：M1–M6 全部 ✅。不需要 `plan/HANDOFF-M7.md`。
- **本机未验证项**（如实记录，不得写成绿）：
  - `docker run --network none` 通道未用过（本机无 docker）；断网证据来自审计钩子通道。
  - 真实地理掩膜与真实 GPS 轨迹回归：项目形态决定不做（见 §三 #9）。
- **发布门重跑入口**：任何时候可跑离线档；`--pre-tag` 在 tag 已存在后会**必红**（这是设计），
  核对已发布事实请用 `--online --tag v0.1.0`。

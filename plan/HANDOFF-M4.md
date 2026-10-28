# HANDOFF-M4 · 下一步：模块 M3「跨实现差分」

> 用法：新对话 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M4.md" 继续完成任务`
> **第一动作（硬约束③）**：先跑布局门 `py -3.12 tools/check-sprint-layout.py`，必须全绿再动手。

---

## 一、当前进度 + 证据

| 项 | 状态 | 证据（2026-10-27 实测） |
|---|---|---|
| 题面定稿 / 计划 00–06 | ✅ | `plan/00`–`plan/06` 齐备 |
| 方法论装订 + 布局门（10 判据） | ✅ | `py -3.12 tools/check-sprint-layout.py` → 全绿 |
| 门变异验证 | ✅ | `py -3.12 tools/mutate-layout-gate.py` → **10/10 符合预期 / 0 SKIP** |
| 里程碑 M1 数据先行 | ✅ | 七份 fixture + 掩膜；8 份生成器 `--check` exit 0 逐字节一致 |
| 里程碑 M2 声明-内容一致性 | ✅ | `crsscope decl` 五项判据落位 |
| **里程碑 M3 GCJ 检测与残差** | ✅ **本轮完成** | `crsscope detect` 六环节落位；D2 复现（GCJ02 落水率 0.0 / WGS84·BD09 1.0，`confidence: high`）；`out_of_coverage` 不硬判；`residual.kind` 三段集合相等；两库 profile 结论可不同 |
| 测试 | ✅ | `py -3.12 -m pytest` → **191 passed**（M4 时点；当前见 `plan/05`）（骨架 168 + detect 23） |
| CI | ⬜ **待首推验证** | `.github/workflows/ci.yml` 已写，**从未被 GitHub 跑过** |
| 判定逻辑（模块 M3–M5 对应里程碑 M4–M5） | ⬜ 未实现 | `xdiff` / `geojson` / `tiles` / `report` 一律 exit 3 + `not implemented` |

**M4 = 模块 M3 `xdiff.py`「跨实现差分」**（`plan/03` §三；编号差一位，见 `plan/00` 决策 ⑨）。

---

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

### 2.1 本轮新增（M3 判定侧）

1. **`detect.run(path, declared_crs, mask_path=None)`** 与 `cli._run_detect` 已接好；掩膜缺失 /
   步长 > 1° 即 `EnvironmentMissing` → exit 3（**不得**默认"全是陆地"）。
2. **`algorithms.distance_to_bbox_deg` 已改为"到矩形边的真距离"**（原实现对框内点恒返回 0，
   "距边界 < 0.05°"会把**所有框内点**算进边界带 → 判据失效）。M4 若再用它做边界带判定，语义已是新的。
3. **`detect` 的候选假设固定 `("WGS84","GCJ02","BD09")`**（`algorithms.HYPOTHESES`），不增不减；
   残差三段固定 `("formula_approximation","vendor_divergence","boundary_jump")`。
4. **`declared(h)` 只作证据**：声明 4326 时 GCJ02 / BD09 各扣 `0.30`，不替判定翻案。
5. **每实现一个未实现子命令，必须从 `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED`
   删掉对应条目**（`detect` 已删）；靶子过期 = 判据失效。

### 2.2 跨实现差分（M4 将用到的既有件）

6. **三个实现已全部本地重实现**（`src/crsscope/algorithms.py`），**不调用外部服务、无三方依赖**：
   - `gcj02_to_wgs84_linear`（`coordTransform_py` 口径，**一步线性近似**，
     `return [lng*2 - mglng, lat*2 - mglat]`）；
   - `gcj02_to_wgs84_iterative`（`gcoord` 口径，**定点迭代**，容差 `INVERSE_TOLERANCE_DEG = 1e-6`）；
   - 两套边界框常数 `CT_PY_BBOX`（**开区间**）/ `GCOORD_BBOX`（**闭区间**），**不合并、不取并集**。
7. **`InverseResult.converged`**：迭代超 `INVERSE_MAX_ITER` 即 `converged=False`——
   M4 **必须**把 `not_converged` 报进结果里，**不得**静默返回一个"看起来对"的值（题面 §M3 纪律）。
8. **语料 `boundary_divergence/`** 的金标里 `expected.boundary_table_row` 与 `xdiff` 的
   `boundary_table` 行**同形**（`plan/04` §一 / `gen.py` 注释明写），M4 可直接逐字段对拍。
   四例：`(73.2,39.5)` 经向分歧 / `(112.0,2.0)` 纬向分歧 / `(112.0,5.0)` 一致 / `(112.0,60.0)` 一致。
9. **`boundary_divergence/gen.py` 内联了两套边界框常数，故意不 import `algorithms`**——
   改它之前先读 `plan/04` §二「参考实现三落点位」（金标复用生产实现 = 用被测物证明被测物）。

### 2.3 门与文档侧（三轮踩过的坑）

10. **台账状态列的编号是里程碑号**（不是模块号）。翻里程碑 ✅ 时，台账里**不许**留"模块 Mx"字样。
11. **布局门 `PENDING_TOOLS`**：`tools/check-release.py` 登记为 M6 落位，M6 翻 ✅ 时必须删除该条。
12. **`.gitignore` 的裸目录名匹配**曾把 `data/mask/` 吞掉（已改成锚定根 `/mask/`）——新增忽略规则时警惕。
13. **`tests/conftest.py` 的补齐判据是"产物目录缺件"**，不是"`expect.json` 缺件"（后者永不触发）。
14. **`exit 3 + not implemented` 是未实现子命令的硬契约**。每实现一个，**必须**从
    `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 表删掉对应条目。

---

## 三、下一棒待办（M4：模块 M3 跨实现差分）

按顺序做。**对照实现固定三个、常数原样照录**（`plan/03` §三）。

1. **实现 `src/crsscope/xdiff.py` 的 `run(path, target)`**（接口见 `plan/03` §三；
   `run(path, target)` 已在 `cli._run_xdiff` 里接好）。
2. **三个实现的常数与判据原样照录，注释给出 `data/README.md` §1.3 出处**；
   `target ∈ {wgs84, gcj02, bd09, webmercator}` 非法 → exit 2（`UsageError`），
   文件缺失 → exit 3（`EnvironmentMissing`）。
3. **`pairwise` 给 `median_m` / `max_m` / `p95_m`，且对 `max_m` 附该点坐标**（§4.4；
   距离只走 `geodesy.haversine_m`，**禁止**平面欧氏）。
4. **`boundary_table` 逐行对拍 `data/fixtures/boundary_divergence/expect.json` 的
   `expected.boundary_table_row`**：`(73.2,39.5)` / `(112.0,2.0)` 两库结论不同，
   `(112.0,5.0)` / `(112.0,60.0)` 一致（`plan/05` §三 M4 DoD）。
5. **`jumps`**：两库对"是否偏移"给出相反结论的坐标 → `reason: "out_of_china 边界内外跳变"`。
6. **`not_converged` 必须出现在结果里**（构造极端输入触发迭代超上限），**不得**抛未捕获异常
   （`plan/03` §三 失败路径）。
7. **`xdiff` 的 findings 用「一项一责」**（照 `decl.py` / `detect.py` 抄形状）。
8. **从 `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 删掉 `"xdiff": "M4"`**，
   并同步 `ARGS`。
9. **新增 `tests/test_xdiff.py`**：吃真实语料 `boundary_divergence`（四例逐字段对拍金标），
   断言两库分歧/一致、`not_converged` 出现在结果里、`pairwise` 的量级可解释、退出码。
10. **收尾**：`plan/05` §一 M4 翻 ✅、`plan/00` 里程碑表同步翻 ✅、台账对应行翻 ✅、
    `plan/06` 缺口表加/改行（**缺口列不得出现已 ✅ 的里程碑号**）、写 `plan/HANDOFF-M5.md`、commit。

**M4 出口判据**（`plan/05` §三）：`(73.2, 39.5)` 与 `(112.0, 2.0)` 两类分歧都报出；
`(112.0, 5.0)` / `(112.0, 60.0)` 报一致；迭代不收敛（构造极端输入）→ `not_converged`
出现在结果里，不抛未捕获异常。

---

## 四、既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 谁在守 |
|---|---|---|
| K01 | 退出码优先级 `2→3→4→5→1→0`，只在 `errors.py` 一处定义 | `tests/test_cli.py` + `tests/test_unimplemented_contract.py` |
| K02 | 版本单点 = `__init__.__version__`，pyproject 用 `dynamic` | `tests/test_version.py` |
| K03 | `DECLARED_CRS_CHOICES = ("4326","3857","4490","crs84")`，**GCJ-02/BD-09 不是合法声明值** | `tests/test_cli.py::test_parser_exposes_all_declared_crs_choices` |
| K04 | `algorithms.KRASOVSKY_A == 6378245.0`、`EE == 0.006693421622965823`、`INVERSE_TOLERANCE_DEG == 1e-6` | `tests/test_core.py::test_krasovsky_constants_are_verbatim` |
| K05 | 两库边界：`CT_PY_BBOX` 开区间、`GCOORD_BBOX` 闭区间 | `tests/test_core.py` + `tests/test_fixtures.py` 独立复算 |
| K06 | 距离只走 `geodesy.haversine_m`，`R = 6371008.8` | `tests/test_core.py` |
| K07 | `MaskStats.water_ratio` 无分母时返回 `None`（**不许**返回 0.0） | `tests/test_core.py::test_water_ratio_is_none_when_nothing_evaluable` |
| K08 | `mask.MAX_RESOLUTION_DEG = 1.0`，超限抛 `EnvironmentMissing`（exit 3） | `tests/test_core.py::test_mask_rejects_resolution_above_cap` |
| K09 | `report.TIMESTAMP_FIELD == "generated_at"` 且报告里**只能有一个**时间戳字段 | `tests/test_determinism.py::test_only_one_timestamp_field_in_payload` |
| K10 | 未实现子命令必须 exit 3 + 含 `not implemented` | `tests/test_unimplemented_contract.py` |
| K11 | `crs` 措辞只准 "no longer used"，读者面不得出现断言式禁用表述 | `tests/test_wording.py` |
| K12 | `io` 层拒绝含 `<!DOCTYPE` / `<!ENTITY` 的 XML（GPX 安全） | `tests/test_io.py::test_xml_with_dtd_or_entity_is_rejected` |
| K13 | `--check` 对生成物**允许缺席**，对 `expect.json` **缺件即 FAIL** | `data/_genlib.FixtureRun._check` + `tests/test_fixtures.py` |
| K14 | `expect.json` 顶层键 = `{fixture, generator_version, cases}` ∪ 白名单 | `tests/test_fixtures.py::test_expect_json_has_required_keys` |
| K15 | 「命中」= `conflict`/`error`（默认），`--fail-on` 收窄；**灰区优先** → `undecidable` 即 5 | `errors.outcome_code` + `tests/test_decl.py::test_outcome_code_default_states` |
| K16 | `warning` 默认**不**算命中；升级只能 `--strict-ring` / `--fail-on` 点名 | `tests/test_decl.py::test_fail_on_narrows_the_hit_set` |
| K17 | `decl` 的检查项**一项一责**：`extent` 读 `axis` 的 orientation | `tests/test_decl.py::test_swapped_axis_hits_axis_conflict_only` |
| **K18** | `detect` 六环节固定顺序、四项 findings **一项一责**（coverage / hypothesis / residual / boundary_profiles） | `tests/test_detect.py::test_findings_follow_fixed_check_order` |
| **K19** | `distance_to_bbox_deg` = **到矩形边的真距离**（框内非 0） | `tests/test_detect.py` + `plan/05` §二之三 实测结论 2 |
| **K20** | 默认 1° 掩膜复现不了 D2（并列第一 → `undecidable`）；D2 **必须**用 `water_track` 自带细网格 | `tests/test_detect.py::test_default_mask_rejects_gcj_offset_only_undecidable` |

---

## 五、本机环境坑（只写实测过的，2026-10-27）

- **`python` 是商店占位符**，一律用 `py -3.12`。
- **本机 3.8 通道不参与验证**（项目下限 3.11）；3.11 行为差异只能靠 CI。
- **setuptools 84.2.1**：`license = "MIT"` 表达式可用；**license classifier 会直接报错**。
- **Bash 直接解包 sdist 会被安全扫描拦截**（解包会写 `.py`）。干净环境验证走
  `pip install <wheel|sdist>` 这条通道，**不要** `tar -xzf` 到工作区。
- **离线装 sdist 会卡在 build isolation**：`pip install --no-index <sdist>` 在全新 venv 里
  要现取 `setuptools>=77`，取不到就报错。两个可行通道：① 带网络 `pip install <sdist>`；
  ② **装 wheel**（`--no-index --find-links dist crsscope`，零 build 依赖）。
- **`py -3.12 -m pytest` 输出没有 `passed` 汇总行**（`addopts = -q` 吞掉了）；
  要计数用 `py -3.12 -m pytest -o addopts=""`。
- **跑 `crsscope <cmd>` 会往 CWD 落 `report.json` / `report.md`**（`--out-dir` 默认当前目录）；
  写测试时**一律**传 `--out-dir tmp_path`，否则会把报告写进仓库根。
- **`data/mask/out/mask_v1.json` 约 3 MB**（61200 格单行 JSON）。`--check` 会整读整比，单次约 0.4 s；
  **不要**把它接进逐测试的循环里。
- **Node v24.15.0 存在**，但本仓库的门**故意用 Python 写**（`tools/*.py`），不引入 Node 依赖。
- `gh` 2.93.0 可用；git 身份 `yuluo554 <282769740+yuluo554@users.noreply.github.com>`。

---

## 六、DoD 逐项 checklist（M4）

- [ ] `xdiff.py` 的 `run()` 落位：三实现对照 + `pairwise` + `boundary_table` + `jumps`
- [ ] `(73.2, 39.5)` / `(112.0, 2.0)` 两 profile 结论不同并被报出；`(112.0, 5.0)` / `(112.0, 60.0)` 报一致
- [ ] `boundary_table` 逐行对拍 `boundary_divergence/expect.json` 的 `boundary_table_row`
- [ ] 迭代不收敛 → `not_converged` 出现在结果里，**不抛**未捕获异常
- [ ] `pairwise` 的 `median_m` / `max_m` / `p95_m` 齐；`max_m` 附该点坐标；距离走 `haversine_m`
- [ ] `UNIMPLEMENTED` 表里删掉 `xdiff`
- [ ] 布局门全绿、变异 10/10、pytest 全绿（计数从 191 起涨）
- [ ] `python -m build` 成功；干净 venv 装 sdist 后 `crsscope --help` 正常
- [ ] `plan/00` 与 `plan/05` 的 M4 状态同提交翻 ✅（**台账里别留"模块 M4"字样**）
- [ ] `plan/HANDOFF-M5.md` 已写

---

## 七、关键命令速查

```bash
py -3.12 tools/check-sprint-layout.py            # 布局门：0 全绿 / 1 FAIL / 2 用法
py -3.12 tools/mutate-layout-gate.py             # 门变异：10 组必须全红
py -3.12 tools/mutate-layout-gate.py --only m04  # 只跑一组
py -3.12 -m pytest -o addopts=""                 # 全量（要汇总行别加 -q）
py -3.12 -m pytest tests/test_detect.py -q       # 已落位的判定守门
py -3.12 -m crsscope --help                      # CLI 面
py -3.12 -m crsscope detect data/fixtures/water_track/out/water_track.gpx \
    --mask data/fixtures/water_track/out/water_track_mask.json --json --out-dir /tmp/o
py -3.12 -m build                                # 构建 dist/

# 语料（8 份生成器，全部 --check 必须 exit 0）
py -3.12 data/fixtures/four_crs/gen.py --check
py -3.12 data/fixtures/swapped_axis/gen.py --check
py -3.12 data/fixtures/declared_lie/gen.py --check
py -3.12 data/fixtures/boundary_divergence/gen.py --check
py -3.12 data/fixtures/water_track/gen.py --check
py -3.12 data/fixtures/tile_flip/gen.py --check
py -3.12 data/fixtures/geojson_struct/gen.py --check
py -3.12 data/mask/gen.py --check
```
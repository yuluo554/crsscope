# HANDOFF-M3 · 下一步：模块 M2「GCJ-02 / BD-09 检测与残差」

> 用法：新对话 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M3.md" 继续完成任务`
> **第一动作（硬约束③）**：先跑布局门 `py -3.12 tools/check-sprint-layout.py`，必须全绿再动手。

---

## 一、当前进度 + 证据

| 项 | 状态 | 证据（2026-10-27 实测） |
|---|---|---|
| 题面定稿 / 计划 00–06 | ✅ | `plan/00`–`plan/06` 齐备 |
| 方法论装订 + 布局门（10 判据） | ✅ | `py -3.12 tools/check-sprint-layout.py` → 全绿 |
| 门变异验证 | ✅ | `py -3.12 tools/mutate-layout-gate.py` → **10/10 符合预期 / 0 SKIP** |
| 里程碑 M1 数据先行 | ✅ | 七份 fixture + 掩膜；8 份生成器 `--check` exit 0 逐字节一致 |
| **里程碑 M2 声明-内容一致性** | ✅ **本轮完成** | `crsscope decl` 五项判据落位；`swapped_axis` / `declared_lie` 各自命中 |
| 测试 | ✅ | `py -3.12 -m pytest` → **168 passed**（骨架 104 + 语料契约 40 + decl 24） |
| CI | ⬜ **待首推验证** | `.github/workflows/ci.yml` 已写，**从未被 GitHub 跑过** |
| 判定逻辑（模块 M2–M5 对应里程碑 M3–M5） | ⬜ 未实现 | `detect` / `xdiff` / `geojson` / `tiles` / `report` 一律 exit 3 + `not implemented` |

**M3 = 模块 M2 `detect.py`「偏移检测与残差」**（`plan/03` §二；编号差一位，见 `plan/00` 决策 ⑨）。

---

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

### 2.1 本轮新增（M2 判定侧）

1. **退出码在 `cli._emit()` 一次性折算**，判定模块**不认识** `--fail-on` / `--allow-undecidable`。
   `detect.run()` 照旧只产出 `findings` + `payload`；`ModuleResult.exit_code` 由 CLI 覆盖。
2. **「命中」的定义写死在 `data/README.md` §4.9 + `plan/00` 决策 ⑪**：
   `conflict` / `error` 级发现**默认即命中 → 1**；`--fail-on` 给定时**收窄**为只认点名的类别
   （类别名匹配发现的 `status` / `reason` / `check` 三者任一）。
3. **灰区优先于命中**：`undecidable` 一出现即 `5`（除非 `--allow-undecidable`），
   同一结果集里另有 `conflict` 也**不**吞掉灰区。实测：`declared_lie` 裸跑 → 5，
   加 `--allow-undecidable` → 1（`tests/test_decl.py::test_declared_lie_hits_magnitude_conflict_only`）。
4. **`warning` 默认不算命中**（`errors.DEFAULT_HIT_STATUSES = {conflict, error}`）——
   否则 §4.6 的 R1 默认 warning 会把历史数据判成失败，违反"分级而非拒绝"。
   `detect` 的 `boundary_jump` 标记若要用 warning 级，**必须**走 `--fail-on` 点名。
5. **`errors.outcome_code(findings, fail_on=…, allow_undecidable=…)`** 是 `5→1→0` 的唯一实现；
   `2/3/4` 仍走异常。新增退出语义只改 `data/README.md` §4.9 与这里。
6. **`decl.py` 的「一项一责」形状可直接搬到 `detect.py`**：每个检查项只回答一件事，
   后判的项可以读先判项的结论（`extent` 读 `axis` 的 orientation），但**不许**重复判同一件事。

### 2.2 语料侧（M1 既有，改它会大面积打挂测试）

7. **共享生成器框架 = `data/_genlib.py`**，`--out` / `--check` 的**唯一**实现。
   各 `data/fixtures/*/gen.py` 只写 `build()`。**不要在某个 fixture 里另起一套 `--check`**。
8. **`expect.json` 的顶层键受测试约束**（`tests/test_fixtures.py`）：必备
   `fixture` / `generator_version` / `cases`；可选 `notes` / `track` / `mask` / `coverage` / `expected` / `rfc`。
   **加新顶层键必须同时改 `EXPECT_OPTIONAL_KEYS`**。
9. **金标里禁止 `observed` 类字段**（`observed` / `actual` / `measured` / `observed_value` / `actual_value`）。
10. **`water_track` 自带细网格**（`resolution_deg = 0.0008`，约 89 m）：1° 默认网格**复现不了 D2**
    （GCJ 位移 250–600 m 跨不过 111 km 的格线）。跑 `detect` 必须显式传
    `--mask data/fixtures/water_track/out/water_track_mask.json`。
11. **默认掩膜 = `data/mask/out/mask_v1.json`**（1°，61200 格，构造网格非地理真值）。
    `mask.load_mask` 要的字段：`version` / `resolution_deg` / `lon_min` / `lat_min` / `n_lon` / `n_lat` / `cells`。
    它约 3 MB，**不要**接进逐测试的循环里。
12. **`boundary_divergence/gen.py` 内联了两套边界框常数，故意不 import `algorithms`**——
    改它之前先读 `plan/04` §二「参考实现三落点位」（金标复用生产实现 = 用被测物证明被测物）。

### 2.3 门与文档侧（两轮踩过的坑）

13. **台账状态列的编号是里程碑号**（不是模块号）。翻里程碑 ✅ 时，台账里**不许**留"模块 Mx"字样。
14. **布局门 `PENDING_TOOLS`**：`tools/check-release.py` 登记为 M6 落位，M6 翻 ✅ 时必须删除该条。
15. **`.gitignore` 的裸目录名匹配**曾把 `data/mask/` 吞掉（已改成锚定根 `/mask/`）——新增忽略规则时警惕。
16. **`tests/conftest.py` 的补齐判据是"产物目录缺件"**，不是"`expect.json` 缺件"（后者永不触发）。
17. **`exit 3 + not implemented` 是未实现子命令的硬契约**。每实现一个，**必须**从
    `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 表删掉对应条目（靶子过期 = 判据失效）。

---

## 三、下一棒待办（M3：模块 M2 检测与残差）

按顺序做。**判定顺序固定、不许并行**（`plan/03` §二：逆变换 → 覆盖检查 → 三路评分 → 排序置信 → 残差三段 → 边界画像）。

1. **实现 `src/crsscope/detect.py` 的 `run()`**（接口见 `plan/03` §二；
   `run(path, declared_crs, mask_path=None)` 已在 `cli._run_detect` 里接好）。
   候选假设固定 `("WGS84", "GCJ02", "BD09")`，**不增不减**。
2. **掩膜缺失 / 步长 > 1° → exit 3**（`mask.load_mask` 已抛 `EnvironmentMissing`）；
   **不得**默认"全是陆地"。可判定点 `< 30` → `confidence: undecidable` → exit 5。
3. **三路评分按 §4.2 原文**（权重 `0.25` / `0.30`、置信阈值 `0.15` / `0.05` 都只在
   `data/README.md` §4.2 定义，**代码里只引用**，不得在注释里复制数字）。
   落水分母规则**只走 `mask.MaskStats`**（`unknown` 与海岸带不进分母，已有测试钉住）。
4. **D2 复现**：吃 `data/fixtures/water_track/`，正确假设（GCJ02）把落水率压到近零，
   且 `expect.json` 里的 `winner` / `water_ratio` 逐字段对拍。**必须传自带细网格**（见 §二.10）。
5. **边界外必须输出 `out_of_coverage`**，不得硬判 WGS84（`plan/01` §M2 验收）。
6. **`boundary_profiles`**：`coordTransform_py` / `gcoord` 各一份判定 +
   **显式警告两库边界不一致**（决策 ④：那是审计发现点，不是任何一方的 bug）。
   样本 `(73.2, 39.5)` 与 `(112.0, 2.0)` 两 profile 结论必须不同。
7. **残差三段固定枚举齐全**（§4.5：`formula_approximation` / `vendor_divergence` / `boundary_jump`），
   断言**集合相等**而不是"存在"。**禁止**输出"已还原为 WGS84 真实坐标"一类断言。
8. **`detect` 的 findings 用「一项一责」**（照 `decl.py` 抄形状）：覆盖检查、评分排序、
   残差、边界画像各一项；灰区（可判定点 < 30 / 并列第一 / 边界带）一律 `undecidable`
   （`errors.outcome_code` 会自动把它折成 exit 5）。
9. **从 `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 删掉 `"detect": "M3"`**，
   并同步 `ARGS`。
10. **新增 `tests/test_detect.py`**：吃真实语料（`water_track` + 细网格 + `boundary_divergence`），
    断言 D2 复现、`out_of_coverage`、残差三段集合相等、两库 profile 结论不同、exit 码。
11. **收尾**：`plan/05` §一 M3 翻 ✅、`plan/00` 里程碑表同步翻 ✅、台账对应行翻 ✅、
    `plan/06` 缺口表加/改行（**缺口列不得出现已 ✅ 的里程碑号**）、写 `plan/HANDOFF-M4.md`、commit。

**M3 出口判据**（`plan/05` §三）：D2 类水域轨迹可复现（正确假设把落水率压到近零）；
边界外输出 `out_of_coverage`，不硬判；`residual.kind` 三段集合相等；
落在两库边界框之间的样本 → 两个 `boundary_profiles` 结论不同。

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
| **K15** | 「命中」= `conflict`/`error`（默认），`--fail-on` 收窄；**灰区优先** → `undecidable` 即 5 | `errors.outcome_code` + `tests/test_decl.py::test_outcome_code_default_states` |
| **K16** | `warning` 默认**不**算命中；升级只能 `--strict-ring` / `--fail-on` 点名 | `tests/test_decl.py::test_fail_on_narrows_the_hit_set` |
| **K17** | `decl` 的检查项**一项一责**：`extent` 读 `axis` 的 orientation，不得自己再判轴序 | `tests/test_decl.py::test_swapped_axis_hits_axis_conflict_only` |

---

## 五、本机环境坑（只写实测过的，2026-10-27）

- **`python` 是商店占位符**，一律用 `py -3.12`。
- **本机 3.8 通道不参与验证**（项目下限 3.11）；3.11 行为差异只能靠 CI。
- **setuptools 84.2.1**：`license = "MIT"` 表达式可用；**license classifier 会直接报错**。
- **Bash 直接解包 sdist 会被安全扫描拦截**（解包会写 `.py`）。干净环境验证走
  `pip install <wheel|sdist>` 这条通道，**不要** `tar -xzf` 到工作区。
- **离线装 sdist 会卡在 build isolation**：`pip install --no-index <sdist>` 在全新 venv 里
  要现取 `setuptools>=77`，取不到就 `error: subprocess-exited-with-error`（本轮实测）。
  两个可行通道：① 带网络 `pip install <sdist>`（本轮实测成功，`crsscope 0.1.0` 可跑）；
  ② **装 wheel**（`--no-index --find-links dist crsscope`，零 build 依赖，本轮实测成功）。
  **wheel 与 sdist 的判定行为必须一致**——两态各跑一条真命令对拍，不要只验 `--version`。
- **`py -3.12 -m pytest` 输出没有 `passed` 汇总行**（`addopts = -q` 吞掉了）；要计数不加 `-q`。
- **跑 `crsscope <cmd>` 会往 CWD 落 `report.json` / `report.md`**（`--out-dir` 默认当前目录）；
  写测试时**一律**传 `--out-dir tmp_path`，否则会把报告写进仓库根。
- **`data/mask/out/mask_v1.json` 约 3 MB**（61200 格单行 JSON）。`--check` 会整读整比，单次约 0.4 s。
- **Node v24.15.0 存在**，但本仓库的门**故意用 Python 写**（`tools/*.py`），不引入 Node 依赖。
- `gh` 2.93.0 可用；git 身份 `yuluo554 <282769740+yuluo554@users.noreply.github.com>`。

---

## 六、DoD 逐项 checklist（M3）

- [ ] `detect.py` 的 `run()` 按固定顺序实现六个环节（逆变换 / 覆盖 / 三路评分 / 排序置信 / 残差三段 / 边界画像）
- [ ] `water_track` + 自带细网格 → `winner == GCJ02`，落水率近零（对拍 `expect.json`）
- [ ] 全样本在边界外 → `out_of_coverage`，**不**硬判 WGS84，附两份 `boundary_profiles`
- [ ] `residual.kind` 三段**集合相等**（不是"存在"）
- [ ] `(73.2, 39.5)` / `(112.0, 2.0)` 两 profile 结论不同；`(112.0, 5.0)` / `(112.0, 60.0)` 一致
- [ ] 掩膜缺失 / 步长 > 1° → exit 3；可判定点 `< 30` → `undecidable` + exit 5
- [ ] `UNIMPLEMENTED` 表里删掉 `detect`
- [ ] 布局门全绿、变异 10/10、pytest 全绿（计数从 168 起涨）
- [ ] `python -m build` 成功；干净 venv 装 sdist 后 `crsscope --help` 正常
- [ ] `plan/00` 与 `plan/05` 的 M3 状态同提交翻 ✅（**台账里别留"模块 M3"字样**）
- [ ] `plan/HANDOFF-M4.md` 已写

---

## 七、关键命令速查

```bash
py -3.12 tools/check-sprint-layout.py            # 布局门：0 全绿 / 1 FAIL / 2 用法
py -3.12 tools/mutate-layout-gate.py             # 门变异：10 组必须全红
py -3.12 tools/mutate-layout-gate.py --only m04  # 只跑一组
py -3.12 -m pytest                               # 全量（要汇总行别加 -q）
py -3.12 -m pytest tests/test_decl.py -q         # 已落位的判定守门
py -3.12 -m crsscope --help                      # CLI 面
py -3.12 -m crsscope decl data/fixtures/swapped_axis/out/swapped_axis.geojson --declared-crs 4326 --json --out-dir /tmp/o
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
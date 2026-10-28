# HANDOFF-M2 · 下一步：模块 M1「声明-内容一致性」

> **本单已完成（2026-10-27）**：DoD 全绿，落位记录见 `plan/05` §二之二与 `plan/00` 里程碑表。
> 下一棒看 `plan/HANDOFF-M3.md`。
>
> 用法：新对话 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M2.md" 继续完成任务`
> **第一动作（硬约束③）**：先跑布局门 `py -3.12 tools/check-sprint-layout.py`，必须全绿再动手。

---

## 一、当前进度 + 证据

| 项 | 状态 | 证据（2026-10-27 实测） |
|---|---|---|
| 题面定稿 / 计划 00–06 | ✅ | `plan/00`–`plan/06` 齐备 |
| 方法论装订 + 布局门（10 判据） | ✅ | `py -3.12 tools/check-sprint-layout.py` → 全绿 |
| 门变异验证 | ✅ | `py -3.12 tools/mutate-layout-gate.py` → **10/10 符合预期 / 0 SKIP** |
| **里程碑 M1 数据先行** | ✅ **本轮完成** | 七份 fixture + 掩膜；8 份生成器 `--check` exit 0 逐字节一致 |
| 测试 | ✅ | `py -3.12 -m pytest` → **146 passed**（M2 时点；当前见 `plan/05`）（骨架 102 + 语料契约 44） |
| CI | ⬜ **待首推验证** | `.github/workflows/ci.yml` 已写，**从未被 GitHub 跑过** |
| 判定逻辑（模块 M1–M5） | ⬜ 未实现 | 五子命令一律 exit 3 + `not implemented` |

**M2 = 模块 M1 `decl.py`「声明-内容一致性」**（`plan/03` §一；编号差一位，见 `plan/00` 决策 ⑨）。
M1（数据）已就绪，M2（声明一致性）可开工；**不要跳到 M3 之前先把 M2 的语料用起来**。

---

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

### 2.1 语料侧（本轮新增，改动会大面积打挂测试）

1. **共享生成器框架 = `data/_genlib.py`**，`--out` / `--check` 的**唯一**实现。
   各 `data/fixtures/*/gen.py` 只写 `build()`，用 `FixtureRun(NAME, VERSION, build, here=_HERE).main()` 收口。
   **不要在某个 fixture 里另起一套 `--check`**——口径会立刻漂移。
2. **`--out` 会删掉产物目录里的残留文件**（`out/` 下不属于本次 `build()` 的文件）。
   产物目录是生成物专属区，不要往里放手工文件。
3. **自检必须写在 `build()` 末尾**：`--check` 不走 `__main__`。写错位置 = 门下从没跑过。
4. **`expect.json` 的顶层键受测试约束**（`tests/test_fixtures.py`）：
   必备 `fixture` / `generator_version` / `cases`；可选 `notes` / `track` / `mask` / `coverage` / `expected` / `rfc`。
   **加新顶层键必须同时改 `EXPECT_OPTIONAL_KEYS`**，否则测试红。
5. **金标里禁止 `observed` 类字段**（`observed` / `actual` / `measured` / `observed_value` / `actual_value`：
   递归扫键名）。真值只存"输入 + 期望"。
6. **`boundary_divergence/gen.py` 内联了两套边界框常数**，**故意不 import `algorithms`**。
   改它之前先读 `plan/04` §二「参考实现三落点位」——金标复用生产实现 = 用被测物证明被测物。
7. **`water_track` 自带细网格**（`resolution_deg = 0.0008`，约 89 m）：
   1° 网格跨不过 250–600 m 的 GCJ 位移，D2 场景复现不了。跑 `detect` 时**必须**显式传这张：
   `--mask data/fixtures/water_track/out/water_track_mask.json`。
   它的陆带 3 格厚、偏移落点离陆带 ≥ 2 行——**别按"更真实"去调几何**，海岸带纪律会立刻把区分度吃掉。
8. **默认掩膜 = `data/mask/out/mask_v1.json`**（1°，61200 格，构造网格非地理真值）。
   `mask.load_mask` 要的字段：`version` / `resolution_deg` / `lon_min` / `lat_min` / `n_lon` / `n_lat` / `cells`。

### 2.2 门与文档侧（本轮踩过的坑）

9. **台账状态列用的是里程碑编号，不是模块编号**。
   本轮的实测：`plan/00` 台账原写"⬜ 待建（模块 M1）"，里程碑 M1 一翻 ✅，`LAYOUT.LEDGER` 立刻报红——
   **那不是假门**，是两套编号（决策 ⑨）在状态列里撞车。台账状态列已统一为"里程碑 Mx"。
   后续把 M3/M4/M5 翻 ✅ 时，**记得同时看台账里有没有"模块 Mx"字样**。
10. **`.gitignore` 的 `mask/` 曾把 `data/mask/` 整棵吞掉**（`git check-ignore data/mask/gen.py` 命中）。
    已改成锚定仓库根的 `/mask/`。新增忽略规则时警惕这种"裸目录名"匹配。
11. **`tests/conftest.py` 的补齐判据是"产物目录缺件"**，不是"`expect.json` 缺件"。
    后者在 M1 之后永不触发（金标已入仓），干净 clone 上会静默缺语料。
12. **布局门 `PENDING_TOOLS`**：`tools/check-release.py` 登记为 M6 落位。
    里程碑 M6 翻 ✅ 时必须从 `tools/check-sprint-layout.py` 删掉该条，否则门变红（有意设计）。

### 2.3 判定侧（未变，但 M2 会天天碰到）

13. **`exit 3 + not implemented` 是骨架阶段的硬契约**。每实现一个子命令，
    **必须**从 `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 表删掉对应条目——
    否则这条测试会一直"通过"而实际早已实现（靶子过期 = 判据失效）。
14. **版本唯一定义处 = `src/crsscope/__init__.py` 的 `__version__`**；pyproject 用 `dynamic`。
15. **两套 GCJ-02 边界框不许合并**（`algorithms.CT_PY_BBOX` 开区间 / `GCOORD_BBOX` 闭区间）。

---

## 三、下一棒待办（M2：模块 M1 声明-内容一致性）

按顺序做。**判定顺序固定、不许并行**（`plan/03` §一：量级 → 轴序 → 单位 → 混用 → 范围）。

1. **实现 `src/crsscope/decl.py` 的 `run()`**（接口见 `plan/03` §一）。
   量级先行：`data/README.md` §4.1 的度域 / 米域 / 中间带三条 + `conflict(magnitude)`。
2. **轴序**：只用可判定样本（`|a| ≤ 180 ∧ |b| ≤ 180`）；样本数 `< 5` → `undecidable(insufficient_samples)`。
   判据：存在样本使 `|b| > 90 ∧ |a| ≤ 90` → `conflict(axis)`；存在 `|a| > 90 ∧ |b| ≤ 90` → `consistent`。
3. **单位 / 混用 / 范围**三项（`plan/03` §一 第 3–5 条）。
4. **让语料真正被读**：M2 的测试要直接吃 `data/fixtures/swapped_axis/out/*.geojson` 与
   `data/fixtures/declared_lie/out/*.geojson`，并断言**两类样本各自命中、互不串扰**：
   - `declared_lie` → `conflict/magnitude`，且 **`axis_decidable is False`**；
   - `swapped_axis` → `conflict/axis`，且量级全在度域（不触发 magnitude）。
   两条金标已在 `expect.json` 的 `expected` 里写好，直接用。
5. **从 `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 删掉 `"decl": "M2"`**，
   并给 `ARGS` 里对应行同步处理（`test_contract_table_matches_handlers` 会看着）。
6. **新增一个真命令测试**：`crsscope decl data/fixtures/swapped_axis/out/swapped_axis.geojson --declared-crs 4326`
   → exit 1（判定命中），`--json` 输出里的 `findings` 含 `check=magnitude`? 不——含 `check=axis`。
   （`--fail-on` 语义见 `data/README.md` §4.9。）
7. **收尾**：`plan/05` §一 M2 翻 ✅、`plan/00` 里程碑表同步翻 ✅、台账对应两行翻 ✅、
   `plan/06` 缺口表加/改行（**注意：缺口列不得出现已 ✅ 的里程碑号**）、写 `plan/HANDOFF-M3.md`、commit。

**M2 出口判据**（`plan/05` §三）：`declared_lie` 与 `swapped_axis` **各自单测命中**；
可判定样本 `< 5` → `undecidable` 且 exit 5（除非 `--allow-undecidable`）；
`--declared-crs gcj02` → exit 2 并列出合法枚举（这条**已经**由骨架测试守着，别改坏）。

---

## 四、既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 谁在守 |
|---|---|---|
| K01 | 退出码优先级 `2→3→4→5→1→0`，只在 `errors.py` 一处定义 | `tests/test_cli.py` + `tests/test_unimplemented_contract.py` |
| K02 | 版本单点 = `__init__.__version__`，pyproject 用 `dynamic` | `tests/test_version.py` |
| K03 | `DECLARED_CRS_CHOICES = ("4326","3857","4490","crs84")`，**GCJ-02/BD-09 不是合法声明值** | `tests/test_cli.py::test_parser_exposes_all_declared_crs_choices` |
| K04 | `algorithms.KRASOVSKY_A == 6378245.0`、`EE == 0.006693421622965823`、`INVERSE_TOLERANCE_DEG == 1e-6` | `tests/test_core.py::test_krasovsky_constants_are_verbatim` |
| K05 | 两库边界：`CT_PY_BBOX` 开区间、`GCOORD_BBOX` 闭区间 | `tests/test_core.py` 四条边界用例 + 本轮新增的 `test_fixtures.py` 独立复算 |
| K06 | 距离只走 `geodesy.haversine_m`，`R = 6371008.8` | `tests/test_core.py` |
| K07 | `MaskStats.water_ratio` 无分母时返回 `None`（**不许**返回 0.0） | `tests/test_core.py::test_water_ratio_is_none_when_nothing_evaluable` |
| K08 | `mask.MAX_RESOLUTION_DEG = 1.0`，超限抛 `EnvironmentMissing`（exit 3） | `tests/test_core.py::test_mask_rejects_resolution_above_cap` |
| K09 | `report.TIMESTAMP_FIELD == "generated_at"` 且报告里**只能有一个**时间戳字段 | `tests/test_determinism.py::test_only_one_timestamp_field_in_payload` |
| K10 | 未实现子命令必须 exit 3 + 含 `not implemented` | `tests/test_unimplemented_contract.py` |
| K11 | `crs` 措辞只准 "no longer used"，读者面不得出现断言式禁用表述 | `tests/test_wording.py` |
| K12 | `io` 层拒绝含 `<!DOCTYPE` / `<!ENTITY` 的 XML（GPX 安全） | `tests/test_io.py::test_xml_with_dtd_or_entity_is_rejected` |
| **K13** | `--check` 对生成物**允许缺席**（干净 clone 常态），对 `expect.json` **缺件即 FAIL** | `data/_genlib.FixtureRun._check` + `tests/test_fixtures.py` |
| **K14** | `expect.json` 顶层键 = `{fixture, generator_version, cases}` ∪ 白名单 | `tests/test_fixtures.py::test_expect_json_has_required_keys` |

---

## 五、本机环境坑（只写实测过的，2026-10-27）

- **`python` 是商店占位符**，一律用 `py -3.12`。
- **本机 3.8 通道不参与验证**（项目下限 3.11）；3.11 行为差异只能靠 CI。
- **setuptools 84.2.1**：`license = "MIT"` 表达式可用；**license classifier 会直接报错**。
- **Bash 直接解包 sdist 会被安全扫描拦截**（解包会写 `.py`）。干净环境验证走
  `pip install <wheel|sdist>` 这条通道，**不要** `tar -xzf` 到工作区。
- **`py -3.12 -m pytest` 输出没有 `passed` 汇总行**（`addopts = -q` 吞掉了）；要计数不加 `-q`。
- **`data/mask/out/mask_v1.json` 约 3 MB**（61200 格单行 JSON）。`--check` 会整读整比，
  单次约 0.4 s——**不要**把它接进逐测试的循环里。
- **Node v24.15.0 存在**，但本仓库的门**故意用 Python 写**（`tools/*.py`），不引入 Node 依赖。
- `gh` 2.93.0 可用；git 身份 `yuluo554 <282769740+yuluo554@users.noreply.github.com>`。

---

## 六、DoD 逐项 checklist（M2）

- [x] `decl.py` 的 `run()` 按固定顺序实现五个检查项
- [x] `swapped_axis` 命中 `conflict/axis`（**单独**，量级不串扰）
- [x] `declared_lie` 命中 `conflict/magnitude`（**单独**，轴序不串扰）
- [x] 可判定样本 `< 5` → `undecidable` + exit 5；`--allow-undecidable` → exit 0
- [x] `--declared-crs gcj02` → exit 2 并列出合法枚举
- [x] `UNIMPLEMENTED` 表里删掉 `decl`
- [x] 布局门全绿、变异 10/10、pytest 全绿（146 → **168**）
- [x] `python -m build` 成功；干净 venv 装 sdist 后 `crsscope --help` 正常
- [x] `plan/00` 与 `plan/05` 的 M2 状态同提交翻 ✅（**台账里别留"模块 M2"字样**）
- [x] `plan/HANDOFF-M3.md` 已写

> **实测修正**：§三.6 期望裸命令 → exit 1 与 `data/README.md` §4.9 字面互斥；
> 已定案为"`conflict`/`error` 默认即命中，且**灰区优先**"，见 `plan/00` 决策 ⑪。
> 因此 `declared_lie` 裸跑 → **5**（它的 `axis` 是灰区），加 `--allow-undecidable` 才 → 1。

---

## 七、关键命令速查

```bash
py -3.12 tools/check-sprint-layout.py            # 布局门：0 全绿 / 1 FAIL / 2 用法
py -3.12 tools/mutate-layout-gate.py             # 门变异：10 组必须全红
py -3.12 tools/mutate-layout-gate.py --only m04  # 只跑一组
py -3.12 -m pytest                               # 全量（要汇总行别加 -q）
py -3.12 -m pytest tests/test_fixtures.py -q     # 语料契约
py -3.12 -m crsscope --help                      # CLI 面
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

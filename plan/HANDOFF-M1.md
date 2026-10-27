# HANDOFF-M1 · 下一步：数据先行

> 用法：新对话 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M1.md" 继续完成任务`
> **第一动作（硬约束③）**：先跑布局门 `py -3.12 tools/check-sprint-layout.py`，必须全绿再动手。

---

## 一、当前进度 + 证据

| 项 | 状态 | 证据（2026-10-27 实测） |
|---|---|---|
| 题面定稿 | ✅ | `plan/01-题目文档.md` |
| 计划文档 00–06 | ✅ | `plan/00`–`plan/06` 齐备，布局门 `LAYOUT.SECTIONS` 按标题行判绿 |
| 方法论装订 | ✅ | `AGENTS.md` + `tools/check-sprint-layout.py`（10 判据）+ `plan/00` 顶部装订行 |
| 门变异验证 | ✅ | `py -3.12 tools/mutate-layout-gate.py` → **10/10 符合预期 / 0 SKIP** |
| 可运行骨架 | ✅ | `pip install -e ".[dev]"` 成功；`crsscope --version` → `0.1.0`；6 个子命令 `--help` 全 exit 0 |
| 测试 | ✅ | `py -3.12 -m pytest` → **102 passed** |
| 构建 | ✅ | `python -m build` → `dist/crsscope-0.1.0.tar.gz`（57 条目）+ `.whl` |
| 双装态 | ✅ | 仓库外两个全新 venv：wheel 装态与 sdist 装态均 `0.1.0` + console script 可跑；wheel 装态加载的非标准库顶层模块 = `[]` |
| CI | ⬜ **待首推验证** | `.github/workflows/ci.yml` 已写（3.11/3.12 × ubuntu/windows），**从未被 GitHub 跑过** |
| 判定逻辑 | ⬜ 未实现 | 五个判定子命令一律 exit 3 + `not implemented` |

**项目不在任何里程碑内**：M1–M6 全部 ⬜（`plan/05` 状态表）。本轮是"计划 + 骨架"。

---

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

1. **`exit 3 + not implemented` 是骨架阶段的硬契约，不许改成"返回空结果集"**。
   守门 = `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 表。
   **每实现一个子命令，必须从该表删掉对应条目**——否则这条测试会一直"通过"而实际早已实现
   （靶子过期 = 判据失效）。
2. **版本唯一定义处 = `src/crsscope/__init__.py` 的 `__version__`**；
   `pyproject.toml` 用 `dynamic = ["version"]`，**不许**在 `[project]` 里写死 `version`。
   `tests/test_version.py` 同时断言 pyproject 与 README。
3. **两套 GCJ-02 边界框不许合并**（`algorithms.CT_PY_BBOX` 开区间 / `GCOORD_BBOX` 闭区间）。
   它们的差异是 M3 的核心交付物，不是需要"顺手统一"的重复代码。
4. **`pyproject.toml` 的 license 用 `license = "MIT"` 表达式**，
   **不能**再写 `License :: OSI Approved :: MIT License` classifier —— setuptools 84 会直接
   `InvalidConfigError`（本轮实测踩过，构建直接失败）。
5. **`.gitattributes` 把 `*.json` / `*.geojson` / `*.gpx` / `*.csv` 标了 `-text`**：
   这些将来是"字节即被测对象"的 fixture 与金标，git 一律不许碰它们的 EOL。
6. **布局门只读仓库内文件，不读 git 元数据**（`tests/test_layout_gate.py` 用 AST 钉住）。
   新增判据也**不许**引入 `git rev-parse` / `ls-files` 这类依赖。
7. **`MANIFEST.in` 必须继续 `recursive-include tests *.py`**：setuptools 默认只收
   `tests/test*.py`，漏掉 `conftest.py` 会让 sdist 解包树里所有 fixture 消失（本轮实测）。
8. **`Report.write_reports` 只在判定成功后调用**（失败路径零副作用，`test_unimplemented_contract`
   的 `test_unimplemented_command_writes_no_report` 守着）。
9. **`data/fixtures/` 与 `data/mask/` 目录目前不存在**。`tests/conftest.py` 的
   `ensure_fixtures` 在目录缺失时直接返回，M1 建目录后它会开始自动补跑缺件生成器。

---

## 三、下一棒待办（M1 数据先行）

按顺序做，**不要跳到 M2**（没有金标的判定代码 = 不可验证的代码）。

1. 建 `data/fixtures/<name>/gen.py` 七份 + `data/mask/gen.py`（清单见 `plan/04` §一）。
   每个 `gen.py`：固定输入 / 无随机 / 无时间依赖；`--out` 生成、`--check` 重生成逐字节比对。
   **自检函数写在 `build()` 末尾**，不写在 `__main__` 里（`--check` 不走 `__main__`）。
2. `expect.json` 只存"输入 + 期望"，**不得**出现 `observed` 一类字段。
   边界分歧金标由两套常数**直接代入**算出，**不复用** `algorithms.py` 的实现。
3. 掩膜：1° 构造网格，`cells` 按 `(lat_idx, lon_idx)` 索引，值 ∈ `land|water|unknown`；
   生成器要打印 `unknown_ratio` / `coastal_ratio` 覆盖率自检。
4. `tests/conftest.py` 的 `ensure_fixtures` 在干净 clone 上必须能补齐（已有实现，验一遍即可）。
5. 写 `tests/test_fixtures.py`：`--check` exit 0 + 每个 `expect.json` 的键集合符合 `plan/04` §2.1。
6. 跑全量：布局门 / 变异 10 组 / pytest / `python -m build` / 干净 venv 装 sdist。
7. 收尾：`plan/05` §一 M1 翻 ✅、`plan/00` 里程碑表同步翻 ✅、写 `plan/HANDOFF-M2.md`、commit。

**M1 出口判据**（`plan/05` §三）：七份 fixture + 掩膜全部 `--check` 逐字节一致、
`expect.json` 齐备且无异物字段、边界分歧三例（73.2°E / 2.0°N / 5°N）数值可复算。

---

## 四、既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 谁在守 |
|---|---|---|
| K01 | 退出码优先级 `2→3→4→5→1→0`，只在 `errors.py` 一处定义 | `tests/test_cli.py` + `tests/test_unimplemented_contract.py` |
| K02 | 版本单点 = `__init__.__version__`，pyproject 用 `dynamic` | `tests/test_version.py` |
| K03 | `DECLARED_CRS_CHOICES = ("4326","3857","4490","crs84")`，**GCJ-02/BD-09 不是合法声明值** | `tests/test_cli.py::test_parser_exposes_all_declared_crs_choices` |
| K04 | `algorithms.KRASOVSKY_A == 6378245.0`、`EE == 0.006693421622965823`、`INVERSE_TOLERANCE_DEG == 1e-6` | `tests/test_core.py::test_krasovsky_constants_are_verbatim` |
| K05 | 两库边界：`CT_PY_BBOX` 开区间、`GCOORD_BBOX` 闭区间 | `tests/test_core.py` 四条边界用例 |
| K06 | 距离只走 `geodesy.haversine_m`，`R = 6371008.8` | `tests/test_core.py` |
| K07 | `MaskStats.water_ratio` 无分母时返回 `None`（**不许**返回 0.0） | `tests/test_core.py::test_water_ratio_is_none_when_nothing_evaluable` |
| K08 | `mask.MAX_RESOLUTION_DEG = 1.0`，超限抛 `EnvironmentMissing`（exit 3） | `tests/test_core.py::test_mask_rejects_resolution_above_cap` |
| K09 | `report.TIMESTAMP_FIELD == "generated_at"` 且报告里**只能有一个**时间戳字段 | `tests/test_determinism.py::test_only_one_timestamp_field_in_payload` |
| K10 | 未实现子命令必须 exit 3 + 含 `not implemented` | `tests/test_unimplemented_contract.py` |
| K11 | `crs` 措辞只准 "no longer used"，读者面（README/AGENTS/src 字面量）不得出现断言式禁用表述 | `tests/test_wording.py` |
| K12 | `io` 层拒绝含 `<!DOCTYPE` / `<!ENTITY` 的 XML（GPX 安全） | `tests/test_io.py::test_xml_with_dtd_or_entity_is_rejected` |

---

## 五、本机环境坑（只写实测过的，2026-10-27）

- **`python` 是商店占位符**，一律用 `py -3.12`。
- **本机有 3.8 与 3.12 两条通道**；项目下限 **3.11**，所以 **3.8 通道不参与任何验证**。
  3.11 的行为差异只能靠 CI。
- **setuptools 84.2.1**：`license-files` 与 license expression 都支持，但
  **license classifier 会直接报错**（见 §二.4）。
- **Bash 直接解包 sdist 会被安全扫描拦截**（解包会写 `.py`）。干净环境验证改用
  `pip install <wheel|sdist>` 这条通道，不要 `tar -xzf` 到工作区。
- **Node v24.15.0 存在**，但本仓库的门**故意用 Python 写**（`tools/*.py`），不要引入 Node 依赖。
- `gh` 2.93.0 可用；git 身份 `yuluo554 <282769740+yuluo554@users.noreply.github.com>`。
- **`py -3.12 -m pytest` 输出没有 `passed` 汇总行**（`addopts = -q` 下被吞）；要计数用
  `py -3.12 -m pytest`（不加 `-q`）。

---

## 六、DoD 逐项 checklist（M1）

- [ ] 七份 `data/fixtures/<name>/gen.py` + `expect.json`
- [ ] `data/mask/gen.py` + 覆盖率自检输出
- [ ] 每份 `gen.py --check` exit 0（逐字节一致）
- [ ] `expect.json` 无 `observed` 类字段
- [ ] 边界分歧三例数值与 `data/README.md` §1.3 对照表逐格一致
- [ ] `tests/test_fixtures.py` 落位并通过
- [ ] 布局门全绿、变异 10/10、pytest 全绿
- [ ] `python -m build` 成功；干净 venv 装 sdist 后 `crsscope --version` 正确
- [ ] `plan/00` 与 `plan/05` 的 M1 状态同提交翻 ✅
- [ ] `plan/HANDOFF-M2.md` 已写

---

## 七、关键命令速查

```bash
py -3.12 tools/check-sprint-layout.py            # 布局门：0 全绿 / 1 FAIL / 2 用法
py -3.12 tools/mutate-layout-gate.py             # 门变异：10 组必须全红
py -3.12 tools/mutate-layout-gate.py --only m04  # 只跑一组
py -3.12 -m pytest                               # 全量（要汇总行别加 -q）
py -3.12 -m pytest tests/test_core.py -q         # 单文件
py -3.12 -m crsscope --help                      # CLI 面
py -3.12 -m crsscope tiles x.json                # 骨架期：exit 3 + not implemented
py -3.12 -m build                                # 构建 dist/
```

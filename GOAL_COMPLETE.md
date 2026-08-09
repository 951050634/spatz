# GOAL_COMPLETE — Online Softmax Merge 论文补充实验

仓库：`/home/wxt/work-online-merge-supplement`
分支：`exp/online-softmax-supplement`
完成日期：2026-08-08
最终 HEAD：`f35157e`（阶段 6 封口提交之前）

本文件记录 6 个阶段（阶段 0 准备、阶段 1 代码合并、阶段 2 P0-4、阶段 3 P0-5、阶段 4 P0-6、阶段 5 可选能力审计）的 PASS 证据与关键命令输出摘要。阶段 6 最终复核结果见文末。

---

## 0. 阶段 0 · 准备与单元测试

- `which python3` → `/usr/bin/python3`（3.12.3）；全程使用 `python3`，并导出 `PYTHONDONTWRITEBYTECODE=1`。
- 单元测试（阶段 0 基线）：
  ```
  $ python3 -m unittest discover -s util/online_softmax_merge/tests -v
  Ran 110 tests in 2.2s
  OK
  ```

## 1. 代码合并（阶段 1）

### 1.1 cherry-pick P0-5/P0-6 8 个提交

从 worktree `/home/wxt/work-online-merge-p0-5-dev-67df03b`（HEAD=8c2dfda）cherry-pick
`67df03b..8c2dfda` 共 8 个提交，保持线性历史，逐条解决冲突并保留两侧语义：

```
git cherry-pick 67df03b..8c2dfda
```

8 个提交：`74be6d0`、`eeb02aa`、`44e7d1f`、`ecbce8e`、`2afee96`、`e7b7310`、`6891914`、`8c2dfda`
（对应合并后的 `0b94bb4`/`bfb34d7`/`af7c7b6`/`1e1ba3d`/`5a5a32a`/`230a10d`/`1b4107f`/`e9ef0ef`）。

PASS 证据：

- P0-5 代码：`experiments/scripts/run_performance_matrix.py`、`analyze_p0_5.py`、
  `experiments/configs/p0_model_workload_cases.json` 等已就位。
- P0-6 代码：`experiments/scripts/run_p0_6_synthesis.py`、`analyze_p0_6.py`、
  `experiments/configs/p0_6_synthesis_configs.json` 等已就位。
- 冲突处理：涉及 P0-5 容量跳过语义、P0-6 FSM 提取的冲突均逐条解决，保留两侧语义。

### 1.2 并入可选能力审计成果与文档

- 从 `/home/wxt/work-online-merge-final-dev-8c2dfda` 并入未提交成果：
  - `experiments/scripts/audit_optional_capabilities.py`
  - `experiments/tests/test_optional_capabilities.py`
  - `experiments/README.md`（改动）
- 将 `docs/SMU_EXPERIMENT_RESULTS_TO_DATE.md` 纳入版本管理。

PASS 证据：

- `git status` 干净。
- 合并后重跑单元测试：`util` 110 tests OK、`experiments/tests` 52 tests OK。
- 阶段 1 检查点：`8e46917 checkpoint: 阶段1 合并P0-5/P0-6代码与可选能力审计成果`。

## 2. P0-4 完整索引与分析（阶段 2）

### 2.1 索引 17 个 67df03b 结果目录

```
python3 experiments/scripts/index_external_runs.py --set-name p0_4 \
  --result-root <17 个路径逐一传入> --require-clean
```

17 个路径：`/home/wxt/work-online-merge-67df03b-p0-4-{scale-00..07,tail-00..02,numerical-00..02,capacity-00..02}-r1`。

产出 manifest：`experiments/manifests/p0_4_index_set.json`（名称以脚本实际输出为准）。

索引摘要（`p0_4_analysis.json` → `index_set`）：

- `set_name = p0_4`，`git_commit = 67df03b…`，`git_dirty_before_indexing = False`
- `run_count = 17`，`record_count = 588`，`artifact_count = 2727`
- `failure_count = 0`

### 2.2 P0-4 分析

```
python3 experiments/scripts/analyze_p0_4.py --index-set experiments/manifests/p0_4_index_set.json \
  --output-dir experiments/parsed/p0_4 --require-clean
```

分析摘要（`p0_4_analysis.json`）：

- `counts`: case_count=49, record_count=588, root_count=17, failure_count=0,
  validation_issue_count=0, paper_eligible_record_count=276
- `acceptance` 9 项全部 `True`：index_set_complete、record_matrix_complete、scaling_coordinate_count、
  models_complete、break_even_complete、paper_eligible_scope_exact、no_failure_entries、
  validation_issue_free、all_external_artifacts_reverified
- 状态分布：PASS=552、SKIPPED_MEMORY_LIMIT=24、UNSUPPORTED_SHAPE=12

Scaling 模型（`C = C0 + Cs*N + Cv*N*D + Cstall`，23 个拟合点）：

| Config | C0 | Cs/row | Cv/element | R² |
| --- | ---: | ---: | ---: | ---: |
| B2R_RVV | 153.48 | 1594.23 | 2.09 | 0.999946 |
| A1_SMU_SCALAR | 1382.77 | 90.28 | 2.13 | 0.999276 |
| A2_SMU_FULL | 1285.58 | 19.32 | 8.03 | 0.999987 |

Break-even（直接测量，A2_SMU_FULL <= B2R_RVV，未混入拟合预测）：

| N | 最小测量 D | 满足的测量 D |
| --- | ---: | --- |
| 1 | 1 | 1, 8, 16, 32 |
| 2 | 1 | 1, 8, 16, 32 |
| 4 | 1 | 1, 8, 16, 32 |
| 8 | 1 | 1, 8, 16, 32 |

边界/容量：FUNCTIONAL_BOUNDARY 68 行（PASS=64, UNSUPPORTED_SHAPE=4）；
CAPACITY_PROBE 36 行（PASS=28, SKIPPED_MEMORY_LIMIT=8）。

产出目录 `experiments/parsed/p0_4/`：12 个文件（analysis JSON、report MD、CSV 等）。

检查点：`20ac12d`（索引）、`565f1c2`（分析）。

## 3. P0-5 正式运行与分析（阶段 3）

### 3.1 完整模型矩阵运行

```
python3 experiments/scripts/run_performance_matrix.py \
  --case-file experiments/configs/p0_model_workload_cases.json \
  --case-ids model_bert_base_heads model_mistral_7b_heads model_qwen2_5_14b_heads model_qwen2_5_72b_heads \
  --simulator /home/wxt/work-online-merge-low-dasm-simulator-5c2aad2-r1/spatz_cluster.vlt \
  --trace-witness-simulator /home/wxt/work-online-merge-traced-simulator-088a44d-r1/spatz_cluster.vlt \
  --require-clean
```

- BERT 复用已有 clean preflight（r2=12/12 PASS）。
- 其余 3 个模型（Mistral-7B、Qwen2.5-14B、Qwen2.5-72B）按 config 完整跑完。
- 结果目录：`/home/wxt/work-online-merge-8c2dfda-p0-5-model-00-r1`（bert+mistral，24 records）、
  `/home/wxt/work-online-merge-8c2dfda-p0-5-model-01-r1`（qwen14b+qwen72b，24 records）。

### 3.2 索引与修复

```
python3 experiments/scripts/index_external_runs.py --set-name p0_5 \
  --result-root <model-00-r1> --result-root <model-01-r1> --require-clean
```

产出 `experiments/manifests/p0_5_index_set.json`。

期间修复（`c32a82b`）：`analyze_p0_5.py` 的容量跳过 gate 从 `value is not None` 改为
`value not in (None, 0)`——simulator 对 capacity_skip 显式未执行时报 `cycles_lo=0` 而非 `None`；
同步更新 `test_experiment_framework.py`（skipped 摘要的 `kernel_cycles_median` 由 None 改为 0）。
52 个 experiments 测试保持全绿。

### 3.3 P0-5 分析

```
python3 experiments/scripts/analyze_p0_5.py --index-set experiments/manifests/p0_5_index_set.json \
  --output-dir experiments/parsed/p0_5 --require-clean
```

分析摘要（`p0_5_analysis.json`）：

- `counts`: case_count=4, record_count=48, root_count=2, failure_count=0,
  validation_issue_count=0, paper_eligible_record_count=36
- 状态分布：PASS=36、SKIPPED_MEMORY_LIMIT=12
- dispositions：MEASURED × 3、EXPLICIT_CAPACITY_SKIP × 1
- `acceptance` 8 项全部 `True`：index_set_complete、record_matrix_complete、paper_eligible_scope_exact、
  workload_dispositions_exact、pinned_model_sources_complete、no_failure_entries、
  validation_issue_free、all_external_artifacts_reverified
- model source audit：4 个模型全部 PASS（config 均取自 HuggingFace 固定 revision，含 SHA-256）
- `paper_eligible=YES` 的行全部存在：BERT、Mistral-7B、Qwen2.5-14B 各 12 行；Qwen2.5-72B 因
  显式容量跳过（footprint 150144 B > TCDM 131072 B）为 `paper_eligible=NO`（12 行 SKIPPED_MEMORY_LIMIT）。

周期中位数（trials=3，全部 PASS，无跨 trial 波动）：

| case | N | D | B1_SCALAR | B2R_RVV | A1_SMU_SCALAR | A2_SMU_FULL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bert-base | 12 | 64 | 271718 | 20785 | 4128 | 7704 |
| mistral-7b | 32 | 128 | 1401702 | 59500 | 12866 | 34728 |
| qwen2.5-14b | 40 | 128 | 1780547 | 75027 | 15733 | 43206 |
| qwen2.5-72b | 64 | 128 | SKIPPED_MEMORY_LIMIT（容量跳过，显式 0） | | | |

加速比（A2 vs B1 / A2 vs B2R / A1 vs B2R）：BERT 35.27×/2.70×/5.04×、
Mistral 40.36×/1.71×/4.62×、Qwen14B 41.21×/1.74×/4.77×。

产出目录 `experiments/parsed/p0_5/`：8 个文件。

检查点：`07adbaa`（索引）、`c32a82b`（gate 修复）、`f35157e`（分析）。

## 4. P0-6 正式综合与分析（阶段 4）

### 4.1 Nangate45 映射综合

```
python3 experiments/scripts/run_p0_6_synthesis.py --require-clean
```

- C0_NONE / C1_SCALAR / C2_FULL 三个 config × 3 次 trial，统一 Yosys ABC `-fast` 流
  （`strash; dretime; map`），Nangate45 典型角（`Nangate45_typ.lib`，lib SHA-256 已核验）。
- 固定模式修剪：flatten 后强制 FSM 提取（`w:*state_q`），techmap 前完成。
- 结果目录：`/home/wxt/work-online-merge-20260808T071000Z_8c2dfdaa_p0-6-synthesis`（9 records）。

### 4.2 索引与分析

```
python3 experiments/scripts/index_external_runs.py --set-name p0_6 \
  --result-root <p0-6-synthesis root> --require-clean
python3 experiments/scripts/analyze_p0_6.py --index-set experiments/manifests/p0_6_index_set.json \
  --output-dir experiments/parsed/p0_6 --require-clean
```

综合结果（`p0_6_synthesis_summary.csv`），与预检基线精确复现：

| config | trials | pass | exact_reproducible | mapped cells | mapped area (Liberty units) | normalized (C1=1.0) |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| C0_NONE | 3 | 3 | True | 0 | 0.0 | 0.0 |
| C1_SCALAR | 3 | 3 | True | 73505 | 77103.292 | 1.0 |
| C2_FULL | 3 | 3 | True | 107372 | 114713.298 | 1.487787 |

- 预检基线：C0=0 cells/0 area、C1=73505 cells/77103.292 area、C2=107372 cells/114713.298 area —— 全部匹配。
- 分析摘要（`p0_6_analysis.json`）：record_count=9、failure_count=0、validation_issue_count=0、
  status_counts.pass=9；`acceptance` 22 项全部 `True`（含 record_matrix_complete、requested_matrix_exact、
  three_exact_processes_per_config、exact_reproducibility_by_config 全部 True、c0_c1_c2_area_ordering、
  tool_and_library_identity_pass、input_hashes_reverified、all_raw_outputs_reverified、
  claim_boundary_explicit、capture_acceptance_gates_pass 等）。
- 声明边界：未布线的 Nangate45 Liberty 单元面积映射，固定 SMU-only 范围、统一 ABC -fast 流；
  QoR 低于默认 ABC 脚本，不包含物理/时序/功耗声明（`physical_ppa_evidence=False`）。

产出目录 `experiments/parsed/p0_6/`：6 个文件。

检查点：`b6a315b`（索引）、`e9bdbf8`（分析）。

## 5. 可选能力审计（阶段 5）

```
python3 experiments/scripts/audit_optional_capabilities.py \
  --output-dir experiments/parsed/optional_capabilities --require-clean
```

审计结果（`optional_capability_audit.csv`，6 项能力；`no_install_or_update_performed=True`）：

| capability_id | requested_scope | status | paper_eligible | 说明 |
| --- | --- | --- | --- | --- |
| EXP_ONLY | 纯 exp() 基线 | BLOCKED_NOT_IMPLEMENTED | NO | 测量策略禁止软件 exp() 与零成本替代 |
| TILE_SCAN | 独立 tile 尺寸扫描 | NOT_APPLICABLE | NO | 无独立 tile 参数 |
| INPUT_PATTERN | 数值模式与 RVV tail 维度 | COMPLETE_SUPPORTING | NO | P0-4 边界覆盖全通过（8 种数值模式、9 个 RVV tail 维度） |
| OPENROAD | P&R 物理实现 | BLOCKED_TOOLCHAIN | NO | openroad 未找到（NOT_FOUND） |
| WORKLOAD_POWER_ENERGY | 功耗/能量 | BLOCKED_EXTERNAL | NO | 缺 openroad/sta/vcd2saif 及后布局功耗流 |
| FIGURE_RENDERING | Python PDF/SVG/PNG 图包 | BLOCKED_PYTHON_PACKAGES | NO | 缺 matplotlib（numpy 可用，pandas/seaborn 不可用） |

工具探测：yosys PASS（`/home/wxt/yosys-sta/oss-cad-suite/bin/yosys`，0.66+4）；
openroad/sta/vcd2saif 均 NOT_FOUND。3 个 blocked_* 项如实标记为外部阻塞，不影响其余任务推进。

产出目录 `experiments/parsed/optional_capabilities/`：4 个文件。

检查点：`5cc72d1 checkpoint: 阶段5 可选能力审计`。

## 6. 阶段 6 · 最终复核

- 单元测试全绿：
  ```
  $ python3 -m unittest discover -s util/online_softmax_merge/tests
  Ran 110 tests in 2.2s  OK
  $ python3 -m unittest discover -s experiments/tests
  Ran 52 tests in 0.035s   OK
  ```
- 四个解析目录均存在且有内容：
  - `experiments/parsed/p0_4/`（12 文件）
  - `experiments/parsed/p0_5/`（8 文件）
  - `experiments/parsed/p0_6/`（6 文件）
  - `experiments/parsed/optional_capabilities/`（4 文件）
- `git status` 干净（`nothing to commit, working tree clean`）。

全部 15 条完成条件满足，目标达成。

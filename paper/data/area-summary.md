# 2026-10-27 回传实验面积数据汇总

本文件汇总 `ssh-return-20261027` 两批回传数据中的面积结果：

- **Phase 6**：完整 Spatz Cluster 逻辑综合（B2R vs A1）。
- **Phase 3**：online-merge 模块级面积复现（三个角色）。

`recovery_scalar_area_20261010` 那批没有可接受面积：`Spatz_No_Smu_area` 和
`Spatz_No_Smu_area_fastOpt` 停在 `OPT_DFF` 被中断，`Spatz_No_Smu_area_targetedAldff`
在 `FSM_EXTRACT` 断言失败，`Spatz_No_Smu_area_targetedNoFsm` 只到 pretechmap 检查点，
因此不纳入本汇总。

两批面积均为 **Nangate45 typical Liberty area units**，不是 µm²。两批都只做了一次
有效映射，不是三次重复，也未标记 FROZEN。SRAM 宏面积、宏内及穿越宏的时序、布线
寄生、布局布线均未测量。

---

## 1. Phase 6：完整 Spatz Cluster

- 数据来源：`phase6/results/phase6_area_summary.csv`、`phase6/results/phase6_area_summary.json`
- 顶层：`spatz_cluster_wrapper`，2 个核心，包含 Spatz/RVV、VLEN 512 VRF、DMA/AXI/TCDM 互联。
- 配置：`scalar-evidence.dram.hjson`；B2R 为 `EnableSmu=0`，A1 为 `EnableSmu=1`；
  共同设置 `SmuPrecisionSupport=1`、`SmuScalarOnly=1`、`SmuMixedNormalizationReciprocal=1`。
- 面积不含 SRAM 宏；20 个 SRAM 黑盒为 16 个 TCDM bank 和 4 个指令缓存 tag/data SRAM。

### 1.1 总量

| 变体 | 标准单元数 | 标准单元面积 | 时序单元面积 | 组合面积 | SRAM 黑盒 |
|---|---:|---:|---:|---:|---:|
| B2R（`EnableSmu=0`） | 3,203,927 | 3,869,820.668 | 769,266.680 | 3,100,553.988 | 20 |
| A1（`EnableSmu=1`，Scalar SMU + RVV） | 3,262,474 | 3,931,950.820 | 772,267.160 | 3,159,683.660 | 20 |
| **增量** | **+58,547** | **+62,130.152（+1.605505%）** | +3,000.480 | +59,129.672 | 0 |

时序单元面积把 `DFF_X1/DFFR_X1/DFFS_X1/DLH_X1/DLL_X1` 全部计入，包括 32,768 个
VRF 数据 latch（`DLH_X1`）和 800 个门控 latch（`DLL_X1`）。Yosys 原始
`sequential_area` 为 679,975.800 / 682,976.280；两种分项口径的总面积一致。

VRF 没有按 SRAM 黑盒排除；B2R 前端保留的 49 个只读查表 ROM（共 6,240 bit）用
`memory_map -rom-only` 映射为标准单元，也未按宏排除。

### 1.2 增量分解

| 组成 | 面积 | 占 Cluster 总增量 |
|---|---:|---:|
| SMU update engine | 59,846.542 | 96.32% |
| SMU OMERGE adapter | 437.304 | 0.70% |
| SMU issue arbiter | 658.084 | 1.06% |
| SMU response demux | 4.788 | 0.01% |
| **新增 SMU 子树合计** | **60,946.718** | **98.09%** |
| 其余控制/接口变化 | 1,183.434 | 1.90% |
| **Cluster 总增量** | **62,130.152** | 100% |

其余变化的模块级差值：

| 模块 | 面积差 |
|---|---:|
| core0 (`spatz_cc`) | +223.706 |
| core1 (`spatz_cc`) | +248.444 |
| AXI 位宽转换 (`axi_dw_converter`) | +109.060 |
| TCDM 互联 (`spatz_tcdm_interconnect`) | −4.256 |
| Cluster 本地逻辑（去掉宏后的残差） | +606.480 |
| **合计** | **+1,183.434** |

B2R 保留共同 OMERGE decode 和 MMIO 接口，因此 62,130.152 是本 epoch 下的
**边际增量**，不是 SMU 的绝对面积，也不能等同于历史 pre-SMU Spatz 基线。

集群内主要模块面积（A1，含后代，供参考）：

| 模块 | 实例数 | 面积 | 占 A1 总面积 |
|---|---:|---:|---:|
| `spatz_cc` core0 | 1 | 1,653,279.908 | 42.05% |
| `spatz_cc` core1 | 1 | 1,578,949.932 | 40.16% |
| `axi_dma_xbar` | 1 | 170,867.760 | 4.35% |
| `axi_dw_converter` | 1 | 90,208.048 | 2.29% |
| `spatz_tcdm_interconnect` | 1 | 71,385.888 | 1.82% |
| `axi_to_mem_interleaved`（DMA） | 1 | 65,599.324 | 1.67% |
| `snitch_icache` | 1 | 51,209.256 | 1.30% |
| `spatz_cluster_peripheral` | 1 | 43,970.066 | 1.12% |
| `online_merge_update_engine` | 1 | 59,846.542 | 1.52% |
| `online_merge_omerge_adapter` | 1 | 437.304 | 0.011% |
| `smu_issue_arbiter` | 1 | 658.084 | 0.017% |
| `smu_response_demux` | 1 | 4.788 | 0.0001% |

完整模块表见 `phase6/results/phase6_cluster_direct_modules.csv`，单元直方图见
`phase6/results/phase6_cell_histogram.csv`。不能把所有层级模块面积直接相加，否则会重复计数。

---

## 2. Phase 3：online-merge 模块级面积

- 数据来源：`phase3/results/phase3-summary.csv`、`phase3/results/phase3-summary.json`
- 顶层：`online_merge_legacy_scalar_mapped_top`、
  `online_merge_mixed_division_scalar_mapped_top`、
  `online_merge_mixed_reciprocal_scalar_mapped_top`。
- 每个角色一次有效映射，Yosys 0.70+221；面积流与 timing-proxy 流是两套独立映射。

### 2.1 面积流

| 角色 | 映射单元数 | 面积 | 时序面积 | 组合面积 | 历史面积 | 相对历史 |
|---|---:|---:|---:|---:|---:|---:|
| Legacy Scalar | 68,902 | 72,302.790 | 2,761.080 | 69,541.710 | 72,399.082 | −0.1330% |
| Mixed+Division | 46,864 | 51,612.246 | 3,521.840 | 48,090.406 | 52,000.074 | −0.7458% |
| Mixed+Reciprocal | 48,141 | 52,079.608 | 2,824.920 | 49,254.688 | 52,407.586 | −0.6258% |

角色间关系：

| 比较 | 面积差 | 百分比 |
|---|---:|---:|
| Mixed+Division vs Legacy Scalar | −20,690.544 | −28.6165% |
| Mixed+Reciprocal vs Legacy Scalar | −20,223.182 | −27.9701% |
| Mixed+Reciprocal vs Mixed+Division | +467.362 | +0.9055% |

### 2.2 timing-proxy 流（独立映射，面积不可与 2.1 混用）

| 角色 | 单元数 | 该流面积 | ABC delay proxy | 目标 | 是否达标 |
|---|---:|---:|---:|---:|---:|
| Legacy Scalar | 55,594 | 62,022.954 | 11,286.15 ps | 1,500 ps | 否 |
| Mixed+Division | 29,039 | 33,929.098 | 14,141.03 ps | 1,500 ps | 否 |
| Mixed+Reciprocal | 32,744 | 37,187.598 | 16,495.05 ps | 1,500 ps | 否 |

ABC delay 是逻辑延迟代理，不是 STA；该流面积必须与 2.1 的面积分开报告。

---

## 3. 两批数据的比较边界

- Phase 3 的 Mixed+Reciprocal 面积 52,079.608（独立模块 top，无约束面积流）与 Phase 6 的
  SMU update engine 59,846.542（完整 Cluster 内 targetedNoFsm 映射后的子树）**口径不同**，
  不能互相替代或直接相减。
- Phase 6 的 B2R/A1 是在同一份匹配 RTL 闭包、同一 flist、同一 Liberty 下的一对映射；
  Phase 3 是独立模块流程。两批只共享工具 epoch 和 Liberty 文件。
- Phase 6 的 OpenSTA 结果基于未缓冲面积网表，存在未缓冲高扇出和 Liberty 域外外推，
  不能据此推导可靠 Fmax 或“SMU 没有时序代价”；本文件只汇总面积，不纳入 STA 结论。

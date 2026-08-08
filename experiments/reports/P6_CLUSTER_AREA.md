# P6 — Cluster-Level Area Overhead（工具链受限，诚实近似）

## 目标与工具链约束

P6-1/2/3 需要 C0_CLUSTER / C1_CLUSTER_SCALAR_SMU / C2_CLUSTER_FULL_SMU 的完整
cluster mapped area。固定工具链（Yosys 0.66 + `read_slang` + Nangate45）无法读入
`spatz_cluster` 顶层：完整 bender flist 包含 **350 个源文件**（`work-p6/cluster_sources.txt`），
其中 AXI / register_interface 等第三方 IP 使用 `parameter type axi_req_t = logic`
并在模块体内做 `.aw` / `.b` 等成员访问；`read_slang` 对每个模块独立 elaboration，
默认参数类型退化为 `logic`，导致成员访问报错（`work-p6/elab_cluster.log`、
`work-p6/elab_cluster_patched.log`，lzc.sv 的 replication 常数已用 `'0` 修补后仍失败）。
逐一修补第三方 RTL 属于大规模兼容性封装，按本阶段原则不做。仓库内也没有 cluster
综合 flow 或已发布 cluster area 数据，因此**不声称完整 cluster mapped area**。

## 精确的 Standalone 增量面积（P0-6，3-trial 完全确定）

| Config | Cells | Mapped Area | 说明 |
| --- | ---: | ---: | ---: |
| C0 (no SMU) | 0 | 0 | 概念 reference |
| C1 — Scalar SMU（增量） | 73,505 | 77,103.292 | 相对 C0 的精确增量 |
| C2 — Full SMU（增量） | 107,372 | 114,713.298 | 相对 C0 的精确增量 |

`Full/Scalar = 1.488`（Full vector datapath 额外 +48.8% standalone）。

## Cluster overhead 的保守上界

把 standalone SMU 面积直接当作 cluster 内新增逻辑，则
`Overhead_cluster ≤ A_SMU_incremental / A_cluster`。下表是**参数化的上界**，
`A_cluster` 是假设的 baseline cluster 逻辑 cell 数（**非实测**，仅用于量级判断）：

| Assumed A_cluster (cells) | Scalar overhead ≤ | Full overhead ≤ |
| ---: | ---: | ---: |
| 200k | 38.6% | 57.4% |
| 500k | 15.4% | 22.9% |
| 1M | 7.7% | 11.5% |
| 2M | 3.9% | 5.7% |

## 结论与论文口径建议

- 完整 cluster-level overhead 需要真实 cluster 综合（当前工具链不可行），论文应
  用 **"incremental SMU mapped area"**（Scalar 77.1k cells / Full 114.7k cells）
  作为硬件面积声明，并明确标注为 standalone SMU 口径。
- Scalar 增量（77k cells）比 Full 增量（115k cells）小 33%，且 Full 的 vector
  datapath 是主要面积来源（P4/P5：+37.6k，+48.8%）。
- 若后续获得 baseline cluster area（如完整 cluster 综合或厂商数字），可直接用
  `overhead = 77,103 / A_cluster` 换算，公式已固化在 CSV。

## 数据文件
- CSV：`experiments/parsed/p6_cluster/p6_cluster_area.csv`
- 生成脚本：`experiments/scripts/derive_p6_cluster_area.py`
- 失败证据：`work-p6/elab_cluster.log`、`work-p6/elab_cluster_patched.log`

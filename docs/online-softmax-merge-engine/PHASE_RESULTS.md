# 阶段成果记录

本文件用于记录每个实施节点的进展、证据和备注。初始状态均为 `未开始`，后续执行时逐项更新。

## Node 0：Baseline 与 Git 准备

状态：已完成

目标：

- 建立清晰的 feature branch，并记录当前仓库基线状态。

验收标准：

- 当前工作位于 `feature/online-softmax-merge-engine`。
- 初始分支和状态已经记录。
- 无关 dirty files 已经记录。
- 构建入口可用。

证据：

- 2026-05-25 17:01 CST 复查 `git status --short --branch`，当前分支为
  `feature/online-softmax-merge-engine`。
- 2026-05-25 运行 `make -C hw/system/spatz_cluster help`，Makefile 目标列表
  可以正常打印；过程中只出现 Bender manifest warning，未修改 tracked source
  files。

备注：

- 本轮复查时工作树已经包含 online merge 相关改动和新增文件；这些改动与本
  任务相关，不作为无关 dirty changes 处理。
- 当前另有 `.codexignore` 和 `ARCHITECTURE.md` untracked 文件，尚未确认与
  本任务直接相关，本轮不纳入阶段提交。

## Node 1：硬件接口定义

状态：已完成

目标：

- 固定 v1 的软件可见寄存器接口和 TCDM 数据布局。

验收标准：

- 寄存器名称、字段和语义已经文档化。
- 软件 reference 和硬件设计使用同一套 merge 方程。
- 地址、`N`、`D` 和 stride 语义无歧义。
- v1 明确排除直接 DRAM 访问和 Spatz ISA 修改。

证据：

- [PLAN.md](PLAN.md) 已记录 `MERGE_*` MMIO 寄存器、`start` /
  `clear_done` 控制字段、`busy` / `done` / `error` 状态字段、TCDM buffer
  布局和默认 merge 方程。
- `spatz_cluster_peripheral_reg.hjson` 中已经加入同名寄存器定义，字段名与
  计划一致。

备注：

- v1 仍明确排除 Spatz ISA、decoder、controller、VFU、VRF 修改，以及直接
  DRAM 访问。

## Node 2：MMIO 寄存器支持

状态：已完成

目标：

- 扩展 cluster peripheral，用于 engine 配置、启动和状态观测。

验收标准：

- 生成后的 C header 包含所有 `MERGE_*` offset 和 field define。
- RTL 通过生成的 `reg2hw` 信号读取配置。
- RTL 通过生成的 `hw2reg` 信号写回状态。
- 现有 peripheral 功能仍然可编译。

证据：

- `hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg.hjson`
  定义了 `MERGE_SRC_M_OLD` 到 `MERGE_STATUS`。
- 生成文件
  `spatz_cluster_peripheral_reg_pkg.sv`、`spatz_cluster_peripheral_reg_top.sv`
  和 `sw/snRuntime/include/spatz_cluster_peripheral.h` 已包含对应 offset 和
  field define。
- `spatz_cluster_peripheral.sv` 将 reg2hw 配置导出为
  `merge_src_*`、`merge_dst_*`、`merge_n`、`merge_d`、`merge_stride`，
  并将 `merge_busy_i`、`merge_done_i`、`merge_error_i` 写入 hw2reg
  `MERGE_STATUS`。

备注：

- 2026-05-25 和 2026-05-31 的 `bin/spatz_cluster.vlt` / `sw.vlt` / CTest 记录
  已覆盖生成寄存器代码、runtime header 和完整 peripheral 集成的构建回归。

## Node 3：Engine RTL

状态：受限语义原型已完成；完整 datapath 待实现

目标：

- 新增独立的 Streaming Merge-Update Engine RTL 模块。

验收标准：

- 模块可以加入 Spatz build source list 并完成编译。
- `start` 后 `busy=1`，直到完成或出错。
- 完成所有请求工作后，`done=1` 且 `busy=0`。
- 非法 `N=0`、`D=0` 或未对齐地址会置 `error=1`。
- 数据搬运只使用 engine 的 TCDM master 端口。

证据：

- 新增 `hw/ip/online_merge/src/online_merge_update_engine.sv`。
- 模块接口包含 clock/reset、9 个 base address、`N`、`D`、`stride`、
  `start`、`clear_done`、`busy`、`done`、`error` 和一组 TCDM
  `tcdm_req_t` / `tcdm_rsp_t` master 端口。
- RTL 状态机包含 `IDLE`、`LOAD_SCALAR`、`COMPUTE_SCALAR`、
  `STORE_SCALAR`、`UPDATE_VECTOR`、`DONE`、`ERROR`。
- `valid_cfg()` 覆盖 `N=0`、`D=0`、未 4-byte 对齐地址和未 4-byte 对齐
  stride 的错误路径。
- 2026-05-25 benchmark 新增 invalid-config cases，覆盖 `N=0`、`D=0`、
  misaligned address 和 misaligned stride 的 `error` 状态观测。
- 2026-05-25 RTL 新增 `supported_scalar_merge()` 检查：当前受限语义只允许
  `l_old=0`、`l_tile=0`，或 `m_old==m_tile && l_old==l_tile` 的等权特例；
  对其它合法但不支持的 mixed-scalar 配置显式置 `error`，避免静默写出近似
  错误结果。

备注：

- 当前 RTL 没有实现完整 `exp()` 和除法 datapath。`compute_scalar_merge()`
  与 `compute_vector_merge()` 只覆盖 `l_old=0`、`l_tile=0`、以及构造出的等
  权重/同指数特例；因此不能声称已满足 PLAN 中完整 online softmax merge
  方程。
- v1 已经收敛为“受限 merge-update 语义验证原型”，并配套了 error-path、
  unsupported-path、break-even 和稳定性记录。后续不应继续扩大论文 A 的语义
  主张；真正下一步是为论文 B 选择并实现完整 `exp`、加法、乘法、除法流水。

## Node 4：Spatz Cluster 集成

状态：已完成

目标：

- 将 engine 接入 cluster MMIO 控制路径和 TCDM interconnect。

验收标准：

- engine 通过 `spatz_tcdm_interconnect` 发起请求。
- core、AXI-to-TCDM、DMA、icache 和 peripheral 路径仍然可编译。
- TCDM event counter 逻辑有效，或已经明确更新。
- v1 不修改 Spatz pipeline 文件。

证据：

- `Bender.yml` 已加入
  `hw/ip/online_merge/src/online_merge_update_engine.sv`。
- `spatz_cluster.sv` 中 `NumTCDMIn = NrTCDMPortsCores + 2`，narrow TCDM
  interconnect 输入连接为 `{axi_soc_req, merge_req, tcdm_req}`。
- `spatz_cluster.sv` 实例化 `i_online_merge_update_engine`，连接 MMIO 导出
  配置、状态返回和 TCDM master 端口。
- `merge_req.q.user.is_core = 1'b0`，`core_id` 与 `req_id` 清零，用于标记
  非 core 流量。
- TCDM event counter 的 `tcdm_event_req/rsp` 使用 `NumTCDMIn`，并纳入
  `merge_req/merge_rsp`。

备注：

- 未发现 Spatz pipeline 文件改动；本轮只读检查覆盖 `spatz_cluster.sv`、
  `Bender.yml` 和 peripheral 连接。
- 2026-05-25 和 2026-05-31 的 Verilator 构建、软件构建和单项 CTest 已验证
  cluster 集成可构建、可运行。

## Node 5：Runtime Wrapper 与 Benchmark

状态：受限语义 benchmark 已完成；完整方程 benchmark 待扩展

目标：

- 提供软件入口和 benchmark 覆盖。

验收标准：

- CMake 中存在 online softmax merge 测试目标。
- `ctest -R online-softmax-merge` 可以运行。
- 硬件输出在误差范围内匹配 CPU reference。
- benchmark 报告 CPU scalar path 和 engine path 对比所需 counters。

证据：

- 新增 `sw/spatzBenchmarks/online-softmax-merge/main.c`。
- Benchmark 内提供 `smu_start(...)`、`smu_wait(void)`、`smu_done(void)`、
  `smu_error(void)`。
- `sw/spatzBenchmarks/CMakeLists.txt` 已加入
  `add_snitch_test(online-softmax-merge online-softmax-merge/main.c)`。
- Benchmark 在 TCDM 中分配 old/tile/output/ref buffers，启动 engine 后比较
  `m/l/O` 输出，并打印 CPU cycles、engine cycles、TCDM accessed 和
  congested counters。
- 2026-05-25 benchmark 增加 `run_invalid_cases()`，对 `N=0`、`D=0`、
  misaligned address、misaligned stride 四种非法配置要求 engine cleanly report
  `MERGE_STATUS.error` 且 `busy=0`。
- 2026-05-25 benchmark 增加 `run_unsupported_cases()`，覆盖配置合法但当前
  受限 datapath 不支持的 `mixed-m` 和 `unequal-l` cases，要求 engine report
  `MERGE_STATUS.error`。
- 2026-05-26 benchmark 增加 `run_full_reference_probe_case()`，使用合法通用
  mixed-scalar 输入覆盖 `m_old > m_tile`、`m_old < m_tile`、`m_old == m_tile`、
  unequal `l`、small `l` 和 mixed `O` 组合；当前 RTL 仍要求该 probe 返回
  `MERGE_STATUS.error`，并记录一个固定完整方程 golden 样本
  `ref_l0=0x3f5e3b41`、`ref_o00=0xbe567a2b`，为后续完整 datapath 接入提供
  测试入口。
- 2026-05-25 benchmark 增加 `run_stride_zero_case()`，使用 packed vector
  buffers 和 `MERGE_STRIDE=0` 覆盖 RTL 中 `stride==0` 表示 `D * 4` 默认
  row stride 的路径。
- 2026-05-25 benchmark 有效 case 改为通过 `smu_wait_observe_busy()` 等待，
  并在长运行 `N=16, D=64` case 上要求完成前至少观测到一次
  `MERGE_STATUS.busy=1`；短 case 仍执行功能验证，但不把软件轮询是否命中
  短暂 busy 作为硬性条件。

备注：

- 当前 CPU reference 与输入 case 被构造成匹配 RTL 的受限 merge 语义；它不是
  PLAN 中完整 online softmax 方程的通用 reference。
- 新增 full-reference probe 只把完整方程 golden 样本作为固定证据记录，不在
  仿真中运行昂贵的 libm 或软件浮点除法。当前它仍是 unsupported-path 测试；
  后续 datapath 实现完整 `exp`、乘法和除法后，应把该 probe 切换为硬件输出
  比对。
- 2026-05-31 已通过三次 verbose Verilator CTest 确认 benchmark 可执行并
  稳定通过；覆盖范围仍限于当前受限语义、zero-stride packed layout、非法配置
  error path 和 unsupported mixed-scalar error path。

## Node 6：验证与性能评估

状态：受限语义原型已完成；完整 online softmax 评估未开始

目标：

- 验证正确性、构建集成和初步性能价值。

验收标准：

- Verilator cluster binary 可以构建。
- 面向 Verilator 的软件可以构建。
- online softmax merge 测试通过。
- 近似误差已经测量并记录。
- 至少一个目标 case 中 engine path 快于 CPU scalar reference。
- 已记录 TCDM accessed 和 congested counters。

证据：

- 2026-05-25 运行 `make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`，结果
  为 `bin/spatz_cluster.vlt` 已是最新，命令退出码为 0。
- 2026-05-25 运行 `make -C hw/system/spatz_cluster sw.vlt`，CMake 日志确认
  添加 `online-softmax-merge`，软件全量构建完成，命令退出码为 0。
- 2026-05-25 在 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R online-softmax-merge --output-on-failure`，1/1 测试通过，总耗时
  90.85 秒。
- 2026-05-25 增加 invalid-config benchmark 覆盖后，重新运行
  `make -C hw/system/spatz_cluster sw.vlt`，软件全量构建完成，命令退出码为 0。
- 2026-05-25 在 `hw/system/spatz_cluster/sw/build` 重新运行
  `ctest -R online-softmax-merge --output-on-failure`，1/1 测试通过，总耗时
  108.40 秒，覆盖有效 case 与非法配置 error-path case。
- 2026-05-25 unsupported mixed-scalar 显式报错改动后，重新运行
  `make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`，Verilator 硬件构建
  完成，命令退出码为 0。
- 2026-05-25 重新运行 `make -C hw/system/spatz_cluster sw.vlt`，软件全量构建
  完成，命令退出码为 0。
- 2026-05-25 在 `hw/system/spatz_cluster/sw/build` 重新运行
  `ctest -R online-softmax-merge --output-on-failure`，1/1 测试通过，总耗时
  109.14 秒，覆盖有效 case、非法配置 error-path case 和 unsupported mixed-scalar
  error-path case。

备注：

- 构建日志包含既有 warning，例如 `tech_cells_generic` manifest warning、
  runtime/benchmark 编译 warning，以及 debug address range table warning；
  未导致构建失败。
- 当前测试通过的是受限语义 benchmark，不能证明完整 online softmax merge
  方程已经实现；不支持的 mixed-scalar 合法配置现在应显式报错，而不是返回
  近似输出。
- 早期 CTest 输出未展示 benchmark 内部 cycle/counter 打印；2026-05-25 后已
  改为使用 verbose CTest 保留 stdout，并在
  [COMPARISON_EXPERIMENT.md](COMPARISON_EXPERIMENT.md) 中归档 `cpu`、
  `engine`、`tcdm_accessed`、`tcdm_congested` 数值。
- 2026-05-25 新增非法配置测试已经通过 `sw.vlt` 和单项 CTest 验证。
- 2026-05-25 新增 zero-stride packed-layout benchmark case 后，重新运行
  `make -C hw/system/spatz_cluster sw.vlt`，软件全量构建完成，命令退出码为
  0。
- 2026-05-25 在 `hw/system/spatz_cluster/sw/build` 重新运行
  `ctest -R online-softmax-merge --output-on-failure`，1/1 测试通过，总耗时
  116.51 秒，覆盖有效 case、zero-stride packed-layout case、非法配置
  error-path case 和 unsupported mixed-scalar error-path case。
- 2026-05-25 新增 busy-observed benchmark check 后，重新运行
  `make -C hw/system/spatz_cluster sw.vlt`，软件全量构建完成，命令退出码为
  0。
- 2026-05-25 在 `hw/system/spatz_cluster/sw/build` 重新运行
  `ctest -R online-softmax-merge --output-on-failure`，1/1 测试通过，总耗时
  116.35 秒；后续 verbose run 暴露 `N=1, D=1` 太短，软件轮询可能错过
  busy，因此 busy-observed 硬性检查收敛到长运行 case。
- 2026-05-25 修正 busy-observed 检查范围后，重新运行
  `make -C hw/system/spatz_cluster sw.vlt`，软件全量构建完成，命令退出码为
  0。
- 2026-05-25 在 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R online-softmax-merge -V`，1/1 测试通过，总耗时 114.31 秒，并
  保留 benchmark stdout。
- 2026-05-25 verbose benchmark 输出的 cycle/counter 摘要如下：

  ```text
  N=1,  D=1,  case=0: cpu=188,   engine=1253, tcdm_accessed=0, tcdm_congested=0
  N=4,  D=8,  case=1: cpu=915,   engine=1489, tcdm_accessed=0, tcdm_congested=0
  N=16, D=64, case=2: cpu=23017, engine=9629, tcdm_accessed=0, tcdm_congested=0
  N=4,  D=8,  case=3: cpu=938,   engine=1480, tcdm_accessed=0, tcdm_congested=0
  N=4,  D=8,  case=4: cpu=917,   engine=1489, tcdm_accessed=0, tcdm_congested=0
  ```

  在 `N=16, D=64, case=2` 受限语义 case 中，engine path 快于 CPU reference
  path；当前记录的 TCDM counters 均为 0，应视为 counter 接线或选择仍需后续
  复核，而不是无访问量结论。
- 2026-05-25 复核 TCDM counter 为 0 的原因：RTL/peripheral 已将
  `{axi_soc_req, merge_req, tcdm_req}` 纳入 `tcdm_events.inc_accessed` /
  `inc_congested`，但 `sw/snRuntime/include/perf_cnt.h` 仍按 16 个 perf
  counters 描述 `perf_reg_t`；当前生成寄存器实际只有
  `SPATZ_CLUSTER_PERIPHERAL_PARAM_NUM_PERF_COUNTERS == 2`，导致 runtime 对
  `hart_select` 和 `perf_counter` 的 MMIO offset 计算错误。已将
  `SNRT_PERF_N_CNT` 对齐到生成 header 的参数。
- 2026-05-25 runtime perf counter layout 修正后，重新运行
  `make -C hw/system/spatz_cluster sw.vlt`，软件全量构建完成，命令退出码为
  0。
- 2026-05-25 在 `hw/system/spatz_cluster/sw/build` 重新运行
  `ctest -R online-softmax-merge -V`，1/1 测试通过，总耗时 116.14 秒，
  TCDM counters 恢复为非零。修正后的 cycle/counter 摘要如下：

  ```text
  N=1,  D=1,  case=0: cpu=188,   engine=1253, tcdm_accessed=328,  tcdm_congested=1
  N=4,  D=8,  case=1: cpu=915,   engine=1489, tcdm_accessed=496,  tcdm_congested=3
  N=16, D=64, case=2: cpu=23017, engine=9629, tcdm_accessed=5218, tcdm_congested=16
  N=4,  D=8,  case=3: cpu=938,   engine=1480, tcdm_accessed=496,  tcdm_congested=3
  N=4,  D=8,  case=4: cpu=917,   engine=1489, tcdm_accessed=496,  tcdm_congested=3
  ```
- 2026-05-26 新增 full-reference probe 后，重新运行
  `make -C hw/system/spatz_cluster sw.vlt`，软件全量构建完成，命令退出码为
  0。
- 2026-05-26 在 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R online-softmax-merge -V`，1/1 测试通过，总耗时 148.11 秒。
  新增 probe 输出如下：

  ```text
  online-softmax-merge full-ref-probe generic-mixed status=0x4 ref_l0=0x3f5e3b41 ref_o00=0xbe567a2b
  ```
- 2026-05-26 根据用户要求增加 `N/D` sweep，复跑
  `ctest -R online-softmax-merge -V` 并形成
  [COMPARISON_EXPERIMENT.md](COMPARISON_EXPERIMENT.md)。本次 1/1 测试通过，
  总耗时 231.66 秒。有效 case 的 CPU scalar path 与 engine path 对比如下：

  ```text
  N=1,  D=1,  case=0: cpu=174,   engine=1225, speedup=0.14x
  N=4,  D=8,  case=1: cpu=902,   engine=1451, speedup=0.62x
  N=8,  D=16, case=2: cpu=3126,  engine=2276, speedup=1.37x
  N=8,  D=32, case=2: cpu=5933,  engine=3284, speedup=1.81x
  N=16, D=32, case=2: cpu=11736, engine=5490, speedup=2.14x
  N=16, D=64, case=2: cpu=23013, engine=9635, speedup=2.39x
  N=4,  D=8,  case=3: cpu=907,   engine=1408, speedup=0.64x
  N=4,  D=8,  case=4: cpu=913,   engine=1383, speedup=0.66x
  ```

- 2026-05-31 为论文 A 补齐 break-even 附近 sweep，新增
  `N=8,D=8`、`N=8,D=12`、`N=4,D=16`、`N=8,D=24`。重新运行
  `make -C hw/system/spatz_cluster sw.vlt`，软件全量构建完成，命令退出码为
  0。
- 2026-05-31 在 `hw/system/spatz_cluster/sw/build` 连续三次运行
  `ctest -R online-softmax-merge -V`，三次均 1/1 通过，总耗时分别为
  229.02 秒、232.16 秒和 219.20 秒；有效 case 的 cycle 和 TCDM counter
  逐项一致。最新有效 case 摘要如下：

  ```text
  N=1,  D=1,  case=0: cpu=191,   engine=1216, speedup=0.16x
  N=4,  D=8,  case=1: cpu=915,   engine=1486, speedup=0.62x
  N=8,  D=8,  case=2: cpu=1704,  engine=1789, speedup=0.95x
  N=8,  D=12, case=2: cpu=2433,  engine=2011, speedup=1.21x
  N=4,  D=16, case=2: cpu=1613,  engine=1694, speedup=0.95x
  N=8,  D=16, case=2: cpu=3114,  engine=2254, speedup=1.38x
  N=8,  D=24, case=2: cpu=4520,  engine=2798, speedup=1.62x
  N=8,  D=32, case=2: cpu=5910,  engine=3284, speedup=1.80x
  N=16, D=32, case=2: cpu=11744, engine=5502, speedup=2.13x
  N=16, D=64, case=2: cpu=23033, engine=9607, speedup=2.40x
  ```

  当前受限等权 case 的 break-even 位于约 64 到 96 个 vector elements 之间。
  最新数据已同步到 [COMPARISON_EXPERIMENT.md](COMPARISON_EXPERIMENT.md) 和
  `data_process/attnres/data/online_softmax_merge_bypass.csv`。


## Paper A 阶段状态

状态：阶段完成

说明：

- 受限语义原型、论文 A 的基础实验、break-even sweep、稳定性记录、图表和
  LaTeX 初稿已经闭环。
- 后续不再扩大受限语义 benchmark 的论文主张。
- 论文 A 的结果可作为论文 B 的 baseline 和背景，但不能作为完整 online softmax
  merge 方程的性能证据。

## 当前下一步

下一阶段按 [PAPER_B_FULL_SYSTEM_PLAN.md](PAPER_B_FULL_SYSTEM_PLAN.md) 推进。
核心方向：

- 保持现有 `MERGE_*` MMIO/TCDM 接口不变。
- 不修改 Spatz ISA、decoder、controller、VFU、VRF、VLSU 或指令 pipeline。
- 在 cluster-local SMU 内部实现 `ExpLUT + reciprocal` 的完整 mixed-scalar
  online softmax merge 近似 datapath。
- 把 `run_full_reference_probe_case()` 从 expected-error 改为 correctness gate。
- 重新运行完整方程 microbenchmark、attention-like workload、误差统计和 A/B
  性能评估。

## Phase B0：文档和状态冻结

状态：已完成

目标：

- 将论文 A 标记为阶段完成。
- 固定论文 B 的旁路 SMU 路线。
- 明确不修改 Spatz pipeline。

验收标准：

- 后续实现可以直接从 Phase B1 开始。
- 文档明确论文 A 数据只能作为 baseline，不能作为完整 online softmax merge
  方程的性能证据。
- 论文 B 第一版保持现有 `MERGE_*` MMIO/TCDM layout，不修改 Spatz ISA、
  decoder、controller、VFU、VRF、VLSU 或指令 pipeline。

证据：

- 新增 [PAPER_B_FULL_SYSTEM_PLAN.md](PAPER_B_FULL_SYSTEM_PLAN.md)，记录
  Phase B0 到 B7 的目标、实现要点、验收标准、测试命令和风险 fallback。
- [PAPER_ROADMAP.md](PAPER_ROADMAP.md) 已将论文 A 状态更新为阶段完成，并
  指向论文 B 完整系统计划。
- [README.md](README.md) 已更新当前实现边界和下一阶段方向。
- 2026-06-01 运行 `git diff --check`，未报告 whitespace error。

备注：

- 2026-06-01 已提交：
  `[docs] Mark restricted merge paper phase complete`。

## Phase B1：软件数值模型

状态：已完成

目标：

- 建立完整 online softmax merge 方程 reference。
- 建立与后续 RTL 计划一致的 `ExpLUT + reciprocal` 近似模型。
- 记录固定 full-reference probe golden values 和误差统计。

验收标准：

- 覆盖 `m_old > m_tile`、`m_old < m_tile`、`m_old == m_tile`、
  `l_old != l_tile`、small `l` 和 mixed signed `O`。
- 输出 max absolute error、guarded max relative error、mean absolute error。
- 初始近似目标达到 `<= 1e-3`，并记录是否可逼近 `<= 1e-4`。

证据：

- 新增 `data_process/attnres/code/full_merge_numeric_model.py`。
- 新增 `data_process/attnres/data/online_softmax_full_merge_numeric.csv`。
- 模型配置：
  - `exp` 近似为 `[-8, 0]` 区间 256 段线性 LUT，低于 `-8` 饱和为 0，
    高于 0 饱和为 1。
  - reciprocal 近似为 `[1, 2]` mantissa 256 段线性 LUT 插值，无 Newton
    refinement。
  - guarded relative error 使用 `abs_err / max(abs(reference), 1.0)`。
- 覆盖 case：
  - `generic-mixed N=4,D=8`
  - `generic-mixed N=8,D=16`
  - `generic-mixed N=8,D=32`
  - `generic-mixed N=16,D=64`
  - `delta-sweep N=16,D=64`
- 2026-06-01 运行：

  ```text
  python3 data_process/attnres/code/full_merge_numeric_model.py
  ```

  输出最差误差：

  ```text
  max_abs_err=9.775161743e-06
  guarded_max_rel_err=3.325012490e-06
  mean_abs_err=2.174088011e-06
  ```

  所有 case 均低于 `1e-3` 初始目标，并已经低于 `1e-4`。
- 2026-06-01 运行 `make -C hw/system/spatz_cluster sw.vlt`，软件全量构建
  完成，退出码 0。
- 2026-06-01 在 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R online-softmax-merge -V`，1/1 测试通过，总耗时 285.30 秒。
  full-reference probe 仍按当前受限 RTL 返回 expected-error，输出已更新为：

  ```text
  online-softmax-merge full-ref-probe generic-mixed status=0x4 ref_l0=0x3f5e3b41 ref_o00=0xbe567a2c
  ```
- 固定 `generic-mixed N=4,D=8` full-reference probe golden：

  ```text
  ref_l0_bits=0x3f5e3b41
  ref_o00_bits=0xbe567a2c
  ```

备注：

- 早期 `run_full_reference_probe_case()` 打印的 `ref_o00=0xbe567a2b` 是基于
  理想化十进制输入的一次最终舍入；Phase B1 复核后，按 C benchmark 中已经
  舍入为 FP32 的 input buffer 计算，authoritative golden 应为
  `0xbe567a2c`。Benchmark 的固定打印值已同步修正，但该 probe 在当前受限 RTL
  下仍保持 expected-error 行为；切换为 correctness gate 属于后续 Phase B4。

## Phase B2：近似 RTL 模块

状态：已完成

目标：

- 实现 SMU 内部可复用的近似数学模块。
- 使 RTL 近似行为与 Phase B1 软件模型保持一致。

验收标准：

- 近似模块可以单独编译。
- 模块级 testbench 或集成 benchmark 能证明近似输出与软件模型一致。

证据：

- 新增 `hw/ip/online_merge/src/online_merge_fp32_helpers.sv`，提供 FP32 bit
  classification、有限正 normal 检查、`abs(x)` 到 `exp` LUT index 的定点
  转换，以及 Q1.23 到 FP32 的辅助函数。
- 新增 `hw/ip/online_merge/src/online_merge_exp_approx.sv`。
  - 输入为 FP32 bit pattern。
  - 设计范围为 `[-8, 0]`。
  - `x > 0` 饱和为 Q1.23 `1.0`。
  - `x < -8` 饱和为 Q1.23 `0.0`。
  - NaN/Inf 输出 `unsupported_o=1`。
  - 输出为 256 段 LUT 线性插值得到的 Q1.23 近似值。
- 新增 `hw/ip/online_merge/src/online_merge_recip_approx.sv`。
  - 输入为正 finite normal FP32 bit pattern。
  - 对 `[1, 2]` mantissa 使用 256 段 LUT 线性插值。
  - 输出为 `recip_q1_23_o * 2**scale_exp_o`。
  - 非正数、NaN、Inf、subnormal 输出 `unsupported_o=1`。
- 新增 `hw/ip/online_merge/test/online_merge_approx_tb.sv`，覆盖：
  - `exp(0)`
  - `exp(-0.75)`
  - `exp(-8)`
  - 正输入饱和
  - NaN unsupported
  - `recip(1.0)`
  - `recip(0x3f5e3b41)`，即 full-reference probe 的 `l0`
  - reciprocal zero / Inf unsupported
- `Bender.yml` 已将三个新 RTL 源文件加入 Spatz cluster build source list，
  testbench 不进入默认集成构建。
- 2026-06-01 运行：

  ```text
  verilator --lint-only --timing -Wall --Wno-DECLFILENAME --Wno-UNUSEDPARAM \
    --Wno-UNUSEDSIGNAL --Wno-fatal \
    hw/ip/online_merge/src/online_merge_fp32_helpers.sv \
    hw/ip/online_merge/src/online_merge_exp_approx.sv \
    hw/ip/online_merge/src/online_merge_recip_approx.sv \
    hw/ip/online_merge/test/online_merge_approx_tb.sv \
    --top-module online_merge_approx_tb
  ```

  结果：Verilator lint-only 退出码 0。
- 2026-06-01 运行：

  ```text
  verilator --binary --timing -Wall --Wno-DECLFILENAME --Wno-UNUSEDPARAM \
  --Wno-UNUSEDSIGNAL --Wno-fatal \
    hw/ip/online_merge/src/online_merge_fp32_helpers.sv \
    hw/ip/online_merge/src/online_merge_exp_approx.sv \
    hw/ip/online_merge/src/online_merge_recip_approx.sv \
    hw/ip/online_merge/test/online_merge_approx_tb.sv \
    --top-module online_merge_approx_tb
  obj_dir/Vonline_merge_approx_tb
  ```

  结果：`online_merge_approx_tb PASS`，退出码 0。
- 2026-06-01 重新运行：

  ```text
  python3 data_process/attnres/code/full_merge_numeric_model.py
  ```

  当前 RTL-aligned LUT 插值模型最差误差：

  ```text
  max_abs_err=9.775161743e-06
  guarded_max_rel_err=3.325012490e-06
  mean_abs_err=2.174088011e-06
  ```

  所有 case 均低于 `1e-3` 初始目标，并已经低于 `1e-4`。
- 2026-06-01 运行：

  ```text
  make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
  ```

  结果：Verilator system binary 构建完成，退出码 0。构建日志仍包含既有
  `tech_cells_generic` manifest warning、testbench/外部 IP latch warning，未导致
  构建失败。

备注：

- Phase B2 只新增可复用近似模块，暂不替换
  `online_merge_update_engine.sv` 的受限语义 datapath；完整 SMU datapath 接入属于
  Phase B3。

## Phase B3/B4：完整 SMU datapath 与 full mixed-scalar gate

状态：已完成最小闭环

实现摘要：

- `hw/ip/online_merge/src/online_merge_update_engine.sv` 已接入
  `online_merge_exp_approx.sv`、`online_merge_recip_approx.sv` 和
  `online_merge_fp32_helpers.sv`。
- 保持现有 `MERGE_*` MMIO/TCDM layout，不修改 Spatz ISA、decoder、controller、
  VFU、VRF、VLSU 或 pipeline。
- `supported_scalar_merge()` 已从论文 A 受限语义放宽到 finite normal/zero 输入，
  只保留 both-zero-`l` 作为 error path。
- datapath 计算：
  `m_new`、两个 exp scale、`l_new`、reciprocal、old/tile weights，再流式计算
  `O_new[j]`。
- 显式扩宽了 Q1.23/Q16.32 乘法和 LUT 插值乘法，避免 SystemVerilog 表达式宽度
  截断导致 benchmark reference 与 RTL 不一致。
- `sw/spatzBenchmarks/online-softmax-merge/main.c` 的 full-reference probe 已从
  expected-error 切换为 correctness gate；软件 reference 与 RTL-aligned
  ExpLUT + reciprocal + Q16.32 fixed-point 路径一致。

验证：

```text
verilator --binary --timing hw/ip/online_merge/src/online_merge_fp32_helpers.sv \
  hw/ip/online_merge/src/online_merge_exp_approx.sv \
  hw/ip/online_merge/src/online_merge_recip_approx.sv \
  hw/ip/online_merge/test/online_merge_approx_tb.sv \
  --top-module online_merge_approx_tb
obj_dir/Vonline_merge_approx_tb
```

结果：`online_merge_approx_tb PASS`。

```text
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build
ctest -R online-softmax-merge -V
```

结果：`online-softmax-merge PASS`，1/1 CTest 通过，总耗时 1105.98 秒。

关键 full mixed-scalar 数据：

| N | D | CPU cycles | Engine cycles | Speedup | TCDM accessed | TCDM congested |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 2327 | 1207 | 1.93x | 327 | 0 |
| 4 | 8 | 17490 | 1478 | 11.83x | 495 | 2 |
| 8 | 16 | 56103 | 2343 | 23.94x | 985 | 4 |
| 8 | 32 | 97554 | 3371 | 28.94x | 1583 | 9 |
| 16 | 64 | 365620 | 9650 | 37.89x | 5229 | 27 |

保留回归：

```text
online-softmax-merge stride-zero N=4 D=8 case=2 status=0x2
online-softmax-merge invalid n-zero status=0x4
online-softmax-merge invalid d-zero status=0x4
online-softmax-merge invalid misaligned-address status=0x4
online-softmax-merge invalid misaligned-stride status=0x4
online-softmax-merge unsupported both-zero-l status=0x4
online-softmax-merge full-ref-probe generic-mixed N=4 D=8 status=0x2 cpu=17072 engine=1465 tcdm_accessed=495 tcdm_congested=2 ref_l0=0x3f5e3b41 ref_o00=0xbe567a3e
```

备注：此处 CPU cycles 是 RTL-aligned fixed-point software reference，不是优化过的
libm/向量化 CPU baseline。它用于 correctness gate 和硬件 path 相对同语义软件路径
的 microbenchmark 对比。

## Phase B5：误差、性能数据和图表

状态：已完成固定近似配置的最小证据

数据和图：

- `data_process/attnres/data/online_softmax_full_mixed_bypass.csv`
- `data_process/attnres/data/online_softmax_full_merge_numeric.csv`
- `data_process/attnres/pic/paper_b_full_mixed_cycles.svg`
- `data_process/attnres/pic/paper_b_full_mixed_speedup.svg`
- `data_process/attnres/pic/paper_b_full_mixed_tcdm.svg`
- `data_process/attnres/pic/paper_b_numeric_error.svg`

数值模型命令：

```text
python3 data_process/attnres/code/full_merge_numeric_model.py
```

固定配置：

- `exp`：`[-8, 0]` 256 段 Q1.23 LUT 线性插值。
- reciprocal：`[1, 2]` mantissa 256 段 Q1.23 LUT 线性插值，无 Newton refinement。
- 当前未做参数 sweep；原因是本阶段优先闭合 RTL datapath、benchmark gate 和
  evidence trail，且固定 256 段配置已满足 `<=1e-3` 与 `<=1e-4` 误差目标。

误差摘要：

```text
generic-mixed N=4,D=8:   max_abs=3.576278687e-07, max_rel=3.576278687e-07, mean_abs=8.158718369e-08
generic-mixed N=8,D=16:  max_abs=2.503395081e-06, max_rel=2.461275348e-06, mean_abs=4.456905160e-07
generic-mixed N=8,D=32:  max_abs=4.410743713e-06, max_rel=2.534528071e-06, mean_abs=8.407656393e-07
generic-mixed N=16,D=64: max_abs=9.775161743e-06, max_rel=2.580572675e-06, mean_abs=2.174088011e-06
delta-sweep N=16,D=64:   max_abs=6.079673767e-06, max_rel=3.325012490e-06, mean_abs=8.102706488e-07
```

绘图：

- `data_process/attnres/code/plot_attnres_results.py` 已扩展 Paper B PNG 绘图入口。
- 当前环境缺少 `matplotlib` 且 pip 安装超时，因此新增 stdlib-only
  `data_process/attnres/code/plot_paper_b_svg.py` 生成 SVG 版本：

  ```text
  python3 data_process/attnres/code/plot_paper_b_svg.py
  ```

## Phase B6：attention-like SMU merge chain

状态：已完成最小硬件 path fallback

实现：

- 在 `online-softmax-merge` benchmark 内新增 attention-like synthetic merge chain。
- 配置：`rows=8`、`blocks=4`、`D=32`。
- 每个 block 构造 tile `m/l/O`，并真实通过 `MERGE_*` MMIO 调用 SMU；每一步输出
  作为下一步 old state。
- 这是完整 SMU microbenchmark + numeric/traffic analysis fallback，不声称端到端
  attention speedup。

数据：

```text
online-softmax-merge attention-like rows=8 blocks=4 D=32 cpu=388826 engine=13432 tcdm_accessed=6188 tcdm_congested=32 state_bytes=4352 saw_busy=1
```

文件：

- `data_process/attnres/data/online_softmax_attention_like_smu.csv`
- `data_process/attnres/pic/paper_b_attention_like_smu.svg`

结论边界：

- 该 workload 证明多 row、多 block、多 hidden dimension 的 `m/l/O` merge 链可以
  通过真实 SMU hardware path 执行并通过 RTL-aligned correctness gate。
- 它不是完整 attention kernel，也不包含 QK、PV、DRAM/runtime 调度，因此只能作为
  attention-like state merge evidence。

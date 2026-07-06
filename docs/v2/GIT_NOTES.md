# CFMA v2 Git 操作记录

## 2026-07-07 阶段 0：基线恢复与验证

计划提交信息：`[cfma-v2] Record stage 0 baseline verification`

主要内容：

- 新增 `docs/v2/STAGE0_BASELINE.md`，记录 v1 closure 文档、dedicated writeback guard 默认禁用状态，以及阶段 0 结论。
- 新增 `docs/v2/evidence/stage0_baseline_build_regression.txt`，保存 fresh baseline build/regression 转录。
- 验证命令：
  - `git diff --check`：PASS；
  - `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`：PASS；
  - `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt`：PASS；
  - `cd hw/system/spatz_cluster/sw/build && PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure`：PASS，3/3。

结论：阶段 0 退出标准满足；下一步进入 `fpnew_complex_fma` standalone reference/testbench。

## 2026-07-07 阶段 1 小阶段：`fpnew_complex_fma` directed standalone 红绿验证

计划提交信息：`[cfma-v2] Add standalone fpnew complex FMA directed test`

主要内容：

- 新增 `hw/ip/spatz/test/fpnew_complex_fma_tb.sv`，用 Verilator standalone testbench 覆盖 FP64/FP32/FP16 exact directed complex-FMA case。
- 修正 `hw/ip/spatz/src/fpnew_complex_fma.sv`：旧实现把 partial products 再次相乘；新实现按 v1 baseline 顺序用两轮 `fpnew_fma` 完成 real/imag 累加，并锁存 operand/tag/status/result。
- 新增 `docs/v2/STAGE1_FPNEW_COMPLEX_FMA.md`，记录根因、红绿证据、验证命令和剩余阶段 1 gap。
- 新增 `docs/v2/evidence/stage1_*`，保存红灯、绿灯和集成验证转录。

验证命令：

- `git diff --check`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing ... hw/ip/spatz/test/fpnew_complex_fma_tb.sv --top-module fpnew_complex_fma_tb`：PASS；
- `build/cfma_v2/obj_verify/Vfpnew_complex_fma_tb`：PASS；
- `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`：PASS；
- `cd hw/system/spatz_cluster/sw/build && PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure`：PASS，3/3。

结论：阶段 1 的 directed standalone arithmetic 切片通过；完整阶段 1 尚需继续覆盖 NaN/Inf、signed zero、rounding modes、fflags 和随机 tuple。

## 2026-07-07 阶段 1 小阶段：扩展 standalone directed matrix

计划提交信息：`[cfma-v2] Extend fpnew complex FMA standalone matrix`

主要内容：

- 重构 `hw/ip/spatz/test/fpnew_complex_fma_tb.sv`，支持命名 case、可变 rounding mode、expected value class（bits/NaN/any）和 expected status class（clear/NX-only/NV-only/any）。
- 扩展 FP64/FP32/FP16 directed matrix：
  - exact finite；
  - signed zero；
  - `+Inf` propagation；
  - quiet NaN propagation；
  - `+Inf * +0` invalid / `NV`；
  - RNE/RUP rounding tie / `NX`；
  - FP64 result backpressure 保持性。
- 更新 `docs/v2/STAGE1_FPNEW_COMPLEX_FMA.md` 的阶段 1 覆盖状态与剩余 gap。
- 新增 `docs/v2/evidence/stage1_matrix_verification.txt`，保存 fresh verification 转录。

验证命令：

- `git diff --check`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing ... hw/ip/spatz/test/fpnew_complex_fma_tb.sv --top-module fpnew_complex_fma_tb`：PASS；
- `build/cfma_v2/obj_matrix_verify/Vfpnew_complex_fma_tb`：PASS，21 个 named cases 全部通过；
- `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`：PASS（目标已是最新）。

结论：阶段 1 directed standalone matrix 已覆盖 e16/e32/e64 的 finite、signed zero、Inf、quiet NaN、invalid NV、rounding NX 和 backpressure；完整阶段 1 仍需 random/reference-driven tuple、RTZ/RDN/RMM、overflow/underflow、signaling NaN。

## 2026-07-07 阶段 2：VFU Dedicated CFMA 契约冻结

计划提交信息：`[cfma-v2] Freeze VFU dedicated CFMA contract`

主要内容：

- 新增 `docs/v2/STAGE2_VFU_CONTRACT.md`，冻结 `vfcmacc.vv` dedicated path 的 request/result/writeback 契约。
- 明确 dedicated CFMA 初始为 blocking multi-cycle single-entry unit。
- 明确 request/tag 必须冻结六操作数、`vd/vd+LMUL`、`vsew/vl/vm/mask_bits/elem_idx`、completion/debug 信息。
- 明确 `cfma_req_valid/ready`、`cfma_rsp_valid/ready`、busy/backpressure 规则。
- 新增 request、compute result、两拍 real/imag writeback timing table。
- 明确 fflags 只在整条 instruction architectural completion 时暴露。
- 明确 flush/kill/debug 策略为 non-resumable/no partial architectural completion。
- 明确 v1 fallback 仍必须可选择，阶段 3/4 不默认启用 dedicated writeback。

验证/自检：

- `git diff --check`：PASS；
- placeholder scan (`TBD|TODO|待定|以后补|fill in|implement later`)：PASS；
- 阶段 2 退出标准已在文档第 11 节逐项对照。

结论：阶段 2 设计契约文档退出标准满足；下一步进入阶段 3 六操作数 VRF 分拍读取的 RTL/trace 设计与验证。

## 2026-07-07 阶段 3 准备：六操作数 VRF 分拍读取现状审查

计划提交信息：`[cfma-v2] Document stage 3 VRF read collector audit`

主要内容：

- 新增 `docs/v2/STAGE3_VRF_READ_AUDIT.md`，审查当前 `spatz_vfu.sv` 中 v1 四阶段 phase-offset 和 dedicated operand latch prototype。
- 明确当前 prototype 与阶段 2 契约的差距：四阶段收集、tag 不完整、mask 未冻结、dynamic format 未实现、writeback 原子性未证明。
- 定义阶段 3 最小 RTL 切片：新增 dedicated read collector，用 R0/R1 两拍读取六 operand 并形成 frozen request bundle，但不启用 dedicated writeback。
- 定义阶段 3 directed trace/test 的建议输出格式和验证 gate。

验证/自检：

- `git diff --check`：PASS；
- placeholder scan (`TBD|TODO|待定|以后补|fill in|implement later`)：PASS。

结论：阶段 3 RTL 改造入口已明确；下一步实现 dedicated read collector 和 directed operand trace/test。

## 2026-07-07 阶段 3 小阶段：standalone CFMA read collector RTL

计划提交信息：`[cfma-v2] Add standalone CFMA VRF read collector`

主要内容：

- 新增 `hw/ip/spatz/src/spatz_cfma_read_collector.sv`，实现阶段 3 的两拍 VRF read collector：
  - R0: `a.real`, `a.imag`, `b.real`；
  - R1: `b.imag`, `c.real`, `c.imag`；
  - bundle 阶段冻结六 operand、`vd_real_addr`、`vd_imag_addr`、`elem_idx`、`last`；
  - `bundle_ready_i=0` 时保持 bundle 稳定并 backpressure 新 start。
- 新增 `hw/ip/spatz/test/spatz_cfma_read_collector_tb.sv`，standalone 验证 R0/R1 地址映射、data latch 和 backpressure。
- 将 `spatz_cfma_read_collector.sv` 加入 `Bender.yml`，确保系统 build 会解析该 RTL。
- 更新 `docs/v2/STAGE3_VRF_READ_AUDIT.md`，记录本小阶段完成内容、红灯和最终验证证据。
- 新增证据：
  - `docs/v2/evidence/stage3_read_collector_red_build.txt`；
  - `docs/v2/evidence/stage3_read_collector_red_status.txt`；
  - `docs/v2/evidence/stage3_read_collector_final_verification.txt`。

验证命令：

- `git diff --check`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing -Wno-TIMESCALEMOD ... spatz_cfma_read_collector_tb.sv`：PASS；
- `build/cfma_v2/obj_read_collector_final/Vspatz_cfma_read_collector_tb`：PASS；
- `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`：PASS；
- `cd hw/system/spatz_cluster/sw/build && PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure`：PASS，3/3。

结论：阶段 3 的 standalone read collector RTL 和验证已完成；下一小阶段需要把 collector 接入 VFU gated/scaffold flow，产生 frozen `cfma_read_bundle_valid`，但仍不启用 dedicated writeback。

## 2026-07-07 阶段 3 小阶段：VFU read collector scaffold 集成

计划提交信息：`[cfma-v2] Scaffold CFMA read collector in VFU`

主要内容：

- 修改 `hw/ip/spatz/src/spatz_vfu.sv`，在 `gen_fpu` 区域实例化 `spatz_cfma_read_collector`。
- 新增默认禁用开关：
  - `CfmaDedicatedReadCollectorEn = 1'b0`；
  - `CfmaDedicatedWritebackEn = 1'b0`。
- 增加 VFU 内部 dedicated read address 计算，统一为阶段 2 契约中的 `a=vs1`, `b=vs2`, `c=vd`：
  - `a.real/a.imag` 来自 `vs1/vs1+LMUL`；
  - `b.real/b.imag` 来自 `vs2/vs2+LMUL`；
  - `c.real/c.imag` 来自 `vd/vd+LMUL`。
- collector 输出 frozen bundle wires 已被系统 build 解析，但默认不接管 VRF read ports，不影响 v1 fallback。
- 更新 `docs/v2/STAGE3_VRF_READ_AUDIT.md`，记录 scaffold 集成状态和下一步 gap。
- 新增 `docs/v2/evidence/stage3_vfu_read_collector_scaffold_verification.txt` 保存验证转录。

验证命令：

- `git diff --check`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing -Wno-TIMESCALEMOD ... spatz_cfma_read_collector_tb.sv`：PASS；
- `build/cfma_v2/obj_read_collector_scaffold/Vspatz_cfma_read_collector_tb`：PASS；
- `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`：PASS；
- `cd hw/system/spatz_cluster/sw/build && PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure`：PASS，3/3。

结论：VFU scaffold 集成通过 build 和 fallback regression；阶段 3 下一小阶段需要受控 mux/trace collector，证明真实 VRF 六操作数读取来源。

## 2026-07-07 阶段 3 小阶段：参数化 VFU read collector mux/trace scaffold

计划提交信息：`[cfma-v2] Parameterize VFU CFMA read collector mux scaffold`

主要内容：

- 修改 `hw/ip/spatz/src/spatz_vfu.sv`，把 collector/writeback enable 从内部 localparam 推进为 VFU module 参数：
  - `CfmaDedicatedReadCollectorEn = 1'b0`；
  - `CfmaDedicatedWritebackEn = 1'b0`。
- 增加外层 `cfma_read_mux_*` wires，使 collector 输出可以在 enable 打开时覆盖 `vrf_raddr_o/vrf_re_o`。
- 默认配置下 mux 关闭，v1 fallback 行为不变。
- 增加仿真-only `CFMA_READ_BUNDLE` trace scaffold，后续 enable-mode directed test 可用它检查六 operand address/data。
- 更新 `docs/v2/STAGE3_VRF_READ_AUDIT.md`，记录本小阶段完成内容和剩余 gap。
- 新增 `docs/v2/evidence/stage3_vfu_read_collector_mux_scaffold_verification.txt` 保存验证转录。

验证命令：

- `git diff --check`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing -Wno-TIMESCALEMOD ... spatz_cfma_read_collector_tb.sv`：PASS；
- `build/cfma_v2/obj_read_collector_mux/Vspatz_cfma_read_collector_tb`：PASS；
- `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`：PASS；
- `cd hw/system/spatz_cluster/sw/build && PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure`：PASS，3/3。

结论：默认关闭的 VFU read collector mux/trace scaffold 通过 build 和 fallback regression；完整阶段 3 仍需 enable-mode directed trace closure。

## 2026-07-07 阶段 3 小阶段：VFU enable-mode read collector directed trace closure

计划提交信息：`[cfma-v2] Verify VFU CFMA read collector enable mode`

主要内容：

- 修改 `hw/ip/spatz/src/spatz.sv`，把 `CfmaDedicatedReadCollectorEn` 和 `CfmaDedicatedWritebackEn` 作为 top-level Spatz 参数透传到 `spatz_vfu`，默认仍为关闭。
- 修改 `hw/ip/spatz/src/spatz_vfu.sv`，扩展仿真-only `CFMA_READ_BUNDLE` trace，使其打印六个 operand 的地址与数据。
- 新增 `hw/ip/spatz/test/spatz_vfu_cfma_read_mux_tb.sv`，在 `CfmaDedicatedReadCollectorEn=1` 下定向验证：
  - R0: `a.real=vs1`, `a.imag=vs1+LMUL`, `b.real=vs2`；
  - R1: `b.imag=vs2+LMUL`, `c.real=vd`, `c.imag=vd+LMUL`；
  - bundle trace 中 sentinel data 与地址一致。
- 更新 `docs/v2/STAGE3_VRF_READ_AUDIT.md`，记录 enable-mode closure、trace 样例和阶段 3 closure 状态。
- 新增 `docs/v2/evidence/stage3_vfu_read_collector_enable_mode_verification.txt` 保存完整验证转录。

验证命令：

- `git diff --check`：PASS；
- `/home/wxt/spatz/install/bender/bender script verilator -t spatz -t rtl`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing ... spatz_vfu_cfma_read_mux_tb.sv`：PASS；
- `build/cfma_v2/obj_vfu_cfma_read_mux_verify/Vspatz_vfu_cfma_read_mux_tb`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing ... spatz_cfma_read_collector_tb.sv`：PASS；
- `build/cfma_v2/obj_read_collector_enable_verify/Vspatz_cfma_read_collector_tb`：PASS；
- `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`：PASS；
- `cd hw/system/spatz_cluster/sw/build && PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure`：PASS，3/3。

结论：阶段 3 的 dedicated read collector 已完成 VFU enable-mode 定向 trace closure；默认关闭的 v1 fallback 仍通过系统 build 和三条 RTL regression。下一阶段可进入 dedicated compute path 连接，但仍保持 writeback/default path 受控关闭。

## 2026-07-07 阶段 4 小阶段：read bundle 驱动 dedicated compute

计划提交信息：`[cfma-v2] Drive CFMA compute from read collector bundle`

主要内容：

- 新增 `hw/ip/spatz/test/spatz_vfu_cfma_compute_bundle_tb.sv`，在 `CfmaDedicatedReadCollectorEn=1`、`CfmaDedicatedWritebackEn=0` 下驱动 FP64 directed case：
  - `a = 1 + 2i`；
  - `b = 3 + 4i`；
  - `c = 5 + 6i`；
  - expected result = `0 + 16i`。
- TDD 红灯证明旧 RTL 虽能形成正确 `CFMA_READ_BUNDLE`，但 `fpnew_complex_fma` 仍消费旧四阶段 latch，real result 错为 `0xc028000000000000`。
- 修改 `hw/ip/spatz/src/spatz_vfu.sv`：
  - enable-mode 下 `cfma_operand_*` 改由 `cfma_read_*[ELEN-1:0]` 驱动；
  - enable-mode 下 `cfma_op_valid = cfma_read_bundle_valid`；
  - `cfma_read_bundle_ready` 接 `cfma_op_ready`，避免 compute backpressure 下丢 bundle；
  - 默认关闭路径继续保留旧四阶段 prototype latch，不改变 v1 fallback。
- 新增 `docs/v2/STAGE4_DEDICATED_COMPUTE.md` 记录阶段目标、红灯、RTL 修改、验证结果和剩余 gap。
- 新增 `docs/v2/evidence/stage4_vfu_compute_bundle_verification.txt` 保存完整验证转录。

验证命令：

- `git diff --check`：PASS；
- `/home/wxt/spatz/install/bender/bender script verilator -t spatz -t rtl`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing ... spatz_vfu_cfma_compute_bundle_tb.sv`：PASS；
- `build/cfma_v2/obj_vfu_cfma_compute_bundle_verify/Vspatz_vfu_cfma_compute_bundle_tb`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing ... spatz_vfu_cfma_read_mux_tb.sv`：PASS；
- `build/cfma_v2/obj_vfu_cfma_read_mux_stage4_verify/Vspatz_vfu_cfma_read_mux_tb`：PASS；
- `install/verilator/bin/verilator_bin --binary --timing ... fpnew_complex_fma_tb.sv`：PASS；
- `build/cfma_v2/obj_complex_fma_stage4_verify/Vfpnew_complex_fma_tb`：PASS；
- `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`：PASS；
- `cd hw/system/spatz_cluster/sw/build && PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure`：PASS，3/3。

结论：阶段 4 的 dedicated compute 已能在 enable-mode 下直接消费阶段 3 read bundle 并产生正确 FP64 directed result；默认关闭的 v1 fallback 仍通过系统 build 和三条 RTL regression。下一阶段应冻结 result/writeback tag，并验证 real/imag 两拍写回原子性。

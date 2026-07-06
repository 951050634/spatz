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

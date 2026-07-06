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

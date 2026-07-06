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

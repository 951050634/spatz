# CFMA v2 阶段 0 基线验证记录

**日期**：2026-07-07
**分支**：feature/cfma-v2-datapath
**HEAD**：460c5eb

## git status（阶段 0 开始前）
```text
## feature/cfma-v2-datapath
```

## v1 closure 文档检查
```text
docs/v1/IMPLEMENTATION_SUMMARY.md: present
1:# CFMA v1 实现总结
3:**归档日期**：2026-07-07
4:**v1 归档分支**：`feature/cfma-instruction-extension`
9:CFMA v1 在 Spatz 上实现并验证了软件可见的 `vfcmacc.vv` 复数 FMA 指令；硬件内部使用已有 FPU 的四阶段复用路径完成计算，不默认启用 dedicated complex-FMA datapath。
13:`vfcmacc.vv vd, vs1, vs2` 的 v1 语义为：
27:## 3. v1 硬件路径
29:v1 没有把 `vfcmacc.vv` 映射为单个 dedicated complex-FMA datapath。当前功能路径是：
37:  -> 整条架构指令完成
49:因此 v1 的主要收益是降低软件可见指令数、fetch/decode/offload 压力，而不是提升原始 FPU 吞吐。
51:## 4. 已完成范围
61:- v1 文档归档。
65:RTL 中存在 `fpnew_complex_fma` integration/prototype 和 split VRF writeback 草稿，但 v1 明确保持默认禁用：
71:该路径不作为 v1 功能结果来源，也不能作为 dedicated hardware correctness 证据。
75:| Step | v1 结论 |
77:| Step 13 | 作为架构决策关闭：v1 保留四阶段 FPU 复用路径，不默认启用 dedicated hardware。 |
78:| Step 14 | v1 保留 conservative serialization/fence，dedicated scoreboard 优化推迟。 |
79:| Step 15 | 当前 v1 源码完成 build 层面的验证记录。 |
82:| Step 18 | 文档交接和归档完成。 |
93:benchmark probe: dp-caxpy old/new 通过；dp-cdotp_old_M128 超过观察窗口未完成
96:注意：这些是归档记录中的证据；若后续要合并、发布或做 v2 基线，应重新运行 fresh verification。
```

## dedicated writeback guard 默认值
```text
1419:    localparam bit CfmaDedicatedWritebackEn = 1'b0;
1508:    assign cfma_result_ready = CfmaDedicatedWritebackEn ? !cfma_wb_pending_q : 1'b1;
1563:      if (CfmaDedicatedWritebackEn && cfma_result_valid && !cfma_wb_pending_q) begin
```

## git diff --check
```text
exit=0
```

## baseline build/regression

完整转录见：`docs/v2/evidence/stage0_baseline_build_regression.txt`。

```text
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS（目标已是最新）
make -C hw/system/spatz_cluster sw.vlt: PASS
ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure: PASS（3/3）
  vfmacc : 22.02 s
  vfcmacc: 116.85 s
  vfnmsac: 22.14 s
```

## 阶段 0 结论

- v1 closure 文档存在，并明确 dedicated datapath 不是 v1 correctness 证据。
- `CfmaDedicatedWritebackEn` 默认仍为 `1'b0`。
- 最小 v1 fallback 相关 build/regression 可复现通过。
- 进入阶段 1 时不得把现有 `fpnew_complex_fma` prototype 当作已验证模块；它仍需要独立 reference/testbench 先行冻结算术、rounding 与 fflags 行为。

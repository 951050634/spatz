# P18 — 论文结论支撑

核心论点：**Online Softmax Merge 中真正值得专用化的是 state-dependent scalar
recurrence，而非整个 kernel**。

证据链（全部来自本阶段新产出）：

1. **软件分析**：B2R（SW recurrence + RVV）的 Cs ≈ 1594.2 cycles/row
   （`final_scaling_model.md`）——recurrence 的软件指令序列开销主导总成本。
2. **硬件分析**：Scalar SMU 把 Cs 降到 90.3 cycles/row（约 17.7× 下降，P2），
   SMU busy/row 仅 24 cycles，其中 EXP/Recip 是单周期组合 LUT（P3）。
3. **vector 分析**：RVV 的 Cv ≈ 2.09，Proposed 保持 Cv ≈ 2.13；Full 的自建
   vector datapath Cv = 8.03（P2）——现有 RVV 已是最优 vector 路径。
4. **性能**：Proposed 在 BERT / Mistral / Qwen14B 上相对 B2R 为 5.04× / 4.62× /
   4.77×（geomean 4.80×，iso-frequency，P9–P11）。
5. **硬件代价**：Proposed 增量面积 77.1k cells（Full 的 67%，P4/P5），standalone
   Fmax 81.0 MHz（pre-layout ABC，P7），critical path 不在 EXP/Recip（P7）；
   area efficiency 比 Full 高 3.57×（P16）。
6. **Full ablation**：vector datapath 增加 +48.8% standalone area 且吞吐低于
   Proposed（P13）。

结论表述建议："Selective scalar offloading（Scalar SMU + existing RVV）优于
Full kernel offloading：它以最小专用硬件消除 recurrence 软件开销，同时保留
RVV 的高效 vector update。"

配套最终图：`experiments/plots/figure2_scaling.png`（scaling mechanism）、
`experiments/plots/figure3_hardware_tradeoff.png`（performance–area trade-off）；
最终表：`experiments/parsed/p16/p16_hardware_results.csv`。

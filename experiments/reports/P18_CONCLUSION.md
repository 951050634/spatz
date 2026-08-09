# P18 — 论文结论支撑

核心论点：**Online Softmax Merge 中真正值得专用化的是 state-dependent scalar
recurrence，而非整个 kernel**。

证据链（全部来自本阶段新产出）：

1. **软件分析**：B2R（SW recurrence + RVV）的 Cs = 1594.233808
   cycles/row（`final_scaling_model.md`）——recurrence 的软件指令序列开销主导总成本。
2. **硬件分析**：A1 Scalar SMU 把拟合 Cs 降到 90.278155 cycles/row（约
   17.66× 下降，P2）。SMU busy/row 为 24 cycles，其中 EXP/Recip 是单周期
   组合 LUT（P3）；24 cycles 不等同于拟合 Cs。
3. **vector 分析**：RVV 的 B2R Cv = 2.086684，A1 Cv = 2.126010；A2 的自建
   vector datapath Cv = 8.029465（P2）——现有 RVV 已是更高效的 vector 路径。
4. **性能**：A1 在 BERT / Mistral / Qwen14B 上相对 B2R 为 5.04× / 4.62× /
   4.77×（exact geomean 4.806510911×，display 4.81×）。这些 latency /
   throughput 是 common 81.0186 MHz iso-frequency 下由 measured cycles 推导，
   不是 wall-time 或 system-throughput measurement（P9–P11）。
5. **硬件代价**：A1 为 **73,505 mapped cells / 77,103.3 Liberty units**；
   A2 为 **107,372 mapped cells / 114,713.3 Liberty units**（P0-6 standalone）。
   P7 additionally estimates A1 standalone Fmax 81.0186 MHz；cluster Fmax 不可用。
   Incremental-SMU area efficiency 比 A2 高 3.57×（P16）。
6. **Full ablation**：A2 vector datapath 增加 +48.8% standalone mapped area
   且 derived throughput 低于 A1（P13）。

结论表述建议："Selective scalar offloading（Scalar SMU + existing RVV）优于
Full kernel offloading：它以最小专用硬件消除 recurrence 软件开销，同时保留
RVV 的高效 vector update。"

Cluster mapped area/overhead、cluster timing/Fmax、physical/layout area、
signoff timing、power、energy 均 unavailable；它们不用于上述结论。

配套最终图：`experiments/plots/figure2_scaling.png`（scaling mechanism）、
`experiments/plots/figure3_hardware_tradeoff.png`（performance–area trade-off）；
最终表：`experiments/parsed/p16/p16_hardware_results.csv`。

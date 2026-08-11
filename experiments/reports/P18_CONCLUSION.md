# P18 — Final Conclusion Support

The active evidence supports one architectural conclusion: in Online
Softmax Merge, the valuable specialization is the state-dependent scalar
recurrence, not replacement of the complete kernel.

1. **Scaling model.** M2 matched-LUT data fit
   `C(N,D) = C0 + Cs·N + Cv·N·D`. Here `Cs` is the fitted N-dependent
   cycles/row coefficient and `Cv` is the fitted ND-dependent cycles/element
   coefficient. B2R has `Cs=1471.8187127369117`, A1 has
   `Cs=90.27815541344518`, and A2 has `Cs=19.317262422475853`. A1 retains a
   fitted `Cv=2.126010148452419`, within 6.22% of B2R `2.2670632230803`, while
   A2 has `Cv=8.029464672201952`.
2. **Measured workloads.** M2 measured BERT/Mistral/Qwen2.5-14B-Instruct cycles as
   B2R/A1/A2 = `19856/4128/7704`, `56296/12866/34728`, and
   `69348/15733/43206`.  A1's geometric-mean speedup is
   `4.526920018368`; A2's is `1.885765610308`.  These are cycle ratios, not
   end-to-end inference or wall-time throughput.
3. **Hardware cost.** A1 is `73,505` mapped cells and `77,103.292`
   Nangate45 Liberty units.  A2 is `107,372` cells and `114,713.298` units,
   or `1.487787291884×` A1 area (`+48.778729%`).
4. **Scalar SMU behavior.** The existing P3 FSM reports a nominal no-stall
   schedule of 24 SMU busy cycles per scalar row (`13+1+1+9`). Model-shape
   observers report 289/769/962 busy cycles for BERT/Mistral/Qwen2.5-14B-Instruct,
   including one or two TCDM waits. These observations remain separate from
   fitted `Cs` and system latency.
5. **Timing boundary.** A1 and A2 have PARTIAL P7-R reg→reg combinational
   delay proxies of `12.34285 ns` and `13.20260 ns`. Synchronous `F_max` is
   UNAVAILABLE because the flow excludes clock-to-Q, setup/hold, skew, I/O
   constraints, and physical buffering/load semantics.

Therefore, the defensible claim is: **Selective scalar offloading (Scalar SMU
+ existing RVV) removes the recurrence software cost while preserving the
efficient RVV vector update, with less standalone hardware than Full-Offload.**
Full remains an ablation, not the primary architecture.

Cluster mapped area/overhead, cluster timing/$F_{max}$, physical/layout area, power,
energy, absolute latency, throughput, and end-to-end inference performance are
UNAVAILABLE and must not be inferred.

## Active evidence

- `experiments/parsed/final_scaling_model.csv`
- `experiments/parsed/final_workload_comparison.csv`
- `experiments/parsed/final_area.csv`
- `experiments/parsed/final_timing.csv`
- `experiments/parsed/final_hardware_results.csv`
- `experiments/reports/FINAL_EVIDENCE_FREEZE.md`

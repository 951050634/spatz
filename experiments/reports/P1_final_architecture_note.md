# P1 — 最终 Proposed Architecture（冻结说明）

依据 `docs/online-softmax-merge-engine/TCAS2后续工程任务规划.md` P1，本阶段起固定：

```text
Proposed Design = Scalar SMU + existing RVV   （= A1_SMU_SCALAR）
Full SMU        仅作 Full-Offload 消融对照      （= A2_SMU_FULL）
```

| 名称 | 角色 | SMU mode | 执行边界 |
| --- | --- | --- | --- |
| B1_SCALAR | Scalar Reference（弱化） | 无 | SW recurrence + scalar vector update |
| B2R_RVV | RVV Software Baseline | 无 | SW recurrence + RVV vector update |
| PROPOSED / A1 | Proposed Design | mode 1 | SMU recurrence + RVV vector update |
| FULL / A2 | Full-Offload Ablation | mode 0 | SMU recurrence + SMU vector update |

冻结要求（不修改算法功能、不重构 runner/配置框架、不删除历史 A1/A2 名称）：
- 后续所有新实验默认围绕 B2R_RVV / A1_SMU_SCALAR / A2_SMU_FULL 三者展开；
- A1_SMU_SCALAR = Proposed，A2_SMU_FULL = Full-Offload ablation；
- 硬件配置与既有 P0-4/P0-5/P0-6 完全一致：默认 Spatz cluster CFG
  `hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson`（CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`），
  `hw/ip/online_merge/src/online_merge_update_engine.sv`。

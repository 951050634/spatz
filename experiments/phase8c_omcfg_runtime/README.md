# Phase 8C — OMCFG matched runtime validation

Status: **PASS**

This directory compares the two one-time persistent-configuration mechanisms
while keeping OMERGE, the Scalar SMU, the RVV output update, inputs, and timing
windows matched:

```text
MMIO config  -> OMERGE -> Scalar SMU -> RVV O update
OMCFG config -> OMERGE -> Scalar SMU -> RVV O update
```

Only the required anchors were run, in the frozen order N8/D32 MMIO, N8/D32
OMCFG, N16/D64 MMIO, and N16/D64 OMCFG. No B2R rerun, extra workload,
synthesis, or datapath change was performed.

## Material Passport

- Origin Skill: `academic-research-suite/experiment-agent`
- Mode: run/validate
- Date: 2026-09-09 (Asia/Shanghai)
- Verification Status: VERIFIED
- Version: Phase 8C v1
- Implementation freeze: `7786820821102d34e32e9517a7630b028693f25a`

## Reproduction

The formal collector defaults to plan-only:

```bash
python3 experiments/phase8c_omcfg_runtime/run_formal.py
```

The recorded formal execution used:

```bash
python3 experiments/phase8c_omcfg_runtime/run_formal.py \
  --execute-formal --jobs 8 --timeout 1800
```

The simulator SHA-256 was
`002161e3e88edd6fa6392dbe79a6a89796477282d5ff951037a211676785a51a`.
`manifest.json` records commands, tool versions, source/build/input hashes,
ELF and `.text` hashes, raw-log hashes, and the fixed run order.

## Artifacts

- `matched_results.csv`: machine-readable four-run result table.
- `matched_results.md`: compact human-readable result table.
- `runtime_configurability.md`: shared-state and same-hardware evidence.
- `correctness.md`: exact output/configuration equivalence evidence.
- `setup_overhead.md`: one-time setup-cycle interpretation.
- `final_report.md`: Phase 8C acceptance report.
- `raw/*.log`: complete simulator, configure, and build logs.
- `manifest.json`: provenance and validation records.

The repository-wide `*.log` ignore rule means raw logs are present locally but
do not appear in ordinary `git status` output.

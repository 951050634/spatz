# P0-6 C0/C1/C2 Mapped Synthesis Report

This report covers an SMU-only contribution scope mapped to the
research-only, non-manufacturable Nangate45 typical Liberty. The
flow is unconstrained and pre-layout; areas are Liberty cell-area
units, not complete-cluster or physical-layout area.
Fixed modes are pruned by forced FSM extraction before technology
mapping. The uniform ABC -fast script has lower output quality than
the default higher-effort script; these are not minimum-area claims.

## Acceptance

- `analysis_git_clean`: `PASS`
- `one_indexed_formal_root`: `PASS`
- `index_set_named_p0_6`: `PASS`
- `capture_git_clean`: `PASS`
- `capture_status_pass`: `PASS`
- `capture_paper_eligible`: `PASS`
- `capture_acceptance_gates_pass`: `PASS`
- `capture_physical_ppa_false`: `PASS`
- `catalog_hash_matches`: `PASS`
- `requested_matrix_exact`: `PASS`
- `input_hashes_reverified`: `PASS`
- `tool_and_library_identity_pass`: `PASS`
- `all_commands_pass`: `PASS`
- `command_schedule_exact`: `PASS`
- `synthesis_timeout_uniform`: `PASS`
- `record_matrix_complete`: `PASS`
- `all_raw_outputs_reverified`: `PASS`
- `three_exact_processes_per_config`: `PASS`
- `c0_c1_c2_area_ordering`: `PASS`
- `claim_boundary_explicit`: `PASS`
- `failure_entries_empty`: `PASS`
- `validation_issue_free`: `PASS`

## Fixed configurations

| Configuration | Trials | Mapped cells | Mapped area (Liberty units) | Sequential area (Liberty units) | Normalized to C1 | Eligible |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| C0_NONE | 3/3 | 0 | 0.000 | 0.000 | 0.000 | YES |
| C1_SCALAR | 3/3 | 73505 | 77103.292 | 2766.400 | 1.000 | YES |
| C2_FULL | 3/3 | 107372 | 114713.298 | 3293.080 | 1.488 | YES |

## Claim boundary

The accepted claim is limited to deterministic pre-layout mapped
cell area for these fixed SMU-only tops. No complete-cluster
area, physical area, Fmax, critical path, timing closure, power,
or energy result is inferred.

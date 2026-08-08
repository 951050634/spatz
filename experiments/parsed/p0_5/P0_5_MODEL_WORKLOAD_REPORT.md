# P0-5 Model-Shape Workload Report

This stage maps pinned model configuration shapes onto one logical
attention position: `N` is the query-head count and `D` is the
derived head dimension. Inputs remain deterministic generated merge
states; this is not end-to-end inference or captured activation data.

## Acceptance

- `index_set_complete`: `PASS`
- `all_external_artifacts_reverified`: `PASS`
- `no_failure_entries`: `PASS`
- `record_matrix_complete`: `PASS`
- `validation_issue_free`: `PASS`
- `pinned_model_sources_complete`: `PASS`
- `workload_dispositions_exact`: `PASS`
- `paper_eligible_scope_exact`: `PASS`

## Workloads

| Model | N | D | Disposition | B1 | B2-R | A1 | A2 | A2 vs B2-R |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| google-bert/bert-base-uncased | 12 | 64 | MEASURED | 271718 | 20785 | 4128 | 7704 | 2.698 |
| mistralai/Mistral-7B-v0.1 | 32 | 128 | MEASURED | 1401702 | 59500 | 12866 | 34728 | 1.713 |
| Qwen/Qwen2.5-14B-Instruct | 40 | 128 | MEASURED | 1780547 | 75027 | 15733 | 43206 | 1.736 |
| Qwen/Qwen2.5-72B-Instruct | 64 | 128 | EXPLICIT_CAPACITY_SKIP | 0 | 0 | 0 | 0 | NA |

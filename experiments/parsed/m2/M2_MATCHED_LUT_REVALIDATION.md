# M2 Matched-LUT Revalidation

## Acceptance

- `expected_analysis_head`: `PASS`
- `index_set_complete`: `PASS`
- `all_external_artifacts_reverified`: `PASS`
- `no_failure_entries`: `PASS`
- `record_matrix_complete`: `PASS`
- `paper_eligible_matrix_complete`: `PASS`
- `measurement_roots_clean_and_code_matched`: `PASS`
- `validation_issue_free`: `PASS`
- `model_sources_complete`: `PASS`
- `scaling_models_complete`: `PASS`
- `workload_rows_complete`: `PASS`
- `correctness_gates_pass`: `PASS`
- `repeat_consistency_pass`: `PASS`
- `status_gates_pass`: `PASS`
- `fairness_gates_pass`: `PASS`
- `fsm_gates_pass`: `PASS`
- `trace_gates_pass`: `PASS`
- `reproducibility_gates_pass`: `PASS`

## Counts

- `root_count`: `9`
- `record_count`: `234`
- `failure_count`: `0`
- `validation_issue_count`: `0`

## Scaling old to new

| Config | C0 | Cs | Cv |
| --- | ---: | ---: | ---: |
| B2R_RVV | 153.477363→161.353823 | 1594.233808→1471.818713 | 2.086684→2.267063 |
| A1_SMU_SCALAR | 1382.770246→1382.770246 | 90.278155→90.278155 | 2.126010→2.126010 |
| A2_SMU_FULL | 1285.577085→1285.577085 | 19.317262→19.317262 | 8.029465→8.029465 |

## Workload old to new

| Workload | B2R cycles | A1 cycles | A2 cycles | A1 speedup | A2 speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| google-bert/bert-base-uncased | 20785→19856 | 4128→4128 | 7704→7704 | 5.035126→4.810078 | 2.697949→2.577362 |
| mistralai/Mistral-7B-v0.1 | 59500→56296 | 12866→12866 | 34728→34728 | 4.624592→4.375564 | 1.713315→1.621055 |
| Qwen/Qwen2.5-14B-Instruct | 75027→69348 | 15733→15733 | 43206→43206 | 4.768766→4.407805 | 1.736495→1.605055 |

## Geomean old to new

- `A1_geomean_speedup`: `4.806511→4.526920`
- `A2_geomean_speedup`: `2.002234→1.885766`

## Correctness and repeat consistency

- `correctness`: `PASS`
- `repeat_consistency`: `PASS`

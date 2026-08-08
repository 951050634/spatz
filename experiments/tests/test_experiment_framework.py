"""Unit tests for the paper-experiment facade."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_instruction_trace as trace_audit
import analyze_p0_4 as p0_4_analysis
import analyze_p0_5 as p0_5_analysis
import experiment_common as common
import index_external_runs as external_index
import make_plots
import parse_results
import run_performance_matrix as matrix


def float_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


class ExperimentFrameworkTest(unittest.TestCase):
    def test_enrich_target_record_computes_full_error_metrics(self) -> None:
        record = common.enrich_target_record(
            {
                "cycles_hi": 1,
                "cycles_lo": 7,
                "max_abs_bits": float_bits(0.5),
                "max_rel_numerator_bits": float_bits(0.25),
                "max_rel_denominator_bits": float_bits(2.0),
                "sum_sq_bits": float_bits(0.25),
                "sum_abs_bits": float_bits(1.0),
                "sum_ref_sq_bits": float_bits(4.0),
                "checked": 4,
                "bit_equal": 3,
            }
        )

        self.assertEqual(record["kernel_cycles"], (1 << 32) + 7)
        self.assertAlmostEqual(record["max_abs_error"], 0.5)
        self.assertAlmostEqual(record["max_rel_error"], 0.125)
        self.assertAlmostEqual(record["mean_abs_error"], 0.25)
        self.assertAlmostEqual(record["rmse"], 0.25)
        self.assertAlmostEqual(record["l2_relative_error"], 0.25)
        self.assertAlmostEqual(record["bit_equal_ratio"], 0.75)
        self.assertEqual(record["inf_count"], 0)

    def test_external_root_guard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repo = temporary / "repo"
            repo.mkdir()
            with self.assertRaisesRegex(ValueError, "outside"):
                common.require_fresh_external_root(
                    repo / "work-online-merge-inside", repo
                )

            existing = temporary / "work-online-merge-existing"
            existing.mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"):
                common.require_fresh_external_root(existing, repo)

            common.require_fresh_external_root(
                temporary / "work-online-merge-fresh", repo
            )

    def test_external_indexer_verifies_artifact_hashes_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            payload = root / "artifact.txt"
            payload.write_text("evidence\n", encoding="utf-8")
            entry = {
                "path": "artifact.txt",
                "kind": "test",
                "bytes": payload.stat().st_size,
                "sha256": common.sha256_file(payload),
            }

            count, total_bytes = external_index.verify_artifacts(
                root, [entry]
            )

            self.assertEqual(count, 1)
            self.assertEqual(total_bytes, payload.stat().st_size)
            with self.assertRaisesRegex(ValueError, "SHA256"):
                external_index.verify_artifacts(
                    root, [{**entry, "sha256": "0" * 64}]
                )
            with self.assertRaisesRegex(ValueError, "escapes"):
                external_index.artifact_path(root, "../outside")

    def test_csv_writer_uses_repository_lf_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.csv"

            common.write_csv(path, [{"value": 1}, {"value": None}])

            payload = path.read_bytes()
            self.assertEqual(payload, b"value\n1\nNA\n")
            self.assertNotIn(b"\r\n", payload)

    def test_single_target_parser_rejects_mixed_output(self) -> None:
        base = {
            "cycles_hi": 0,
            "cycles_lo": 10,
            "max_abs_bits": float_bits(0.0),
            "max_rel_numerator_bits": float_bits(0.0),
            "max_rel_denominator_bits": float_bits(1.0),
            "sum_sq_bits": float_bits(0.0),
            "sum_abs_bits": float_bits(0.0),
            "sum_ref_sq_bits": float_bits(1.0),
            "checked": 1,
            "bit_equal": 1,
        }
        output = "OM_RESULT " + json.dumps(
            {"implementation": "B1", **base}
        )

        record, errors = matrix.parse_one_result(output, "B2-R")

        self.assertIsNone(record)
        self.assertTrue(errors)
        self.assertIn("implementation mismatch", errors[-1]["message"])

    def test_simulator_configuration_distinguishes_measurement_and_trace(
        self,
    ) -> None:
        measurement = (
            'OM_SIM_CONFIG {"schema_version":1,'
            '"profile":"low_perturbation",'
            '"dasm_trace_enabled":false,'
            '"fsm_observer_enabled":true}'
        )
        traced = measurement.replace(
            '"profile":"low_perturbation"', '"profile":"default"'
        ).replace(
            '"dasm_trace_enabled":false',
            '"dasm_trace_enabled":true',
        )

        measurement_record, measurement_errors = (
            matrix.parse_simulator_configuration(
                measurement, "low_perturbation", False
            )
        )
        traced_record, traced_errors = matrix.parse_simulator_configuration(
            traced, "default", True
        )
        _, wrong_errors = matrix.parse_simulator_configuration(
            traced, "low_perturbation", False
        )

        self.assertEqual(measurement_errors, [])
        self.assertEqual(measurement_record["dasm_trace_enabled"], False)
        self.assertEqual(traced_errors, [])
        self.assertEqual(traced_record["dasm_trace_enabled"], True)
        self.assertEqual(len(wrong_errors), 2)

    def test_terminal_cases_skip_hot_implementation_static_gate(self) -> None:
        for config_name in (
            "B1_SCALAR",
            "B2R_RVV",
            "A1_SMU_SCALAR",
        ):
            self.assertEqual(
                matrix.implementation_static_gate_reasons(
                    "", None, config_name, "unsupported"
                ),
                [],
            )

        self.assertTrue(
            matrix.implementation_static_gate_reasons(
                "", None, "B1_SCALAR", "pass"
            )
        )
        self.assertTrue(
            matrix.implementation_static_gate_reasons(
                "", None, "B2R_RVV", "pass"
            )
        )

    def test_trace_witness_projection_excludes_only_timing_fields(self) -> None:
        measurement = {
            "implementation": "B2-R",
            "status": "pass",
            "checked": 9,
            "max_abs_error": 0.0,
            "kernel_cycles": 100,
            "tcdm_accessed": 50,
        }
        traced = {
            **measurement,
            "kernel_cycles": 900,
            "tcdm_accessed": 500,
        }

        self.assertEqual(
            matrix.target_functional_projection(measurement),
            matrix.target_functional_projection(traced),
        )
        traced["checked"] = 8
        self.assertNotEqual(
            matrix.target_functional_projection(measurement),
            matrix.target_functional_projection(traced),
        )

    def test_case_loader_rejects_unsafe_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "N": 1,
                            "D": 1,
                            "case_id": "../escape",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "case_id"):
                matrix.load_cases(path)

    def test_case_selection_is_explicit_and_ordered(self) -> None:
        def case(case_id: str) -> matrix.Case:
            return matrix.Case(
                n=1,
                d=1,
                seed=1,
                case_kind="main",
                case_id=case_id,
                evidence_class="MAIN_PERFORMANCE",
                size_class="TEST",
                timeout_seconds=1,
                max_kernel_cycles=1,
            )

        cases = [case("first"), case("second"), case("third")]

        selected = matrix.selected_cases("third,first", cases)

        self.assertEqual(
            [item.case_id for item in selected], ["third", "first"]
        )
        with self.assertRaisesRegex(ValueError, "unknown"):
            matrix.selected_cases("missing", cases)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            matrix.selected_cases("first,first", cases)

    def test_policy_predicts_exact_tcdm_capacity_boundaries(self) -> None:
        policy = json.loads(
            (
                SCRIPT_DIR.parent / "configs/measurement_policy.json"
            ).read_text(encoding="utf-8")
        )

        def case(n: int, d: int) -> matrix.Case:
            return matrix.Case(
                n=n,
                d=d,
                seed=1,
                case_kind="main",
                case_id=f"N{n}_D{d}",
                evidence_class="CAPACITY_PROBE",
                size_class="BOUNDARY",
                timeout_seconds=1,
                max_kernel_cycles=1,
            )

        self.assertEqual(
            matrix.expected_case_status(case(83, 64), policy), "pass"
        )
        self.assertEqual(
            matrix.expected_case_status(case(84, 64), policy),
            "capacity_skip",
        )
        self.assertEqual(
            matrix.expected_case_status(case(8, 687), policy), "pass"
        )
        self.assertEqual(
            matrix.expected_case_status(case(8, 688), policy),
            "capacity_skip",
        )

    def test_p0_4_case_catalogs_cover_required_coordinates(self) -> None:
        config_dir = SCRIPT_DIR.parent / "configs"
        scaling = matrix.load_cases(
            config_dir / "p0_scaling_cases.json"
        )
        tails = matrix.load_cases(config_dir / "p0_rvv_tail_cases.json")
        numerical = matrix.load_cases(
            config_dir / "p0_numerical_boundary_cases.json"
        )
        capacity = matrix.load_cases(
            config_dir / "p0_capacity_cases.json"
        )

        required_scaling = (
            {(n, 64) for n in (1, 2, 4, 8, 16, 32)}
            | {(8, d) for d in (1, 8, 16, 32, 64, 128)}
            | {
                (n, d)
                for n in (1, 2, 4, 8)
                for d in (1, 8, 16, 32)
            }
        )
        self.assertEqual(len(required_scaling), 23)
        self.assertEqual(
            {(case.n, case.d) for case in scaling}, required_scaling
        )
        self.assertEqual(
            {case.evidence_class for case in scaling},
            {"MAIN_PERFORMANCE"},
        )
        self.assertEqual(
            {case.d for case in tails},
            {1, 7, 15, 17, 31, 33, 63, 65, 127},
        )
        self.assertEqual(
            {case.case_kind for case in numerical},
            {
                "equal-m",
                "delta-neg8",
                "delta-below-neg8",
                "l-old-zero",
                "l-tile-zero",
                "small-l",
                "signed-o",
                "both-zero-l",
            },
        )
        self.assertEqual(
            {(case.n, case.d) for case in capacity},
            {
                (48, 64),
                (64, 64),
                (80, 64),
                (8, 256),
                (8, 512),
                (83, 64),
                (84, 64),
                (8, 687),
                (8, 688),
            },
        )

    def test_p0_4_shard_plan_is_complete_and_nonoverlapping(self) -> None:
        config_dir = SCRIPT_DIR.parent / "configs"
        plan = json.loads(
            (config_dir / "p0_4_shards.json").read_text(encoding="utf-8")
        )
        catalog_names = {
            "p0_scaling_cases.json",
            "p0_rvv_tail_cases.json",
            "p0_numerical_boundary_cases.json",
            "p0_capacity_cases.json",
        }
        catalogs = {
            name: {
                case.case_id for case in matrix.load_cases(config_dir / name)
            }
            for name in catalog_names
        }
        selected_ids: list[str] = []
        suites: list[str] = []
        for shard in plan["shards"]:
            suites.append(shard["suite"])
            self.assertIn(shard["case_file"], catalogs)
            self.assertTrue(shard["case_ids"])
            self.assertTrue(
                set(shard["case_ids"]).issubset(
                    catalogs[shard["case_file"]]
                )
            )
            selected_ids.extend(shard["case_ids"])

        expected_ids = set().union(*catalogs.values())
        self.assertEqual(len(plan["shards"]), 17)
        self.assertEqual(len(suites), len(set(suites)))
        self.assertEqual(len(selected_ids), len(set(selected_ids)))
        self.assertEqual(set(selected_ids), expected_ids)
        self.assertEqual(plan["trials"], 3)
        self.assertEqual(plan["counter_profiles"], ["memory"])

    def test_p0_5_model_shapes_are_pinned_and_exact(self) -> None:
        config_dir = SCRIPT_DIR.parent / "configs"
        catalog_path = config_dir / "p0_model_workload_cases.json"
        raw_cases = json.loads(catalog_path.read_text(encoding="utf-8"))
        cases = matrix.load_cases(catalog_path)
        by_id = {case.case_id: case for case in cases}
        policy = json.loads(
            (config_dir / "measurement_policy.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            {(case.n, case.d) for case in cases},
            {(12, 64), (32, 128), (40, 128), (64, 128)},
        )
        self.assertEqual(
            {case.evidence_class for case in cases}, {"MODEL_WORKLOAD"}
        )
        for item in raw_cases:
            self.assertEqual(item["N"], item["num_attention_heads"])
            self.assertEqual(
                item["D"],
                item["hidden_size"] // item["num_attention_heads"],
            )
            self.assertEqual(
                item["hidden_size"] % item["num_attention_heads"], 0
            )
            self.assertRegex(item["model_revision"], r"^[0-9a-f]{40}$")
            self.assertRegex(item["model_config_sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(item["model_revision"], item["model_config_url"])
            self.assertGreater(item["model_config_bytes"], 0)
            self.assertEqual(
                item["workload_mapping"],
                "one_attention_position_all_query_heads",
            )

        expected = {
            "model_bert_base_heads": "pass",
            "model_mistral_7b_heads": "pass",
            "model_qwen2_5_14b_heads": "pass",
            "model_qwen2_5_72b_heads": "capacity_skip",
        }
        self.assertEqual(
            {
                case_id: matrix.expected_case_status(case, policy)
                for case_id, case in by_id.items()
            },
            expected,
        )

    def test_p0_5_shard_plan_is_complete_and_nonoverlapping(self) -> None:
        config_dir = SCRIPT_DIR.parent / "configs"
        plan = json.loads(
            (config_dir / "p0_5_shards.json").read_text(encoding="utf-8")
        )
        case_ids = {
            case.case_id
            for case in matrix.load_cases(
                config_dir / "p0_model_workload_cases.json"
            )
        }
        selected = [
            case_id
            for shard in plan["shards"]
            for case_id in shard["case_ids"]
        ]

        self.assertEqual(len(plan["shards"]), 2)
        self.assertEqual(len(selected), len(set(selected)))
        self.assertEqual(set(selected), case_ids)
        self.assertEqual(
            {shard["case_file"] for shard in plan["shards"]},
            {"p0_model_workload_cases.json"},
        )
        self.assertEqual(plan["trials"], 3)
        self.assertEqual(plan["counter_profiles"], ["memory"])
        self.assertEqual(
            plan["configurations"],
            [
                "B1_SCALAR",
                "B2R_RVV",
                "A1_SMU_SCALAR",
                "A2_SMU_FULL",
            ],
        )

    def test_p0_5_source_audit_and_comparison(self) -> None:
        config_dir = SCRIPT_DIR.parent / "configs"
        catalog_path = config_dir / "p0_model_workload_cases.json"
        raw_cases = json.loads(catalog_path.read_text(encoding="utf-8"))
        cases = {
            case.case_id: case for case in matrix.load_cases(catalog_path)
        }

        issues, source_rows = p0_5_analysis.validate_model_catalog(
            raw_cases, cases
        )

        self.assertEqual(issues, [])
        self.assertEqual(len(source_rows), 4)
        self.assertEqual(
            {row["source_audit"] for row in source_rows}, {"PASS"}
        )

        summaries = []
        for source in source_rows:
            skipped = source["case_id"] == "model_qwen2_5_72b_heads"
            for index, config in enumerate(p0_4_analysis.CONFIGS):
                summaries.append(
                    {
                        "case_id": source["case_id"],
                        "config": config,
                        "status": (
                            "SKIPPED_MEMORY_LIMIT" if skipped else "PASS"
                        ),
                        "kernel_cycles_median": (
                            0
                            if skipped
                            else 200 - index * 20
                        ),
                        "paper_eligible": "NO" if skipped else "YES",
                        "memory_footprint_bytes": 1000,
                    }
                )
        comparison_issues: list[str] = []
        comparisons = p0_5_analysis.build_workload_comparisons(
            source_rows, summaries, comparison_issues
        )

        self.assertEqual(comparison_issues, [])
        self.assertEqual(
            Counter(row["disposition"] for row in comparisons),
            Counter({"MEASURED": 3, "EXPLICIT_CAPACITY_SKIP": 1}),
        )
        measured = next(
            row for row in comparisons if row["disposition"] == "MEASURED"
        )
        self.assertEqual(measured["A2_vs_B2R_speedup"], 180 / 140)
        self.assertIn(
            "MODEL_WORKLOAD", p0_4_analysis.PAPER_ELIGIBLE_EVIDENCE
        )

    def test_p0_4_model_fit_recovers_exact_linear_parameters(self) -> None:
        coordinates = (
            {(n, 64) for n in (1, 2, 4, 8, 16, 32)}
            | {(8, d) for d in (1, 8, 16, 32, 64, 128)}
            | {
                (n, d)
                for n in (1, 2, 4, 8)
                for d in (1, 8, 16, 32)
            }
        )
        summaries = []
        for config, c0, cs, cv in (
            ("B2R_RVV", 100, 10, 2),
            ("A2_SMU_FULL", 80, 8, 1),
        ):
            summaries.extend(
                {
                    "case_id": f"N{n}_D{d}",
                    "evidence_class": "MAIN_PERFORMANCE",
                    "N": n,
                    "D": d,
                    "config": config,
                    "status": "PASS",
                    "paper_eligible": "YES",
                    "kernel_cycles_median": c0 + cs * n + cv * n * d,
                }
                for n, d in coordinates
            )
        issues: list[str] = []

        models, parameters, residuals = p0_4_analysis.fit_models(
            summaries, issues
        )

        self.assertEqual(issues, [])
        self.assertEqual(len(parameters), 2)
        self.assertEqual(len(residuals), 46)
        self.assertEqual(
            models["B2R_RVV"]["parameters_cycles"]["C0"]["decimal"],
            100.0,
        )
        self.assertEqual(
            models["B2R_RVV"]["parameters_cycles"]["Cs"]["decimal"],
            10.0,
        )
        self.assertEqual(
            models["B2R_RVV"]["parameters_cycles"]["Cv"]["decimal"],
            2.0,
        )
        self.assertEqual(models["B2R_RVV"]["R_squared"]["decimal"], 1.0)

    def test_p0_4_break_even_uses_only_direct_measurements(self) -> None:
        summaries = []
        for n in (1, 2, 4, 8):
            for d in (1, 8, 16, 32):
                summaries.extend(
                    (
                        {
                            "N": n,
                            "D": d,
                            "config": "B2R_RVV",
                            "evidence_class": "MAIN_PERFORMANCE",
                            "status": "PASS",
                            "kernel_cycles_median": 100,
                        },
                        {
                            "N": n,
                            "D": d,
                            "config": "A2_SMU_FULL",
                            "evidence_class": "MAIN_PERFORMANCE",
                            "status": "PASS",
                            "kernel_cycles_median": 120 - d,
                        },
                    )
                )
        issues: list[str] = []

        rows, per_n = p0_4_analysis.measured_break_even(
            summaries, issues
        )

        self.assertEqual(issues, [])
        self.assertEqual(len(rows), 16)
        self.assertEqual(
            {row["minimum_measured_D"] for row in per_n}, {32}
        )

    def test_p0_4_record_audit_accepts_complete_exact_trials(self) -> None:
        policy = json.loads(
            (
                SCRIPT_DIR.parent / "configs/measurement_policy.json"
            ).read_text(encoding="utf-8")
        )
        case = matrix.Case(
            n=1,
            d=1,
            seed=1,
            case_kind="main",
            case_id="test_case",
            evidence_class="MAIN_PERFORMANCE",
            size_class="TEST",
            timeout_seconds=1,
            max_kernel_cycles=1000,
        )
        records = []
        for config_index, config in enumerate(p0_4_analysis.CONFIGS):
            for trial in range(3):
                record = {
                    "run_id": "test_run",
                    "case_id": case.case_id,
                    "config": config,
                    "trial": trial,
                    "N": 1,
                    "D": 1,
                    "seed": 1,
                    "input_pattern": "main",
                    "evidence_class": "MAIN_PERFORMANCE",
                    "counter_profile": "memory",
                    "expected_target_status": "pass",
                    "target_status": "pass",
                    "status": "PASS",
                    "git_dirty": False,
                    "reproducible": "YES",
                    "static_code_gate": "PASS",
                    "fairness_gate": "PASS",
                    "comparison_set_complete": "YES",
                    "measurement_simulator_gate": "PASS",
                    "logical_N": 1,
                    "logical_D": 1,
                    "padded_N": 1,
                    "padded_D": 1,
                    "padding_ratio": 1.0,
                    "footprint_bytes": 56,
                    "allocation_bytes": 256,
                    "runtime_reserved_bytes": 16512,
                    "memory_footprint_bytes": 16768,
                    "paper_eligible": "YES",
                    "paper_ineligible_reasons": None,
                    "kernel_cycles": 100 + config_index,
                    "nonfinite": 0,
                    "nan_count": 0,
                    "inf_count": 0,
                    "target_result_hash": f"target-{config}",
                    "input_hash": "same-input",
                    "binary_hash": f"binary-{config}",
                    "tcdm_accessed": 1,
                    "tcdm_congested": 0,
                    "max_abs_error": 0.0,
                    "max_rel_error": 0.0,
                    "mean_abs_error": 0.0,
                    "l2_relative_error": 0.0,
                }
                if config in {"A1_SMU_SCALAR", "A2_SMU_FULL"}:
                    record.update(
                        {
                            "fsm_gate": "PASS",
                            "load_scalar_cycles": 1,
                            "compute_scalar_cycles": 1,
                            "compute_weight_cycles": 1,
                            "store_scalar_cycles": 1,
                            "update_vector_cycles": 1,
                            "smu_busy_cycles": 5,
                        }
                    )
                else:
                    record["fsm_gate"] = "NA"
                if config == "B2R_RVV":
                    record.update(
                        {
                            "dynamic_trace_verified": "YES",
                            "trace_witness_gate": "PASS",
                            "trace_source": "INDEPENDENT_DASM_WITNESS",
                            "trace_target_equivalence_gate": "PASS",
                            "measurement_target_projection_hash": "same",
                            "trace_witness_target_projection_hash": "same",
                        }
                    )
                records.append(record)
        runs = [
            {
                "run_id": "test_run",
                "root": Path("/external/test"),
                "manifest": {"selected_case_ids": [case.case_id]},
                "records": records,
            }
        ]

        issues, audited, summaries = p0_4_analysis.audit_records(
            {}, {case.case_id: case}, policy, runs
        )

        self.assertEqual(issues, [])
        self.assertEqual(len(audited), 12)
        self.assertEqual(len(summaries), 4)

    def test_smu_fsm_parser_requires_warmup_then_measured(self) -> None:
        output = "\n".join(
            "OM_FSM "
            + json.dumps(
                {
                    "invocation": invocation,
                    "terminal_state": "DONE",
                }
            )
            for invocation in (0, 1)
        )

        measured, errors = matrix.measured_fsm(
            output, "A2_SMU_FULL"
        )

        self.assertEqual(errors, [])
        self.assertEqual(measured["invocation"], 1)

    def test_reproducibility_requires_exact_cycles(self) -> None:
        records = [
            {
                "config": "B1_SCALAR",
                "counter_profile": "memory",
                "N": 1,
                "D": 1,
                "seed": 1,
                "input_pattern": "main",
                "trial": trial,
                "kernel_cycles": cycles,
                "status": "PASS",
            }
            for trial, cycles in enumerate((10, 10, 11))
        ]

        matrix.apply_reproducibility(records, 3)

        self.assertEqual(
            {record["status"] for record in records},
            {"NONDETERMINISTIC"},
        )
        self.assertEqual(
            {record["reproducible"] for record in records}, {"NO"}
        )

    def test_reproducibility_requires_stable_target_result(self) -> None:
        records = [
            {
                "config": "B1_SCALAR",
                "counter_profile": "memory",
                "N": 1,
                "D": 1,
                "seed": 1,
                "input_pattern": "main",
                "trial": trial,
                "kernel_cycles": 10,
                "target_result_hash": result_hash,
                "status": "PASS",
            }
            for trial, result_hash in enumerate(("same", "same", "other"))
        ]

        matrix.apply_reproducibility(records, 3)

        self.assertEqual(
            {record["status"] for record in records},
            {"NONDETERMINISTIC"},
        )
        self.assertEqual(
            {record["reproducible"] for record in records}, {"NO"}
        )

    def test_terminal_capacity_records_can_be_reproducible(self) -> None:
        records = [
            {
                "config": "B1_SCALAR",
                "counter_profile": "memory",
                "case_id": "capacity",
                "evidence_class": "CAPACITY_PROBE",
                "N": 84,
                "D": 64,
                "seed": 1,
                "input_pattern": "main",
                "kernel_cycles": 0,
                "target_result_hash": "same",
                "status": "SKIPPED_MEMORY_LIMIT",
            }
            for _ in range(3)
        ]

        matrix.apply_reproducibility(records, 3)

        self.assertEqual(
            {record["reproducible"] for record in records}, {"YES"}
        )

    def test_paper_gate_requires_dynamic_b2r_trace(self) -> None:
        record = {
            "status": "PASS",
            "git_dirty": False,
            "counter_profile": "memory",
            "reproducible": "YES",
            "static_code_gate": "PASS",
            "fairness_gate": "PASS",
            "comparison_set_complete": "YES",
            "fsm_gate": "NA",
            "config": "B2R_RVV",
            "dynamic_trace_verified": "NO",
        }

        matrix.apply_paper_eligibility([record])

        self.assertEqual(record["paper_eligible"], "NO")
        self.assertEqual(
            record["paper_ineligible_reasons"],
            "DYNAMIC_RVV_TRACE_PENDING",
        )

    def test_paper_gate_marks_boundary_evidence_supporting_only(self) -> None:
        record = {
            "status": "PASS",
            "git_dirty": False,
            "counter_profile": "memory",
            "reproducible": "YES",
            "static_code_gate": "PASS",
            "fairness_gate": "PASS",
            "comparison_set_complete": "YES",
            "fsm_gate": "NA",
            "config": "B1_SCALAR",
            "dynamic_trace_verified": "NO",
            "evidence_class": "FUNCTIONAL_BOUNDARY",
        }

        matrix.apply_paper_eligibility([record])

        self.assertEqual(record["paper_eligible"], "NO")
        self.assertEqual(
            record["paper_ineligible_reasons"],
            "FUNCTIONAL_BOUNDARY_ONLY",
        )

    def test_cross_config_fairness_detects_compile_mismatch(self) -> None:
        common_fields = {
            "counter_profile": "memory",
            "N": 1,
            "D": 1,
            "seed": 1,
            "input_pattern": "main",
            "cfg_hash": "cfg",
            "simulator_hash": "sim",
            "input_hash": "input",
            "logical_N": 1,
            "logical_D": 1,
            "padded_N": 1,
            "padded_D": 1,
            "padding_ratio": 1.0,
        }
        records = [
            {
                **common_fields,
                "config": "B1_SCALAR",
                "compiler_fairness_hash": "same",
            },
            {
                **common_fields,
                "config": "B2R_RVV",
                "compiler_fairness_hash": "different",
            },
        ]

        matrix.apply_cross_config_fairness(
            records, {"B1_SCALAR", "B2R_RVV"}
        )

        self.assertEqual(
            {record["fairness_gate"] for record in records}, {"FAIL"}
        )
        self.assertEqual(
            {record["comparison_set_complete"] for record in records},
            {"YES"},
        )
        self.assertEqual(
            {record["fairness_mismatches"] for record in records},
            {"compiler_fairness_hash"},
        )

    def test_progressive_rows_compute_strong_baseline_speedups(self) -> None:
        records = []
        for config, cycles in (("B1_SCALAR", 120), ("B2R_RVV", 80)):
            records.extend(
                {
                    "config": config,
                    "counter_profile": "memory",
                    "N": 2,
                    "D": 8,
                    "seed": 1,
                    "input_pattern": "main",
                    "size_class": "SMALL",
                    "trial": trial,
                    "kernel_cycles": cycles,
                    "status": "PASS",
                    "reproducible": "YES",
                    "paper_eligible": "YES",
                }
                for trial in range(3)
            )

        rows = parse_results.progressive_rows(records)
        by_config = {row["config"]: row for row in rows}

        self.assertAlmostEqual(
            by_config["B2R_RVV"]["speedup_vs_B1"], 1.5
        )
        self.assertAlmostEqual(
            by_config["B1_SCALAR"]["speedup_vs_B2R"], 2 / 3
        )

    def test_trace_decoder_and_categories(self) -> None:
        instructions, ranges = trace_audit.decode_disassembly(
            "00000010 <online_merge_trace_begin>:\n"
            "  10: ret\n"
            "00000020 <online_merge_b2_r>:\n"
            "  20: vsetvli a0, a1, e32, m8\n"
            "  24: flw ft0, 0(a0)\n"
            "00000030 <online_merge_trace_end>:\n"
            "  30: ret\n"
        )

        self.assertEqual(instructions[0x20], "vsetvli")
        self.assertEqual(
            trace_audit.symbol_for(0x24, ranges), "online_merge_b2_r"
        )
        self.assertEqual(
            trace_audit.category("vsetvli", "online_merge_b2_r"),
            "rvv",
        )
        self.assertEqual(
            trace_audit.category("flw", "online_merge_b2_r"),
            "load_store",
        )

    def test_trace_cycle_attribution_covers_marker_span(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            disassembly = root / "objdump.txt"
            trace = root / "trace.dasm"
            disassembly.write_text(
                "00000010 <online_merge_trace_begin>:\n"
                "  10: ret\n"
                "00000020 <online_merge_b2_r>:\n"
                "  20: vsetvli a0, a1, e32, m8\n"
                "  24: flw ft0, 0(a0)\n"
                "00000030 <online_merge_trace_end>:\n"
                "  30: ret\n",
                encoding="utf-8",
            )
            trace.write_text(
                "0 100 0 0x10 DASM\n"
                "0 101 0 0x20 DASM\n"
                "0 105 0 0x24 DASM\n"
                "0 110 0 0x30 DASM\n",
                encoding="utf-8",
            )

            payload = trace_audit.audit_trace(
                trace, disassembly, "B2R_RVV", 1, 1
            )

        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["retired_rvv_instructions"], 1)
        self.assertEqual(payload["marker_tick_span"], 9)
        self.assertEqual(sum(payload["category_cycle_spans"].values()), 9)

    def test_compile_command_filter_is_target_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = [
                {
                    "file": "/src/main.c",
                    "command": "cc -o CMakeFiles/wanted.dir/main.c.o",
                },
                {
                    "file": "/src/main.c",
                    "command": "cc -o CMakeFiles/unwanted.dir/main.c.o",
                },
            ]
            (root / "compile_commands.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

            selected = matrix.target_compile_commands(root, "wanted")

        self.assertEqual(len(selected), 1)
        self.assertIn("wanted.dir", selected[0]["command"])

    def test_compiler_fairness_hash_ignores_only_selector_and_output(
        self,
    ) -> None:
        first = (
            "clang -O3 -DONLINE_MERGE_IMPLEMENTATION_SELECT=1 "
            "-o one.o -c main.c"
        )
        second = (
            "clang -O3 -DONLINE_MERGE_IMPLEMENTATION_SELECT=4 "
            "-o two.o -c main.c"
        )
        weaker = (
            "clang -O1 -DONLINE_MERGE_IMPLEMENTATION_SELECT=4 "
            "-o two.o -c main.c"
        )

        self.assertEqual(
            matrix.compiler_fairness_hash(first),
            matrix.compiler_fairness_hash(second),
        )
        self.assertNotEqual(
            matrix.compiler_fairness_hash(first),
            matrix.compiler_fairness_hash(weaker),
        )

    def test_plot_gate_rejects_paper_ineligible_rows(self) -> None:
        with self.assertRaisesRegex(SystemExit, "paper-ineligible"):
            make_plots.require_eligible(
                [{"paper_eligible": "NO"}], allow=False
            )

    def test_plot_gate_rejects_incomplete_matrix(self) -> None:
        with self.assertRaisesRegex(SystemExit, "incomplete"):
            make_plots.require_complete_matrix(
                [{"N": "1", "D": "1", "config": "B1_SCALAR"}]
            )


if __name__ == "__main__":
    unittest.main()

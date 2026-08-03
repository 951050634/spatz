"""Unit tests for the paper-experiment facade."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_instruction_trace as trace_audit
import experiment_common as common
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

# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(MODULE_DIR))

import analyze_fsm as analysis  # noqa: E402


def raw_record(
    implementation: str,
    repeat: int,
    cycles: int,
    *,
    n: int = 1,
    d: int = 1,
    source_root: str = "/tmp/work-online-merge-input",
) -> dict[str, object]:
    return {
        "source_root": source_root,
        "implementation": implementation,
        "N": n,
        "D": d,
        "seed": 1,
        "case_kind": "main",
        "repeat": repeat,
        "cycles": cycles,
        "tcdm_accessed": 100,
        "tcdm_congested": 10,
        "status": "pass",
        "target_status": "pass",
        "command_status": "pass",
        "command_returncode": 0,
        "nonfinite": 0,
        "max_abs": 0.001,
        "max_rel": 0.002,
        "rmse": 0.0005,
        "bit_equal_ratio": 0.75,
    }


def raw_records(
    *,
    n: int = 1,
    d: int = 1,
    repeats: int = 3,
    source_root: str = "/tmp/work-online-merge-input",
) -> list[dict[str, object]]:
    records = []
    for repeat in range(repeats):
        records.append(raw_record(
            "B2-R",
            repeat,
            200 + 10 * repeat,
            n=n,
            d=d,
            source_root=source_root,
        ))
        records.append(raw_record(
            "B3",
            repeat,
            20 + repeat,
            n=n,
            d=d,
            source_root=source_root,
        ))
    return records


def fsm_observation(
    invocation: int,
    *,
    n: int = 1,
    d: int = 1,
    terminal_state: str = "DONE",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "invocation": invocation,
        "N": n,
        "D": d,
        "terminal_state": terminal_state,
        "load_scalar_cycles": 2,
        "compute_scalar_cycles": 1,
        "compute_weight_cycles": 1,
        "store_scalar_cycles": 2,
        "update_vector_cycles": 4,
        "busy_cycles": 10,
    }


def validated_observations(
    *,
    n: int = 1,
    d: int = 1,
    repeats: int = 3,
) -> list[dict[str, object]]:
    raw = [
        fsm_observation(invocation, n=n, d=d)
        for invocation in range(repeats + 1)
    ]
    return analysis.validate_observations(
        raw, (n, d), list(range(repeats))
    )


class A1ObservationSelectionTest(unittest.TestCase):
    def test_scalar_only_prefix_is_excluded_from_full_smu_analysis(self) -> None:
        scalar_only = [
            {
                **fsm_observation(invocation),
                "update_vector_cycles": 0,
                "busy_cycles": 6,
            }
            for invocation in range(4)
        ]
        full = [fsm_observation(invocation + 4) for invocation in range(4)]
        selected = analysis.validate_observations(
            scalar_only + full, (1, 1), [0, 1, 2]
        )
        self.assertEqual([row["invocation"] for row in selected], [0, 1, 2, 3])
        self.assertEqual(
            [row["source_invocation"] for row in selected], [4, 5, 6, 7]
        )
        self.assertTrue(
            all(row["update_vector_cycles"] == 4 for row in selected)
        )


def record_map(
    *,
    n: int = 1,
    d: int = 1,
    repeats: int = 3,
    source_root: str = "/tmp/work-online-merge-input",
) -> dict[tuple[int, int, str, int], dict[str, object]]:
    return {
        (n, d, str(record["implementation"]), int(record["repeat"])):
            record
        for record in raw_records(
            n=n,
            d=d,
            repeats=repeats,
            source_root=source_root,
        )
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def make_result_root(parent: Path) -> Path:
    root = parent / "work-online-merge-fsm-input"
    root.mkdir()
    case_root = root / analysis.case_slug(1, 1, 3)
    case_root.mkdir()
    log_path = case_root / "simulator.log"
    log_lines = [
        analysis.FSM_PREFIX + json.dumps(
            fsm_observation(invocation), sort_keys=True
        )
        for invocation in range(4)
    ]
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    commit = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    write_json(root / "run_manifest.json", {
        "git_commit": commit,
        "git_dirty": False,
        "cfg_path": "hw/system/spatz_cluster/cfg/test.hjson",
        "cfg_hash": "cfg-hash",
        "tool_versions": {
            "simulator": {
                "path": "/tmp/spatz_cluster.vlt",
                "sha256": "simulator-hash",
                "status": "present",
            },
        },
        "wall_clock_start_end": {
            "first_command_start": "2026-01-01T00:00:00+00:00",
            "last_command_end": "2026-01-01T00:00:01+00:00",
        },
        "validation_result": {
            "failure_count": 0,
            "record_count": 6,
            "statuses": ["pass"],
        },
        "cases": [{
            "n": 1,
            "d": 1,
            "seed": 1,
            "case_kind": "main",
            "repeats": 3,
        }],
    })
    records = raw_records(source_root=str(root))
    for record in records:
        record.pop("source_root")
        record["git_commit"] = commit
    write_json(root / "records.json", records)
    write_json(root / "failures.json", [])
    write_json(root / "commands.json", [{
        "argv": ["/tmp/spatz_cluster.vlt", "online-merge.elf"],
        "command": "/tmp/spatz_cluster.vlt online-merge.elf",
        "start_utc": "2026-01-01T00:00:00+00:00",
        "end_utc": "2026-01-01T00:00:01+00:00",
        "log_path": str(log_path),
        "returncode": 0,
        "status": "pass",
        "timeout_seconds": 1800,
    }])
    return root


class AnalyzeFsmTest(unittest.TestCase):
    def test_parse_valid_and_malformed_structured_records(self) -> None:
        valid = analysis.FSM_PREFIX + json.dumps(fsm_observation(0))
        text = "\n".join((
            "unrelated simulator output",
            valid,
            analysis.FSM_PREFIX + "{not-json",
            analysis.FSM_PREFIX + "[]",
        ))
        observations, errors = analysis.parse_fsm_text(text)
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["invocation"], 0)
        self.assertEqual(observations[0]["line_number"], 2)
        self.assertEqual(
            [error["kind"] for error in errors],
            ["malformed_fsm_json", "non_object_fsm_record"],
        )

    def test_state_sum_busy_mismatch_is_rejected(self) -> None:
        observations = [fsm_observation(i) for i in range(4)]
        observations[2]["busy_cycles"] = 11
        with self.assertRaisesRegex(
            analysis.AnalysisError, "does not match busy"
        ):
            analysis.validate_observations(
                observations, (1, 1), [0, 1, 2]
            )

    def test_duplicate_and_noncontiguous_invocations_are_rejected(self) -> None:
        duplicate = [fsm_observation(i) for i in (0, 1, 1, 3)]
        with self.assertRaisesRegex(
            analysis.AnalysisError, "duplicate FSM invocation"
        ):
            analysis.validate_observations(
                duplicate, (1, 1), [0, 1, 2]
            )
        noncontiguous = [fsm_observation(i) for i in (0, 1, 2, 4)]
        with self.assertRaisesRegex(
            analysis.AnalysisError, "not contiguous"
        ):
            analysis.validate_observations(
                noncontiguous, (1, 1), [0, 1, 2]
            )

    def test_error_terminal_is_rejected(self) -> None:
        observations = [fsm_observation(i) for i in range(4)]
        observations[3]["terminal_state"] = "ERROR"
        with self.assertRaisesRegex(
            analysis.AnalysisError, "ended in 'ERROR'"
        ):
            analysis.validate_observations(
                observations, (1, 1), [0, 1, 2]
            )

    def test_busy_exceeding_a2_end_to_end_is_rejected(self) -> None:
        records = record_map(repeats=1)
        records[(1, 1, "B3", 0)]["cycles"] = 9
        observations = validated_observations(repeats=1)
        with self.assertRaisesRegex(
            analysis.AnalysisError, "busy 10 exceeds A2 end-to-end 9"
        ):
            analysis.build_case_rows(
                (1, 1),
                [0],
                records,
                observations,
                Path("/tmp/work-online-merge-input"),
                Path("/tmp/work-online-merge-input/simulator.log"),
            )

    def test_per_repeat_ablation_and_shares(self) -> None:
        observations, rows = analysis.build_case_rows(
            (1, 1),
            [0, 1, 2],
            record_map(),
            validated_observations(),
            Path("/tmp/work-online-merge-input"),
            Path("/tmp/work-online-merge-input/simulator.log"),
        )
        self.assertEqual(len(observations), 4)
        self.assertEqual(len(rows), 3)
        first = rows[0]
        self.assertEqual(first["A0_cycles"], 200)
        self.assertEqual(first["A2_end_to_end_cycles"], 20)
        self.assertEqual(first["A2_speedup_vs_A0"], 10.0)
        self.assertEqual(first["scalar_cycles"], 6)
        self.assertEqual(first["vector_cycles"], 4)
        self.assertEqual(first["busy_cycles"], 10)
        self.assertEqual(
            first["command_setup_wait_error_nonoverlap_cycles"], 10
        )
        self.assertEqual(first["scalar_share_of_busy"], 0.6)
        self.assertEqual(first["vector_share_of_busy"], 0.4)
        self.assertEqual(
            first["nonoverlap_share_of_A2_end_to_end"], 0.5
        )

    def test_case_summary_uses_measured_medians(self) -> None:
        _, rows = analysis.build_case_rows(
            (1, 1),
            [0, 1, 2],
            record_map(),
            validated_observations(),
            Path("/tmp/work-online-merge-input"),
            Path("/tmp/work-online-merge-input/simulator.log"),
        )
        summary = analysis.summarize_case(rows)
        medians = summary["median_cycles"]
        self.assertEqual(medians["A0_cycles"]["numerator"], 210)
        self.assertEqual(
            medians["A2_end_to_end_cycles"]["numerator"], 21
        )
        self.assertEqual(
            summary["A2_speedup_vs_A0_median_cycles"]["decimal"],
            10.0,
        )
        self.assertEqual(
            summary["scalar_share_of_busy_from_medians"]["decimal"],
            0.6,
        )

    def test_nonpass_records_are_retained_in_full(self) -> None:
        timeout = raw_record("B3", 0, 1)
        timeout.update({
            "status": "timeout",
            "target_status": "pass",
            "detail": {"signal": "TERM", "preserved": True},
        })
        _, retained = analysis.validated_pass_records(
            {"records": [timeout]}, []
        )
        self.assertEqual(retained["nonpass_records"][0], timeout)

    def test_direct_rtl_state_encoding_and_busy_expression(self) -> None:
        inspected = analysis.inspect_state_encoding(REPO_ROOT)
        self.assertTrue(inspected["encoding_matches"])
        self.assertTrue(inspected["busy_expression_matches"])
        self.assertTrue(inspected["mutually_exclusive_enum"])
        self.assertEqual(
            inspected["declaration_order_encoding"],
            analysis.EXPECTED_STATE_ENCODING,
        )

    def test_full_analysis_and_deterministic_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_result_root(parent)
            report = analysis.analyze(
                repo_root=REPO_ROOT,
                result_roots=[root],
                required_cases=[(1, 1)],
                tool_path=MODULE_DIR / "analyze_fsm.py",
            )
            for gate in (
                "required_cases_complete",
                "at_least_three_measured_repeats_per_case",
                "all_required_A0_A2_records_pass",
                "all_fsm_invocations_terminate_done",
                "all_fsm_state_sums_match_busy",
                "all_A2_end_to_end_reconciles",
                "observer_records_parse_cleanly",
                "state_enum_encoding_confirmed",
                "input_roots_git_clean",
                "analysis_commit_matches_inputs",
                "input_cfg_identity_complete_and_consistent",
                "input_simulator_identity_complete_and_consistent",
                "input_measurement_windows_recorded",
                "input_validation_results_recorded",
            ):
                self.assertTrue(report["acceptance"][gate], gate)
            first = parent / "first"
            second = parent / "second"
            analysis.write_outputs(first, report)
            analysis.write_outputs(second, report)
            for name in (
                "analysis.json",
                "fsm_observations.csv",
                "fsm_breakdown.csv",
                "ablation_a0_a2.csv",
                "artifact_manifest.json",
            ):
                self.assertEqual(
                    (first / name).read_bytes(),
                    (second / name).read_bytes(),
                    name,
                )

    def test_output_directory_must_be_external_and_controlled(self) -> None:
        with self.assertRaisesRegex(
            analysis.AnalysisError, "outside the Git worktree"
        ):
            analysis.validate_output_dir(
                REPO_ROOT / "work-online-merge-fsm-test", REPO_ROOT
            )
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            with self.assertRaisesRegex(
                analysis.AnalysisError, "basename must start"
            ):
                analysis.validate_output_dir(
                    parent / "uncontrolled", REPO_ROOT
                )
            valid = parent / "work-online-merge-fsm-test"
            self.assertEqual(
                analysis.validate_output_dir(valid, REPO_ROOT),
                valid.resolve(),
            )
            valid.mkdir()
            with self.assertRaisesRegex(
                analysis.AnalysisError, "already exists"
            ):
                analysis.validate_output_dir(valid, REPO_ROOT)


if __name__ == "__main__":
    unittest.main()

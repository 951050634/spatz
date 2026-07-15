# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from unittest import mock

MODULE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(MODULE_DIR))
sys.path.insert(0, str(TEST_DIR))

import analyze_concurrency as analysis  # noqa: E402
import run_concurrency as runner  # noqa: E402
import run_experiments as common  # noqa: E402
import test_run_concurrency as capture_fixture  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def set_u64(record: dict[str, object], prefix: str, value: int) -> None:
    record[f"{prefix}_hi"] = value >> 32
    record[f"{prefix}_lo"] = value & 0xFFFFFFFF


def set_fsm_busy(record: dict[str, object], busy: int) -> None:
    if busy < 40:
        raise ValueError("synthetic FSM busy value must be at least 40")
    record.update({
        "load_scalar_cycles": 10,
        "compute_scalar_cycles": 10,
        "compute_weight_cycles": 10,
        "store_scalar_cycles": 10,
        "update_vector_cycles": busy - 40,
        "busy_cycles": busy,
    })


def configure_schedule(
    case: common.Case,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    records, fsm_records = capture_fixture.full_schedule(case)
    fsm_by_invocation = {
        int(record["invocation"]): record for record in fsm_records
    }
    for record in records:
        scenario = str(record["scenario"])
        repeat = int(record["repeat"])
        phase = int(record["phase_bytes"])
        phase_index = phase // 8
        invocation = int(record["smu_invocation"])

        if scenario == "C0_SMU":
            busy = 90 if repeat == -1 else 100 + 10 * repeat
            set_fsm_busy(fsm_by_invocation[invocation], busy)
            set_u64(record, "total_cycles", busy + 20)
        elif scenario == "C0_REG":
            core = 900 if repeat == -1 else 120 + 10 * repeat
            set_u64(record, "total_cycles", core)
            set_u64(record, "core_cycles", core)
        elif scenario == "C0_STREAM":
            core = 800 if repeat == -1 else 240 + 10 * repeat
            set_u64(record, "total_cycles", core)
            set_u64(record, "core_cycles", core)
        elif scenario == "C1":
            if repeat == -1:
                total, core, busy = 5000, 1000, 100
            else:
                total = (160, 260, 180, 190)[repeat]
                core = (150, 160, 170, 180)[repeat]
                busy = (125, 140, 150, 160)[repeat]
            set_u64(record, "total_cycles", total)
            set_u64(record, "core_cycles", core)
            set_fsm_busy(fsm_by_invocation[invocation], busy)
        elif scenario == "C2":
            if repeat == -1:
                total, core, busy = 6000, 1100, 110
            else:
                total = 300 + 10 * repeat
                core = 270 + 10 * repeat
                busy = 140 + 10 * repeat
            set_u64(record, "total_cycles", total)
            set_u64(record, "core_cycles", core)
            record["tcdm_accessed"] = 1000
            record["tcdm_congested"] = 250 + repeat if repeat >= 0 else 999
            set_fsm_busy(fsm_by_invocation[invocation], busy)
        elif scenario == "C3_CORE":
            core = (
                9000 + phase_index
                if repeat == -1
                else 300 + 5 * phase_index + 2 * repeat
            )
            set_u64(record, "total_cycles", core)
            set_u64(record, "core_cycles", core)
        elif scenario == "C3":
            if repeat == -1:
                total = 9999
                core = 8500 + phase_index
                busy = 120 + phase_index
            else:
                total = 600 + 10 * phase_index + 2 * (repeat - 1)
                core = 330 + 5 * phase_index + 2 * repeat
                busy = 150 + phase_index + repeat
            set_u64(record, "total_cycles", total)
            set_u64(record, "core_cycles", core)
            record["tcdm_accessed"] = 2000
            record["tcdm_congested"] = (
                100 + 10 * phase_index + repeat if repeat >= 0 else 1999
            )
            set_fsm_busy(fsm_by_invocation[invocation], busy)
        else:  # pragma: no cover - full_schedule is intentionally fixed
            raise AssertionError(f"unexpected scenario {scenario}")
    return records, fsm_records


def git_head() -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def common_metadata(commit: str) -> dict[str, object]:
    return {
        "git_commit": commit,
        "git_dirty": False,
        "cfg_path": "hw/system/spatz_cluster/cfg/test.hjson",
        "cfg_hash": "synthetic-cfg-sha256",
        "tool_version": {"simulator": "synthetic-verilator"},
    }


def manifest_for(
    case: common.Case,
    metadata: dict[str, object],
    *,
    status: str = "pass",
    record_count: int | None = None,
    metadata_count: int = 1,
    fsm_count: int | None = None,
    failure_count: int = 0,
) -> dict[str, object]:
    expected_records = len(runner.expected_record_keys(case.repeats))
    expected_fsm = runner.expected_smu_invocations(case.repeats)
    return {
        "schema_version": 1,
        **metadata,
        "case": asdict(case),
        "expected_schedule": {
            "scenario_counts": runner.expected_scenario_counts(case.repeats),
            "record_count": expected_records,
            "smu_invocation_count": expected_fsm,
            "phases_bytes": list(runner.PHASES),
        },
        "tool_versions": {
            "simulator": {
                "path": "/tmp/synthetic-spatz-cluster.vlt",
                "sha256": "synthetic-simulator-sha256",
                "status": "present",
            },
        },
        "simulator_source": {
            "path": "/tmp/synthetic-source",
            "status": "pass",
            "commit": metadata["git_commit"],
            "dirty": False,
        },
        "wall_clock_start_end": {
            "first_command_start": "2026-01-01T00:00:00+00:00",
            "last_command_end": "2026-01-01T00:00:01+00:00",
        },
        "validation_result": {
            "statuses": [status],
            "record_count": (
                expected_records if record_count is None else record_count
            ),
            "metadata_count": metadata_count,
            "fsm_record_count": expected_fsm if fsm_count is None else fsm_count,
            "failure_count": failure_count,
        },
    }


def write_root_files(
    root: Path,
    manifest: dict[str, object],
    records: list[dict[str, object]],
    metadata: list[dict[str, object]],
    fsm_records: list[dict[str, object]],
    failures: list[dict[str, object]],
    commands: list[dict[str, object]],
) -> Path:
    root.mkdir()
    write_json(root / "run_manifest.json", manifest)
    write_json(root / "concurrency_records.json", records)
    write_json(root / "concurrency_metadata.json", metadata)
    write_json(root / "fsm_records.json", fsm_records)
    write_json(root / "failures.json", failures)
    write_json(root / "commands.json", commands)
    write_json(root / "artifact_manifest.json", [{
        "path": "/tmp/synthetic-input.elf",
        "sha256": "synthetic-elf-sha256",
        "measurement_window": "synthetic target mcycle windows",
    }])
    return root


def make_passing_root(
    parent: Path,
    name: str = "work-online-merge-concurrency-input",
    *,
    repeats: int = 3,
) -> Path:
    case = common.Case(16, 64, 1, "main", repeats, 30)
    raw_records, raw_fsm = configure_schedule(case)
    command = capture_fixture.command()
    records, metadata, fsm_records, failures = runner.normalize_run(
        raw_records,
        [capture_fixture.raw_meta(case)],
        raw_fsm,
        case,
        command,
        runner.PASS_BANNER,
        [],
    )
    if failures:
        raise AssertionError(f"synthetic passing fixture failed: {failures}")
    provenance = common_metadata(git_head())
    runner.add_metadata(records, provenance)
    runner.add_metadata(metadata, provenance)
    runner.add_metadata(fsm_records, provenance)
    manifest = manifest_for(case, provenance)
    return write_root_files(
        parent / name,
        manifest,
        records,
        metadata,
        fsm_records,
        [],
        [asdict(command)],
    )


def make_terminal_root(parent: Path, status: str) -> Path:
    case = common.Case(16, 64, 1, "main", 3, 30)
    provenance = common_metadata(git_head())
    record = runner.synthetic_record(case, status, f"synthetic {status}")
    runner.add_metadata([record], provenance)
    command_status = "timeout" if status == "timeout" else "pass"
    returncode = -15 if status == "timeout" else 0
    command = capture_fixture.command(command_status, returncode)
    failures = []
    if status == "timeout":
        failures = [{
            **provenance,
            "kind": "synthetic_timeout",
            "detail": "retained timeout evidence",
            "status": status,
        }]
    manifest = manifest_for(
        case,
        provenance,
        status=status,
        record_count=1,
        metadata_count=0,
        fsm_count=0,
        failure_count=len(failures),
    )
    return write_root_files(
        parent / f"work-online-merge-{status}",
        manifest,
        [record],
        [],
        [],
        failures,
        [asdict(command)],
    )


def clean_git_context() -> dict[str, object]:
    return {"commit": git_head(), "dirty": False}


def find_row(
    report: dict[str, object], scenario: str, phase: int, repeat: int
) -> dict[str, object]:
    rows = report["observations"]
    assert isinstance(rows, list)
    matches = [
        row
        for row in rows
        if row["scenario"] == scenario
        and row["phase_bytes"] == phase
        and row["repeat"] == repeat
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one row, got {len(matches)}")
    return matches[0]


class AnalyzeConcurrencyTest(unittest.TestCase):
    def analyze_root(self, root: Path) -> dict[str, object]:
        with mock.patch.object(
            analysis, "git_context", return_value=clean_git_context()
        ):
            return analysis.analyze(
                REPO_ROOT,
                [root],
                [(16, 64)],
                MODULE_DIR / "analyze_concurrency.py",
            )

    def test_known_c1_and_c2_raw_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.analyze_root(make_passing_root(Path(temporary)))
        c1 = find_row(report, "C1", 0, 0)
        self.assertEqual(c1["T_smu"], 100)
        self.assertEqual(c1["T_core"], 120)
        self.assertEqual(c1["T_concurrent"], 160)
        self.assertEqual(c1["T_smu_concurrent"], 125)
        self.assertEqual(c1["T_core_concurrent"], 150)
        self.assertEqual(c1["overlap_saved_cycles"], 60)
        self.assertEqual(
            Fraction(c1["eta_overlap_numerator"], c1["eta_overlap_denominator"]),
            Fraction(3, 5),
        )
        self.assertEqual(
            Fraction(c1["slowdown_smu_numerator"], c1["slowdown_smu_denominator"]),
            Fraction(5, 4),
        )
        self.assertEqual(
            Fraction(
                c1["slowdown_core_numerator"],
                c1["slowdown_core_denominator"],
            ),
            Fraction(5, 4),
        )

        c2 = find_row(report, "C2", 0, 0)
        self.assertEqual(c2["T_core"], 240)
        self.assertEqual(c2["T_concurrent"], 300)
        self.assertEqual(
            Fraction(
                c2["congestion_ratio_numerator"],
                c2["congestion_ratio_denominator"],
            ),
            Fraction(1, 4),
        )
        self.assertEqual(
            Fraction(
                c2["core_bytes_per_cycle_numerator"],
                c2["core_bytes_per_cycle_denominator"],
            ),
            Fraction(runner.STREAM_BYTES, 270),
        )
        self.assertEqual(
            Fraction(
                c2["smu_elements_per_cycle_numerator"],
                c2["smu_elements_per_cycle_denominator"],
            ),
            Fraction(16 * 64, 140),
        )
        c2_summary = next(
            row
            for row in report["scenario_summaries"]
            if row["scenario"] == "C2"
        )
        exact_median = Fraction(runner.STREAM_BYTES, 280)
        self.assertEqual(
            c2_summary["medians"]["core_bytes_per_cycle"]["numerator"],
            exact_median.numerator,
        )
        self.assertEqual(
            c2_summary["medians"]["core_bytes_per_cycle"]["denominator"],
            exact_median.denominator,
        )

    def test_negative_overlap_is_retained_raw_and_unclamped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.analyze_root(make_passing_root(Path(temporary)))
        row = find_row(report, "C1", 0, 1)
        self.assertEqual(row["overlap_saved_cycles"], -20)
        self.assertFalse(row["concurrency_faster_than_serial"])
        self.assertEqual(
            Fraction(
                row["eta_overlap_numerator"],
                row["eta_overlap_denominator"],
            ),
            Fraction(-2, 11),
        )
        summaries = report["scenario_summaries"]
        c1 = next(row for row in summaries if row["scenario"] == "C1")
        self.assertEqual(c1["negative_overlap_count"], 1)
        self.assertTrue(report["acceptance_gates"]["raw_overlap_not_clamped"])

    def test_warmups_phase_summaries_and_exact_baseline_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.analyze_root(make_passing_root(Path(temporary)))
        self.assertEqual(len(report["observations"]), 72)
        self.assertEqual(report["measured_observation_count"], 54)

        phase = 40
        c3 = find_row(report, "C3", phase, 0)
        self.assertEqual(c3["T_core"], 325)
        self.assertEqual(c3["core_baseline_scenario"], "C3_CORE")
        self.assertEqual(c3["T_concurrent"], 648)

        c1_summary = next(
            row
            for row in report["scenario_summaries"]
            if row["scenario"] == "C1"
        )
        self.assertEqual(c1_summary["warmup_count"], 1)
        self.assertEqual(c1_summary["measured_count"], 3)
        self.assertEqual(
            c1_summary["medians"]["T_concurrent"]["numerator"], 180
        )

        phase_summaries = report["bank_phase_summaries"]
        self.assertEqual(len(phase_summaries), 16)
        phase_zero = next(
            row for row in phase_summaries if row["phase_bytes"] == 0
        )
        self.assertEqual(phase_zero["warmup_count"], 1)
        self.assertEqual(phase_zero["measured_count"], 3)
        self.assertEqual(
            phase_zero["medians"]["T_concurrent"]["numerator"], 600
        )

        selection = report["bank_phase_selection"][0]
        self.assertEqual(selection["best"]["phase_bytes"], 0)
        self.assertEqual(selection["worst"]["phase_bytes"], 120)
        self.assertEqual(selection["median"]["phase_bytes"], 56)

    def test_repeat_count_gate_uses_each_run_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.analyze_root(
                make_passing_root(Path(temporary), repeats=4)
            )
        run = report["analyzed_runs"][0]
        self.assertEqual(run["warmup_count"], 18)
        self.assertEqual(run["measured_count"], 72)
        self.assertTrue(
            report["acceptance_gates"]
            ["warmups_retained_but_excluded_from_statistics"]
        )

    def test_missing_duplicate_fsm_and_incomplete_schedule_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            missing = make_passing_root(parent, "work-online-merge-missing-fsm")
            fsm = read_json(missing / "fsm_records.json")
            assert isinstance(fsm, list)
            fsm.pop()
            write_json(missing / "fsm_records.json", fsm)
            with self.assertRaisesRegex(
                analysis.AnalysisError, "FSM invocation set mismatch"
            ):
                self.analyze_root(missing)

            duplicate = make_passing_root(
                parent, "work-online-merge-duplicate-fsm"
            )
            fsm = read_json(duplicate / "fsm_records.json")
            assert isinstance(fsm, list)
            fsm.append(dict(fsm[-1]))
            write_json(duplicate / "fsm_records.json", fsm)
            with self.assertRaisesRegex(
                analysis.AnalysisError, "duplicate FSM invocation"
            ):
                self.analyze_root(duplicate)

            incomplete = make_passing_root(
                parent, "work-online-merge-incomplete-target"
            )
            records = read_json(incomplete / "concurrency_records.json")
            assert isinstance(records, list)
            records.pop()
            write_json(incomplete / "concurrency_records.json", records)
            with self.assertRaisesRegex(
                analysis.AnalysisError, "incomplete passing schedule"
            ):
                self.analyze_root(incomplete)

    def test_malformed_numeric_and_component_windows_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            malformed = make_passing_root(
                parent, "work-online-merge-malformed-number"
            )
            records = read_json(malformed / "concurrency_records.json")
            assert isinstance(records, list)
            c1 = next(
                row
                for row in records
                if row["scenario"] == "C1" and row["repeat"] == 0
            )
            c1["total_cycles"] = "not-an-integer"
            write_json(malformed / "concurrency_records.json", records)
            with self.assertRaisesRegex(
                analysis.AnalysisError, "total_cycles must be an integer"
            ):
                self.analyze_root(malformed)

            short = make_passing_root(
                parent, "work-online-merge-short-window"
            )
            records = read_json(short / "concurrency_records.json")
            assert isinstance(records, list)
            c1 = next(
                row
                for row in records
                if row["scenario"] == "C1" and row["repeat"] == 0
            )
            c1["total_cycles"] = 100
            write_json(short / "concurrency_records.json", records)
            with self.assertRaisesRegex(
                analysis.AnalysisError, "shorter than a component window"
            ):
                self.analyze_root(short)

    def test_nonpass_terminal_and_failure_evidence_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            passing = make_passing_root(parent)
            capacity = make_terminal_root(parent, "capacity_skip")
            unsupported = make_terminal_root(parent, "unsupported")
            timeout = make_terminal_root(parent, "timeout")
            with mock.patch.object(
                analysis, "git_context", return_value=clean_git_context()
            ):
                report = analysis.analyze(
                    REPO_ROOT,
                    [timeout, unsupported, passing, capacity],
                    [(16, 64)],
                    MODULE_DIR / "analyze_concurrency.py",
                )
        counts = report["retained_input"]["status_counts"]
        self.assertEqual(counts["capacity_skip"], 1)
        self.assertEqual(counts["unsupported"], 1)
        self.assertEqual(counts["timeout"], 1)
        self.assertEqual(len(report["skipped_runs"]), 3)
        self.assertEqual(len(report["retained_input"]["failures"]), 1)
        self.assertEqual(len(report["retained_input"]["commands"]), 4)
        self.assertTrue(
            report["acceptance_gates"]["all_input_evidence_retained"]
        )
        self.assertTrue(report["all_acceptance_gates_pass"])

    def test_nonpass_only_root_produces_structured_nonacceptance_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = make_terminal_root(parent, "capacity_skip")
            report = self.analyze_root(root)
            self.assertFalse(report["all_acceptance_gates_pass"])
            self.assertEqual(report["observations"], [])
            self.assertEqual(report["scenario_summaries"], [])
            output = parent / "work-online-merge-nonpass-analysis"
            hashes = analysis.write_outputs(output, report)
            self.assertEqual(len(hashes), 6)
            self.assertEqual(
                read_json(output / "analysis.json")["missing_cases"],
                [[16, 64]],
            )

    def test_multiple_roots_order_independent_outputs_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root_b = make_passing_root(parent, "work-online-merge-input-b")
            root_a = make_passing_root(parent, "work-online-merge-input-a")
            with mock.patch.object(
                analysis, "git_context", return_value=clean_git_context()
            ):
                report_ba = analysis.analyze(
                    REPO_ROOT,
                    [root_b, root_a],
                    [(16, 64)],
                    MODULE_DIR / "analyze_concurrency.py",
                )
                report_ab = analysis.analyze(
                    REPO_ROOT,
                    [root_a, root_b],
                    [(16, 64)],
                    MODULE_DIR / "analyze_concurrency.py",
                )
            self.assertEqual(report_ba, report_ab)
            self.assertEqual(len(report_ab["observations"]), 144)
            self.assertEqual(len(report_ab["analyzed_runs"]), 2)
            self.assertTrue(report_ab["all_acceptance_gates_pass"])

            first = parent / "first"
            second = parent / "second"
            analysis.write_outputs(first, report_ab)
            analysis.write_outputs(second, report_ba)
            for name in (
                "analysis.json",
                "concurrency_observations.csv",
                "concurrency_summary.csv",
                "bank_phase_summary.csv",
                "retained_status_records.csv",
                "artifact_manifest.json",
            ):
                self.assertEqual(
                    (first / name).read_bytes(),
                    (second / name).read_bytes(),
                    name,
                )
            manifest = read_json(first / "artifact_manifest.json")
            assert isinstance(manifest, dict)
            for name, expected in manifest["outputs"].items():
                actual = hashlib.sha256((first / name).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, name)
            summary_header = (
                first / "concurrency_summary.csv"
            ).read_text(encoding="utf-8").splitlines()[0]
            self.assertIn(
                "core_bytes_per_cycle_median_numerator", summary_header
            )
            self.assertIn(
                "core_bytes_per_cycle_median_denominator", summary_header
            )

    def test_passing_manifest_failures_and_provenance_mismatch_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            failed = make_passing_root(
                parent, "work-online-merge-passing-with-failure"
            )
            write_json(failed / "failures.json", [{"kind": "unexpected"}])
            with self.assertRaisesRegex(
                analysis.AnalysisError, "contains failures"
            ):
                self.analyze_root(failed)

            mismatch = make_passing_root(
                parent, "work-online-merge-provenance-mismatch"
            )
            records = read_json(mismatch / "concurrency_records.json")
            assert isinstance(records, list)
            records[0]["cfg_hash"] = "wrong-cfg"
            write_json(mismatch / "concurrency_records.json", records)
            with self.assertRaisesRegex(
                analysis.AnalysisError, "cfg_hash does not match manifest"
            ):
                self.analyze_root(mismatch)

    def test_output_directory_must_be_external_fresh_and_controlled(self) -> None:
        with self.assertRaisesRegex(
            analysis.AnalysisError, "outside the Git worktree"
        ):
            analysis.validate_output_dir(
                REPO_ROOT / "work-online-merge-concurrency-analysis",
                REPO_ROOT,
            )
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            with self.assertRaisesRegex(
                analysis.AnalysisError, "basename must start"
            ):
                analysis.validate_output_dir(parent / "uncontrolled", REPO_ROOT)
            valid = parent / "work-online-merge-concurrency-analysis"
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

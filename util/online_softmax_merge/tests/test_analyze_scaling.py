# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import json
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(MODULE_DIR))

import analyze_scaling as analysis  # noqa: E402


def point(
    implementation: str,
    n: int,
    d: int,
    cycles: int,
) -> dict[str, object]:
    return {
        "implementation": implementation,
        "N": n,
        "D": d,
        "measured_repeats": 3,
        "cycles_min": cycles - 1,
        "cycles_median": Fraction(cycles),
        "cycles_max": cycles + 1,
        "cycles_per_element": Fraction(cycles, n * d),
        "elements_per_cycle": Fraction(n * d, cycles),
        "speedup_vs_B2_R": Fraction(1),
        "tcdm_accessed_median": Fraction(10),
        "tcdm_congested_median": Fraction(2),
        "congestion_ratio_median": Fraction(1, 5),
        "footprint_bytes": 1024,
        "allocation_bytes": 512,
        "tcdm_capacity_bytes": 131072,
        "source_roots": ["/tmp/work-online-merge-input"],
    }


def raw_record(
    implementation: str,
    n: int,
    d: int,
    repeat: int,
    cycles: int,
    source_root: str = "/tmp/work-online-merge-input-a",
    status: str = "pass",
    git_commit: str = "commit-a",
) -> dict[str, object]:
    return {
        "source_root": source_root,
        "git_commit": git_commit,
        "implementation": implementation,
        "N": n,
        "D": d,
        "seed": 1,
        "case_kind": "main",
        "repeat": repeat,
        "cycles": cycles,
        "tcdm_accessed": 100,
        "tcdm_congested": 10,
        "congestion_ratio": 0.1,
        "status": status,
        "target_status": status,
        "command_status": "pass" if status == "pass" else status,
        "command_returncode": 0 if status == "pass" else None,
        "nonfinite": 0,
        "max_abs": 0.0,
        "footprint_bytes": 1024,
        "allocation_bytes": 512,
        "tcdm_capacity_bytes": 131072,
    }


class AnalyzeScalingTest(unittest.TestCase):
    def test_exact_synthetic_model_recovery(self) -> None:
        points = []
        for n, d in ((1, 1), (1, 2), (2, 1), (3, 4)):
            cycles = 10 + 2 * n + 3 * n * d
            points.append(point("B3", n, d, cycles))
        model = analysis.fit_model(points)
        parameters = model["parameters_cycles"]
        self.assertEqual(parameters["C0"]["numerator"], 10)
        self.assertEqual(parameters["Cs"]["numerator"], 2)
        self.assertEqual(parameters["Cv"]["numerator"], 3)
        self.assertEqual(model["R_squared"]["decimal"], 1.0)
        self.assertTrue(
            all(row["Cstall_cycles"]["numerator"] == 0
                for row in model["residuals"])
        )

    def test_nonzero_residual_and_r_squared(self) -> None:
        points = [
            point("B2-R", 1, 1, 13),
            point("B2-R", 1, 2, 19),
            point("B2-R", 2, 1, 20),
            point("B2-R", 3, 4, 51),
        ]
        model = analysis.fit_model(points)
        self.assertGreater(model["sum_squared_residuals"]["decimal"], 0.0)
        self.assertLess(model["R_squared"]["decimal"], 1.0)
        self.assertTrue(
            any(row["Cstall_cycles"]["numerator"] != 0
                for row in model["residuals"])
        )

    def test_measured_break_even_selects_minimum_d(self) -> None:
        points = [
            point("B2-R", 1, 1, 100),
            point("B3", 1, 1, 110),
            point("B2-R", 1, 8, 120),
            point("B3", 1, 8, 120),
            point("B2-R", 1, 16, 140),
            point("B3", 1, 16, 130),
        ]
        table = analysis.break_even_table(points, (1,), (1, 8, 16))
        self.assertTrue(table["complete"])
        self.assertEqual(table["per_N"][0]["minimum_measured_D"], 8)
        self.assertEqual(table["per_N"][0]["satisfying_measured_D"], [8, 16])
        self.assertFalse(table["model_predictions_mixed_with_measurements"])

    def test_equivalent_duplicate_records_are_deduplicated(self) -> None:
        records = []
        for implementation in analysis.MODEL_IMPLEMENTATIONS:
            for repeat in range(3):
                records.append(raw_record(
                    implementation, 2, 4, repeat, 100 + repeat
                ))
                records.append(raw_record(
                    implementation, 2, 4, repeat, 100 + repeat,
                    source_root="/tmp/work-online-merge-input-b",
                    git_commit="commit-b",
                ))
        prepared = analysis.prepare_points({"records": records})
        self.assertEqual(len(prepared["points"]), 2)
        self.assertEqual(
            len(prepared["equivalent_duplicate_pass_records"]), 6
        )
        self.assertTrue(
            all(item["record_count"] == 2
                for item in prepared["equivalent_duplicate_pass_records"])
        )

    def test_conflicting_duplicate_records_are_rejected(self) -> None:
        records = [
            raw_record("B3", 2, 4, 0, 100),
            raw_record(
                "B3", 2, 4, 0, 101,
                source_root="/tmp/work-online-merge-input-b",
            ),
        ]
        with self.assertRaisesRegex(
            analysis.AnalysisError, "conflicting passing records"
        ):
            analysis.prepare_points({"records": records})

    def test_non_provenance_duplicate_difference_is_rejected(self) -> None:
        left = raw_record("B3", 2, 4, 0, 100)
        right = raw_record(
            "B3", 2, 4, 0, 100,
            source_root="/tmp/work-online-merge-input-b",
            git_commit="commit-b",
        )
        right["max_abs"] = 0.25
        with self.assertRaisesRegex(
            analysis.AnalysisError, "conflicting passing records"
        ):
            analysis.prepare_points({"records": [left, right]})

    def test_nonpass_records_and_failure_entries_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work-online-merge-input"
            root.mkdir()
            (root / "run_manifest.json").write_text(json.dumps({
                "git_commit": "abc",
                "git_dirty": False,
                "cfg_hash": "cfg",
                "validation_result": {"failure_count": 1},
                "tool_versions": {"simulator": {"sha256": "sim"}},
            }))
            timeout = raw_record(
                "B3", 8, 64, 0, 0, status="timeout"
            )
            timeout["cycles"] = None
            (root / "records.json").write_text(json.dumps([timeout]))
            failure = {"status": "timeout", "detail": "preserved"}
            (root / "failures.json").write_text(json.dumps([failure]))
            evidence = analysis.load_evidence([root])
            with self.assertRaisesRegex(
                analysis.AnalysisError, "duplicate result root"
            ):
                analysis.load_evidence([root, root])
            prepared = analysis.prepare_points(evidence)
            self.assertEqual(prepared["status_counts"], {"timeout": 1})
            self.assertEqual(len(prepared["nonpass_records"]), 1)
            self.assertEqual(evidence["failures"][0]["failure"], failure)

    def test_outputs_are_deterministic(self) -> None:
        fit_points = [
            point("B2-R", 1, 1, 15),
            point("B2-R", 1, 2, 18),
            point("B2-R", 2, 1, 20),
            point("B3", 1, 1, 14),
            point("B3", 1, 2, 17),
            point("B3", 2, 1, 19),
        ]
        report = {
            "analysis_provenance": {
                "git": {"commit": "abc", "dirty": False},
                "tool_path": "/tmp/analyze_scaling.py",
                "tool_sha256": "tool-hash",
                "python": {"executable": "python3", "version": "3"},
            },
            "input_evidence": {"roots": []},
            "models": {
                implementation: analysis.fit_model([
                    row for row in fit_points
                    if row["implementation"] == implementation
                ])
                for implementation in analysis.MODEL_IMPLEMENTATIONS
            },
            "break_even": analysis.break_even_table(
                fit_points, (1,), (1, 2)
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            first = parent / "first"
            second = parent / "second"
            analysis.write_outputs(first, report)
            analysis.write_outputs(second, report)
            for name in (
                "analysis.json", "model_residuals.csv", "break_even.csv",
                "artifact_manifest.json",
            ):
                self.assertEqual(
                    (first / name).read_bytes(), (second / name).read_bytes()
                )

    def test_output_directory_must_be_external_and_controlled(self) -> None:
        with self.assertRaisesRegex(
            analysis.AnalysisError, "outside the Git worktree"
        ):
            analysis.validate_output_dir(
                REPO_ROOT / "work-online-merge-analysis-test", REPO_ROOT
            )
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            with self.assertRaisesRegex(
                analysis.AnalysisError, "basename must start"
            ):
                analysis.validate_output_dir(parent / "uncontrolled", REPO_ROOT)
            valid = parent / "work-online-merge-analysis-test"
            self.assertEqual(
                analysis.validate_output_dir(valid, REPO_ROOT), valid.resolve()
            )
            valid.mkdir()
            with self.assertRaisesRegex(
                analysis.AnalysisError, "already exists"
            ):
                analysis.validate_output_dir(valid, REPO_ROOT)


if __name__ == "__main__":
    unittest.main()

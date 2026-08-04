"""Unit tests for independent P0-6 synthesis validation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import analyze_p0_6 as analysis
import experiment_common as common


class AnalyzeP06Test(unittest.TestCase):
    def setUp(self) -> None:
        catalog_path = (
            Path(__file__).resolve().parents[1]
            / "configs/p0_6_synthesis.json"
        )
        self.catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.configs = analysis.validate_catalog(self.catalog)

    def test_catalog_locks_bounded_mapping_effort(self) -> None:
        altered = json.loads(json.dumps(self.catalog))
        altered["mapping"]["fixed_mode_pruning"]["before_techmap"] = False

        with self.assertRaisesRegex(analysis.AnalysisError, "pruning"):
            analysis.validate_catalog(altered)

    @staticmethod
    def stat_payload(
        top: str,
        cell_count: int,
        area: float,
        sequential: float,
    ) -> dict:
        design = {
            "num_cells": cell_count,
            "num_cells_by_type": (
                {"AND2_X1": cell_count} if cell_count else {}
            ),
        }
        if cell_count:
            design["area"] = area
            design["sequential_area"] = sequential
        return {
            "creator": "Yosys fixed version",
            "modules": {"\\" + top: {"num_cells": cell_count}},
            "design": design,
        }

    def build_trial_matrix(
        self, root: Path
    ) -> tuple[list[dict], dict[str, object]]:
        commit = "a" * 40
        catalog_hash = "b" * 64
        liberty_hash = "c" * 64
        manifest = {
            "git_commit": commit,
            "catalog_sha256": catalog_hash,
            "liberty_sha256": liberty_hash,
        }
        dimensions = {
            "C0_NONE": (0, 0.0, 0.0),
            "C1_SCALAR": (2, 3.0, 1.0),
            "C2_FULL": (4, 6.0, 2.0),
        }
        records = []
        for config_id in analysis.CONFIG_IDS:
            config = self.configs[config_id]
            cell_count, area, sequential = dimensions[config_id]
            payload = self.stat_payload(
                str(config["top"]), cell_count, area, sequential
            )
            cell_types = payload["design"]["num_cells_by_type"]
            for trial in range(1, 4):
                trial_dir = root / config_id / f"trial-{trial}"
                trial_dir.mkdir(parents=True)
                files = {
                    "mapped-stat.json": json.dumps(
                        payload, sort_keys=True
                    )
                    + "\n",
                    "mapped-stat.txt": f"{config_id} stat\n",
                    "mapped-netlist.json": json.dumps(
                        {"config_id": config_id}, sort_keys=True
                    )
                    + "\n",
                    "mapped-netlist.v": f"module {config_id}; endmodule\n",
                    "flow.ys": "fixed flow\n",
                    "yosys.log": f"{config_id} trial {trial}\n",
                }
                for name, content in files.items():
                    (trial_dir / name).write_text(content, encoding="utf-8")
                records.append(
                    {
                        "config_id": config_id,
                        "trial": trial,
                        "top": config["top"],
                        "engine_present": config["engine_present"],
                        "fixed_mode": config["fixed_mode"],
                        "git_commit": commit,
                        "git_dirty": False,
                        "catalog_sha256": catalog_hash,
                        "liberty_sha256": liberty_hash,
                        "status": "pass",
                        "failure_reason": None,
                        "paper_eligible": "YES",
                        "physical_ppa_evidence": "NO",
                        "all_cells_in_liberty": True,
                        "exact_reproducible": True,
                        "mapped_cell_count": cell_count,
                        "mapped_cell_area": area,
                        "sequential_cell_area": sequential,
                        "combinational_cell_area": area - sequential,
                        "cell_types_sha256": common.sha256_json(cell_types),
                        "mapped_stat_sha256": common.sha256_file(
                            trial_dir / "mapped-stat.json"
                        ),
                        "mapped_netlist_json_sha256": common.sha256_file(
                            trial_dir / "mapped-netlist.json"
                        ),
                        "mapped_netlist_verilog_sha256": common.sha256_file(
                            trial_dir / "mapped-netlist.v"
                        ),
                        "rendered_flow_sha256": common.sha256_file(
                            trial_dir / "flow.ys"
                        ),
                    }
                )
        return records, manifest

    def test_raw_matrix_is_rehashed_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records, manifest = self.build_trial_matrix(root)

            rows, cell_maps, issues, exact = analysis.audit_records(
                root,
                records,
                manifest,
                self.configs,
                {"AND2_X1"},
            )

            self.assertEqual(len(rows), 9)
            self.assertEqual(issues, [])
            self.assertTrue(all(exact.values()))
            self.assertEqual(cell_maps["C1_SCALAR"], {"AND2_X1": 2})
            self.assertTrue(
                all(row["raw_reverification"] == "PASS" for row in rows)
            )

    def test_raw_difference_breaks_exact_reproducibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records, manifest = self.build_trial_matrix(root)
            changed = root / "C2_FULL/trial-3/mapped-stat.txt"
            changed.write_text("different stat\n", encoding="utf-8")

            _, _, issues, exact = analysis.audit_records(
                root,
                records,
                manifest,
                self.configs,
                {"AND2_X1"},
            )

            self.assertFalse(exact["C2_FULL"])
            self.assertTrue(exact["C0_NONE"])
            self.assertTrue(
                any("C2_FULL" in issue and "exactly" in issue
                    for issue in issues)
            )

    def test_summary_uses_exact_values_without_estimation(self) -> None:
        rows = []
        for config_id, area in (
            ("C0_NONE", 0.0),
            ("C1_SCALAR", 3.0),
            ("C2_FULL", 6.0),
        ):
            rows.extend(
                {
                    "config_id": config_id,
                    "trial": trial,
                    "status": "pass",
                    "paper_eligible": "YES",
                    "mapped_cell_count": int(area),
                    "mapped_cell_area": area,
                    "sequential_cell_area": area / 3.0,
                    "combinational_cell_area": area * 2.0 / 3.0,
                }
                for trial in range(1, 4)
            )

        summaries = analysis.summarize_trials(
            rows, {config_id: True for config_id in analysis.CONFIG_IDS}
        )
        indexed = {row["config_id"]: row for row in summaries}

        self.assertEqual(indexed["C2_FULL"]["delta_area_from_C0"], 6.0)
        self.assertEqual(indexed["C1_SCALAR"]["normalized_area_to_C1"], 1.0)
        self.assertEqual(indexed["C2_FULL"]["normalized_area_to_C1"], 2.0)
        self.assertTrue(
            all(row["paper_eligible"] == "YES" for row in summaries)
        )

    def test_stat_parser_rejects_unknown_or_unscored_cells(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stat.json"
            payload = self.stat_payload("top", 2, 3.0, 1.0)
            path.write_text(json.dumps(payload), encoding="utf-8")

            parsed = analysis.parse_mapped_stat(
                path, "top", {"AND2_X1"}
            )

            self.assertEqual(parsed["mapped_cell_area"], 3.0)
            with self.assertRaisesRegex(analysis.AnalysisError, "non-Liberty"):
                analysis.parse_mapped_stat(path, "top", {"INV_X1"})
            del payload["design"]["area"]
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(analysis.AnalysisError, "omits"):
                analysis.parse_mapped_stat(path, "top", {"AND2_X1"})

    def test_input_manifest_rechecks_current_and_pinned_hashes(self) -> None:
        required_roles = (
            "runner",
            "catalog",
            "flow_template",
            "mapped_wrapper",
            "resource_wrapper",
            "fp32_helpers",
            "exp_approximation",
            "reciprocal_approximation",
            "update_engine",
            "fixed_configuration_reference",
            "liberty",
            "library_readme",
            "yosys_launcher",
            "yosys_executable",
            "slang_plugin",
        )
        pinned_roles = {
            "liberty",
            "library_readme",
            "yosys_launcher",
            "yosys_executable",
            "slang_plugin",
        }
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            root = Path(directory) / "root"
            repo.mkdir()
            root.mkdir()
            entries = []
            for role in required_roles:
                path = repo / f"{role}.txt"
                path.write_text(role + "\n", encoding="utf-8")
                digest = common.sha256_file(path)
                pinned = role in pinned_roles
                entries.append(
                    {
                        "role": role,
                        "path": path.name,
                        "sha256": digest,
                        "expected_sha256": digest if pinned else None,
                        "expected_sha256_matches": True if pinned else None,
                    }
                )
            (root / "input_manifest.json").write_text(
                json.dumps(entries), encoding="utf-8"
            )

            checks, issues = analysis.verify_input_manifest(repo, root)

            self.assertEqual(len(checks), len(required_roles))
            self.assertEqual(issues, [])
            (repo / "runner.txt").write_text("changed\n", encoding="utf-8")
            _, changed_issues = analysis.verify_input_manifest(repo, root)
            self.assertIn("current input differs for runner", changed_issues)


if __name__ == "__main__":
    unittest.main()

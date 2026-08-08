from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_optional_capabilities as optional


class OptionalCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.policy = optional.load_json(
            self.repo_root / "experiments/configs/measurement_policy.json",
            dict,
        )
        self.numerical = optional.load_json(
            self.repo_root
            / "experiments/configs/p0_numerical_boundary_cases.json",
            list,
        )
        self.tails = optional.load_json(
            self.repo_root / "experiments/configs/p0_rvv_tail_cases.json",
            list,
        )

    def test_catalog_coverage_is_exact(self) -> None:
        passed, details = optional.catalog_coverage(
            self.numerical, self.tails
        )
        self.assertTrue(passed)
        self.assertEqual(
            set(details["numerical_patterns"]),
            optional.EXPECTED_NUMERICAL_PATTERNS,
        )
        self.assertEqual(
            set(details["rvv_tail_dimensions"]),
            optional.EXPECTED_RVV_TAILS,
        )

    def test_blockers_do_not_create_substitute_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            p0_4 = Path(temporary) / "p0_4_analysis.json"
            p0_4.write_text(
                json.dumps({"acceptance": {"complete": True}}),
                encoding="utf-8",
            )
            missing = {
                name: {
                    "name": name,
                    "status": "NOT_FOUND",
                    "path": None,
                }
                for name in ("openroad", "sta", "vcd2saif", "yosys")
            }
            packages = {
                name: {
                    "name": name,
                    "status": (
                        "AVAILABLE" if name == "numpy" else "NOT_FOUND"
                    ),
                }
                for name in optional.PYTHON_PACKAGES
            }
            rows = optional.capability_rows(
                self.policy,
                self.numerical,
                self.tails,
                p0_4,
                missing,
                packages,
            )
        by_id = {row["capability_id"]: row for row in rows}
        self.assertEqual(
            by_id["EXP_ONLY"]["status"], "BLOCKED_NOT_IMPLEMENTED"
        )
        self.assertIn("zero-cost", by_id["EXP_ONLY"]["reason"])
        self.assertEqual(by_id["TILE_SCAN"]["status"], "NOT_APPLICABLE")
        self.assertEqual(
            by_id["INPUT_PATTERN"]["status"], "COMPLETE_SUPPORTING"
        )
        self.assertEqual(by_id["OPENROAD"]["status"], "BLOCKED_TOOLCHAIN")
        self.assertEqual(
            by_id["WORKLOAD_POWER_ENERGY"]["status"],
            "BLOCKED_EXTERNAL",
        )
        self.assertTrue(
            all(row["paper_eligible"] == "NO" for row in rows)
        )

    def test_failed_p0_4_acceptance_keeps_patterns_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "analysis.json"
            path.write_text(
                json.dumps(
                    {"acceptance": {"complete": True, "issue_free": False}}
                ),
                encoding="utf-8",
            )
            passed, reason = optional.p0_4_acceptance(path)
        self.assertFalse(passed)
        self.assertEqual(reason, "P0_4_ACCEPTANCE_FAILED:issue_free")

    def test_tool_state_records_not_found_without_execution(self) -> None:
        lookup = mock.Mock(return_value=None)
        state = optional.tool_state("openroad", lookup)
        self.assertEqual(state["status"], "NOT_FOUND")
        self.assertIsNone(state["path"])
        lookup.assert_called_once_with("openroad")


if __name__ == "__main__":
    unittest.main()

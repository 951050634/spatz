"""Unit tests for the P0-6 mapped-synthesis runner."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_p0_6_synthesis as synthesis


class P06SynthesisTest(unittest.TestCase):
    def setUp(self) -> None:
        catalog_path = (
            Path(__file__).resolve().parents[1]
            / "configs/p0_6_synthesis.json"
        )
        self.catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    def test_catalog_fixes_three_production_configurations(self) -> None:
        configurations = synthesis.validate_catalog(self.catalog)

        self.assertEqual(
            tuple(row["config_id"] for row in configurations),
            synthesis.EXPECTED_CONFIG_IDS,
        )
        self.assertEqual(
            [(row["engine_present"], row["fixed_mode"])
             for row in configurations],
            [(False, None), (True, 1), (True, 0)],
        )

        altered = copy.deepcopy(self.catalog)
        altered["configurations"][1]["fixed_mode"] = 0
        with self.assertRaisesRegex(
            synthesis.SynthesisError, "semantics"
        ):
            synthesis.validate_catalog(altered)

    def test_flow_rendering_requires_safe_pinned_path(self) -> None:
        template = "dfflibmap -liberty @LIBERTY@\n"
        path = Path("/fixed/pdk/Nangate45_typ.lib")

        rendered = synthesis.render_flow(template, path)

        self.assertEqual(
            rendered, "dfflibmap -liberty /fixed/pdk/Nangate45_typ.lib\n"
        )
        with self.assertRaisesRegex(synthesis.SynthesisError, "whitespace"):
            synthesis.render_flow(template, Path("/unsafe/pdk with space.lib"))
        with self.assertRaisesRegex(synthesis.SynthesisError, "lacks"):
            synthesis.render_flow("proc\n", path)

    def test_mapped_stat_requires_only_liberty_cells(self) -> None:
        payload = {
            "creator": "Yosys fixed version",
            "modules": {
                "\\online_merge_c1_scalar_mapped_top": {
                    "num_cells": 2
                }
            },
            "design": {
                "num_cells": 2,
                "num_cells_by_type": {"AND2_X1": 2},
                "area": 3.0,
                "sequential_area": 1.0,
            },
        }

        summary = synthesis.validate_stat_payload(
            payload,
            "online_merge_c1_scalar_mapped_top",
            {"AND2_X1"},
        )

        self.assertEqual(summary["mapped_cell_count"], 2)
        self.assertEqual(summary["mapped_cell_area"], 3.0)
        self.assertEqual(summary["combinational_cell_area"], 2.0)
        with self.assertRaisesRegex(
            synthesis.SynthesisError, "non-Liberty"
        ):
            synthesis.validate_stat_payload(
                payload,
                "online_merge_c1_scalar_mapped_top",
                {"INV_X1"},
            )

    def test_zero_cell_c0_does_not_invent_area(self) -> None:
        payload = {
            "creator": "Yosys fixed version",
            "modules": {"\\online_merge_c0_none_mapped_top": {}},
            "design": {"num_cells": 0, "num_cells_by_type": {}},
        }

        summary = synthesis.validate_stat_payload(
            payload, "online_merge_c0_none_mapped_top", {"INV_X1"}
        )

        self.assertEqual(summary["mapped_cell_area"], 0.0)
        self.assertEqual(summary["sequential_cell_area"], 0.0)

    def test_exact_reproducibility_requires_three_identical_processes(
        self,
    ) -> None:
        rows = []
        for config_id in synthesis.EXPECTED_CONFIG_IDS:
            for trial in range(1, 4):
                rows.append(
                    {
                        "config_id": config_id,
                        "trial": trial,
                        "status": "pass",
                        "mapped_cell_count": 7,
                        "mapped_cell_area": 9.0,
                        "sequential_cell_area": 1.0,
                        "combinational_cell_area": 8.0,
                        "cell_types_sha256": "1" * 64,
                        "mapped_stat_sha256": "2" * 64,
                        "mapped_netlist_json_sha256": "3" * 64,
                        "mapped_netlist_verilog_sha256": "4" * 64,
                        "rendered_flow_sha256": "5" * 64,
                    }
                )

        exact = synthesis.reproducibility_by_config(rows, 3)

        self.assertTrue(all(exact.values()))
        one_each = [row for row in rows if row["trial"] == 1]
        self.assertFalse(
            any(synthesis.reproducibility_by_config(one_each, 3).values())
        )
        rows[-1]["mapped_stat_sha256"] = "f" * 64
        altered = synthesis.reproducibility_by_config(rows, 3)
        self.assertFalse(altered["C2_FULL"])
        self.assertTrue(altered["C0_NONE"])

    def test_trial_command_loads_library_and_fixed_top(self) -> None:
        argv = synthesis.command_for_trial(
            Path("/fixed/bin/yosys"),
            Path("/fixed/pdk/typ.lib"),
            (Path("/repo/a.sv"), Path("/repo/b.sv")),
            "online_merge_c2_full_mapped_top",
        )

        self.assertEqual(argv[1:4], ["-Q", "-m", "slang"])
        self.assertIn("read_liberty -lib /fixed/pdk/typ.lib", argv[-1])
        self.assertIn("read_slang --std 1800-2017", argv[-1])
        self.assertIn(
            "hierarchy -check -top online_merge_c2_full_mapped_top",
            argv[-1],
        )
        self.assertTrue(argv[-1].endswith("script flow.ys"))

    def test_output_validation_preserves_partial_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "mapped-stat.json").write_text(
                json.dumps(
                    {
                        "creator": "Yosys fixed version",
                        "modules": {
                            "\\online_merge_c0_none_mapped_top": {}
                        },
                        "design": {
                            "num_cells": 0,
                            "num_cells_by_type": {},
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary, errors, hashes = synthesis.validate_trial_outputs(
                root, "online_merge_c0_none_mapped_top", {"INV_X1"}
            )

            self.assertEqual(summary["mapped_cell_count"], 0)
            self.assertEqual(set(hashes), {"mapped-stat.json"})
            self.assertEqual(len(errors), 3)
            self.assertTrue(all("missing output" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

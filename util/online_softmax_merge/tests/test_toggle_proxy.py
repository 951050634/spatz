#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

import analyze_toggle_proxy as analyzer  # noqa: E402
import run_toggle_proxy as runner  # noqa: E402


class ToggleCaptureTest(unittest.TestCase):
    def test_parse_exact_trace_windows(self) -> None:
        output = """
SNITCH_TRACE_WINDOW index=0 event=start time=10
SNITCH_TRACE_WINDOW index=0 event=end time=12
SNITCH_TRACE_WINDOW index=1 event=start time=20
SNITCH_TRACE_WINDOW index=1 event=end time=24
"""
        windows, errors = runner.parse_trace_windows(output)
        self.assertEqual(errors, [])
        self.assertEqual(
            [window["implementation"] for window in windows], ["B2-R", "B3"]
        )
        self.assertEqual(windows[0]["marker_span_half_cycles"], 2)

    def test_reject_missing_falling_edge(self) -> None:
        windows, errors = runner.parse_trace_windows(
            "SNITCH_TRACE_WINDOW index=0 event=start time=10\n"
        )
        self.assertEqual(windows, [])
        self.assertTrue(errors)

    def test_uint64_word_reconstruction(self) -> None:
        self.assertEqual(runner.uint64_from_words(1, 2), (1 << 32) + 2)


class ToggleAnalyzerTest(unittest.TestCase):
    def test_streaming_vcd_counts_known_bit_toggles(self) -> None:
        vcd = """$version synthetic $end
$timescale 1ps $end
$scope module TOP $end
$scope module i_online_merge_update_engine $end
$var wire 3 ! state_q [2:0] $end
$var wire 4 \" o_new_q [3:0] $end
$var wire 2 # tcdm_req_o [1:0] $end
$var wire 1 % clk_i $end
$upscope $end
$scope module gen_core[0] $end
$var wire 1 & active $end
$upscope $end
$upscope $end
$enddefinitions $end
#10
b000 !
b0000 \"
bx #
0%
0&
#11
b101 !
b0011 \"
b00 #
1%
1&
#12
0%
#20
b101 !
b0011 \"
b00 #
0%
1&
#21
b001 !
b0111 \"
b11 #
1%
0&
#22
0%
"""
        windows = [
            {
                "index": 0,
                "implementation": "B2-R",
                "repeat": 0,
                "start_time": 10,
                "end_time": 12,
                "marker_span_half_cycles": 2,
                "target_cycles": 1,
            },
            {
                "index": 1,
                "implementation": "B3",
                "repeat": 0,
                "start_time": 20,
                "end_time": 22,
                "marker_span_half_cycles": 2,
                "target_cycles": 1,
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.vcd"
            path.write_text(vcd, encoding="utf-8")
            result = analyzer.parse_vcd(path, windows)

        first, second = result["windows"]
        self.assertEqual(first["total_bit_toggles"], 7)
        self.assertEqual(first["unknown_transitions"], 2)
        self.assertEqual(second["total_bit_toggles"], 7)
        hierarchy = {
            row["category"]: row["bit_toggles"]
            for row in first["hierarchy"]
        }
        self.assertEqual(hierarchy["smu_control_fsm"], 2)
        self.assertEqual(hierarchy["smu_vector_datapath"], 2)
        self.assertEqual(hierarchy["core_or_rvv_baseline"], 1)
        self.assertEqual(hierarchy["global_clock_reset"], 2)

    def test_classifier_prioritizes_clock_aliases(self) -> None:
        aliases = [
            "TOP.i_online_merge_update_engine.clk_i",
            "TOP.clk_i",
        ]
        self.assertEqual(
            analyzer.classify_signal(aliases), "global_clock_reset"
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class TraceProxyGatingTest(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (REPO_ROOT / relative).read_text(encoding="utf-8")

    def test_probe_is_a_verilator_top_level_output(self) -> None:
        text = self.read(
            "hw/system/spatz_cluster/src/generated/testharness.sv"
        )
        self.assertIn("output logic cluster_probe_o", text)
        self.assertIn("assign cluster_probe_o = cluster_probe;", text)

    def test_cpp_gate_dumps_active_and_falling_edge(self) -> None:
        text = self.read("hw/ip/snitch_test/src/verilator_lib.cc")
        self.assertIn('std::getenv("SNITCH_TRACE_GATE")', text)
        self.assertIn(
            "trace_gate_active || trace_gate_was_active", text
        )
        self.assertIn("SNITCH_TRACE_WINDOW index=%u event=%s", text)

    def test_target_marks_only_two_representative_windows(self) -> None:
        text = self.read(
            "sw/spatzBenchmarks/online-softmax-merge/main.c"
        )
        self.assertIn("#if ONLINE_MERGE_TRACE_PROXY", text)
        self.assertIn("return repeat == 0u", text)
        self.assertIn(
            "implementation == ONLINE_MERGE_IMPLEMENTATION_B2_R", text
        )
        self.assertIn(
            "implementation == ONLINE_MERGE_IMPLEMENTATION_B3", text
        )

    def test_trace_mode_is_an_explicit_cmake_definition(self) -> None:
        text = self.read("sw/spatzBenchmarks/CMakeLists.txt")
        self.assertIn('set(ONLINE_MERGE_TRACE_PROXY "0" CACHE STRING', text)
        self.assertIn(
            "PRIVATE ONLINE_MERGE_TRACE_PROXY=${ONLINE_MERGE_TRACE_PROXY}",
            text,
        )

    def test_verilator_binary_can_be_kept_outside_worktree(self) -> None:
        text = self.read("hw/system/spatz_cluster/Makefile")
        self.assertIn("VLT_BIN ?= bin/spatz_cluster.vlt", text)
        self.assertIn("${VLT_BIN}: $(VLT_AR)", text)

    def test_makefile_has_explicit_low_perturbation_profile(self) -> None:
        text = self.read("hw/system/spatz_cluster/Makefile")
        self.assertIn("SPATZ_DASM_TRACE ?= 1", text)
        self.assertIn("DEFS += -DSPATZ_DISABLE_DASM", text)

        core = self.read("hw/ip/spatz_cc/src/spatz_cc.sv")
        self.assertIn("`ifndef SPATZ_DISABLE_DASM", core)
        engine = self.read(
            "hw/ip/online_merge/src/online_merge_update_engine.sv"
        )
        self.assertIn('"OM_SIM_CONFIG {', engine)
        self.assertIn('"\\\"fsm_observer_enabled\\\":true}"', engine)


if __name__ == "__main__":
    unittest.main()

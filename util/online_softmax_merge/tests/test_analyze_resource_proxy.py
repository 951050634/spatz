#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import analyze_resource_proxy as analyzer  # noqa: E402


def stat_payload(top: str, post: bool = False) -> dict:
    counts = {"$_AND_": 5} if post else {"$mul": 1, "$adff": 1}
    cells = sum(counts.values())
    module = {
        "num_cells": cells,
        "num_wire_bits": 32,
        "num_memories": 0,
        "num_memory_bits": 0,
        "num_cells_by_type": counts,
    }
    return {
        "creator": "Yosys test",
        "modules": {"\\" + top: module},
        "design": dict(module),
    }


def pre_netlist(top: str) -> dict:
    return {
        "creator": "Yosys test",
        "modules": {
            top: {
                "cells": {
                    "mul": {
                        "type": "$mul",
                        "parameters": {
                            "A_WIDTH": "00001000",
                            "B_WIDTH": "00000100",
                            "Y_WIDTH": "00001100",
                            "A_SIGNED": "0",
                            "B_SIGNED": "1",
                        },
                    },
                    "reg": {
                        "type": "$adff",
                        "parameters": {"WIDTH": "00000111"},
                    },
                }
            }
        },
    }


class AnalyzeResourceProxyTest(unittest.TestCase):
    def test_parameter_decode_and_structural_inspection(self) -> None:
        self.assertEqual(analyzer.decode_parameter("00001100", "x"), 12)
        inspected = analyzer.inspect_pre_netlist(pre_netlist("top"))
        self.assertEqual(inspected["register_bits"], 7)
        self.assertEqual(inspected["register_cells"], 1)
        self.assertEqual(inspected["multipliers"][0]["A_WIDTH"], 8)
        self.assertEqual(inspected["multipliers"][0]["B_SIGNED"], 1)
        with self.assertRaises(analyzer.AnalysisError):
            analyzer.decode_parameter("2'b10", "x")

    def test_stat_validation_checks_top_and_cell_sums(self) -> None:
        summary, modules = analyzer.validate_stat(
            stat_payload("top"), "top", "pre_techmap"
        )
        self.assertEqual(summary["num_cells"], 2)
        self.assertEqual(modules[0]["module"], "top")
        with self.assertRaises(analyzer.AnalysisError):
            analyzer.validate_stat(stat_payload("top"), "other", "pre")
        broken = stat_payload("top")
        broken["design"]["num_cells"] = 99
        with self.assertRaises(analyzer.AnalysisError):
            analyzer.validate_stat(broken, "top", "pre")

    def test_output_directory_is_external_fresh_and_controlled(self) -> None:
        with self.assertRaises(analyzer.AnalysisError):
            analyzer.validate_output_dir(
                REPO_ROOT / "work-online-merge-analysis", REPO_ROOT
            )
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            with self.assertRaises(analyzer.AnalysisError):
                analyzer.validate_output_dir(parent / "bad-name", REPO_ROOT)
            existing = parent / "work-online-merge-existing"
            existing.mkdir()
            with self.assertRaises(analyzer.AnalysisError):
                analyzer.validate_output_dir(existing, REPO_ROOT)

    def make_capture(self, root: Path) -> Path:
        capture = root / "work-online-merge-capture"
        capture.mkdir()
        scopes = ("exp", "reciprocal", "full")
        tops = {scope: f"{scope}_top" for scope in scopes}
        results = []
        artifacts = []
        for scope in scopes:
            scope_dir = capture / scope
            scope_dir.mkdir()
            files = {
                "pre-stat.json": stat_payload(tops[scope]),
                "post-stat.json": stat_payload(tops[scope], post=True),
                "pre-netlist.json": pre_netlist(tops[scope]),
                "post-netlist.json": {"modules": {}},
            }
            for name, payload in files.items():
                path = scope_dir / name
                path.write_text(json.dumps(payload), encoding="utf-8")
                role = name.replace("-", "_").replace(".", "_")
                artifacts.append({
                    "relative_or_external_path": f"{scope}/{name}",
                    "sha256": analyzer.sha256_file(path),
                    "synthesis_scope": scope,
                    "role": role,
                })
            results.append({
                "scope": scope,
                "top": tops[scope],
                "status": "pass",
            })

        input_path = REPO_ROOT / "util/online_softmax_merge/README.md"
        documents = {
            "run_manifest.json": {
                "status": "pass",
                "resource_proxy_evidence": True,
                "git_dirty": False,
                "requested_scopes": list(scopes),
            },
            "scope_results.json": results,
            "failures.json": [],
            "commands.json": [{"status": "pass"}],
            "artifact_manifest.json": artifacts,
            "input_manifest.json": [{
                "role": "readme",
                "relative_or_external_path": (
                    "util/online_softmax_merge/README.md"
                ),
                "sha256": analyzer.sha256_file(input_path),
            }],
        }
        for name, payload in documents.items():
            (capture / name).write_text(json.dumps(payload), encoding="utf-8")
        return capture

    def test_complete_capture_generates_proxy_and_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture = self.make_capture(root)
            with mock.patch.object(
                analyzer,
                "git_context",
                return_value={"commit": "a" * 40, "dirty": False},
            ):
                report = analyzer.analyze(REPO_ROOT, capture)
            self.assertTrue(report["all_acceptance_gates_pass"])
            self.assertTrue(report["resource_proxy_evidence"])
            self.assertFalse(report["physical_ppa_evidence"])
            self.assertEqual(
                report["physical_ppa_blocker"]["status"],
                "blocked_external",
            )
            self.assertEqual(len(report["scopes"]), 3)
            self.assertEqual(len(report["multipliers"]), 3)
            self.assertEqual(
                report["scope_decomposition"]["scalar_fsm_control"]["status"],
                "unsupported",
            )

            output = root / "work-online-merge-analysis"
            hashes = analyzer.write_outputs(output, report)
            self.assertEqual(
                set(hashes),
                {
                    "analysis.json",
                    "resource_summary.csv",
                    "multiplier_widths.csv",
                    "cell_types.csv",
                    "module_resources.csv",
                    "artifact_manifest.json",
                },
            )

    def test_tampered_artifact_fails_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            capture = self.make_capture(Path(directory))
            path = capture / "full" / "pre-stat.json"
            payload = json.loads(path.read_text())
            path.write_text(json.dumps(payload, indent=2))
            with mock.patch.object(
                analyzer,
                "git_context",
                return_value={"commit": "a" * 40, "dirty": False},
            ):
                report = analyzer.analyze(REPO_ROOT, capture)
            self.assertFalse(
                report["acceptance_gates"]["captured_artifact_hashes_match"]
            )
            self.assertFalse(report["all_acceptance_gates_pass"])


if __name__ == "__main__":
    unittest.main()

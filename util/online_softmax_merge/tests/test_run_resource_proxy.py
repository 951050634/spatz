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

SCRIPT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import run_resource_proxy as runner  # noqa: E402


FAKE_YOSYS = r'''#!/usr/bin/env python3
import json
import re
import sys
import time
from pathlib import Path

MODE = __MODE__
args = sys.argv[1:]
if "-V" in args:
    if MODE == "version_fail":
        raise SystemExit(3)
    print("Yosys 99.1 (fake resource-proxy test)")
    raise SystemExit(0)
command = args[args.index("-p") + 1] if "-p" in args else ""
if command == "help read_slang":
    if MODE == "probe_fail":
        raise SystemExit(4)
    print("Slang-based SystemVerilog frontend")
    raise SystemExit(0)
if MODE == "timeout":
    time.sleep(3)
if MODE == "synthesis_fail":
    print("synthetic synthesis failure")
    raise SystemExit(7)
match = re.search(r"hierarchy -check -top ([A-Za-z0-9_$]+)", command)
if match is None:
    raise SystemExit(8)
top = match.group(1)
stat = {
    "creator": "Yosys 99.1 (fake resource-proxy test)",
    "modules": {
        "\\\\" + top: {
            "num_cells": 7,
            "num_cells_by_type": {"$mul": 1},
        }
    },
    "design": {
        "num_cells": 7,
        "num_cells_by_type": {"$mul": 1},
    },
}
Path("pre-stat.json").write_text(json.dumps(stat))
if MODE == "missing_outputs":
    raise SystemExit(0)
Path("post-stat.json").write_text(json.dumps(stat))
Path("pre-stat.txt").write_text("pre statistics\n")
Path("post-stat.txt").write_text("post statistics\n")
Path("pre-netlist.json").write_text("{}\n")
Path("post-netlist.json").write_text("{}\n")
'''


class ResourceProxyRunnerTests(unittest.TestCase):
    def make_fake_yosys(self, directory: Path, mode: str) -> Path:
        path = directory / f"fake-yosys-{mode}"
        path.write_text(FAKE_YOSYS.replace("__MODE__", repr(mode)))
        path.chmod(0o755)
        return path

    def run_fake(
        self,
        mode: str,
        scopes: tuple[str, ...] = ("exp",),
        timeout_seconds: int = 10,
    ) -> tuple[int, Path, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory(
            prefix="work-online-merge-resource-test-", dir="/tmp"
        )
        root = Path(temporary.name)
        yosys = self.make_fake_yosys(root, mode)
        output = root / "work-online-merge-capture"
        arguments = [
            "--repo-root",
            str(REPO_ROOT),
            "--work-dir",
            str(output),
            "--yosys",
            str(yosys),
            "--timeout-seconds",
            str(timeout_seconds),
            "--probe-timeout-seconds",
            "10",
        ]
        for scope in scopes:
            arguments.extend(("--scope", scope))
        return runner.main(arguments), output, temporary

    def test_required_and_default_scopes_are_explicit(self) -> None:
        self.assertEqual(
            runner.REQUIRED_SCOPES, ("exp", "reciprocal", "full")
        )
        self.assertEqual(
            runner.DEFAULT_SCOPES,
            ("exp", "reciprocal", "vector", "full"),
        )
        self.assertFalse(runner.SCOPES["vector"].additive)

    def test_yosys_token_rejects_ambiguous_command_paths(self) -> None:
        self.assertEqual(runner.yosys_token(Path("/tmp/a-b.sv")), "/tmp/a-b.sv")
        for value in ("/tmp/has space.sv", "/tmp/a;bad.sv", 'a"b'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    runner.yosys_token(value)

    def test_output_root_must_be_external_fresh_and_named(self) -> None:
        with self.assertRaises(ValueError):
            runner.validate_output_root(
                REPO_ROOT / "work-online-merge-x", REPO_ROOT
            )
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            with self.assertRaises(ValueError):
                runner.validate_output_root(Path(directory), REPO_ROOT)
        with tempfile.TemporaryDirectory(
            prefix="work-online-merge-test-", dir="/tmp"
        ) as directory:
            root = Path(directory)
            (root / "existing").write_text("preserve me")
            with self.assertRaises(ValueError):
                runner.validate_output_root(root, REPO_ROOT)

    def test_stat_validation_requires_creator_top_and_cell_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pre-stat.json"
            path.write_text(
                json.dumps(
                    {
                        "creator": "Yosys fake",
                        "modules": {"\\top": {}},
                        "design": {"num_cells": 4},
                    }
                )
            )
            payload, errors = runner.validate_stat_payload(path, "top")
            self.assertIsNotNone(payload)
            self.assertEqual(errors, [])
            _, errors = runner.validate_stat_payload(path, "other")
            self.assertIn("missing expected top other", errors[0])

    def test_successful_capture_preserves_inputs_commands_and_outputs(
        self,
    ) -> None:
        returncode, output, temporary = self.run_fake(
            "pass", ("exp", "reciprocal", "full")
        )
        try:
            self.assertEqual(returncode, 0)
            manifest = json.loads(
                (output / "run_manifest.json").read_text()
            )
            results = json.loads(
                (output / "scope_results.json").read_text()
            )
            commands = json.loads((output / "commands.json").read_text())
            inputs = json.loads(
                (output / "input_manifest.json").read_text()
            )
            self.assertEqual(manifest["status"], "pass")
            self.assertFalse(manifest["physical_ppa_evidence"])
            self.assertEqual(
                [result["status"] for result in results],
                ["pass", "pass", "pass"],
            )
            self.assertTrue(all(entry["sha256"] for entry in inputs))
            synthesis_commands = commands[2:]
            self.assertTrue(
                all("generic_resource.ys" in item["command"]
                    for item in synthesis_commands)
            )
            self.assertFalse(any(output.glob("**/invocation.ys")))
            self.assertTrue((output / "full" / "post-netlist.json").is_file())
        finally:
            temporary.cleanup()

    def test_zero_return_with_missing_outputs_is_tool_error(self) -> None:
        returncode, output, temporary = self.run_fake("missing_outputs")
        try:
            self.assertEqual(returncode, 1)
            result = json.loads(
                (output / "scope_results.json").read_text()
            )[0]
            failure = json.loads((output / "failures.json").read_text())[0]
            self.assertEqual(result["status"], "tool_error")
            self.assertIn("missing output", result["failure_reason"])
            self.assertEqual(failure["partial_outputs"], ["pre-stat.json"])
        finally:
            temporary.cleanup()

    def test_nonzero_synthesis_is_preserved(self) -> None:
        returncode, output, temporary = self.run_fake("synthesis_fail")
        try:
            self.assertEqual(returncode, 1)
            result = json.loads(
                (output / "scope_results.json").read_text()
            )[0]
            self.assertEqual(result["status"], "tool_error")
            self.assertIn("status tool_error", result["failure_reason"])
            log = (output / "exp" / "yosys.log").read_text()
            self.assertIn("synthetic synthesis failure", log)
        finally:
            temporary.cleanup()

    def test_synthesis_timeout_remains_timeout(self) -> None:
        returncode, output, temporary = self.run_fake(
            "timeout", timeout_seconds=1
        )
        try:
            self.assertEqual(returncode, 1)
            result = json.loads(
                (output / "scope_results.json").read_text()
            )[0]
            manifest = json.loads(
                (output / "run_manifest.json").read_text()
            )
            self.assertEqual(result["status"], "timeout")
            self.assertEqual(manifest["status"], "timeout")
            self.assertIn(
                "HOST_TIMEOUT", (output / "exp" / "yosys.log").read_text()
            )
        finally:
            temporary.cleanup()

    def test_plugin_probe_failure_becomes_structured_terminal_rows(
        self,
    ) -> None:
        returncode, output, temporary = self.run_fake(
            "probe_fail", ("exp", "full")
        )
        try:
            self.assertEqual(returncode, 1)
            results = json.loads(
                (output / "scope_results.json").read_text()
            )
            self.assertEqual(
                [result["status"] for result in results],
                ["tool_error", "tool_error"],
            )
            self.assertTrue(
                all(result["command_index"] is None for result in results)
            )
        finally:
            temporary.cleanup()

    def test_versioned_wrapper_and_script_hold_required_boundaries(
        self,
    ) -> None:
        wrapper = (
            REPO_ROOT
            / "hw/ip/online_merge/synth/online_merge_resource_wrapper.sv"
        ).read_text()
        script = (
            REPO_ROOT / "hw/ip/online_merge/synth/generic_resource.ys"
        ).read_text()
        self.assertIn("localparam int unsigned AddrWidth = 17", wrapper)
        self.assertIn("localparam int unsigned DataWidth = 64", wrapper)
        self.assertIn("module online_merge_full_resource_top", wrapper)
        self.assertIn("tee -q -o pre-stat.json stat -json", script)
        self.assertIn("write_json pre-netlist.json", script)
        self.assertIn("techmap", script)
        self.assertIn("write_json post-netlist.json", script)
        self.assertNotIn("liberty", "\n".join(
            line for line in script.splitlines()
            if not line.lstrip().startswith("#")
        ))


if __name__ == "__main__":
    unittest.main()

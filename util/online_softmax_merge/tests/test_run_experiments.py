# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import json
import math
import struct
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(MODULE_DIR))

import run_experiments as runner  # noqa: E402

GENERATOR_PATH = (
    REPO_ROOT
    / "sw/spatzBenchmarks/online-softmax-merge/generate_case.py"
)
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "online_merge_generate_case", GENERATOR_PATH
)
assert GENERATOR_SPEC is not None and GENERATOR_SPEC.loader is not None
generator = importlib.util.module_from_spec(GENERATOR_SPEC)
GENERATOR_SPEC.loader.exec_module(generator)


def bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def raw_record(
    implementation: str = "B3",
    repeat: int = 0,
    status: str = "pass",
) -> dict[str, object]:
    return {
        "implementation": implementation,
        "N": 2,
        "D": 4,
        "stride": 16,
        "seed": 7,
        "case_kind": "main",
        "case_class": "main",
        "repeat": repeat,
        "cycles_hi": 1,
        "cycles_lo": 80,
        "tcdm_accessed": 40,
        "tcdm_congested": 10,
        "max_abs_bits": bits(0.25),
        "max_rel_numerator_bits": bits(0.25),
        "max_rel_denominator_bits": bits(2.0),
        "sum_sq_bits": bits(0.5),
        "checked": 8,
        "bit_equal": 4,
        "nonfinite": 0,
        "status": status,
    }


class RunExperimentsTest(unittest.TestCase):
    def test_parse_and_enrich_result(self) -> None:
        raw = raw_record()
        line = runner.RESULT_PREFIX + json.dumps(raw)
        records, failures, errors = runner.parse_target_output(line)
        self.assertEqual(len(records), 1)
        self.assertEqual(failures, [])
        self.assertEqual(errors, [])
        record = runner.enrich_record(
            records[0],
            {
                "git_commit": "abc",
                "cfg_path": "cfg",
                "cfg_hash": "def",
                "tool_version": "tool",
            },
        )
        self.assertEqual(record["cycles"], (1 << 32) + 80)
        self.assertTrue(math.isclose(record["max_rel"], 0.125))
        self.assertEqual(record["bit_equal_ratio"], 0.5)
        self.assertTrue(math.isclose(record["rmse"], 0.25))
        self.assertEqual(
            record["congestion_ratio"], 0.25
        )

    def test_synthetic_failure_preserves_each_implementation(self) -> None:
        case = runner.Case(8, 32, 9, "main", 5)
        records = runner.synthetic_records(case, "timeout")
        self.assertEqual(
            [record["implementation"] for record in records],
            list(runner.EXPECTED_IMPLEMENTATIONS),
        )
        self.assertTrue(
            all(record["status"] == "timeout" for record in records)
        )
        self.assertTrue(all(record["cycles"] is None for record in records))

    def test_summary_uses_median_and_keeps_statuses(self) -> None:
        base = {
            "implementation": "B1",
            "N": 1,
            "D": 1,
            "seed": 1,
            "case_kind": "main",
        }
        records = [
            {**base, "cycles": 9, "status": "pass"},
            {**base, "cycles": 5, "status": "pass"},
            {**base, "cycles": None, "status": "timeout"},
            {**base, "cycles": 7, "status": "pass"},
        ]
        summary = runner.summarize(records)[0]
        self.assertEqual(summary["cycles_min"], 5)
        self.assertEqual(summary["cycles_median"], 7)
        self.assertEqual(summary["cycles_max"], 9)
        self.assertEqual(summary["statuses"], {"pass": 3, "timeout": 1})

    def test_summary_retains_a1_component_medians(self) -> None:
        base = {
            "implementation": "A1",
            "N": 8,
            "D": 32,
            "seed": 1,
            "case_kind": "main",
            "status": "pass",
        }
        records = [
            {
                **base,
                "cycles": 120,
                "smu_scalar_cycles": 80,
                "rvv_vector_cycles": 40,
            },
            {
                **base,
                "cycles": 100,
                "smu_scalar_cycles": 70,
                "rvv_vector_cycles": 30,
            },
            {
                **base,
                "cycles": 110,
                "smu_scalar_cycles": 75,
                "rvv_vector_cycles": 35,
            },
        ]
        summary = runner.summarize(records)[0]
        self.assertEqual(summary["cycles_median"], 110)
        self.assertEqual(summary["smu_scalar_cycles_median"], 75)
        self.assertEqual(summary["rvv_vector_cycles_median"], 35)

    def test_malformed_structured_json_is_reported(self) -> None:
        output = runner.RESULT_PREFIX + '{"implementation":"B1"'
        records, failures, errors = runner.parse_target_output(output)
        self.assertEqual(records, [])
        self.assertEqual(failures, [])
        self.assertEqual(errors[0]["kind"], "malformed_structured_json")

    def test_nonzero_command_cannot_hide_passing_target(self) -> None:
        case = runner.Case(2, 4, 7, "main", 3)
        records = []
        for implementation in runner.EXPECTED_IMPLEMENTATIONS:
            for repeat in range(case.repeats):
                records.append(raw_record(implementation, repeat))
        command = runner.CommandRecord(
            argv=["sim"],
            command="sim",
            start_utc="start",
            end_utc="end",
            returncode=1,
            status="tool_error",
            timeout_seconds=30,
            log_path="log",
        )
        normalized, errors = runner.normalize_target_records(
            records, case, {}, command, []
        )
        self.assertEqual(errors, [])
        self.assertTrue(
            all(row["status"] == "tool_error" for row in normalized)
        )
        self.assertTrue(
            all(row["target_status"] == "pass" for row in normalized)
        )

    def test_timeout_preserves_complete_target_metrics(self) -> None:
        case = runner.Case(2, 4, 7, "main", 3)
        records = []
        for implementation in runner.EXPECTED_IMPLEMENTATIONS:
            for repeat in range(case.repeats):
                records.append(raw_record(implementation, repeat))
        command = runner.CommandRecord(
            argv=["sim"],
            command="sim",
            start_utc="start",
            end_utc="end",
            returncode=0,
            status="timeout",
            timeout_seconds=30,
            log_path="log",
        )
        normalized, errors = runner.normalize_target_records(
            records, case, {}, command, []
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            len(normalized),
            len(runner.EXPECTED_IMPLEMENTATIONS) * case.repeats,
        )
        self.assertTrue(all(row["status"] == "timeout" for row in normalized))
        self.assertTrue(
            all(row["target_status"] == "pass" for row in normalized)
        )
        self.assertTrue(all(row["cycles"] is not None for row in normalized))

    def test_partial_implementation_set_is_tool_error(self) -> None:
        case = runner.Case(2, 4, 7, "main", 3)
        records = [raw_record("B1", repeat) for repeat in range(3)]
        command = runner.CommandRecord(
            argv=["sim"],
            command="sim",
            start_utc="start",
            end_utc="end",
            returncode=0,
            status="pass",
            timeout_seconds=30,
            log_path="log",
        )
        normalized, errors = runner.normalize_target_records(
            records, case, {}, command, []
        )
        self.assertTrue(
            any(
                error["kind"] == "missing_implementation"
                for error in errors
            )
        )
        self.assertTrue(
            all(row["status"] == "tool_error" for row in normalized)
        )
        self.assertEqual(
            {row["implementation"] for row in normalized},
            set(runner.EXPECTED_IMPLEMENTATIONS),
        )

    def test_rvv_disassembly_gate_accepts_required_vla_sequence(self) -> None:
        disassembly = """\
80001000 <online_merge_rvv_update>:
80001000: vsetvli a4, a3, e32, m8, ta, ma
80001004: vle32.v v8, (a0)
80001008: vle32.v v16, (a1)
8000100c: vfmul.vf v8, v8, fa0
80001010: vfmacc.vf v8, fa1, v16
80001014: vse32.v v8, (a2)
80001018: bnez a3, 0x80001000 <online_merge_rvv_update>
8000101c <next_symbol>:
8000101c: ret
"""
        snippet, missing = runner.inspect_rvv_disassembly(disassembly)
        self.assertEqual(missing, [])
        self.assertIsNotNone(snippet)
        assert snippet is not None
        self.assertIn("vsetvli", snippet)
        self.assertNotIn("next_symbol", snippet)

    def test_rvv_disassembly_gate_requires_two_loads_and_backedge(
        self,
    ) -> None:
        one_load = """\
80001000 <online_merge_rvv_update>:
80001000: vsetvli a4, a3, e32, m8, ta, ma
80001004: vle32.v v8, (a0)
80001008: vfmul.vf v8, v8, fa0
8000100c: vfmacc.vf v8, fa1, v16
80001010: vse32.v v8, (a2)
80001014: bnez a3, 0x80001000 <online_merge_rvv_update>
"""
        _, missing = runner.inspect_rvv_disassembly(one_load)
        self.assertIn("2 vle32.v instructions", missing)
        self.assertNotIn("strip-mining back-edge", missing)

        no_backedge = """\
80001000 <online_merge_rvv_update>:
80001000: vsetvli a4, a3, e32, m8, ta, ma
80001004: vle32.v v8, (a0)
80001008: vle32.v v16, (a1)
8000100c: vfmul.vf v8, v8, fa0
80001010: vfmacc.vf v8, fa1, v16
80001014: vse32.v v8, (a2)
80001018: ret
"""
        _, missing = runner.inspect_rvv_disassembly(no_backedge)
        self.assertIn("strip-mining back-edge", missing)
        self.assertNotIn("2 vle32.v instructions", missing)

    def test_rvv_disassembly_gate_rejects_unknown_or_missing_sequence(
        self,
    ) -> None:
        disassembly = """\
80001000 <online_merge_rvv_update>:
80001000: vsetvli a4, a3, e32, m8, ta, ma
80001004: <unknown>
"""
        snippet, missing = runner.inspect_rvv_disassembly(disassembly)
        self.assertIsNotNone(snippet)
        self.assertIn("vle32.v", missing)
        self.assertIn("decoded RVV instructions", missing)

        snippet, missing = runner.inspect_rvv_disassembly(
            "80001000 <different_symbol>:\n80001000: ret\n"
        )
        self.assertIsNone(snippet)
        self.assertEqual(
            missing,
            [f"missing symbol {runner.RVV_UPDATE_SYMBOL}"],
        )

    def test_missing_simulator_version_detection_does_not_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            versions = runner.detect_tool_versions(
                root,
                root / "missing-simulator",
                root / "missing-build",
                "true",
            )
        self.assertEqual(versions["simulator"]["status"], "missing")
        self.assertNotIn("sha256", versions["simulator"])

    def test_external_path_is_preserved(self) -> None:
        root = Path("/repo").resolve()
        external = Path("/external/cfg.hjson").resolve()
        self.assertEqual(runner.display_path(external, root), str(external))

    def test_capacity_precheck_uses_allocator_rounded_bytes(self) -> None:
        fitting = runner.Case(1, 5700, repeats=3)
        skipped = runner.Case(1, 5726, repeats=3)
        self.assertTrue(runner.capacity_fits(fitting))
        self.assertFalse(runner.capacity_fits(skipped))
        footprint, allocation = runner.layout_bytes(skipped.n, skipped.d)
        self.assertLessEqual(footprint, runner.TCDM_LIMIT_BYTES)
        self.assertGreater(allocation, runner.TCDM_LIMIT_BYTES)

    def test_capacity_skip_has_explicit_case_class(self) -> None:
        records = runner.synthetic_records(
            runner.Case(1, 5726, repeats=3), "capacity_skip"
        )
        self.assertTrue(
            all(record["case_class"] == "capacity" for record in records)
        )

    def test_global_timeout_and_job_options_must_be_positive(self) -> None:
        args = Namespace(
            timeout_seconds=1,
            large_timeout_seconds=1,
            build_timeout_seconds=1,
            jobs=1,
        )
        runner.validate_run_options(args)
        for attribute in (
            "timeout_seconds",
            "large_timeout_seconds",
            "build_timeout_seconds",
            "jobs",
        ):
            invalid = Namespace(**vars(args))
            setattr(invalid, attribute, 0)
            with self.assertRaisesRegex(ValueError, "must be positive"):
                runner.validate_run_options(invalid)

    def test_cmake_defines_preserve_order_and_values(self) -> None:
        definitions = runner.parse_cmake_defines(
            ["BUILD_TESTS=ON", "URL=https://example.test/a=b"]
        )
        self.assertEqual(
            definitions,
            [
                ("BUILD_TESTS", "ON"),
                ("URL", "https://example.test/a=b"),
            ],
        )
        self.assertEqual(
            runner.cmake_define_arguments(definitions),
            ["-DBUILD_TESTS=ON", "-DURL=https://example.test/a=b"],
        )
        self.assertEqual(
            runner.cmake_define_manifest(definitions),
            [
                {
                    "key": "BUILD_TESTS",
                    "value": "ON",
                    "argument": "-DBUILD_TESTS=ON",
                },
                {
                    "key": "URL",
                    "value": "https://example.test/a=b",
                    "argument": "-DURL=https://example.test/a=b",
                },
            ],
        )

    def test_cmake_defines_reject_invalid_or_ambiguous_keys(self) -> None:
        invalid = (
            "KEY",
            "=value",
            "1KEY=value",
            "KEY:STRING=value",
            "-DKEY=value",
            "KEY=",
            "KEY=line\nbreak",
            "KEY=tab\tbreak",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                runner.parse_cmake_defines([value])

        with self.assertRaisesRegex(ValueError, "duplicate.*LLVM_PATH"):
            runner.parse_cmake_defines(
                ["LLVM_PATH=/first", "LLVM_PATH=/second"]
            )

    def test_cmake_defines_reject_per_case_settings(self) -> None:
        for key in runner.RESERVED_CMAKE_DEFINE_KEYS:
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, "conflicts with per-case settings"
            ):
                runner.parse_cmake_defines([f"{key}=override"])

    def test_configure_argv_appends_non_case_definitions(self) -> None:
        case = runner.Case(8, 32, 7, "main", 3)
        definitions = runner.parse_cmake_defines(
            ["BUILD_TESTS=ON", "ELEN=64"]
        )
        argv = runner.make_configure_argv(
            "cmake",
            Path("/source"),
            Path("/build"),
            case,
            definitions,
        )
        self.assertEqual(
            argv[-7:],
            [
                "-DONLINE_MERGE_N=8",
                "-DONLINE_MERGE_D=32",
                "-DONLINE_MERGE_SEED=7",
                "-DONLINE_MERGE_CASE_KIND=main",
                "-DONLINE_MERGE_REPEATS=3",
                "-DBUILD_TESTS=ON",
                "-DELEN=64",
            ],
        )

    def test_parse_args_accepts_repeated_cmake_defines(self) -> None:
        args = runner.parse_args(
            [
                "--cmake-define",
                "BUILD_TESTS=ON",
                "--cmake-define",
                "ELEN=64",
            ]
        )
        self.assertEqual(args.cmake_define, ["BUILD_TESTS=ON", "ELEN=64"])

    def test_case_mapping_errors_are_clear_value_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required field.*D"):
            runner.case_from_mapping({"N": 1}, 3)
        with self.assertRaisesRegex(ValueError, "invalid field value"):
            runner.case_from_mapping({"N": [], "D": 1}, 3)

    def test_case_validation_rejects_kind_repeat_and_timeout(self) -> None:
        with self.assertRaises(ValueError):
            runner.validate_case(runner.Case(1, 1, case_kind="bad"))
        with self.assertRaises(ValueError):
            runner.validate_case(runner.Case(1, 1, repeats=2))
        with self.assertRaises(ValueError):
            runner.validate_case(runner.Case(1, 1, timeout_seconds=0))

    def test_work_dir_must_be_external_and_named(self) -> None:
        repo = Path("/tmp/repo").resolve()
        with self.assertRaises(ValueError):
            runner.validate_work_dir(repo / "work-online-merge-run", repo)
        with self.assertRaises(ValueError):
            runner.validate_work_dir(Path("/tmp/results"), repo)
        runner.validate_work_dir(Path("/tmp/work-online-merge-run"), repo)


class GenerateCaseTest(unittest.TestCase):
    def test_generator_is_deterministic_and_main_domain_is_bounded(
        self,
    ) -> None:
        first = generator.generate_header(4, 7, 123, "main", 5)
        second = generator.generate_header(4, 7, 123, "main", 5)
        different = generator.generate_header(4, 7, 124, "main", 5)
        self.assertEqual(first, second)
        self.assertNotEqual(first, different)

        m_old, l_old, o_old, m_tile, l_tile, o_tile = generator.make_inputs(
            32, 17, 123, "main"
        )
        self.assertTrue(all(-4.0 <= value <= 4.0 for value in m_old + m_tile))
        self.assertTrue(all(-1.0 <= value <= 1.0 for value in o_old + o_tile))
        for old, tile in zip(l_old, l_tile, strict=True):
            self.assertFalse(old == 0.0 and tile == 0.0)
            for value in (old, tile):
                self.assertTrue(value == 0.0 or 2.0**-8 <= value <= 8.0)

    def test_capacity_header_is_small_and_does_not_expand_arrays(self) -> None:
        header = generator.generate_header(1000, 1000, 1, "main", 3)
        self.assertIn("ONLINE_MERGE_CASE_CAPACITY_SKIP 1u", header)
        self.assertLess(len(header), 4096)
        self.assertIn("online_merge_o_old_bits[1]", header)

    def test_different_dimensions_change_generated_header(self) -> None:
        one = generator.generate_header(1, 1, 1, "main", 3)
        two = generator.generate_header(2, 7, 1, "main", 3)
        self.assertIn("ONLINE_MERGE_CASE_N 1u", one)
        self.assertIn("ONLINE_MERGE_CASE_D 7u", two)
        self.assertNotEqual(one, two)


if __name__ == "__main__":
    unittest.main()

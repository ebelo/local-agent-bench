import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_paper_matrix.py"
SPEC = importlib.util.spec_from_file_location("run_paper_matrix", SCRIPT)
run_paper_matrix = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_paper_matrix)


class RunPaperMatrixTest(unittest.TestCase):
    def test_native_latency_gate_uses_platform_native_command(self) -> None:
        manifest = {
            "dataset": "clean-room-test",
            "latency_gate": {
                "benchmark": "latency-gate",
                "native_benchmark": "platform-native-latency-gate",
                "threshold_seconds": 20,
                "runtime_timeout": 45,
                "task_timeout": 20,
                "min_score": 0.9,
                "repeats": 3,
                "min_passes": 2,
            },
            "benchmarks": [
                {"id": "latency-gate", "path": "benchmarks/latency_gate.json"},
                {"id": "platform-native-latency-gate", "path": "benchmarks/platform_native_latency_gate.json"},
            ],
        }
        job = {
            "phase": "platform-native-basic",
            "command": "run-platform-native",
            "runtime": "pi-native",
            "model": "ornith:9b",
            "model_paper_id": "ornith-9b",
            "latency_threshold_seconds": 120,
        }

        gate = run_paper_matrix._latency_gate_job(manifest, job, Path("/tmp/results"), None)
        cmd = run_paper_matrix._command_for_job(gate, manifest, skip_preflight=False)

        self.assertEqual(gate["command"], "run-platform-native")
        self.assertEqual(gate["benchmark_id"], "platform-native-latency-gate")
        self.assertEqual(gate["latency_threshold"], 120.0)
        self.assertGreaterEqual(gate["runtime_timeout"], 135)
        self.assertIn("--deterministic-score-only", cmd)

    def test_phase_skip_preflight_is_added_to_command(self) -> None:
        manifest = {"judge_model": "ollama/judge", "judge_timeout": 30}
        job = {
            "command": "run-platform-native",
            "runtime": "pi-native",
            "model": "ornith:9b",
            "benchmark": "benchmarks/platform_native.json",
            "output": Path("/tmp/out.json"),
            "runtime_timeout": 180,
            "skip_preflight": True,
            "deterministic_platform_score": True,
        }

        cmd = run_paper_matrix._command_for_job(job, manifest, skip_preflight=False)

        self.assertIn("--skip-preflight", cmd)

    def test_full_native_job_uses_judge_by_default(self) -> None:
        manifest = {
            "dataset": "clean-room-test",
            "judge_model": "ollama/judge",
            "judge_timeout": 30,
            "models": [{"id": "ornith:9b", "paper_id": "ornith-9b"}],
            "benchmarks": [{"id": "platform-native-reality", "path": "benchmarks/platform_native_reality.json"}],
        }
        phases = [
            {
                "id": "platform-native-reality",
                "command": "run-platform-native",
                "runtimes": ["pi-native"],
                "models": ["ornith:9b"],
                "benchmarks": ["platform-native-reality"],
                "runs": 1,
                "runtime_timeout": 240,
            }
        ]

        job = run_paper_matrix._expand_jobs(manifest, phases, Path("/tmp/results"))[0]
        cmd = run_paper_matrix._command_for_job(job, manifest, skip_preflight=False)

        self.assertIn("--judge-model", cmd)
        self.assertIn("ollama/judge", cmd)
        self.assertNotIn("--deterministic-score-only", cmd)

    def test_latency_gate_dry_run_expands_repeats(self) -> None:
        manifest = {
            "dataset": "clean-room-test",
            "latency_gate": {
                "benchmark": "latency-gate",
                "threshold_seconds": 20,
                "repeats": 3,
            },
            "benchmarks": [{"id": "latency-gate", "path": "benchmarks/latency_gate.json"}],
        }
        jobs = [
            {
                "phase": "controlled-runtime-effect",
                "command": "run",
                "runtime": "hermes-react",
                "model": "qwen2.5-coder:7b",
                "model_paper_id": "qwen25-coder-7b",
                "latency_threshold_seconds": None,
            }
        ]

        gates = run_paper_matrix._latency_gate_jobs_for_jobs(manifest, jobs, Path("/tmp/results"), None)

        self.assertEqual([gate["gate_attempt"] for gate in gates], [1, 2, 3])
        self.assertTrue(str(gates[1]["output"]).endswith("run02.json"))

    def test_combined_latency_gate_requires_min_passes(self) -> None:
        attempts = [
            {"phase": "p", "runtime": "r", "model": "m", "passed": True, "latency_s": 5.0, "reason": "ok"},
            {"phase": "p", "runtime": "r", "model": "m", "passed": False, "latency_s": 6.0, "reason": "bad"},
            {"phase": "p", "runtime": "r", "model": "m", "passed": True, "latency_s": 7.0, "reason": "ok"},
        ]

        verdict = run_paper_matrix._combined_latency_gate_verdict(attempts, min_passes=2)

        self.assertTrue(verdict["passed"])
        self.assertEqual(verdict["passed_attempts"], 2)
        self.assertEqual(verdict["latency_s"], 6.0)

    def test_native_futility_gate_skips_after_zero_score_runs(self) -> None:
        manifest = {"futility_gate": {"enabled": True, "min_runs": 3, "max_total_score": 0.0}}
        job = {
            "command": "run-platform-native",
            "phase": "platform-native-basic",
            "runtime": "pi-native",
            "model": "ornith:9b",
            "benchmark_id": "platform-native",
        }
        stats = {"completed": 3, "max_total_score": 0.0, "scores": [0.0, 0.0, 0.0]}

        verdict = run_paper_matrix._futility_verdict(manifest, job, stats)

        self.assertTrue(verdict["skip"])
        self.assertIn("3 completed runs", verdict["reason"])

    def test_force_removes_stale_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text('{"old": true}\n', encoding="utf-8")

            run_paper_matrix._remove_forced_output(path, force=True)

            self.assertFalse(path.exists())

    def test_non_force_keeps_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text('{"old": true}\n', encoding="utf-8")

            run_paper_matrix._remove_forced_output(path, force=False)

            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()

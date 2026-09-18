from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness.py"
TASK = ROOT / "examples" / "end_to_end"
sys.path.insert(0, str(ROOT / "scripts"))

import bench_run  # noqa: E402

TRIVIAL_ENTRY = """\
import sys
print("trivial task ran")
raise SystemExit({exit_code})
"""

SLEEP_ENTRY = """\
import time
time.sleep(30)
"""


class BenchmarkTaskTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="bench-run-")
        self.dir = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_task(self, *, entry: str, body: str, arguments: list[str], timeout_seconds: int = 30) -> Path:
        task_dir = self.dir / f"task-{entry.replace('.py', '')}"
        task_dir.mkdir()
        (task_dir / entry).write_text(body, encoding="utf-8")
        (task_dir / "bench_task.json").write_text(
            json.dumps({
                "schema_version": "1.0",
                "task_id": "tiny-task",
                "entry": entry,
                "arguments": arguments,
                "timeout_seconds": timeout_seconds,
            }),
            encoding="utf-8",
        )
        return task_dir

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_committed_task_declaration_loads(self) -> None:
        task = bench_run.load_task(TASK)
        self.assertEqual(task["task_id"], "end-to-end-depot")
        self.assertIn("{workdir}", task["arguments"])
        self.assertTrue(Path(task["entry_path"]).is_file())

    def test_missing_declaration_or_entry_is_refused(self) -> None:
        empty = self.dir / "no-declaration"
        empty.mkdir()
        with self.assertRaises(ValueError):
            bench_run.load_task(empty)
        task_dir = self.write_task(entry="tiny.py", body=TRIVIAL_ENTRY.format(exit_code=0), arguments=["--out", "{workdir}"])
        (task_dir / "tiny.py").unlink()
        with self.assertRaises(ValueError):
            bench_run.load_task(task_dir)

    def test_run_records_engineering_facts_for_the_committed_task(self) -> None:
        output = self.dir / "report.json"
        report = bench_run.run_bench(TASK, harness_root=ROOT, output_path=output)
        self.assertEqual(report["exit_code"], 0, report["stderr_tail"])
        self.assertFalse(report["timed_out"])
        self.assertGreater(report["wall_seconds"], 0.0)
        self.assertEqual(report["harness"]["revision"], bench_run.harness_revision(ROOT))
        self.assertTrue(report["project"]["present"])
        self.assertGreater(report["project"]["receipts"]["count"], 0)
        self.assertIn("not a capability benchmark", report["scope"])
        self.assertTrue(output.is_file())
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["label"], "end-to-end-depot")

    def test_repeated_runs_only_differ_in_timing(self) -> None:
        first = bench_run.run_bench(TASK, harness_root=ROOT, output_path=self.dir / "a.json")
        second = bench_run.run_bench(TASK, harness_root=ROOT, output_path=self.dir / "b.json")
        document = bench_run.compare_bench(self.dir / "a.json", self.dir / "b.json")
        self.assertTrue(document["task_equal"])
        self.assertEqual(first["exit_code"], second["exit_code"])
        self.assertEqual(document["gates_changed"], {})
        self.assertEqual(document["deltas"]["exit_code"]["a"], document["deltas"]["exit_code"]["b"])
        self.assertIn("no capability claim", document["scope"])

    def test_a_failing_entry_is_a_recorded_fact(self) -> None:
        task_dir = self.write_task(entry="fails.py", body=TRIVIAL_ENTRY.format(exit_code=3), arguments=["--out", "{workdir}"])
        report = bench_run.run_bench(task_dir, harness_root=ROOT, output_path=self.dir / "fails.json")
        self.assertEqual(report["exit_code"], 3)
        self.assertFalse(report["timed_out"])
        self.assertFalse(report["project"]["present"])

    def test_a_timeout_is_a_recorded_fact(self) -> None:
        task_dir = self.write_task(
            entry="sleepy.py", body=SLEEP_ENTRY, arguments=["--out", "{workdir}"], timeout_seconds=1,
        )
        report = bench_run.run_bench(task_dir, harness_root=ROOT, output_path=self.dir / "timeout.json")
        self.assertTrue(report["timed_out"])
        self.assertIsNone(report["exit_code"])
        self.assertIn("timed out", report["stderr_tail"])

    def test_harness_ref_extracts_a_checkout_with_identity(self) -> None:
        checkout = bench_run.extract_harness_ref(ROOT, "HEAD", self.dir / "ref")
        self.assertTrue((checkout / "scripts" / "harness.py").is_file())
        self.assertTrue((checkout / "examples" / "end_to_end" / "run_demo.py").is_file())
        revision = bench_run.resolve_ref(ROOT, "HEAD")
        self.assertEqual(len(revision), 40)
        with self.assertRaises(ValueError):
            bench_run.resolve_ref(ROOT, "no-such-revision")

    def test_harness_ref_requires_a_task_inside_the_repository(self) -> None:
        task_dir = self.write_task(entry="tiny.py", body=TRIVIAL_ENTRY.format(exit_code=0), arguments=["--out", "{workdir}"])
        with self.assertRaises(ValueError) as caught:
            bench_run.run_bench(
                task_dir, harness_ref="HEAD", output_path=self.dir / "never.json",
            )
        self.assertIn("inside the harness repository", str(caught.exception))

    def test_cli_run_and_compare(self) -> None:
        first = self.run_cli(
            "bench", "run", "--task", str(TASK), "--harness-root", str(ROOT),
            "--output", str(self.dir / "cli-a.json"), "--label", "first", "--json",
        )
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(json.loads(first.stdout)["label"], "first")
        second = self.run_cli(
            "bench", "run", "--task", str(TASK), "--harness-root", str(ROOT),
            "--output", str(self.dir / "cli-b.json"), "--label", "second", "--json",
        )
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        compared = self.run_cli("bench", "compare", str(self.dir / "cli-a.json"), str(self.dir / "cli-b.json"), "--json")
        self.assertEqual(compared.returncode, 0, compared.stdout + compared.stderr)
        document = json.loads(compared.stdout)
        self.assertTrue(document["task_equal"])
        self.assertEqual(document["gates_changed"], {})
        # A refused invocation is a CLI error (exit 2), not a failed verdict.
        refused = self.run_cli("bench", "run", "--task", str(self.dir / "missing"), "--output", str(self.dir / "x.json"))
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)


if __name__ == "__main__":
    unittest.main()
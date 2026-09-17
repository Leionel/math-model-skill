"""Agent contract layer tests.

The point of ``harness agents check`` is not that seven YAML files exist; it is
that a contract cannot claim a tool, artifact role, schema, reference or Gate
that the Harness does not actually have. These tests therefore assert both the
passing shipped set and the specific rejections.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from agent_contracts.check_contracts import check_all  # noqa: E402
from agent_contracts.contract import (  # noqa: E402
    FORBIDDEN_ACTION_FABRICATION,
    FORBIDDEN_ACTION_FLOOR,
    SAFE_INVARIANTS,
    TRUTH_MUTATING_LEAVES,
    cli_command_surface,
    load_contract,
    stale_truth_mutating_names,
    truth_mutating_commands,
)


def _copy_contracts(temp: Path) -> Path:
    target = temp / "agents"
    shutil.copytree(ROOT / "agents", target)
    return target


def _patch(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"probe expects {old!r} in {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


class ShippedContractSetTest(unittest.TestCase):
    def test_all_shipped_contracts_pass_the_check(self) -> None:
        result = check_all()
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["ground_truth"]["contracts"], 7)

    def test_cli_reports_pass_and_emits_machine_output(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "harness.py"), "agents", "check", "--json"],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("recomputed fact", payload["boundary"])

    def test_every_stage_is_owned_exactly_once(self) -> None:
        result = check_all()
        owners: dict[str, list[str]] = {}
        for row in result["agents"]:
            if row["name"] == "orchestrator":
                continue
            for stage in row["stage_authority"]:
                owners.setdefault(stage, []).append(row["name"])
        self.assertEqual(sorted(owners), ["F1", "M1", "P1", "P2", "S0", "S1", "W1", "W2"])
        self.assertTrue(all(len(names) == 1 for names in owners.values()), owners)

    def test_prohibition_floor_covers_every_safety_invariant(self) -> None:
        self.assertEqual(
            set(FORBIDDEN_ACTION_FLOOR),
            set(SAFE_INVARIANTS),
            "a new safety invariant needs a matching agent prohibition",
        )
        self.assertEqual(len(FORBIDDEN_ACTION_FABRICATION), 3)


class ContractRejectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="agent-contracts-")
        self.contracts = _copy_contracts(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _errors(self) -> list[str]:
        return check_all(self.contracts)["errors"]

    def _expect(self, fragment: str) -> None:
        errors = self._errors()
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_invented_tool_is_rejected(self) -> None:
        _patch(self.contracts / "modeler" / "agent.yaml", "  - model\n", "  - model\n  - summon_gpu_cluster\n")
        self._expect("allowed tool is not a harness command: summon_gpu_cluster")

    def test_invented_mcp_tool_is_rejected(self) -> None:
        nl = chr(10)
        _patch(
            self.contracts / "reviewer" / "agent.yaml",
            f"  - review{nl}",
            f"  - review{nl}  - mcp:fabricate_result{nl}",
        )
        self._expect("allowed tool is not a harness command: mcp:fabricate_result")

    def test_control_plane_write_is_rejected(self) -> None:
        _patch(
            self.contracts / "modeler" / "agent.yaml",
            "  write: [model_contract]",
            "  write: [model_contract, run_manifest]",
        )
        self._expect("may not write control-plane role run_manifest")

    def test_dropping_a_forge_prohibition_is_rejected(self) -> None:
        _patch(self.contracts / "writer" / "agent.yaml", "  - forge_gate_status\n", "")
        self._expect("missing mandatory prohibition: forge_gate_status")

    def test_dropping_an_invariant_prohibition_is_rejected(self) -> None:
        _patch(
            self.contracts / "experimenter" / "agent.yaml",
            "  - promote_unfrozen_result\n",
            "",
        )
        self._expect("missing mandatory prohibition: promote_unfrozen_result")

    def test_orchestrator_cannot_hold_a_truth_mutating_command(self) -> None:
        _patch(self.contracts / "orchestrator" / "agent.yaml", "  - status\n", "  - status\n  - freeze\n")
        self._expect("orchestrator may not hold a truth-mutating command: freeze")

    def test_reviewer_cannot_write_the_author_plane(self) -> None:
        _patch(
            self.contracts / "reviewer" / "agent.yaml",
            "  write: [review_report]",
            "  write: [review_report, paper]",
        )
        self._expect("reviewer may not write author-plane role paper")

    def test_reviewer_cannot_execute_anything_but_the_review_plane(self) -> None:
        _patch(self.contracts / "reviewer" / "agent.yaml", "  - status\n", "  - status\n  - execute\n")
        self._expect("reviewer may not hold any truth-mutating command except the review plane")

    def test_no_agent_may_make_the_human_no_ai_declaration(self) -> None:
        _patch(
            self.contracts / "compliance" / "agent.yaml",
            "  - ai status\n",
            "  - ai status\n  - ai confirm-none\n",
        )
        self._expect("ai confirm-none is a human-only declaration")

    def test_duplicate_stage_ownership_is_rejected(self) -> None:
        _patch(self.contracts / "writer" / "agent.yaml", "stages: [W1]", "stages: [W1, W2]")
        self._expect("stage W2 has 2 owners")

    def test_duplicate_artifact_writer_is_rejected(self) -> None:
        _patch(
            self.contracts / "writer" / "agent.yaml",
            "  write: [paper_plan,",
            "  write: [paper_plan, validation_report,",
        )
        self._expect("validation_report has 2 writers")

    def test_uncovered_stage_is_rejected(self) -> None:
        _patch(self.contracts / "modeler" / "agent.yaml", "stages: [M1]", "stages: [P1]")
        self._expect("stages with no owning agent: ['M1']")

    def test_nonexistent_schema_reference_is_rejected(self) -> None:
        _patch(
            self.contracts / "writer" / "agent.yaml",
            "    schema: paper_plan.schema.json",
            "    schema: paper_dream.schema.json",
        )
        self._expect("output schema does not exist: paper_dream.schema.json")

    def test_output_that_persists_without_a_schema_is_rejected(self) -> None:
        _patch(
            self.contracts / "writer" / "agent.yaml",
            "  - name: paper_plan\n    schema: paper_plan.schema.json\n    persists: true",
            "  - name: paper_plan\n    schema: null\n    persists: true",
        )
        self._expect("persists but names no schema")

    def test_nonexistent_reference_file_is_rejected(self) -> None:
        _patch(
            self.contracts / "reviewer" / "agent.yaml",
            "  - references/review/judge_lens.md",
            "  - references/review/not_a_real_lens.md",
        )
        self._expect("reference file does not exist: references/review/not_a_real_lens.md")

    def test_unknown_stage_is_rejected(self) -> None:
        _patch(self.contracts / "modeler" / "agent.yaml", "stages: [M1]", "stages: [M1, Z9]")
        self._expect("is not one of")

    def test_a_mutation_requiring_a_new_gate_name_is_rejected(self) -> None:
        """S0 and F1 are boundary stages; a made-up gate is still refused."""

        _patch(self.contracts / "compliance" / "agent.yaml", "stages: [S1, F1]", "stages: [S1, F2]")
        self._expect("is not one of")


class GroundTruthSurfaceTest(unittest.TestCase):
    def test_mutating_sentinel_matches_the_live_cli(self) -> None:
        surface = cli_command_surface()
        self.assertEqual(stale_truth_mutating_names(surface), set())
        self.assertIn("freeze", truth_mutating_commands(surface))
        self.assertIn("submit", truth_mutating_commands(surface))
        self.assertNotIn("status", truth_mutating_commands(surface))

    def test_command_group_granting_is_monotone(self) -> None:
        """Naming the `ai` group must count as naming `ai record`."""

        surface = cli_command_surface()
        self.assertIn("ai confirm-none", TRUTH_MUTATING_LEAVES)
        self.assertIn("ai", truth_mutating_commands(surface))

    def test_orchestrator_shipped_tools_are_all_non_mutating(self) -> None:
        mutating = truth_mutating_commands(cli_command_surface())
        orchestrator = next(row for row in check_all()["agents"] if row["name"] == "orchestrator")
        declared = {str(item) for item in load_contract(ROOT / "agents" / "orchestrator" / "agent.yaml")["allowed_tools"]}
        self.assertEqual(orchestrator["writes"], [])
        self.assertEqual(declared & mutating, set())


if __name__ == "__main__":
    unittest.main()

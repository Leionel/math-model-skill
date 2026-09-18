from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts" / "mcp_server.py"
CLI = ROOT / "scripts" / "harness.py"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import mcp_server  # noqa: E402
from agent_contracts import policy  # noqa: E402


class PolicyCompilationTest(unittest.TestCase):
    def test_every_committed_role_compiles(self) -> None:
        policies = policy.compile_all()
        self.assertEqual(
            sorted(policies),
            ["compliance", "experimenter", "modeler", "orchestrator", "problem_analyst", "reviewer", "writer"],
        )
        for role, row in policies.items():
            self.assertTrue(row["cli_commands"], role)
            self.assertTrue(row["mcp_tools"], role)

    def test_declared_scope_survives_compilation(self) -> None:
        # Nothing a contract declares may disappear silently: the policy's CLI
        # paths plus its declared MCP names must equal the declared tool list.
        for role, row in policy.compile_all().items():
            declared = set(row["cli_commands"]) | {f"mcp:{name}" for name in row["declared_mcp_tools"]}
            self.assertEqual(len(declared), len(row["cli_commands"]) + len(row["declared_mcp_tools"]), role)
            self.assertTrue(declared, role)

    def test_orchestrator_reaches_the_recomputed_state_tools(self) -> None:
        row = policy.compile_policy("orchestrator")
        self.assertEqual(row["declared_mcp_tools"], ["check_gate", "get_run_state"])
        self.assertIn("research_status", row["mcp_tools"])
        self.assertEqual(row["mutating_tools"], [])

    def test_only_the_reviewer_holds_the_mutating_tool(self) -> None:
        policies = policy.compile_all()
        self.assertEqual(policies["reviewer"]["mutating_tools"], ["request_review"])
        for role, row in policies.items():
            if role != "reviewer":
                self.assertEqual(row["mutating_tools"], [], role)

    def test_facade_paths_are_derived_from_the_server_builders(self) -> None:
        self.assertEqual(policy.facade_command_path("research_status"), "status")
        self.assertEqual(policy.facade_command_path("paper_status"), "paper plan")
        self.assertEqual(policy.facade_command_path("submission_check"), "submit check")
        self.assertEqual(policy.facade_command_path("ai_status"), "ai status")
        self.assertEqual(policy.facade_command_path("validate_current_stage"), "check")
        self.assertIsNone(policy.facade_command_path("no_such_tool"))

    def test_unknown_role_is_refused(self) -> None:
        with self.assertRaises(policy.AgentPolicyError) as caught:
            policy.compile_policy("no-such-role")
        self.assertIn("unknown agent role: no-such-role", " ".join(caught.exception.errors))


class ContractFaultTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="agent-policy-")
        self.agents = Path(self.temp.name) / "agents"
        shutil.copytree(ROOT / "agents", self.agents)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def contract(self, role: str) -> Path:
        return self.agents / role / "agent.yaml"

    def test_contract_naming_an_unknown_tool_is_refused(self) -> None:
        path = self.contract("orchestrator")
        text = path.read_text(encoding="utf-8").replace("  - context\n", "  - context\n  - ghost-command\n")
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(policy.AgentPolicyError) as caught:
            policy.compile_policy("orchestrator", agents_dir=self.agents)
        self.assertIn("contract names a tool the Harness does not have: ghost-command", " ".join(caught.exception.errors))

    def test_contract_naming_an_unknown_artifact_role_is_refused(self) -> None:
        path = self.contract("writer")
        text = path.read_text(encoding="utf-8").replace("read: [model_contract", "read: [ghost_role, model_contract")
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(policy.AgentPolicyError) as caught:
            policy.compile_policy("writer", agents_dir=self.agents)
        self.assertIn("contract names an unknown artifact role to read: ghost_role", " ".join(caught.exception.errors))

    def test_one_broken_contract_fails_the_whole_roster(self) -> None:
        path = self.contract("modeler")
        path.write_text(path.read_text(encoding="utf-8").replace("  - model\n", "  - ghost-command\n"), encoding="utf-8")
        with self.assertRaises(policy.AgentPolicyError):
            policy.compile_all(agents_dir=self.agents)


class BoundaryEnforcementTest(unittest.TestCase):
    def test_visible_tools_follow_the_role_policy(self) -> None:
        default = {tool["name"] for tool in mcp_server.visible_tools({})}
        scoped = {tool["name"] for tool in mcp_server.visible_tools({mcp_server.AGENT_ROLE_ENV: "orchestrator"})}
        self.assertIn("verify_artifact", default)
        self.assertNotIn("verify_artifact", scoped)
        self.assertNotIn("paper_status", scoped)
        self.assertIn("research_status", scoped)
        self.assertEqual(scoped, set(policy.compile_policy("orchestrator")["mcp_tools"]))

    def test_calls_outside_the_policy_are_refused(self) -> None:
        env = {mcp_server.AGENT_ROLE_ENV: "orchestrator"}
        with self.assertRaises(mcp_server.ToolCallError) as caught:
            mcp_server.call_tool("verify_artifact", {"artifact_id": "X"}, env=env)
        self.assertIn("outside the policy of agent role orchestrator", str(caught.exception))
        with self.assertRaises(mcp_server.ToolCallError):
            mcp_server.call_tool("paper_status", {}, role="modeler")

    def test_an_unknown_role_never_falls_back_to_the_full_surface(self) -> None:
        with self.assertRaises(Exception) as caught:
            mcp_server.visible_tools({mcp_server.AGENT_ROLE_ENV: "ghost"})
        self.assertIn("unknown agent role", str(caught.exception))

    def test_without_a_role_the_surface_is_unchanged(self) -> None:
        self.assertEqual(
            {tool["name"] for tool in mcp_server.visible_tools({})},
            {tool["name"] for tool in mcp_server.visible_tools(None)},
        )


class ServerClient:
    """Newline-JSON MCP client that can pass server arguments."""

    def __init__(self, *arguments: str, allowed_roots: list[Path] | None = None) -> None:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env.pop(mcp_server.ALLOWED_ROOTS_ENV, None)
        env.pop(mcp_server.AGENT_ROLE_ENV, None)
        if allowed_roots is not None:
            env[mcp_server.ALLOWED_ROOTS_ENV] = os.pathsep.join(str(path) for path in allowed_roots)
        self.process = subprocess.Popen(
            [sys.executable, str(SERVER), *arguments],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=str(ROOT),
            env=env,
        )
        self.next_id = 0

    def request(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        identifier = self.next_id
        payload: dict = {"jsonrpc": "2.0", "id": identifier, "method": method}
        if params is not None:
            payload["params"] = params
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        self.process.stdin.flush()
        for _ in range(32):
            line = self.process.stdout.readline()
            if not line:
                raise AssertionError("server closed the stream before answering")
            message = json.loads(line.decode("utf-8"))
            if message.get("id") == identifier:
                return message
        raise AssertionError(f"no response for id {identifier}")

    def close(self, timeout: float = 10.0) -> int:
        assert self.process.stdin is not None
        self.process.stdin.close()
        return self.process.wait(timeout=timeout)


class ServerPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="agent-policy-server-")
        self.project = Path(self.temp.name) / "project"
        initialized = subprocess.run(
            [sys.executable, str(CLI), "init", "--project", str(self.project), "--competition", "cumcm", "--preset", "research", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stdout + initialized.stderr)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_scoped_server_lists_and_calls_only_the_role_tools(self) -> None:
        client = ServerClient("--agent-role", "orchestrator", allowed_roots=[self.project])
        try:
            listing = client.request("tools/list")
            names = {tool["name"] for tool in listing["result"]["tools"]}
            self.assertIn("get_run_state", names)
            self.assertNotIn("verify_artifact", names)

            allowed = client.request("tools/call", {"name": "get_run_state", "arguments": {"project_root": str(self.project)}})
            self.assertNotIn("isError", allowed.get("result", {}), allowed)

            refused = client.request("tools/call", {"name": "verify_artifact", "arguments": {"project_root": str(self.project), "artifact_id": "X"}})
            self.assertTrue(refused["result"].get("isError"))
            self.assertIn("outside the policy of agent role orchestrator", refused["result"]["content"][0]["text"])
        finally:
            client.close()

    def test_unknown_role_refuses_to_start(self) -> None:
        client = ServerClient("--agent-role", "ghost", allowed_roots=[self.project])
        self.assertEqual(client.close(), 2)


if __name__ == "__main__":
    unittest.main()
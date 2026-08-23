from __future__ import annotations

import json
import os
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
import harness as harness_cli  # noqa: E402


EXPECTED_TOOLS = {
    "research_status",
    "research_context",
    "model_status",
    "solve_status",
    "paper_status",
    "validate_current_stage",
    "submission_check",
    "doctor",
    "ai_status",
}


def sample_arguments(tool: str) -> dict:
    if tool == "research_context":
        return {"stage": "model"}
    if tool == "validate_current_stage":
        return {"gate": "M1", "strict": True}
    if tool == "submission_check":
        return {"strict": True}
    return {}


class FacadeMappingTest(unittest.TestCase):
    """Every facade tool must map onto the real harness CLI surface."""

    def test_facade_covers_exactly_the_planned_tools(self) -> None:
        self.assertEqual({row["name"] for row in mcp_server.FACADE_TOOLS}, EXPECTED_TOOLS)
        self.assertEqual(set(mcp_server.TOOL_BUILDERS), EXPECTED_TOOLS)

    def test_every_mapping_parses_with_the_real_cli_parser(self) -> None:
        parser = harness_cli.build_parser()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for tool in sorted(EXPECTED_TOOLS):
                argv = mcp_server.build_argv(tool, sample_arguments(tool), root)
                self.assertEqual(argv[:2], [sys.executable, str(CLI)], tool)
                try:
                    parsed = parser.parse_args(argv[2:])
                except SystemExit as exc:  # argparse rejects unknown commands/flags
                    self.fail(f"{tool} argv rejected by the real CLI parser: {argv[2:]} ({exc})")
                self.assertEqual(str(Path(parsed.project).resolve()), str(root.resolve()), tool)

    def test_strict_flag_and_stage_reach_the_argv(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            strict_argv = mcp_server.build_argv("validate_current_stage", {"gate": "W2", "strict": True}, root)
            self.assertIn("--strict", strict_argv)
            self.assertIn("W2", strict_argv)
            context_argv = mcp_server.build_argv("research_context", {"stage": "paper:intro"}, root)
            self.assertEqual(context_argv[3:5], ["--stage", "paper:intro"])

    def test_invalid_arguments_are_tool_call_errors(self) -> None:
        with self.assertRaises(mcp_server.ToolCallError):
            mcp_server.build_argv("validate_current_stage", {"gate": "XX"}, Path("."))
        with self.assertRaises(mcp_server.ToolCallError):
            mcp_server.build_argv("research_context", {}, Path("."))
        with self.assertRaises(mcp_server.ToolCallError):
            mcp_server.build_argv("no_such_tool", {}, Path("."))


class WhitelistTest(unittest.TestCase):
    """P0 rule: project_root must be validated against an explicit allowlist."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="mcp-whitelist-")
        self.allowed = Path(self.temp.name)
        self.inside = self.allowed / "contest-a"
        self.inside.mkdir()
        self.outside = Path(self.temp.name + "-sibling")
        self.outside.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()
        self.outside.rmdir()

    def _env(self, **override: str) -> dict[str, str]:
        env = dict(os.environ)
        env[mcp_server.ALLOWED_ROOTS_ENV] = str(self.allowed)
        env.update(override)
        return env

    def test_inside_root_passes_and_canonicalizes(self) -> None:
        canonical = mcp_server.ensure_allowed(str(self.inside / ".." / "contest-a"), self._env())
        self.assertEqual(canonical, self.inside.resolve())

    def test_nested_path_under_allowed_root_passes(self) -> None:
        nested = self.inside / "deep" / "nested"
        nested.mkdir(parents=True)
        self.assertEqual(mcp_server.ensure_allowed(nested, self._env()), nested.resolve())

    def test_outside_root_is_rejected_with_reason(self) -> None:
        with self.assertRaises(mcp_server.ToolCallError) as caught:
            mcp_server.ensure_allowed(self.outside, self._env())
        self.assertIn("outside the allowed roots", str(caught.exception))

    def test_empty_or_missing_whitelist_denies_everything(self) -> None:
        with self.assertRaises(mcp_server.ToolCallError) as caught:
            mcp_server.ensure_allowed(self.inside, {})
        self.assertIn(mcp_server.ALLOWED_ROOTS_ENV, str(caught.exception))
        with self.assertRaises(mcp_server.ToolCallError):
            mcp_server.ensure_allowed(self.inside, {mcp_server.ALLOWED_ROOTS_ENV: ""})

    def test_case_only_path_differences_match_on_windows_semantics(self) -> None:
        upper = str(self.inside).upper()
        if os.path.normcase(upper) == os.path.normcase(str(self.inside)):
            self.assertEqual(mcp_server.ensure_allowed(upper, self._env()), self.inside.resolve())

    def test_blank_project_root_is_rejected(self) -> None:
        with self.assertRaises(mcp_server.ToolCallError):
            mcp_server.ensure_allowed("", self._env())
        with self.assertRaises(mcp_server.ToolCallError):
            mcp_server.ensure_allowed(None, self._env())


class ServerClient:
    """Minimal newline-JSON MCP test client around one spawned server."""

    def __init__(self, allowed_roots: list[Path] | None) -> None:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env.pop(mcp_server.ALLOWED_ROOTS_ENV, None)
        if allowed_roots is not None:
            env[mcp_server.ALLOWED_ROOTS_ENV] = os.pathsep.join(str(path) for path in allowed_roots)
        self.process = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=str(ROOT),
            env=env,
        )
        self.next_id = 0

    def send(self, payload: dict | list) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        self.process.stdin.flush()

    def request(self, method: str, params: dict | None = None) -> tuple[int, dict]:
        self.next_id += 1
        identifier = self.next_id
        payload: dict = {"jsonrpc": "2.0", "id": identifier, "method": method}
        if params is not None:
            payload["params"] = params
        self.send(payload)
        return identifier, self.receive(identifier)

    def receive(self, identifier: int) -> dict:
        assert self.process.stdout is not None
        for _ in range(32):
            line = self.process.stdout.readline()
            if not line:
                raise AssertionError("server closed the stream before answering")
            message = json.loads(line.decode("utf-8"))
            if message.get("id") == identifier:
                return message
        raise AssertionError(f"no response for id {identifier}")

    def initialize(self) -> dict:
        _, message = self.request(
            "initialize",
            {"protocolVersion": mcp_server.PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
        )
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return message["result"]

    def close(self) -> None:
        try:
            if self.process.stdin is not None and not self.process.stdin.closed:
                self.process.stdin.close()
            self.process.wait(timeout=10)
        except Exception:
            self.process.kill()
            self.process.wait(timeout=10)
        finally:
            for stream in (self.process.stdout, self.process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()


class ProtocolEndToEndTest(unittest.TestCase):
    """Drive the real stdio server against a real initialized v2 project."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="mcp-e2e-")
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        init = subprocess.run(
            [sys.executable, str(CLI), "init", "--project", str(self.project), "--competition", "cumcm", "--preset", "research", "--json"],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertEqual(init.returncode, 0, init.stdout + init.stderr)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def call(self, client: ServerClient, name: str, arguments: dict) -> dict:
        _, message = client.request("tools/call", {"name": name, "arguments": arguments})
        return message["result"]

    def test_initialize_negotiates_and_lists_exactly_the_facade(self) -> None:
        client = ServerClient([self.root])
        try:
            result = client.initialize()
            self.assertEqual(result["protocolVersion"], mcp_server.PROTOCOL_VERSION)
            self.assertEqual(result["serverInfo"]["name"], mcp_server.SERVER_NAME)
            _, message = client.request("tools/list")
            tools = message["result"]["tools"]
            self.assertEqual({row["name"] for row in tools}, EXPECTED_TOOLS)
            for row in tools:
                self.assertIn("project_root", row["inputSchema"]["properties"])
                self.assertIn("project_root", row["inputSchema"]["required"])
        finally:
            client.close()

    def test_status_call_returns_verbatim_json_and_exit_code_zero(self) -> None:
        client = ServerClient([self.root])
        try:
            client.initialize()
            result = self.call(client, "research_status", {"project_root": str(self.project)})
            self.assertNotIn("isError", result)
            structured = result["structuredContent"]
            self.assertTrue(structured["ok"])
            self.assertEqual(structured["exit_code"], 0)
            report = json.loads(structured["stdout"])
            self.assertEqual(report["schema_version"], "2.0")
            self.assertEqual(json.loads(result["content"][0]["text"]), report)
        finally:
            client.close()

    def test_gate_failure_is_a_verdict_not_an_execution_error(self) -> None:
        client = ServerClient([self.root])
        try:
            client.initialize()
            result = self.call(client, "validate_current_stage", {"project_root": str(self.project), "gate": "M1"})
            self.assertNotIn("isError", result)
            structured = result["structuredContent"]
            self.assertFalse(structured["ok"])
            self.assertEqual(structured["exit_code"], 1)
            verdict = json.loads(structured["stdout"])
            self.assertFalse(verdict["ok"])
            self.assertTrue(verdict["errors"])
        finally:
            client.close()

    def test_out_of_tree_project_root_is_rejected_with_reason(self) -> None:
        client = ServerClient([self.project])
        try:
            client.initialize()
            outside = self.root.parent
            result = self.call(client, "doctor", {"project_root": str(outside)})
            self.assertTrue(result.get("isError"))
            self.assertIn("outside the allowed roots", result["content"][0]["text"])
        finally:
            client.close()

    def test_unset_whitelist_denies_every_call(self) -> None:
        client = ServerClient(None)
        try:
            client.initialize()
            result = self.call(client, "ai_status", {"project_root": str(self.project)})
            self.assertTrue(result.get("isError"))
            self.assertIn(mcp_server.ALLOWED_ROOTS_ENV, result["content"][0]["text"])
        finally:
            client.close()

    def test_unknown_tool_and_invalid_params_report_errors(self) -> None:
        client = ServerClient([self.root])
        try:
            client.initialize()
            unknown = self.call(client, "freeze_results", {"project_root": str(self.project)})
            self.assertTrue(unknown.get("isError"))
            self.assertIn("unknown tool", unknown["content"][0]["text"])
            bad_gate = self.call(client, "validate_current_stage", {"project_root": str(self.project), "gate": "F9"})
            self.assertTrue(bad_gate.get("isError"))
            self.assertIn("gate must be one of", bad_gate["content"][0]["text"])
            missing_root = self.call(client, "doctor", {})
            self.assertTrue(missing_root.get("isError"))
        finally:
            client.close()

    def test_ping_and_batch_requests_are_answered_per_jsonrpc(self) -> None:
        client = ServerClient([self.root])
        try:
            _, pong = client.request("ping")
            self.assertEqual(pong["result"], {})
            client.next_id += 1
            identifier = client.next_id
            client.send([
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": identifier, "method": "ping"},
            ])
            self.assertEqual(client.receive(identifier)["result"], {})
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()

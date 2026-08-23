#!/usr/bin/env python3
"""Read/query MCP facade over ``scripts/harness.py`` for DeepSeek Harness sessions.

Implements the minimal Model Context Protocol surface consumed by
``@deepseek-ai/dsh-mcp-client``: newline-delimited JSON-RPC 2.0 over stdio with
``initialize``, ``tools/list``, and ``tools/call``. The official ``mcp`` package
is deliberately not a dependency: this facade only bridges high-intent
read/check tools (Phase 0 decision in docs/DSH_PLUGIN_INTEGRATION_WORKPLAN_2026-08-22.md).

Safety contract (P0):

- Every tool takes an explicit ``project_root``; the server never assumes its
  own working directory is the project root.
- Roots are canonicalized and must sit inside ``MATH_HARNESS_ALLOWED_ROOTS``
  (an ``os.pathsep``-separated list). An unset or empty variable denies every
  call; out-of-tree paths are rejected with the reason echoed back.
- Every child process runs with ``cwd=project_root`` and forced UTF-8.
- Checker verdicts pass through verbatim: the server reports the child's exit
  code and output and never translates a FAIL into a PASS. ``isError`` marks
  execution failures only (bad arguments, rejected roots, timeouts), never a
  checker verdict.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

HARNESS_REPO = Path(__file__).resolve().parent.parent
HARNESS_CLI = HARNESS_REPO / "scripts" / "harness.py"
ALLOWED_ROOTS_ENV = "MATH_HARNESS_ALLOWED_ROOTS"
CALL_TIMEOUT_SECONDS = 55
PROTOCOL_VERSION = "2025-03-26"
SERVER_NAME = "math_harness"
SERVER_VERSION = "1.0.0"
GATES = ("M1", "P1", "P2", "W1", "W2", "S1")

PARSE_ERROR = -32700
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


class ToolCallError(Exception):
    """A tool call cannot be executed; the reason is reported to the caller."""


def allowed_roots(env: Mapping[str, str] | None = None) -> list[Path]:
    """Canonicalize the configured allowlist; an empty configuration denies all."""

    source = os.environ if env is None else env
    raw = source.get(ALLOWED_ROOTS_ENV, "")
    roots: list[Path] = []
    for item in raw.split(os.pathsep):
        candidate = item.strip()
        if candidate:
            roots.append(Path(candidate).expanduser().resolve())
    return roots


def is_within(child: Path, ancestor: Path) -> bool:
    """Containment check that is case-insensitive where the OS is."""

    child_text = os.path.normcase(str(child))
    ancestor_text = os.path.normcase(str(ancestor))
    return child_text == ancestor_text or child_text.startswith(ancestor_text.rstrip(os.sep) + os.sep)


def ensure_allowed(project_root: Any, env: Mapping[str, str] | None = None) -> Path:
    """Return the canonical project root or raise :class:`ToolCallError`."""

    raw = os.fspath(project_root) if isinstance(project_root, (str, os.PathLike)) else ""
    if not isinstance(raw, str) or not raw.strip():
        raise ToolCallError("project_root must be a non-empty string path")
    canonical = Path(raw).expanduser().resolve()
    roots = allowed_roots(env)
    if not roots:
        raise ToolCallError(
            f"rejected: {ALLOWED_ROOTS_ENV} is unset or empty, so every project_root is denied "
            "(fail-closed whitelist); configure it in the MCP row's env before use"
        )
    for root in roots:
        if is_within(canonical, root):
            return canonical
    listing = os.pathsep.join(str(root) for root in roots)
    raise ToolCallError(f"rejected: project_root {canonical} is outside the allowed roots [{listing}]")


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "exit_code": {"type": "integer"}, "stdout": {"type": "string"}, "stderr": {"type": "string"}},
    "required": ["ok", "exit_code", "stdout", "stderr"],
}


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"name": name, "description": description, "inputSchema": _schema(properties, required), "outputSchema": OUTPUT_SCHEMA}


PROJECT_ROOT_PROPERTY: dict[str, Any] = {
    "project_root": {
        "type": "string",
        "description": "Absolute path of the contest project root; must be inside MATH_HARNESS_ALLOWED_ROOTS.",
    }
}


def _build_research_status(arguments: Mapping[str, Any]) -> list[str]:
    return ["status"]


def _build_research_context(arguments: Mapping[str, Any]) -> list[str]:
    stage = arguments.get("stage")
    if not isinstance(stage, str) or not stage.strip():
        raise ToolCallError("stage must be one of research / model / solve / paper:<section>")
    return ["context", "--stage", stage]


def _build_model_status(arguments: Mapping[str, Any]) -> list[str]:
    return ["model"]


def _build_solve_status(arguments: Mapping[str, Any]) -> list[str]:
    return ["solve"]


def _build_paper_status(arguments: Mapping[str, Any]) -> list[str]:
    return ["paper", "plan"]


def _build_validate_current_stage(arguments: Mapping[str, Any]) -> list[str]:
    gate = arguments.get("gate")
    if gate not in GATES:
        raise ToolCallError(f"gate must be one of {', '.join(GATES)}")
    argv = ["check", gate]
    if arguments.get("strict") is True:
        argv.append("--strict")
    return argv


def _build_submission_check(arguments: Mapping[str, Any]) -> list[str]:
    argv = ["submit", "check"]
    if arguments.get("strict") is True:
        argv.append("--strict")
    return argv


def _build_doctor(arguments: Mapping[str, Any]) -> list[str]:
    return ["doctor", "--offline"]


def _build_ai_status(arguments: Mapping[str, Any]) -> list[str]:
    return ["ai", "status"]


FACADE_TOOLS: list[dict[str, Any]] = [
    _tool(
        "research_status",
        "Read-only factual status projection of a v2 harness project (gates, pending human checkpoints, stale artifacts).",
        PROJECT_ROOT_PROPERTY,
        ["project_root"],
    ),
    _tool(
        "research_context",
        "Show the minimal stage-local context plan before authoring a stage.",
        {**PROJECT_ROOT_PROPERTY, "stage": {"type": "string", "description": "research, model, solve, or paper:<section>"}},
        ["project_root", "stage"],
    ),
    _tool(
        "model_status",
        "Model-decision authoring surface state (reads 01_RESEARCH_NOTES.md, targets 02_MODEL_DECISION.md).",
        PROJECT_ROOT_PROPERTY,
        ["project_root"],
    ),
    _tool(
        "solve_status",
        "Solve-stage surface state (reads 02_MODEL_DECISION.md, targets 03_SOLUTION_REPORT.md); runs no computation.",
        PROJECT_ROOT_PROPERTY,
        ["project_root"],
    ),
    _tool(
        "paper_status",
        "Paper-plan surface state (targets paper/00_PAPER_PLAN.md when absent).",
        PROJECT_ROOT_PROPERTY,
        ["project_root"],
    ),
    _tool(
        "validate_current_stage",
        "Run one existing deterministic Gate checker (M1/P1/P2/W1/W2/S1) and pass its JSON verdict and exit code through verbatim.",
        {**PROJECT_ROOT_PROPERTY, "gate": {"type": "string", "enum": list(GATES)}, "strict": {"type": "boolean", "description": "Enable strict mode."}},
        ["project_root", "gate"],
    ),
    _tool(
        "submission_check",
        "Run the existing factual S1 submission checker and pass its JSON verdict and exit code through verbatim.",
        {**PROJECT_ROOT_PROPERTY, "strict": {"type": "boolean", "description": "Enable strict mode."}},
        ["project_root"],
    ),
    _tool(
        "doctor",
        "Check Python, optional dependencies, schemas, and critical files for a project root.",
        PROJECT_ROOT_PROPERTY,
        ["project_root"],
    ),
    _tool(
        "ai_status",
        "Show the current tri-state AI usage declaration recorded in the run manifest.",
        PROJECT_ROOT_PROPERTY,
        ["project_root"],
    ),
]

TOOL_BUILDERS = {
    "research_status": _build_research_status,
    "research_context": _build_research_context,
    "model_status": _build_model_status,
    "solve_status": _build_solve_status,
    "paper_status": _build_paper_status,
    "validate_current_stage": _build_validate_current_stage,
    "submission_check": _build_submission_check,
    "doctor": _build_doctor,
    "ai_status": _build_ai_status,
}


def build_argv(tool_name: str, arguments: Mapping[str, Any], project_root: Path) -> list[str]:
    """Compose the full harness.py argv for one facade call (used by tests too)."""

    builder = TOOL_BUILDERS.get(tool_name)
    if builder is None:
        raise ToolCallError(f"unknown tool: {tool_name}")
    return [sys.executable, str(HARNESS_CLI), *builder(arguments), "--project", str(project_root), "--json"]


def run_harness(argv: list[str], project_root: Path, timeout: float = CALL_TIMEOUT_SECONDS) -> tuple[int, str, str]:
    """Run harness.py with cwd=project_root under forced UTF-8 and capture output."""

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(argv, cwd=str(project_root), capture_output=True, env=env, timeout=timeout, check=False)
    decode_errors = "backslashreplace"
    stdout = completed.stdout.decode("utf-8", errors=decode_errors)
    stderr = completed.stderr.decode("utf-8", errors=decode_errors)
    return completed.returncode, stdout, stderr


def call_tool(name: Any, arguments: Any, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Execute one tools/call and return its MCP result envelope."""

    if not isinstance(name, str):
        raise ToolCallError("params.name must be a string")
    if name not in TOOL_BUILDERS:
        raise ToolCallError(f"unknown tool: {name}")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, Mapping):
        raise ToolCallError("params.arguments must be an object")
    project_root = ensure_allowed(arguments.get("project_root"), env)
    try:
        argv = build_argv(name, arguments, project_root)
        exit_code, stdout, stderr = run_harness(argv, project_root)
    except subprocess.TimeoutExpired as exc:
        raise ToolCallError(f"harness call timed out after {CALL_TIMEOUT_SECONDS}s; run long builds via background jobs instead") from exc
    text = stdout if stdout.strip() else stderr
    structured = {"ok": exit_code == 0, "exit_code": exit_code, "stdout": stdout, "stderr": stderr}
    return {"content": [{"type": "text", "text": text}], "structuredContent": structured}


class StdioSession:
    """One stdio MCP session; each DSH preset row spawns its own instance."""

    def __init__(self, reader: Any, writer: Any, env: Mapping[str, str] | None = None) -> None:
        self._reader = reader
        self._writer = writer
        self._env = env

    def serve(self) -> None:
        for raw_line in iter(self._reader.readline, b""):
            line = raw_line.strip()
            if not line:
                continue
            responses: list[dict[str, Any]] = []
            try:
                message = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                responses.append(self._error(None, PARSE_ERROR, "parse error: request line is not valid JSON"))
            else:
                batch = message if isinstance(message, list) else [message]
                for item in batch:
                    response = self._handle(item)
                    if response is not None:
                        responses.append(response)
            for response in responses:
                self._write(response)

    def _handle(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, Mapping):
            return self._error(None, PARSE_ERROR, "parse error: request is not an object")
        identifier = message.get("id")
        method = message.get("method")
        if method is None:
            # A pure response or notification without a method carries no work.
            return None
        params = message.get("params") or {}
        if method == "initialize":
            requested = params.get("protocolVersion") if isinstance(params, Mapping) else None
            result = {
                "protocolVersion": requested if isinstance(requested, str) else PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
            return self._result(identifier, result)
        if method == "ping":
            return self._result(identifier, {})
        if method == "tools/list":
            return self._result(identifier, {"tools": FACADE_TOOLS})
        if method == "tools/call":
            return self._result(identifier, self._call(params))
        if isinstance(identifier, (str, int)):
            return self._error(identifier, METHOD_NOT_FOUND, f"method not found: {method}")
        return None

    def _call(self, params: Any) -> dict[str, Any]:
        if not isinstance(params, Mapping):
            return self._error_envelope("params must be an object")
        try:
            return call_tool(params.get("name"), params.get("arguments"), self._env)
        except ToolCallError as exc:
            return self._error_envelope(str(exc))

    def _error_envelope(self, reason: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": reason}], "isError": True}

    def _result(self, identifier: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": identifier, "result": result}

    def _error(self, identifier: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}

    def _write(self, payload: Mapping[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False)
        self._writer.write((line + "\n").encode("utf-8"))
        self._writer.flush()


def main() -> int:
    sys.stderr.write(f"{SERVER_NAME} {SERVER_VERSION}: serving harness facade on stdio\n")
    StdioSession(sys.stdin.buffer, sys.stdout.buffer).serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

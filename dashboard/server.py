"""Harness observability console: a read-only view over the MCP tool surface.

The deliberate design constraint: this server has **no write path**. Every byte
it renders comes from the same MCP tools an external agent calls
(``get_run_state``, ``list_artifacts``, ``check_gate``, ``verify_artifact``)
plus the generated evidence already on disk. A button here cannot approve a
freeze, pass a Gate or edit an artifact, because the Harness does not accept a
decision from a console — a human decision is a control-state record with its
own boundary, and a freeze is a producer command.

Run it against a demo project::

    python dashboard/server.py --project tmp/demo-run --port 8765

``DASHBOARD_ALLOWED_ROOTS`` (os.pathsep-separated) gates which project roots may
be served; unset means serve nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DASHBOARD_DIR = Path(__file__).resolve().parent
REPO_ROOT = DASHBOARD_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import mcp_server  # noqa: E402
from project_layout import resolve_control_path  # noqa: E402

ALLOWED_ROOTS_ENV = "DASHBOARD_ALLOWED_ROOTS"
GATE_ORDER = ("S0", "M1", "P1", "P2", "W1", "W2", "S1", "F1")


def _tool(root: Path, name: str, **arguments: Any) -> dict[str, Any]:
    envelope = mcp_server.call_tool(name, {"project_root": str(root), **arguments}, None)
    return envelope.get("structuredContent") or {"errors": ["tool returned no structured content"]}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _receipts(root: Path) -> list[dict[str, Any]]:
    index_path = resolve_control_path(root, "run_index.json")
    index = _read_json(index_path)
    rows = []
    for entry in index.get("receipts", []) if isinstance(index.get("receipts"), list) else []:
        if not isinstance(entry, dict):
            continue
        receipt = _read_json(root / str(entry.get("receipt_path", "")))
        rows.append({
            "receipt_id": entry.get("receipt_id"),
            "stage": entry.get("stage") or receipt.get("stage"),
            "selected": (entry.get("receipt_id") in (index.get("selection") or {}).get("selected_receipt_ids", [])),
            "exit_code": receipt.get("exit_code"),
            "argv": receipt.get("argv"),
            "started_at": receipt.get("started_at"),
            "finished_at": receipt.get("finished_at"),
            "path": entry.get("receipt_path"),
        })
    return sorted(rows, key=lambda row: str(row.get("started_at") or ""))


def _reviews(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((root / "reports" / "review").glob("*.json")):
        report = _read_json(path)
        if "perspective" not in report:
            continue
        rows.append({
            "perspective": report.get("perspective"),
            "independence_level": report.get("independence_level"),
            "verdict": report.get("verdict"),
            "reviewed_at": report.get("reviewed_at"),
            "findings": len(report.get("findings") or []),
            "path": path.relative_to(root).as_posix(),
        })
    return rows


def _timeline(state: dict[str, Any], receipts: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge Gate, execution and review facts into one chronological trace."""
    events: list[dict[str, Any]] = []
    for receipt in receipts:
        events.append({
            "at": receipt.get("started_at"),
            "kind": "execution",
            "label": f"{receipt.get('stage')} run",
            "detail": " ".join(str(item) for item in (receipt.get("argv") or [])[:3]),
            "ok": receipt.get("exit_code") == 0,
        })
    for review in reviews:
        events.append({
            "at": review.get("reviewed_at"),
            "kind": "review",
            "label": f"{review.get('perspective')} ({review.get('independence_level')})",
            "detail": f"verdict={review.get('verdict')} findings={review.get('findings')}",
            "ok": review.get("verdict") == "pass",
        })
    return sorted(events, key=lambda row: str(row.get("at") or ""))


BOUNDARY_STAGES = ("S0", "F1")


MCP_ROOTS_ENV = "MATH_HARNESS_ALLOWED_ROOTS"


def _narrow_mcp_roots(root: Path) -> None:
    """Restrict the MCP fail-closed allowlist to the project being served."""

    configured = os.environ.get(MCP_ROOTS_ENV, "")
    entries = [Path(item).expanduser().resolve() for item in configured.split(os.pathsep) if item.strip()]
    if entries:
        if not any(mcp_server.is_within(root, allowed) for allowed in entries):
            msg = f"refusing {root}: outside {MCP_ROOTS_ENV}"
            raise RuntimeError(msg)
        return
    os.environ[MCP_ROOTS_ENV] = str(root)


def snapshot(root: Path) -> dict[str, Any]:
    """One recomputed view of a project. Nothing here is cached or written."""

    _narrow_mcp_roots(root.resolve())
    state = _tool(root, "get_run_state")
    artifacts = _tool(root, "list_artifacts")
    gates = [str(name).lower() for name in (state.get("gates_passed") or [])]
    blocked = str(state.get("first_blocked_gate") or "").lower()
    receipts = _receipts(root)
    reviews = _reviews(root)
    manifest = _read_json(resolve_control_path(root, "run_manifest.json"))
    checkpoints = {
        str(row.get("stage")): row for row in manifest.get("human_checkpoints", []) if isinstance(row, dict)
    }
    return {
        "project_root": str(root),
        "run_id": state.get("run_id"),
        "stage": state.get("stage"),
        "preset": state.get("preset"),
        "gate_status": state.get("gate_status"),
        "first_blocked_gate": state.get("first_blocked_gate"),
        "gates": [
            {
                "gate": gate,
                "state": (
                    "boundary" if gate in BOUNDARY_STAGES
                    else "passed" if gate.lower() in gates
                    else "blocked" if gate.lower() == blocked
                    else "locked"
                ),
                "human_checkpoint": (checkpoints.get(gate.lower()) or {}).get("decision"),
                "checkpoint_by": (checkpoints.get(gate.lower()) or {}).get("decided_by"),
            }
            for gate in GATE_ORDER
        ],
        "blockers": state.get("blockers") or [],
        "next_actions": state.get("next_actions") or [],
        "stale_artifacts": state.get("stale_artifacts") or [],
        "pending_human_checkpoints": state.get("pending_human_checkpoints") or [],
        "artifacts": artifacts.get("artifacts") or [],
        "artifact_errors": artifacts.get("errors") or [],
        "receipts": receipts,
        "reviews": reviews,
        "timeline": _timeline(state, receipts, reviews),
        "ai_usage_state": manifest.get("ai_usage_state"),
        "sources": [
            "mcp:get_run_state", "mcp:list_artifacts",
            "run_index.json + receipts/*.json", "reports/review/*.json", "run_manifest.json",
        ],
        "read_only": True,
    }


class Handler(BaseHTTPRequestHandler):
    root: Path = Path(".")  # set by serve()

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler protocol
        if self.path in ("/", "/index.html"):
            self._send(200, (DASHBOARD_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if self.path.startswith("/api/snapshot"):
            try:
                self._json(200, snapshot(self.root))
            except mcp_server.ToolCallError as exc:
                self._json(403, {"error": str(exc)})
            except OSError as exc:
                self._json(500, {"error": str(exc)})
            return
        self._json(404, {"error": f"no route {self.path}"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler protocol
        self._json(405, {
            "error": "the console is read-only by design",
            "why": (
                "a Gate PASS, freeze, receipt or human decision must come from a producer command "
                "or a control-state record, never from a dashboard button"
            ),
            "instead": "harness check <GATE> · harness freeze · harness ai verify · harness review",
        })

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - protocol name
        sys.stderr.write(f"dashboard: {format % args}\n")


def serve(project: Path, port: int, host: str = "127.0.0.1") -> int:
    allowed = os.environ.get(ALLOWED_ROOTS_ENV, "")
    roots = [Path(item).expanduser().resolve() for item in allowed.split(os.pathsep) if item.strip()]
    if roots and project.resolve() not in roots:
        print(
            f"refusing to serve {project}: not in {ALLOWED_ROOTS_ENV} "
            f"({allowed!r}); unset it to serve any single explicit project",
            file=sys.stderr,
        )
        return 2
    Handler.root = project.resolve()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"harness console: http://{host}:{server.server_address[1]}/  project={project}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path, help="contest project root to observe")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--snapshot", action="store_true", help="print one snapshot and exit")
    args = parser.parse_args(argv)
    if args.snapshot:
        print(json.dumps(snapshot(args.project.resolve()), ensure_ascii=False, indent=2))
        return 0
    return serve(args.project.resolve(), args.port, args.host)


if __name__ == "__main__":
    raise SystemExit(main())

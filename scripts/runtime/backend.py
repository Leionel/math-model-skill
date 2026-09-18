"""Execution backend and execution capsules: re-run one recorded command, compare bytes.

The capsule is derived from a command receipt (``argv``, ``cwd``, ``exit_code``,
``output_refs``).  Reproduction runs in an **isolated copy** of the project so a
re-run can never clobber the recorded artifacts, and the receipt's absolute root
is rewritten to the copy's root, which is also what makes a capsule usable after
the project moves.  Fields the receipt does not capture — environment variables
and the seed — are recorded as ``null``/``false`` rather than invented.

Only a local backend exists today; the interface is the seam a container or
remote backend would implement later.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from _common import child_env, load_structured, sha256_file  # noqa: E402


class CapsuleError(ValueError):
    """A receipt cannot be turned into a capsule, or a capsule is not reproducible."""


class LocalBackend:
    """Execute on this host; the reference implementation of the backend seam."""

    backend_id = "local"

    def snapshot_environment(self) -> dict[str, Any]:
        return {
            "backend": self.backend_id,
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "variables_captured": False,
        }

    def execute(self, argv: list[str], cwd: Path, *, timeout: int) -> dict[str, Any]:
        started = time.monotonic()
        completed = subprocess.run(
            [str(token) for token in argv],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=child_env(),
            timeout=timeout,
            check=False,
        )
        return {
            "exit_code": completed.returncode,
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
            "duration_s": round(time.monotonic() - started, 3),
        }

    def collect_outputs(self, root: Path, refs: list[Mapping[str, Any]]) -> list[dict[str, str]]:
        collected: list[dict[str, str]] = []
        for ref in refs:
            raw = ref.get("path")
            if not isinstance(raw, str) or not raw:
                continue
            path = (root / raw).resolve()
            if not path.is_file():
                raise CapsuleError(f"recorded output is missing after the re-run: {raw}")
            collected.append({"path": raw, "sha256": sha256_file(path)})
        return collected

    def compute_digests(self, root: Path, paths: list[str]) -> list[dict[str, str]]:
        return [
            {"path": raw, "sha256": sha256_file((root / raw).resolve())}
            for raw in paths
            if (root / raw).is_file()
        ]

    def terminate(self) -> None:
        """No remote process to stop; a hosted backend would kill its worker here."""


def build_capsule(receipt_path: Path | str, *, backend: LocalBackend | None = None) -> dict[str, Any]:
    """Derive a capsule from one command receipt."""

    path = Path(receipt_path).resolve()
    if not path.is_file():
        raise CapsuleError(f"receipt does not exist: {path}")
    receipt = load_structured(path)
    if not isinstance(receipt, Mapping):
        raise CapsuleError("receipt must be an object")
    argv = receipt.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(token, str) for token in argv):
        raise CapsuleError("receipt.argv must be a non-empty array of strings")
    receipt_id = receipt.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id:
        raise CapsuleError("receipt.receipt_id is required")
    exit_code = receipt.get("exit_code")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        raise CapsuleError("receipt.exit_code is required")
    cwd = receipt.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise CapsuleError("receipt.cwd is required")
    outputs = [
        {"path": str(ref["path"]), "sha256": str(ref["sha256"])}
        for ref in receipt.get("output_refs", [])
        if isinstance(ref, Mapping) and isinstance(ref.get("path"), str) and isinstance(ref.get("sha256"), str)
    ]
    metadata = receipt.get("metadata") if isinstance(receipt.get("metadata"), Mapping) else {}
    active_backend = backend or LocalBackend()
    return {
        "schema_version": "1.0",
        "capsule_id": f"capsule-{receipt_id}",
        "source_receipt": {"path": str(path), "receipt_id": receipt_id, "exit_code": exit_code},
        "command": {
            "argv": list(argv),
            "cwd": cwd,
            "run_id": str(receipt["run_id"]) if isinstance(receipt.get("run_id"), str) else None,
            "integrity_mode": str(metadata["integrity_mode"]) if isinstance(metadata.get("integrity_mode"), str) else None,
        },
        "randomness": {"seed": None, "captured": False},
        "environment": active_backend.snapshot_environment(),
        "expected": {"exit_code": exit_code},
        "outputs": outputs,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "notes": [
            "derived from a command receipt; environment variables and seed are not captured",
            "reproduction runs in an isolated copy of the project",
            "recorded outputs are removed from the copy first, so a producer that refuses to overwrite still re-derives them",
        ],
    }


def load_capsule_or_receipt(source: Path | str) -> dict[str, Any]:
    """Read an execution capsule, or derive one from a receipt path."""

    path = Path(source).resolve()
    document = load_structured(path)
    if isinstance(document, Mapping) and "source_receipt" in document:
        return dict(document)
    return build_capsule(path)


def reproduce(
    receipt_or_capsule: Path | str | Mapping[str, Any],
    *,
    backend: LocalBackend | None = None,
    isolate: bool = True,
    timeout: int = 900,
) -> dict[str, Any]:
    """Re-run the capsule's command and compare exit code and output bytes."""

    active_backend = backend or LocalBackend()
    if isinstance(receipt_or_capsule, Mapping):
        document: Any = dict(receipt_or_capsule)
        source: Path | None = None
    else:
        source = Path(receipt_or_capsule).resolve()
        document = load_structured(source)
    if not isinstance(document, Mapping):
        raise CapsuleError("source document must be an object")
    if "source_receipt" in document:
        capsule = dict(document)
    elif source is not None:
        capsule = load_capsule_or_receipt(source)
    else:
        raise CapsuleError("a capsule object must carry source_receipt")
    argv = [str(token) for token in capsule["command"]["argv"]]
    original_cwd = Path(str(capsule["command"]["cwd"]))
    scratch: Path | None = None
    removed_before_run: list[str] = []
    if isolate:
        if not original_cwd.is_dir():
            raise CapsuleError(f"capsule command root does not exist: {original_cwd}")
        scratch = Path(tempfile.mkdtemp(prefix="capsule-reproduce-"))
        # Resolved once: a short 8.3 temp name would otherwise never match the
        # resolved paths of the files inside it.
        workdir = (scratch / "project").resolve()
        shutil.copytree(original_cwd, workdir)
        # Both spellings of the recorded root are rewritten: on Windows a
        # receipt can carry the resolved root while a command argument carries
        # the short 8.3 form (or the other way round), and either one must point
        # at the copy or the command would write into the recorded project.
        root_spellings = {str(original_cwd), str(original_cwd.resolve())}
        for spelling in sorted(root_spellings):
            argv = [token.replace(spelling, str(workdir)) for token in argv]
        # The recorded run started before its outputs existed; producers here
        # refuse to overwrite, so the copy is restored to that precondition for
        # exactly the files this capsule re-derives. An output the command also
        # reads as input makes the re-run fail loudly instead of quietly.
        for row in capsule.get("outputs", []):
            if not isinstance(row, Mapping):
                continue
            target = (workdir / str(row.get("path", ""))).resolve()
            try:
                target.relative_to(workdir)
            except ValueError:
                continue
            if target.is_file():
                target.unlink()
                removed_before_run.append(str(row["path"]))
    else:
        workdir = original_cwd
    result = active_backend.execute(argv, workdir, timeout=timeout)
    expected_outputs = [
        {"path": str(row["path"]), "sha256": str(row["sha256"])}
        for row in capsule.get("outputs", [])
        if isinstance(row, Mapping)
    ]
    try:
        actual_outputs = active_backend.collect_outputs(workdir, expected_outputs)
    except CapsuleError as exc:
        actual_outputs = []
        missing = str(exc)
    else:
        missing = None
    actual_by_path = {row["path"]: row["sha256"] for row in actual_outputs}
    comparisons = [
        {
            "path": row["path"],
            "expected": row["sha256"],
            "actual": actual_by_path.get(row["path"]),
            "match": actual_by_path.get(row["path"]) == row["sha256"],
        }
        for row in expected_outputs
    ]
    mismatches = [row["path"] for row in comparisons if not row["match"]]
    exit_matches = result["exit_code"] == capsule["expected"]["exit_code"]
    report = {
        "schema_version": "1.0",
        "capsule_id": capsule["capsule_id"],
        "ok": bool(exit_matches and not mismatches and missing is None),
        "isolated": isolate,
        "workdir": str(workdir),
        "removed_before_run": removed_before_run,
        "exit_code": result["exit_code"],
        "expected_exit_code": capsule["expected"]["exit_code"],
        "exit_code_matches": exit_matches,
        # A failed run that fails the same way is a faithful reproduction, not a
        # success; the outcome label keeps the two apart for a reader.
        "recorded_outcome": "success" if capsule["expected"]["exit_code"] == 0 else "failure",
        "outputs": comparisons,
        "mismatches": mismatches,
        "missing_output": missing,
        "environment": capsule["environment"],
        "duration_s": result["duration_s"],
        "stdout_tail": "\n".join(result["stdout"].strip().splitlines()[-5:]),
        "stderr_tail": "\n".join(result["stderr"].strip().splitlines()[-5:]),
        "notes": list(capsule.get("notes", [])),
    }
    if scratch is not None:
        shutil.rmtree(scratch, ignore_errors=True)
        report["workdir"] = None
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="a command receipt, or a capsule built from one")
    parser.add_argument("--capsule-out", help="write the derived capsule here")
    parser.add_argument("--no-isolate", action="store_true", help="run in the recorded root instead of a copy")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        capsule = load_capsule_or_receipt(args.source)
        if args.capsule_out:
            target = Path(args.capsule_out)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(capsule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = reproduce(capsule, isolate=not args.no_isolate, timeout=args.timeout)
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else json.dumps({key: report[key] for key in ("ok", "exit_code", "expected_exit_code", "mismatches", "missing_output")}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
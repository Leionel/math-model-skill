#!/usr/bin/env python3
"""Generate immutable LaTeX result macros from frozen results and a presentation contract."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, resolve_path, sha256_file  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


def format_value(result: dict[str, object], entry: dict[str, object]) -> str:
    display = str(result.get("display_value", ""))
    kind = entry.get("format")
    scale = Decimal(str(entry.get("scale", 1)))
    if kind in {"number", "scientific", "currency", "percentage"} and entry.get("rounding") != "frozen_display_value":
        try:
            value = Decimal(str(result.get("value"))) * scale
            digits = int(entry.get("digits", result.get("precision", 0)))
            quantum = Decimal(1).scaleb(-digits)
            rounding_mode = {
                "floor": ROUND_FLOOR,
                "ceil": ROUND_CEILING,
                "half_up": ROUND_HALF_UP,
                "significant_figures": ROUND_HALF_UP,
                "none": ROUND_HALF_UP,
            }.get(str(entry.get("rounding")), ROUND_HALF_UP)
            display = f"{value.quantize(quantum, rounding=rounding_mode):.{digits}f}"
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"cannot format result {result.get('result_id')}")
    elif kind == "percentage" and entry.get("rounding") == "frozen_display_value" and scale != 1:
        raise ValueError("percentage scaling requires an explicit rounding policy; frozen_display_value cannot be rescaled")
    return f"{entry.get('prefix', '')}{display}{entry.get('suffix', '')}{entry.get('unit_display', '')}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--presentation-contract", required=True)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    contract_path = resolve_path(args.presentation_contract, root).resolve()
    frozen_path = resolve_path(args.frozen_results, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    provenance_path = resolve_path(args.provenance, root).resolve()
    contract, schema_errors, _ = _validate_document(
        contract_path, Path(__file__).resolve().parents[2] / "schemas" / "presentation_contract.schema.json"
    )
    if schema_errors:
        print(json.dumps({"ok": False, "errors": schema_errors}, ensure_ascii=False, indent=2))
        return 1
    try:
        frozen = load_structured(frozen_path)
        if not isinstance(contract, dict) or not isinstance(frozen, dict):
            raise ValueError("presentation contract and frozen results must be objects")
        if contract.get("run_id") != frozen.get("run_id"):
            raise ValueError("presentation contract and frozen results must share one run_id")
        frozen_ref = contract.get("frozen_results", {})
        if not isinstance(frozen_ref, dict) or resolve_path(str(frozen_ref.get("path", "")), root).resolve() != frozen_path:
            raise ValueError("presentation contract does not point to supplied frozen_results")
        if frozen_ref.get("sha256") != sha256_file(frozen_path):
            raise ValueError("presentation contract frozen_results hash drift")
        if frozen.get("claimable") is not True:
            raise ValueError("presentation macros require claimable frozen results")
        results = {
            row.get("result_id"): row for row in frozen.get("results", [])
            if isinstance(row, dict) and isinstance(row.get("result_id"), str)
        }
        macros: list[dict[str, str]] = []
        names: set[str] = set()
        for entry in contract.get("entries", []):
            macro = entry["macro"]
            if macro in names:
                raise ValueError(f"duplicate macro name {macro}")
            names.add(macro)
            result = results.get(entry["result_id"])
            if result is None:
                raise ValueError(f"unknown result_id {entry['result_id']}")
            rendered = format_value(result, entry)
            macros.append({"macro": macro, "result_id": entry["result_id"], "value": rendered})
        lines = ["% Generated from frozen results. Do not edit by hand."]
        lines.extend(f"\\newcommand{{\\{row['macro']}}}{{{row['value']}}}" for row in macros)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and not args.force:
            raise FileExistsError(f"refusing to overwrite existing file: {output_path}; pass --force")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        provenance = {
            "schema_version": "1.0",
            "run_id": frozen["run_id"],
            "presentation_contract": {"path": contract_path.relative_to(root).as_posix(), "sha256": sha256_file(contract_path)},
            "frozen_results": {"path": frozen_path.relative_to(root).as_posix(), "sha256": sha256_file(frozen_path)},
            "generated_tex": {"path": output_path.relative_to(root).as_posix(), "sha256": sha256_file(output_path)},
            "macros": macros,
        }
        if provenance_path.exists() and not args.force:
            raise FileExistsError(f"refusing to overwrite existing file: {provenance_path}; pass --force")
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "output": str(output_path), "macros": len(macros)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

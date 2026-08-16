#!/usr/bin/env python3
"""Data Contract Generator from Auto-EDA.

Converts tabular data into a compliant data_contract.json matching schemas/data_contract.schema.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from auto_eda import analyze_dataframe, load_dataset

ROOT = Path(__file__).resolve().parents[2]


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def map_to_contract_dtype(raw_dtype: str) -> str:
    raw_lower = raw_dtype.lower()
    if "int" in raw_lower:
        return "integer"
    if "float" in raw_lower or "double" in raw_lower:
        return "number"
    if "bool" in raw_lower:
        return "boolean"
    if "datetime" in raw_lower:
        return "datetime"
    if "category" in raw_lower:
        return "category"
    return "string"


def generate_data_contract(
    data_file: Path,
    run_id: str = "run-001",
    data_id: str | None = None,
    layer: str = "raw",
    target_columns: list[str] | None = None,
    split_keys: list[str] | None = None,
    time_boundary: str | None = None,
) -> dict[str, Any]:
    """Build a compliant data_contract document from a data file."""
    df = load_dataset(data_file)
    target_columns = list(target_columns or [])
    split_keys = list(split_keys or [])
    missing_targets = [name for name in target_columns if name not in df.columns]
    if missing_targets:
        raise ValueError(f"target columns do not exist in data: {missing_targets}")
    missing_split_keys = [name for name in split_keys if name not in df.columns]
    if missing_split_keys:
        raise ValueError(f"split keys do not exist in data: {missing_split_keys}")
    eda = analyze_dataframe(df, data_file.name, target_columns, split_keys, time_boundary)

    file_sha = compute_sha256(data_file)
    d_id = data_id or data_file.stem
    try:
        source_path = data_file.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        source_path = data_file.as_posix()

    contract_columns = []
    for col_info in eda["columns"]:
        c_dtype = map_to_contract_dtype(col_info["raw_dtype"])
        col_role = "target" if target_columns and col_info["name"] in target_columns else col_info["role"]
        if col_role not in ("identifier", "feature", "target", "time", "group", "weight", "output", "metadata"):
            col_role = "feature"

        allowed: dict[str, Any] = {}
        if c_dtype in ("integer", "number") and "min" in col_info and "max" in col_info:
            allowed["minimum"] = col_info["min"]
            allowed["maximum"] = col_info["max"]

        contract_columns.append({
            "name": col_info["name"],
            "dtype": c_dtype,
            "semantic_type": col_info["semantic_type"],
            "unit": None,
            "nullable": col_info["missing_count"] > 0,
            "missing_count": col_info["missing_count"],
            "unique": col_info["unique_count"] == col_info["total_count"],
            "role": col_role,
            "allowed": allowed,
        })

    # Find primary keys
    pk_cols = [c["name"] for c in contract_columns if c["role"] == "identifier"]
    if not pk_cols and any(c["unique"] for c in contract_columns):
        first_uniq = next(c["name"] for c in contract_columns if c["unique"])
        pk_cols = [first_uniq]
    duplicate_key_count = int(df.duplicated(subset=pk_cols).sum()) if pk_cols else 0

    invariants = [
        {
            "invariant_id": f"INV-{d_id.upper()}-ROW-COUNT",
            "description": "Dataset must contain at least 1 record",
            "check": "row_count >= 1",
            "status": "pass" if eda["row_count"] >= 1 else "fail",
            "observed": eda["row_count"],
        },
        {
            "invariant_id": f"INV-{d_id.upper()}-NO-DUP-ROWS",
            "description": "Dataset duplicate row count sanity check",
            "check": "duplicate_rows == 0",
            "status": "pass" if eda["duplicate_rows"] == 0 else "fail",
            "observed": eda["duplicate_rows"],
        },
    ]

    time_min = eda["time_series_info"].get("min_time") if eda["time_series_info"]["has_time_series"] else None
    time_max = eda["time_series_info"].get("max_time") if eda["time_series_info"]["has_time_series"] else None

    leakage_status = eda["leakage_audit"].get("status", "not_run")
    contract_status = "validated" if leakage_status in {"pass", "not_applicable"} else "draft"
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "data_id": d_id,
        "source": {
            "path": source_path,
            "sha256": file_sha,
        },
        "layer": layer,
        "table": {
            "format": data_file.suffix.lstrip(".").lower() or "csv",
            "row_count": eda["row_count"],
            "column_count": eda["column_count"],
            "primary_key": pk_cols,
            "duplicate_key_count": duplicate_key_count,
            "encoding": "utf-8",
            "timezone": None,
        },
        "columns": contract_columns,
        "invariants": invariants,
        "leakage_policy": {
            "target_columns": target_columns or [],
            "split_keys": split_keys,
            "time_boundary": time_boundary,
            "forbidden_features": eda["leakage_audit"].get("forbidden_features", []),
            "status": leakage_status,
        },
        "profile": {
            "row_count": eda["row_count"],
            "missing_cells": eda["total_missing_cells"],
            "duplicate_rows": eda["duplicate_rows"],
            "time_min": time_min,
            "time_max": time_max,
        },
        "observation_structure_candidates": eda.get("observation_structure_candidates", []),
        "status": contract_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate data_contract.json from tabular data file.")
    parser.add_argument("data_file", help="Path to input data file (CSV/Excel/Parquet/JSON)")
    parser.add_argument("--run-id", default="run-001", help="Current run ID")
    parser.add_argument("--data-id", help="Explicit data identifier")
    parser.add_argument("--layer", default="raw", choices=["raw", "interim", "processed", "external"])
    parser.add_argument("--target", action="append", help="Target column names")
    parser.add_argument("--split-key", action="append", default=[], help="Declared split/group key names")
    parser.add_argument("--time-boundary", help="Declared train/test time boundary")
    parser.add_argument("--output", "-o", default="data_contract.json", help="Output path for data contract")

    args = parser.parse_args()
    d_file = Path(args.data_file)
    if not d_file.is_file():
        print(f"ERROR: Data file not found: {d_file}", file=sys.stderr)
        return 1

    try:
        contract = generate_data_contract(
            data_file=d_file,
            run_id=args.run_id,
            data_id=args.data_id,
            layer=args.layer,
            target_columns=args.target,
            split_keys=args.split_key,
            time_boundary=args.time_boundary,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: Could not generate data contract: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated compliant data contract at: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

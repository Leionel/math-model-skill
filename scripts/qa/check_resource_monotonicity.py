#!/usr/bin/env python3
"""Verify resource-monotonicity across nested frozen runs.

A run that uses strictly more resources (more bombs, more vehicles, more
budget, a superset of decision variables) must not report a worse objective
than its subset run. This closes the 2025-A battle failure where a 3-bomb
schedule (3.63 s) was frozen while its own 1-bomb subset achieved 4.59 s and
passed every per-run obligation.

Pairs are declared in a small spec file:

```json
{
  "pairs": [
    {
      "baseline": "results/frozen_q2.json",
      "baseline_metric": "R-Q2-DURATION",
      "superset": "results/frozen_q3.json",
      "superset_metric": "R-Q3-DURATION",
      "direction": "maximize",
      "tolerance": 0.0,
      "reason": "Q3 optimizes the same objective with 3 bombs instead of 1"
    }
  ]
}
```

No hashes are involved: this compares metric values across frozen files only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402


def metric_value(frozen: dict[str, Any], metric_id: str) -> float | None:
    for row in frozen.get("results", []):
        if isinstance(row, dict) and row.get("result_id") == metric_id:
            value = row.get("value")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="JSON file with a pairs array")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    details: list[dict[str, Any]] = []

    spec = load_structured(resolve_path(args.spec, root).resolve())
    pairs = spec.get("pairs") if isinstance(spec, dict) else spec
    if not isinstance(pairs, list) or not pairs:
        print(json.dumps({"ok": False, "errors": ["spec must contain a non-empty pairs array"], "warnings": []}, ensure_ascii=False))
        return 1

    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            errors.append(f"pairs[{index}] must be an object")
            continue
        label = pair.get("reason") or f"pairs[{index}]"
        try:
            baseline = load_structured(resolve_path(str(pair["baseline"]), root).resolve())
            superset = load_structured(resolve_path(str(pair["superset"]), root).resolve())
        except KeyError as exc:
            errors.append(f"{label}: missing key {exc}")
            continue
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{label}: cannot load frozen file: {exc}")
            continue
        if baseline.get("run_id") == superset.get("run_id"):
            errors.append(f"{label}: baseline and superset are the same run ({baseline.get('run_id')})")
            continue
        base_value = metric_value(baseline, str(pair.get("baseline_metric", "")))
        sup_value = metric_value(superset, str(pair.get("superset_metric", "")))
        if base_value is None or sup_value is None:
            errors.append(
                f"{label}: metric not found (baseline_metric={pair.get('baseline_metric')!r} -> {base_value}, "
                f"superset_metric={pair.get('superset_metric')!r} -> {sup_value})"
            )
            continue
        direction = pair.get("direction", "maximize")
        tolerance = float(pair.get("tolerance", 0.0) or 0.0)
        if direction == "maximize":
            ok = sup_value >= base_value - tolerance
            relation = f"superset {sup_value:.6g} >= baseline {base_value:.6g} - {tolerance:g}"
        elif direction == "minimize":
            ok = sup_value <= base_value + tolerance
            relation = f"superset {sup_value:.6g} <= baseline {base_value:.6g} + {tolerance:g}"
        else:
            errors.append(f"{label}: direction must be maximize or minimize")
            continue
        if not ok:
            errors.append(
                f"{label}: resource monotonicity violated ({relation}) — the superset run uses more "
                "resources but reports a worse objective than its subset run; rerun the superset "
                "optimization seeded from the subset solution"
            )
        if baseline.get("claimable") is not True:
            warnings.append(f"{label}: baseline run is not claimable; comparison is diagnostic only")
        details.append({
            "reason": label,
            "baseline_run": baseline.get("run_id"),
            "superset_run": superset.get("run_id"),
            "baseline_metric": pair.get("baseline_metric"),
            "superset_metric": pair.get("superset_metric"),
            "baseline_value": base_value,
            "superset_value": sup_value,
            "direction": direction,
            "ok": ok,
        })

    ok = not errors and (not args.strict or not warnings)
    report = {"ok": ok, "spec": rel_path(resolve_path(args.spec, root).resolve(), root), "pairs": details, "errors": errors, "warnings": warnings}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

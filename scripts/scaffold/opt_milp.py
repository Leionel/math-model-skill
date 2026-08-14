#!/usr/bin/env python3
"""Mixed-Integer Linear Programming (MILP) Modeling Scaffold.

Provides clean abstractions for formulating and solving LP/MILP problems,
capturing dual values, objective values, slack variables, and exportable results.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from scipy.optimize import linprog


def solve_lp_scipy(
    c: list[float],
    A_ub: list[list[float]] | None = None,
    b_ub: list[float] | None = None,
    A_eq: list[list[float]] | None = None,
    b_eq: list[float] | None = None,
    bounds: list[tuple[float | None, float | None]] | None = None,
    integrality: list[int] | None = None,
    maximize: bool = False,
) -> dict[str, Any]:
    """Solve LP/MILP using scipy.optimize.linprog (Highs solver)."""
    c_arr = [-x for x in c] if maximize else c

    res = linprog(
        c=c_arr,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        integrality=integrality,
        method="highs",
    )

    obj_val = -float(res.fun) if maximize and res.fun is not None else (float(res.fun) if res.fun is not None else None)

    return {
        "success": bool(res.success),
        "status_code": int(res.status),
        "status_message": str(res.message),
        "objective_value": obj_val,
        "variables": [float(x) for x in res.x] if res.x is not None else [],
        "iterations": int(res.nit) if hasattr(res, "nit") else 0,
        "slack": [float(s) for s in res.slack] if hasattr(res, "slack") and res.slack is not None else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MILP solver scaffold demo.")
    parser.add_argument("--demo", action="store_true", help="Run demo linear program")
    parser.parse_args()

    # Demo: Maximize z = 3x1 + 2x2 subject to x1 + x2 <= 4, x1 - x2 <= 2, x1,x2 >= 0
    res = solve_lp_scipy(
        c=[3.0, 2.0],
        A_ub=[[1.0, 1.0], [1.0, -1.0]],
        b_ub=[4.0, 2.0],
        bounds=[(0, None), (0, None)],
        maximize=True,
    )
    print(json.dumps(res, indent=2))
    return 0 if res["success"] else 1


if __name__ == "__main__":
    sys.exit(main())

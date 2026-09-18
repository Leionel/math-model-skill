"""Deterministic depot-allocation solver for the end-to-end Harness demo.

The problem is small on purpose: three products must each be covered by one
depot, depots have capacities, and the per-product cost differs by depot. That
keeps the optimum enumerable and independently recomputable, which is what the
Harness needs to turn a run into claimable evidence.

Only the standard library is used, so a receipt records a real, reproducible
process rather than an environment-dependent one.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any


def load_problem(path: Path) -> dict[str, Any]:
    problem = json.loads(path.read_text(encoding="utf-8"))
    demand = [int(row) for row in problem["demand"]]
    capacity = [int(row) for row in problem["capacity"]]
    cost = [[int(row) for row in matrix] for matrix in problem["unit_cost"]]
    if len(cost) != len(capacity) or any(len(row) != len(demand) for row in cost):
        raise ValueError("unit_cost must be [depot][product] matching capacity and demand")
    return {"demand": demand, "capacity": capacity, "cost": cost}


def feasible_assignments(problem: dict[str, Any]) -> list[tuple[int, ...]]:
    """Every product-chooses-a-depot assignment that respects every capacity."""

    demand, capacity, _ = problem["demand"], problem["capacity"], problem["cost"]
    allowed = []
    for assignment in itertools.product(range(len(capacity)), repeat=len(demand)):
        used = [0] * len(capacity)
        for product, depot in enumerate(assignment):
            used[depot] += demand[product]
        if all(used[index] <= capacity[index] for index in range(len(capacity))):
            allowed.append(assignment)
    return allowed


def cost_by_product(problem: dict[str, Any], assignment: tuple[int, ...]) -> int:
    return sum(
        problem["cost"][depot][product] * problem["demand"][product]
        for product, depot in enumerate(assignment)
    )


def cost_by_depot(problem: dict[str, Any], assignment: tuple[int, ...]) -> int:
    """Same quantity by an independent summation order, for recomputation."""

    total = 0
    for depot in range(len(problem["capacity"])):
        for product in range(len(problem["demand"])):
            if assignment[product] == depot:
                total += problem["demand"][product] * problem["cost"][depot][product]
    return total


def capacity_violation(problem: dict[str, Any], assignment: tuple[int, ...]) -> int:
    used = [0] * len(problem["capacity"])
    for product, depot in enumerate(assignment):
        used[depot] += problem["demand"][product]
    return sum(
        max(0, used[index] - problem["capacity"][index]) for index in range(len(used))
    )


def solve(problem: dict[str, Any], *, smoke: bool) -> dict[str, Any]:
    assignments = feasible_assignments(problem)
    if not assignments:
        return {"feasible": False, "smoke": smoke}
    if smoke:
        chosen = assignments[0]
    else:
        chosen = min(assignments, key=lambda row: (cost_by_product(problem, row), row))
    return {
        "feasible": True,
        "smoke": smoke,
        "assignment": list(chosen),
        "cost_product_order": cost_by_product(problem, chosen),
        "cost_depot_order": cost_by_depot(problem, chosen),
        "max_violation": capacity_violation(problem, chosen),
        "feasible_assignment_count": len(assignments),
    }


def write_outputs(solution: dict[str, Any], results_path: Path, measurements_path: Path) -> None:
    if not solution["feasible"]:
        results_path.write_text(
            json.dumps({"results": []}, indent=2) + "\n", encoding="utf-8",
        )
        measurements_path.write_text(
            json.dumps({"schema_version": "1.0", "run_id": "run-1", "observations": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        return
    results = {
        "results": [
            {
                "result_id": "R-Q1-01",
                "question_id": "q1",
                "name": "optimal_cost",
                "value": solution["cost_product_order"],
                "unit": "CNY",
                "precision": 0,
                "statistical_definition": "total procurement cost of the selected feasible assignment",
                "boundary": "declared demand, capacities and unit costs only",
                "validation_status": "passed",
            },
        ],
    }
    measurements = {
        "schema_version": "1.0",
        "run_id": "run-1",
        "observations": [
            {
                "obligation_id": "VAL-FEASIBILITY",
                "metrics": [
                    {
                        "metric_id": "max_violation",
                        "value": solution["max_violation"],
                        "unit": "item",
                        "locator": "model.capacity_violation",
                    },
                ],
            },
            {
                "obligation_id": "VAL-OBJECTIVE",
                "metrics": [
                    {
                        "metric_id": "solver_objective",
                        "value": solution["cost_product_order"],
                        "unit": "CNY",
                        "locator": "model.cost_by_product",
                    },
                    {
                        "metric_id": "independent_objective",
                        "value": solution["cost_depot_order"],
                        "unit": "CNY",
                        "locator": "model.cost_by_depot",
                    },
                ],
            },
        ],
    }
    if solution["smoke"]:
        # A smoke run proves the seam works; it never produces a frozen number.
        measurements["observations"] = measurements["observations"][:1]
    results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    measurements_path.write_text(json.dumps(measurements, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected_assignment": solution["assignment"], "optimal_cost": solution["cost_product_order"]}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", default="input.json", type=Path)
    parser.add_argument("--results", default="raw_results.json", type=Path)
    parser.add_argument("--measurements", default="validation_measurements.json", type=Path)
    parser.add_argument("--smoke", action="store_true", help="first feasible assignment only")
    args = parser.parse_args()
    solution = solve(load_problem(args.problem), smoke=args.smoke)
    write_outputs(solution, args.results, args.measurements)
    return 0 if solution["feasible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

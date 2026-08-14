#!/usr/bin/env python3
"""Run finite derivation-graph and equation-contract checks.

This is the first layer of the proposed math-correctness scheduler.  It is
deliberately structural: it catches orphan equations, undefined intermediates,
broken derivation chains, missing metadata, and common operation preconditions.
It does not claim symbolic equivalence or theorem proving.  Those checks are
represented as explicit UNVERIFIED/FAIL/PASS obligations in the report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


OPERATION_PRECONDITIONS = {
    # Each inner tuple is a sufficient conjunction.  Cholesky may be declared
    # against either a positive-definite or an explicitly supported
    # semidefinite factorization; one isolated word is never enough.
    "cholesky": (("symmetric", "positive definite"), ("symmetric", "positive semidefinite")),
    "inverse": (("square", "nonsingular"),),
    "inv(": (("square", "nonsingular"),),
    "log": (("positive",),),
    "sqrt": (("nonnegative",),),
    "cvar": (("random variable", "tail", "confidence", "direction"),),
}
REQUIRED_METADATA = ("equation_type", "math_risk", "symbols", "domains", "unit_signature")
STATUS_ORDER = {"PASS": 3, "UNVERIFIED": 2, "NOT_APPLICABLE": 1, "FAIL": 0}


def _status_for_check(value: Any) -> str:
    if value in {"PASS", "FAIL", "UNVERIFIED", "NOT_APPLICABLE"}:
        return value
    return "UNVERIFIED"


def _preconditions_satisfy(text: str, alternatives: tuple[tuple[str, ...], ...]) -> bool:
    folded = text.casefold()
    return any(all(term.casefold() in folded for term in alternative) for alternative in alternatives)


def _graph_cycle(nodes: set[str], edges: list[tuple[str, str]]) -> list[str] | None:
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    for source, target in edges:
        adjacency.setdefault(source, []).append(target)
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if state.get(node) == 1:
            start = stack.index(node) if node in stack else 0
            return stack[start:] + [node]
        if state.get(node) == 2:
            return None
        state[node] = 1
        stack.append(node)
        for child in adjacency.get(node, []):
            cycle = visit(child)
            if cycle:
                return cycle
        stack.pop()
        state[node] = 2
        return None

    for node in nodes:
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def _reachable(adjacency: dict[str, list[str]], starts: set[str]) -> set[str]:
    seen: set[str] = set()
    todo = list(starts)
    while todo:
        node = todo.pop()
        if node in seen:
            continue
        seen.add(node)
        todo.extend(adjacency.get(node, []))
    return seen


def evaluate_derivation_integrity(
    contract: dict[str, Any], *, require_metadata: bool = False
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    model_reports: list[dict[str, Any]] = []
    equation_count = 0
    graph_count = 0

    for model in contract.get("models", []):
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("model_id", ""))
        details = model.get("plan_details") if isinstance(model.get("plan_details"), dict) else {}
        equations = [
            row for row in details.get("equation_plan", [])
            if isinstance(row, dict) and isinstance(row.get("equation_id"), str)
        ]
        equation_count += len(equations)
        equation_ids = {row["equation_id"] for row in equations}
        declared_symbols = {
            str(row.get("symbol"))
            for row in model.get("variables", [])
            if isinstance(row, dict) and isinstance(row.get("symbol"), str)
        }
        declared_symbols.update(
            str(row.get("parameter"))
            for row in details.get("parameter_plan", [])
            if isinstance(row, dict) and isinstance(row.get("parameter"), str)
        )
        declared_symbols.update(str(item) for item in model.get("inputs", []) if isinstance(item, str))
        for equation in equations:
            declared_symbols.update(
                str(item) for item in equation.get("outputs", []) if isinstance(item, str)
            )
        graph = details.get("derivation_graph")
        if isinstance(graph, dict):
            for node in graph.get("nodes", []):
                if isinstance(node, dict):
                    declared_symbols.update(
                        str(item) for item in node.get("outputs", []) if isinstance(item, str)
                    )

        local_errors: list[str] = []
        local_warnings: list[str] = []
        equation_checks: list[dict[str, Any]] = []
        for equation in equations:
            equation_id = equation["equation_id"]
            eq_errors: list[str] = []
            eq_warnings: list[str] = []
            if require_metadata:
                for field in REQUIRED_METADATA:
                    if field not in equation:
                        eq_errors.append(f"missing equation metadata: {field}")
                if equation.get("math_risk") == "high" and not equation.get("preconditions"):
                    eq_errors.append("high-risk equation requires preconditions")
                verification = equation.get("verification")
                if not isinstance(verification, dict) or not verification:
                    eq_errors.append("formal equation contract requires verification statuses")
            symbols = equation.get("symbols", [])
            if isinstance(symbols, list):
                unknown_symbols = sorted(set(symbols) - declared_symbols)
                if unknown_symbols:
                    eq_errors.append(f"UNDEFINED_SYMBOL: {unknown_symbols}")
            variables = equation.get("variables", [])
            if isinstance(variables, list) and isinstance(symbols, list) and symbols:
                missing_symbols = sorted(set(variables) - set(symbols))
                if missing_symbols:
                    eq_errors.append(f"equation.variables missing from symbols: {missing_symbols}")

            expression = " ".join(
                str(equation.get(key, "")) for key in ("purpose", "expression_or_derivation", "transformation_rule")
            )
            preconditions = " ".join(str(item) for item in equation.get("preconditions", []))
            for operation, alternatives in OPERATION_PRECONDITIONS.items():
                if operation in expression.casefold() and not _preconditions_satisfy(preconditions, alternatives):
                    message = f"missing complete precondition metadata for {operation}: {alternatives}"
                    (eq_errors if require_metadata else eq_warnings).append(message)

            verification = equation.get("verification") if isinstance(equation.get("verification"), dict) else {}
            failed_checks = [
                key for key, value in verification.items()
                if key.endswith("_check") and _status_for_check(value) == "FAIL"
            ]
            if failed_checks:
                eq_errors.append(f"verification checks FAIL: {failed_checks}")
            unverified_checks = [
                key for key, value in verification.items()
                if key.endswith("_check") and _status_for_check(value) == "UNVERIFIED"
            ]
            if unverified_checks:
                eq_warnings.append(f"verification checks UNVERIFIED: {unverified_checks}")
            equation_status = "FAIL" if eq_errors else ("UNVERIFIED" if eq_warnings else "PASS")
            equation_checks.append({
                "equation_id": equation_id,
                "math_risk": equation.get("math_risk", "UNVERIFIED"),
                "equation_type": equation.get("equation_type", "UNVERIFIED"),
                "status": equation_status,
                "errors": eq_errors,
                "warnings": eq_warnings,
            })
            local_errors.extend(f"{equation_id}: {message}" for message in eq_errors)
            local_warnings.extend(f"{equation_id}: {message}" for message in eq_warnings)

        graph = details.get("derivation_graph")
        if not isinstance(graph, dict):
            message = "UNVERIFIED: plan_details.derivation_graph is absent"
            (local_errors if require_metadata else local_warnings).append(message)
            model_reports.append({"model_id": model_id, "status": "FAIL" if require_metadata else "UNVERIFIED", "equations": equation_checks})
            errors.extend(f"model {model_id}: {message}" for message in ([message] if require_metadata else []))
            warnings.extend(f"model {model_id}: {message}" for message in ([] if require_metadata else [message]))
            continue

        graph_count += 1
        nodes = [row for row in graph.get("nodes", []) if isinstance(row, dict) and isinstance(row.get("id"), str)]
        node_by_id: dict[str, dict[str, Any]] = {}
        for node in nodes:
            node_id = node["id"]
            if node_id in node_by_id:
                local_errors.append(f"duplicate derivation node: {node_id}")
            node_by_id[node_id] = node
        node_ids = set(node_by_id)
        edges: list[tuple[str, str]] = []
        for edge in graph.get("edges", []):
            if not isinstance(edge, list) or len(edge) != 2 or not all(isinstance(item, str) for item in edge):
                local_errors.append(f"invalid derivation edge: {edge!r}")
                continue
            source, target = edge
            edges.append((source, target))
            if source not in node_ids or target not in node_ids:
                local_errors.append(f"derivation edge references unknown node: {edge!r}")
        cycle = _graph_cycle(node_ids, edges)
        if cycle:
            local_errors.append("BROKEN_DERIVATION_CHAIN: cycle " + " -> ".join(cycle))

        source_node_ids = set(graph.get("source_node_ids", [])) if graph.get("source_node_ids") else set()
        terminal_node_ids = set(graph.get("terminal_node_ids", [])) if graph.get("terminal_node_ids") else set()
        unknown_sources = sorted(source_node_ids - node_ids)
        unknown_terminals = sorted(terminal_node_ids - node_ids)
        if unknown_sources:
            local_errors.append(f"source_node_ids reference unknown nodes: {unknown_sources}")
        if unknown_terminals:
            local_errors.append(f"terminal_node_ids reference unknown nodes: {unknown_terminals}")

        equation_node_ids: set[str] = set()
        for node_id, node in node_by_id.items():
            equation_node_ids.add(str(node.get("equation_id", node_id)))
        missing_nodes = sorted(equation_ids - equation_node_ids)
        if missing_nodes:
            local_errors.append(f"missing derivation nodes for equations: {missing_nodes}")

        incoming = {node_id: 0 for node_id in node_ids}
        adjacency = {node_id: [] for node_id in node_ids}
        for source, target in edges:
            if source in node_ids and target in node_ids:
                adjacency[source].append(target)
                incoming[target] += 1
        source_node_ids = source_node_ids or {
            node_id for node_id, count in incoming.items() if count == 0
        }
        if not source_node_ids:
            local_errors.append("BROKEN_DERIVATION_CHAIN: no source node")
        declared_sources = set(declared_symbols) | set(str(item) for item in model.get("inputs", []) if isinstance(item, str))
        produced: set[str] = set(declared_sources)
        topo_indegree = dict(incoming)
        topo_queue = [node_id for node_id, count in topo_indegree.items() if count == 0]
        topological_order: list[str] = []
        while topo_queue:
            node_id = topo_queue.pop(0)
            topological_order.append(node_id)
            for child in adjacency.get(node_id, []):
                topo_indegree[child] -= 1
                if topo_indegree[child] == 0:
                    topo_queue.append(child)
        # A cycle has already been reported above; retain every node here so
        # the remaining checks still produce useful diagnostics.
        topological_order.extend(node_id for node_id in node_ids if node_id not in topological_order)
        for node_id in topological_order:
            node = node_by_id[node_id]
            node_inputs = {str(item) for item in node.get("inputs", []) if isinstance(item, str)}
            node_outputs = {str(item) for item in node.get("outputs", []) if isinstance(item, str)}
            predecessors = {source for source, target in edges if target == node_id}
            output_producers = {
                output: producer_id
                for producer_id, producer in node_by_id.items()
                for output in producer.get("outputs", [])
                if isinstance(output, str)
            }
            missing_edges = sorted(
                item for item in node_inputs
                if item in output_producers and output_producers[item] not in predecessors
            )
            if missing_edges:
                local_errors.append(
                    f"MISSING_DERIVATION_EDGE at {node.get('id')}: inputs {missing_edges} "
                    "are produced upstream but no corresponding graph edge exists"
                )
            unknown_inputs = sorted(item for item in node_inputs if item not in produced and item not in node_ids and item not in equation_ids)
            if unknown_inputs:
                local_errors.append(f"UNDEFINED_INTERMEDIATE at {node.get('id')}: {unknown_inputs}")
            produced.update(node_outputs)

        objective_nodes = {
            node_id for node_id, node in node_by_id.items()
            if node.get("type") in {"objective", "objective_component"}
            or node.get("equation_id") in {
                row.get("equation_id") for row in equations if row.get("equation_type") == "objective"
            }
        }
        terminal_nodes = set(graph.get("terminal_node_ids", [])) if graph.get("terminal_node_ids") else objective_nodes
        if not objective_nodes and require_metadata:
            local_errors.append("UNVERIFIED: derivation graph has no objective terminal")
        reachable = _reachable(adjacency, source_node_ids)
        unreachable = sorted(node_ids - reachable)
        if unreachable:
            local_errors.append(f"BROKEN_DERIVATION_CHAIN: unreachable nodes {unreachable}")
        reverse: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for source, target in edges:
            if source in node_ids and target in node_ids:
                reverse[target].append(source)
        reaches_terminal = _reachable(reverse, terminal_nodes) if terminal_nodes else set()
        orphan = sorted(node_ids - reaches_terminal)
        if orphan:
            local_errors.append(f"UNUSED_MECHANISM/ORPHAN_EQUATION: {orphan}")

        model_status = "FAIL" if local_errors else ("UNVERIFIED" if local_warnings else "PASS")
        model_reports.append({
            "model_id": model_id,
            "status": model_status,
            "equations": equation_checks,
            "derivation_graph": {
                "node_count": len(node_ids),
                "edge_count": len(edges),
                "source_nodes": sorted(source_node_ids),
                "objective_nodes": sorted(objective_nodes),
            },
        })
        errors.extend(f"model {model_id}: {message}" for message in local_errors)
        warnings.extend(f"model {model_id}: {message}" for message in local_warnings)

    details = {
        "status_vocabulary": ["PASS", "FAIL", "UNVERIFIED", "NOT_APPLICABLE"],
        "model_count": len(model_reports),
        "equation_count": equation_count,
        "derivation_graph_count": graph_count,
        "models": model_reports,
        "math_validation_level": "L1_structural" if not errors and require_metadata else "L0_declared_or_unverified",
    }
    return errors, warnings, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--require-metadata", action="store_true")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    contract_path = resolve_path(args.model_contract, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        contract, schema_errors, _ = _validate_document(
            contract_path, Path(__file__).resolve().parents[2] / "schemas" / "model_contract.schema.json"
        )
        errors.extend(f"model_contract schema: {message}" for message in schema_errors)
        if not isinstance(contract, dict):
            raise ValueError("model contract must be an object")
        semantic_errors, semantic_warnings, details = evaluate_derivation_integrity(
            contract, require_metadata=args.require_metadata
        )
        errors.extend(semantic_errors)
        warnings.extend(semantic_warnings)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "model_contract": rel_path(contract_path, root),
        "require_metadata": args.require_metadata,
        "details": details,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

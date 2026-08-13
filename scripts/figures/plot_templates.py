#!/usr/bin/env python3
"""Render evidence-oriented paper figures from tidy CSV/JSON using controlled templates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path, sha256_file, write_json  # noqa: E402


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        return value
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return [row for row in value["rows"] if isinstance(row, dict)]
    raise ValueError("input must be a CSV, an array of row objects, or {'rows': [...]} JSON")


def numeric(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"field {field!r} contains non-numeric value {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"field {field!r} contains non-finite value")
    return result


def canonical_args(args: argparse.Namespace) -> dict[str, Any]:
    excluded = {"project_root", "input", "output", "receipt", "force"}
    return {key: value for key, value in sorted(vars(args).items()) if key not in excluded}


def deterministic_generated_at(source_date_epoch: str | None) -> str:
    if source_date_epoch is None:
        return "deterministic-unspecified"
    try:
        seconds = int(source_date_epoch)
    except ValueError as exc:
        raise ValueError("SOURCE_DATE_EPOCH must be an integer") from exc
    from datetime import datetime, timezone

    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def series_groups(rows: list[dict[str, Any]], field: str | None) -> list[tuple[str, list[dict[str, Any]]]]:
    if not field:
        return [("", rows)]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get(field, ""))
        groups.setdefault(key, []).append(row)
    return sorted(groups.items())


def set_paper_axes(ax: Any, *, title: str | None, xlabel: str | None, ylabel: str | None) -> None:
    if title:
        ax.set_title(title, loc="left", fontweight="semibold", pad=8)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.margins(x=0.02)


def plot_line(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    for label, group in series_groups(rows, args.group):
        x = [row[args.x] for row in group]
        y = [numeric(row[args.y], args.y) for row in group]
        ax.plot(x, y, marker="o" if len(group) <= 20 else None, label=label or None)
        if args.low and args.high:
            low = [numeric(row[args.low], args.low) for row in group]
            high = [numeric(row[args.high], args.high) for row in group]
            ax.fill_between(x, low, high, alpha=0.18, linewidth=0)
    if args.group:
        ax.legend(ncol=min(3, len(series_groups(rows, args.group))))


def plot_comparison(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    values = [(str(row[args.category]), numeric(row[args.y], args.y)) for row in rows]
    if args.sort:
        values.sort(key=lambda item: item[1])
    labels, y = zip(*values, strict=True)
    positions = range(len(values))
    ax.scatter(y, positions, s=34, zorder=3)
    ax.hlines(positions, 0, y, linewidth=1, color="#BBBBBB", zorder=1)
    ax.set_yticks(list(positions), labels)
    for value, position in zip(y, positions, strict=True):
        ax.annotate(f"{value:g}", (value, position), xytext=(5, 0), textcoords="offset points", va="center")
    ax.axvline(0, color="#777777", linewidth=0.8)


def plot_distribution(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    groups = series_groups(rows, args.group)
    if args.mode == "ecdf":
        for label, group in groups:
            values = sorted(numeric(row[args.x], args.x) for row in group)
            probabilities = [(index + 1) / len(values) for index in range(len(values))]
            ax.step(values, probabilities, where="post", label=label or None)
        ax.set_ylabel("Empirical cumulative probability")
    else:
        for label, group in groups:
            values = [numeric(row[args.x], args.x) for row in group]
            ax.hist(values, bins=args.bins, alpha=0.55, density=args.density, label=label or None)
    if args.group:
        ax.legend()


def plot_scatter(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    for label, group in series_groups(rows, args.group):
        x = [numeric(row[args.x], args.x) for row in group]
        y = [numeric(row[args.y], args.y) for row in group]
        ax.scatter(x, y, alpha=0.75, edgecolor="white", linewidth=0.35, label=label or None)
    if args.group:
        ax.legend()
    if args.identity:
        bounds = [*ax.get_xlim(), *ax.get_ylim()]
        low, high = min(bounds), max(bounds)
        ax.plot([low, high], [low, high], linestyle="--", color="#777777", linewidth=1)


def plot_sensitivity(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    values = [(str(row[args.category]), numeric(row[args.y], args.y)) for row in rows]
    values.sort(key=lambda item: abs(item[1]))
    labels, effects = zip(*values, strict=True)
    colors = ["#D55E00" if value < 0 else "#0072B2" for value in effects]
    ax.barh(range(len(values)), effects, color=colors, alpha=0.9)
    ax.set_yticks(range(len(values)), labels)
    ax.axvline(0, color="#222222", linewidth=0.8)


def plot_pareto(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    for row in rows:
        x, y = numeric(row[args.x], args.x), numeric(row[args.y], args.y)
        nondominated = str(row.get(args.pareto_flag, "")).casefold() in {"true", "1", "yes", "pass"}
        ax.scatter(
            [x], [y], s=48 if nondominated else 26,
            marker="o" if nondominated else "x",
            color="#0072B2" if nondominated else "#999999",
            alpha=0.95 if nondominated else 0.65,
        )
        if args.label:
            ax.annotate(str(row.get(args.label, "")), (x, y), xytext=(4, 4), textcoords="offset points")


def plot_heatmap(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    import numpy as np

    x_values = list(dict.fromkeys(str(row[args.x]) for row in rows))
    y_values = list(dict.fromkeys(str(row[args.y]) for row in rows))
    lookup = {(str(row[args.x]), str(row[args.y])): numeric(row[args.value], args.value) for row in rows}
    matrix = np.full((len(y_values), len(x_values)), np.nan)
    for y_index, y_value in enumerate(y_values):
        for x_index, x_value in enumerate(x_values):
            if (x_value, y_value) in lookup:
                matrix[y_index, x_index] = lookup[(x_value, y_value)]
    image = ax.imshow(matrix, aspect="auto", cmap=args.cmap)
    ax.set_xticks(range(len(x_values)), x_values)
    ax.set_yticks(range(len(y_values)), y_values)
    ax.figure.colorbar(image, ax=ax, shrink=0.86, label=args.value_label or args.value)
    if args.annotate and matrix.size <= 100:
        for y_index in range(matrix.shape[0]):
            for x_index in range(matrix.shape[1]):
                value = matrix[y_index, x_index]
                if math.isfinite(value):
                    ax.text(x_index, y_index, f"{value:g}", ha="center", va="center", fontsize=7)


def plot_network(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    try:
        import networkx as nx
    except ImportError as exc:
        raise ValueError("network template requires optional dependency networkx") from exc
    graph = nx.DiGraph() if args.directed else nx.Graph()
    for row in rows:
        graph.add_edge(str(row[args.source]), str(row[args.target]), weight=numeric(row.get(args.weight, 1), args.weight))
    positions = nx.spring_layout(graph, seed=args.seed, weight="weight")
    degrees = dict(graph.degree())
    nx.draw_networkx_nodes(graph, positions, node_size=[80 + 25 * degrees[node] for node in graph], node_color="#56B4E9", edgecolors="white", ax=ax)
    nx.draw_networkx_edges(graph, positions, alpha=0.45, arrows=args.directed, ax=ax)
    nx.draw_networkx_labels(graph, positions, font_size=7, ax=ax)
    ax.set_axis_off()


PLOTTERS = {
    "line": plot_line,
    "comparison": plot_comparison,
    "distribution": plot_distribution,
    "scatter": plot_scatter,
    "sensitivity": plot_sensitivity,
    "pareto": plot_pareto,
    "heatmap": plot_heatmap,
    "network": plot_network,
}


def validate_arguments(args: argparse.Namespace) -> None:
    required = {
        "line": ("x", "y"), "comparison": ("category", "y"), "distribution": ("x",),
        "scatter": ("x", "y"), "sensitivity": ("category", "y"), "pareto": ("x", "y", "pareto_flag"),
        "heatmap": ("x", "y", "value"), "network": ("source", "target"),
    }[args.template]
    missing = [name for name in required if not getattr(args, name)]
    if missing:
        raise ValueError(f"template {args.template} requires: {', '.join('--' + name.replace('_', '-') for name in missing)}")
    if bool(args.low) != bool(args.high):
        raise ValueError("--low and --high must be supplied together")
    if args.output_format == "raster" and Path(args.output).suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        raise ValueError("output_format=raster requires PNG/JPEG/TIFF output")
    if args.output_format == "vector" and Path(args.output).suffix.lower() not in {".pdf", ".svg", ".eps"}:
        raise ValueError("output_format=vector requires PDF/SVG/EPS output")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", choices=sorted(PLOTTERS), required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--x")
    parser.add_argument("--y")
    parser.add_argument("--category")
    parser.add_argument("--group")
    parser.add_argument("--low")
    parser.add_argument("--high")
    parser.add_argument("--value")
    parser.add_argument("--value-label")
    parser.add_argument("--source")
    parser.add_argument("--target")
    parser.add_argument("--weight", default="weight")
    parser.add_argument("--pareto-flag")
    parser.add_argument("--label")
    parser.add_argument("--title")
    parser.add_argument("--xlabel")
    parser.add_argument("--ylabel")
    parser.add_argument("--mode", choices=("hist", "ecdf"), default="hist")
    parser.add_argument("--bins", type=int, default=20)
    parser.add_argument("--density", action="store_true")
    parser.add_argument("--sort", action="store_true")
    parser.add_argument("--identity", action="store_true")
    parser.add_argument("--annotate", action="store_true")
    parser.add_argument("--cmap", default="viridis")
    parser.add_argument("--directed", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--width", type=float, default=6.4)
    parser.add_argument("--height", type=float, default=3.8)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--style", default="assets/styles/mathmodel.mplstyle")
    parser.add_argument("--output-format", choices=("auto", "vector", "raster"), default="auto")
    parser.add_argument("--source-date-epoch", help="optional integer timestamp for deterministic provenance")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    input_path = resolve_path(args.input, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    receipt_path = resolve_path(args.receipt, root).resolve()
    style_path = resolve_path(args.style, root).resolve()
    try:
        validate_arguments(args)
        rows = load_rows(input_path)
        if not rows:
            raise ValueError("input has no rows")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        if style_path.is_file():
            plt.style.use(style_path)
        figure, ax = plt.subplots(figsize=(args.width, args.height), constrained_layout=True)
        PLOTTERS[args.template](ax, rows, args)
        set_paper_axes(ax, title=args.title, xlabel=args.xlabel, ylabel=args.ylabel)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and not args.force:
            raise FileExistsError(f"refusing to overwrite existing file: {output_path}; pass --force")
        save_metadata = {"Creator": "math-modeling evidence plot template"}
        if output_path.suffix.lower() == ".pdf":
            save_metadata.update({"CreationDate": None, "ModDate": None})
        figure.savefig(output_path, dpi=args.dpi, metadata=save_metadata)
        plt.close(figure)
        argument_contract = canonical_args(args)
        argument_sha256 = hashlib.sha256(
            json.dumps(argument_contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        receipt = {
            "schema_version": "1.0",
            "template": args.template,
            "generated_at": deterministic_generated_at(args.source_date_epoch),
            "input": {"path": rel_path(input_path, root), "sha256": sha256_file(input_path)},
            "output": {"path": rel_path(output_path, root), "sha256": sha256_file(output_path)},
            "style": {"path": rel_path(style_path, root), "sha256": sha256_file(style_path)} if style_path.is_file() else None,
            "rows": len(rows),
            "fields": {key: getattr(args, key) for key in ("x", "y", "category", "group", "low", "high", "value", "source", "target", "weight", "pareto_flag", "label") if getattr(args, key)},
            "render": {"width_in": args.width, "height_in": args.height, "dpi": args.dpi, "seed": args.seed},
            "arguments": argument_contract,
            "arguments_sha256": argument_sha256,
        }
        write_json(receipt_path, receipt, overwrite=args.force)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "template": args.template, "output": rel_path(output_path, root), "receipt": rel_path(receipt_path, root)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

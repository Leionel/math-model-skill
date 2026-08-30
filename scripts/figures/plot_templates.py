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

MM_PER_INCH = 25.4
PAPER_PLACEMENTS: dict[str, dict[str, float | int]] = {
    "single_column": {
        "width_mm": 85.0,
        "height_mm": 58.0,
        "font_size_pt": 7.4,
        "line_width_pt": 1.0,
        "marker_size_pt": 3.2,
        "annotation_limit": 5,
        "legend_max_rows": 1,
    },
    "half_width": {
        "width_mm": 90.0,
        "height_mm": 64.0,
        "font_size_pt": 7.7,
        "line_width_pt": 1.05,
        "marker_size_pt": 3.4,
        "annotation_limit": 6,
        "legend_max_rows": 1,
    },
    "full_width": {
        "width_mm": 180.0,
        "height_mm": 92.0,
        "font_size_pt": 9.0,
        "line_width_pt": 1.3,
        "marker_size_pt": 4.2,
        "annotation_limit": 12,
        "legend_max_rows": 2,
    },
    "full_page": {
        "width_mm": 180.0,
        "height_mm": 220.0,
        "font_size_pt": 9.2,
        "line_width_pt": 1.3,
        "marker_size_pt": 4.4,
        "annotation_limit": 14,
        "legend_max_rows": 2,
    },
}


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

def is_truthy(value: Any) -> bool:
    return str(value).casefold() in {"true", "1", "yes", "pass", "selected"}


def resolve_render_settings(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve a final paper footprint without changing legacy --width/--height use."""
    if args.paper_placement:
        preset = PAPER_PLACEMENTS[args.paper_placement]
        width_mm = float(preset["width_mm"])
        height_mm = float(preset["height_mm"])
        return {
            "sizing_mode": "placement",
            "paper_placement": args.paper_placement,
            "target_width_mm": width_mm,
            "target_height_mm": height_mm,
            "width_in": width_mm / MM_PER_INCH,
            "height_in": height_mm / MM_PER_INCH,
            "font_size_pt": float(preset["font_size_pt"]),
            "line_width_pt": float(preset["line_width_pt"]),
            "marker_size_pt": float(preset["marker_size_pt"]),
            "annotation_limit": int(preset["annotation_limit"]),
            "legend_max_rows": int(preset["legend_max_rows"]),
            "auto_scaled": True,
        }
    if args.target_width_mm is not None:
        width_mm = args.target_width_mm
        height_mm = width_mm * args.height / args.width
        scale = math.sqrt(width_mm / 85.0)
        return {
            "sizing_mode": "target_width_mm",
            "paper_placement": None,
            "target_width_mm": width_mm,
            "target_height_mm": height_mm,
            "width_in": width_mm / MM_PER_INCH,
            "height_in": height_mm / MM_PER_INCH,
            "font_size_pt": min(10.0, max(7.0, 7.4 * scale)),
            "line_width_pt": min(1.4, max(0.85, 1.0 * scale)),
            "marker_size_pt": min(5.0, max(3.0, 3.2 * scale)),
            "annotation_limit": max(4, min(14, round(width_mm / 15.0))),
            "legend_max_rows": 1 if width_mm < 120.0 else 2,
            "auto_scaled": True,
        }
    return {
        "sizing_mode": "legacy",
        "paper_placement": None,
        "target_width_mm": None,
        "target_height_mm": None,
        "width_in": args.width,
        "height_in": args.height,
        "font_size_pt": None,
        "line_width_pt": 1.4,
        "marker_size_pt": 4.0,
        "annotation_limit": 12,
        "legend_max_rows": None,
        "auto_scaled": False,
    }


def apply_render_defaults(plt: Any, settings: dict[str, Any]) -> None:
    if not settings["auto_scaled"]:
        return
    font_size = settings["font_size_pt"]
    plt.rcParams.update(
        {
            "font.size": font_size,
            "axes.titlesize": font_size * 1.08,
            "axes.labelsize": font_size,
            "xtick.labelsize": font_size * 0.9,
            "ytick.labelsize": font_size * 0.9,
            "legend.fontsize": font_size * 0.9,
            "lines.linewidth": settings["line_width_pt"],
            "lines.markersize": settings["marker_size_pt"],
        }
    )


def annotation_indices(count: int, limit: int) -> list[int]:
    if count <= limit:
        return list(range(count))
    if limit <= 1:
        return [0]
    return sorted({round(index * (count - 1) / (limit - 1)) for index in range(limit)})


def annotation_limit(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    return args.annotation_limit if args.annotation_limit is not None else settings["annotation_limit"]


def marker_area(settings: dict[str, Any], reference: float) -> float:
    return reference * (settings["marker_size_pt"] / 3.2) ** 2



def format_delta(left: float, right: float, mode: str) -> str:
    delta = right - left
    if mode == "percent" and left != 0:
        return f"Δ = {delta / abs(left):+.1%}"
    return f"Δ = {delta:+g}"


def coerce_axis_value(rows: list[dict[str, Any]], field: str, value: str) -> float | str:
    try:
        for row in rows:
            numeric(row[field], field)
    except ValueError:
        return value
    return numeric(value, field)


def add_prediction_annotations(
    ax: Any,
    rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> None:
    if args.train_test_boundary is None:
        return
    boundary = coerce_axis_value(rows, args.x, args.train_test_boundary)
    boundary_x = ax.convert_xunits(boundary)
    ax.axvline(boundary_x, color="#777777", linestyle="--", linewidth=0.8)
    ax.axvspan(boundary_x, ax.get_xlim()[1], color="#BBBBBB", alpha=0.14, label=args.forecast_label)


def add_annotation_guides(ax: Any, args: argparse.Namespace, template: str) -> None:
    horizontal_value_templates = {"comparison", "dumbbell", "interval_comparison", "sensitivity"}
    if args.baseline is not None:
        reference = ax.axvline if template in horizontal_value_templates else ax.axhline
        reference(args.baseline, color="#777777", linestyle="--", linewidth=0.8, label="Baseline")
    if args.stable_range:
        lower, upper = args.stable_range
        ax.axvspan(lower, upper, color="#009E73", alpha=0.12, label="Stable region")
    if args.failure_boundary is not None:
        ax.axvline(
            args.failure_boundary,
            color="#D55E00",
            linestyle="--",
            linewidth=0.9,
            label="Failure boundary",
        )


def finalize_legend(ax: Any, settings: dict[str, Any], *, default_columns: int) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    if settings["legend_max_rows"] is None:
        columns = min(default_columns, len(handles))
    else:
        columns = max(1, math.ceil(len(handles) / settings["legend_max_rows"]))
    ax.legend(handles, labels, ncol=columns)


def canonical_args(args: argparse.Namespace) -> dict[str, Any]:
    excluded = {"project_root", "input", "output", "receipt", "force", "render_settings"}
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
    for index, (label, group) in enumerate(series_groups(rows, args.group)):
        x = [row[args.x] for row in group]
        y = [numeric(row[args.y], args.y) for row in group]
        ax.plot(
            x,
            y,
            marker="o" if len(group) <= 20 else None,
            label=label or None,
            linewidth=args.render_settings["line_width_pt"],
            markersize=args.render_settings["marker_size_pt"],
        )
        if args.low and args.high:
            low = [numeric(row[args.low], args.low) for row in group]
            high = [numeric(row[args.high], args.high) for row in group]
            ax.fill_between(
                x,
                low,
                high,
                alpha=0.18,
                linewidth=0,
                label=args.uncertainty_label if index == 0 else None,
            )
    add_prediction_annotations(ax, rows, args)
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


def distribution_groups(
    rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[tuple[str, list[float]]]:
    """Return deterministic category/value groups for distribution charts."""

    value_field = args.y or args.x
    category_field = args.category or args.group
    if not category_field:
        return [(args.value_label or "All observations", [numeric(row[value_field], value_field) for row in rows])]
    return [
        (label, [numeric(row[value_field], value_field) for row in group])
        for label, group in series_groups(rows, category_field)
    ]


def deterministic_jitter(label: str, index: int, seed: int, width: float) -> float:
    digest = hashlib.sha256(f"{seed}:{label}:{index}".encode("utf-8")).digest()
    fraction = int.from_bytes(digest[:8], "big") / (2**64 - 1)
    return (fraction * 2 - 1) * width


def raw_point_overlay(
    ax: Any,
    groups: list[tuple[str, list[float]]],
    args: argparse.Namespace,
    *,
    label: str = "Raw observations",
) -> None:
    for position, (group_label, values) in enumerate(groups, start=1):
        offsets = [
            position + deterministic_jitter(group_label, index, args.seed, args.point_jitter)
            for index in range(len(values))
        ]
        ax.scatter(
            offsets,
            values,
            s=marker_area(args.render_settings, 20),
            color="#333333",
            alpha=0.58,
            linewidth=0,
            zorder=4,
            label=label if position == 1 else None,
        )


def plot_small_multiples(
    ax: Any,
    rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[Any]:
    """Facet grouped trend rows into compact, shared-scale panels."""

    figure = ax.figure
    ax.remove()
    groups = series_groups(rows, args.group)
    columns = min(args.facet_columns, len(groups))
    panel_rows = math.ceil(len(groups) / columns)
    grid = figure.add_gridspec(panel_rows, columns)
    axes: list[Any] = []
    for index, (label, group) in enumerate(groups):
        panel = figure.add_subplot(
            grid[index // columns, index % columns],
            sharex=axes[0] if axes else None,
            sharey=axes[0] if axes else None,
        )
        x = [row[args.x] for row in group]
        y = [numeric(row[args.y], args.y) for row in group]
        panel.plot(
            x,
            y,
            marker="o" if len(group) <= 20 else None,
            linewidth=args.render_settings["line_width_pt"],
            markersize=args.render_settings["marker_size_pt"],
        )
        if args.low and args.high:
            lower = [numeric(row[args.low], args.low) for row in group]
            upper = [numeric(row[args.high], args.high) for row in group]
            panel.fill_between(x, lower, upper, alpha=0.18, linewidth=0)
        add_prediction_annotations(panel, group, args)
        panel.set_title(label or f"Series {index + 1}", loc="left", fontweight="semibold", pad=6)
        axes.append(panel)
    return axes


def plot_violin(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    groups = distribution_groups(rows, args)
    labels, values = zip(*groups, strict=True)
    artists = ax.violinplot(values, showmeans=False, showmedians=True, widths=0.78)
    for index, body in enumerate(artists["bodies"]):
        body.set_facecolor(("#0072B2", "#D55E00", "#009E73", "#CC79A7")[index % 4])
        body.set_edgecolor("white")
        body.set_alpha(0.72)
    for key in ("cmedians", "cbars", "cmins", "cmaxes"):
        artists[key].set_color("#444444")
        artists[key].set_linewidth(args.render_settings["line_width_pt"])
    ax.set_xticks(range(1, len(labels) + 1), labels)
    if args.show_points:
        raw_point_overlay(ax, groups, args)


def plot_box(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    groups = distribution_groups(rows, args)
    labels, values = zip(*groups, strict=True)
    artists = ax.boxplot(
        values,
        patch_artist=True,
        labels=labels,
        medianprops={"color": "#222222", "linewidth": args.render_settings["line_width_pt"]},
    )
    for index, box in enumerate(artists["boxes"]):
        box.set_facecolor(("#56B4E9", "#E69F00", "#009E73", "#CC79A7")[index % 4])
        box.set_alpha(0.72)
    if args.show_points:
        raw_point_overlay(ax, groups, args)


def swarm_offsets(values: list[float], *, width: float = 0.34) -> list[float]:
    """Place close observations on alternating lanes without a seaborn dependency."""

    offsets = [0.0] * len(values)
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    span = max(values) - min(values)
    proximity = max(span / max(12, len(values) * 2), 1e-12)
    run_index = 0
    previous: float | None = None
    for original_index, value in ordered:
        if previous is None or value - previous > proximity:
            run_index = 0
        elif run_index == 0:
            run_index = 1
        else:
            run_index += 1
        if run_index == 0:
            offsets[original_index] = 0.0
        else:
            lane = (run_index + 1) // 2
            direction = -1 if run_index % 2 else 1
            offsets[original_index] = direction * min(width, lane * 0.085)
        previous = value
    return offsets


def plot_beeswarm(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    groups = distribution_groups(rows, args)
    for position, (label, values) in enumerate(groups, start=1):
        offsets = [position + offset for offset in swarm_offsets(values)]
        ax.scatter(
            offsets,
            values,
            s=marker_area(args.render_settings, 25),
            color="#0072B2",
            alpha=0.78,
            edgecolor="white",
            linewidth=0.35,
        )
    ax.set_xticks(range(1, len(groups) + 1), [label for label, _ in groups])


def plot_strip(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    groups = distribution_groups(rows, args)
    colors = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")
    for position, (label, values) in enumerate(groups, start=1):
        offsets = [
            position + deterministic_jitter(label, index, args.seed, args.point_jitter)
            for index in range(len(values))
        ]
        ax.scatter(
            offsets,
            values,
            s=marker_area(args.render_settings, 22),
            color=colors[(position - 1) % len(colors)],
            alpha=0.7,
            edgecolor="white",
            linewidth=0.3,
        )
    ax.set_xticks(range(1, len(groups) + 1), [label for label, _ in groups])
def plot_sensitivity(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    values = [(str(row[args.category]), numeric(row[args.y], args.y)) for row in rows]
    values.sort(key=lambda item: abs(item[1]))
    labels, effects = zip(*values, strict=True)
    colors = ["#D55E00" if value < 0 else "#0072B2" for value in effects]
    ax.barh(range(len(values)), effects, color=colors, alpha=0.9)
    ax.set_yticks(range(len(values)), labels)
    ax.axvline(0, color="#222222", linewidth=0.8)



def plot_dumbbell(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    values = [
        (str(row[args.category]), numeric(row[args.x], args.x), numeric(row[args.y], args.y))
        for row in rows
    ]
    if args.sort:
        values.sort(key=lambda item: item[2])
    labels, left, right = zip(*values, strict=True)
    positions = list(range(len(values)))
    for position, start, end in zip(positions, left, right, strict=True):
        ax.hlines(
            position,
            start,
            end,
            color="#999999",
            linewidth=args.render_settings["line_width_pt"],
            zorder=1,
        )
    area = marker_area(args.render_settings, 30)
    ax.scatter(left, positions, s=area, color="#0072B2", zorder=3, label=args.left_label or args.x)
    ax.scatter(right, positions, s=area, color="#D55E00", zorder=3, label=args.right_label or args.y)
    ax.set_yticks(positions, labels)
    if args.annotate:
        for index in annotation_indices(len(values), annotation_limit(args, args.render_settings)):
            endpoint = max(left[index], right[index])
            ax.annotate(
                format_delta(left[index], right[index], args.delta_mode),
                (endpoint, positions[index]),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
            )


def plot_slope(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    values = [
        (str(row[args.category]), numeric(row[args.x], args.x), numeric(row[args.y], args.y))
        for row in rows
    ]
    if args.sort:
        values.sort(key=lambda item: item[2])
    for index, (category, start, end) in enumerate(values):
        color = "#0072B2" if end >= start else "#D55E00"
        ax.plot(
            [0, 1],
            [start, end],
            marker="o",
            color=color,
            alpha=0.82,
            linewidth=args.render_settings["line_width_pt"],
            markersize=args.render_settings["marker_size_pt"],
        )
        if args.annotate and index in annotation_indices(
            len(values),
            annotation_limit(args, args.render_settings),
        ):
            ax.annotate(
                f"{category}: {format_delta(start, end, args.delta_mode)}",
                (1, end),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
            )
    ax.set_xticks([0, 1], [args.left_label or args.x, args.right_label or args.y])


def plot_residual(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    for label, group in series_groups(rows, args.group):
        x = [numeric(row[args.x], args.x) for row in group]
        residuals = [numeric(row[args.y], args.y) for row in group]
        ax.scatter(
            x,
            residuals,
            s=marker_area(args.render_settings, 34),
            alpha=0.75,
            edgecolor="white",
            linewidth=0.35,
            label=label or None,
        )
    ax.axhline(0, color="#777777", linestyle="--", linewidth=args.render_settings["line_width_pt"], label="Zero residual")


def plot_calibration(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    for label, group in series_groups(rows, args.group):
        x = [numeric(row[args.x], args.x) for row in group]
        y = [numeric(row[args.y], args.y) for row in group]
        ax.scatter(
            x,
            y,
            s=marker_area(args.render_settings, 34),
            alpha=0.8,
            edgecolor="white",
            linewidth=0.35,
            label=label or None,
        )
    bounds = [*ax.get_xlim(), *ax.get_ylim()]
    lower, upper = min(bounds), max(bounds)
    ax.plot(
        [lower, upper],
        [lower, upper],
        linestyle="--",
        color="#777777",
        linewidth=args.render_settings["line_width_pt"],
        label="Ideal calibration",
    )
    ax.set_xlim(lower, upper)
    ax.set_ylim(lower, upper)
    ax.set_aspect("equal", adjustable="box")
    if args.annotate:
        ax.annotate("Ideal calibration", (upper, upper), xytext=(-4, -4), textcoords="offset points", ha="right", va="top")


def plot_interval_comparison(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    values: list[tuple[str, float, float, float]] = []
    for row in rows:
        estimate = numeric(row[args.y], args.y)
        lower = numeric(row[args.low], args.low)
        upper = numeric(row[args.high], args.high)
        if lower > estimate or estimate > upper:
            raise ValueError("interval_comparison requires --low <= --y <= --high for every row")
        values.append((str(row[args.category]), estimate, lower, upper))
    if args.sort:
        values.sort(key=lambda item: item[1])
    labels, estimates, lower, upper = zip(*values, strict=True)
    positions = list(range(len(values)))
    left_error = [value - bound for value, bound in zip(estimates, lower, strict=True)]
    right_error = [bound - value for value, bound in zip(estimates, upper, strict=True)]
    ax.errorbar(
        estimates,
        positions,
        xerr=[left_error, right_error],
        fmt="o",
        markersize=args.render_settings["marker_size_pt"],
        color="#0072B2",
        ecolor="#777777",
        elinewidth=args.render_settings["line_width_pt"],
        capsize=2.5,
        zorder=3,
    )
    ax.set_yticks(positions, labels)
    if args.annotate:
        for index in annotation_indices(len(values), annotation_limit(args, args.render_settings)):
            ax.annotate(
                f"{estimates[index]:g} [{lower[index]:g}, {upper[index]:g}]",
                (upper[index], positions[index]),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
            )


def plot_scenario_envelope(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    for index, (label, group) in enumerate(series_groups(rows, args.group)):
        x = [row[args.x] for row in group]
        y = [numeric(row[args.y], args.y) for row in group]
        lower = [numeric(row[args.low], args.low) for row in group]
        upper = [numeric(row[args.high], args.high) for row in group]
        if any(low > high for low, high in zip(lower, upper, strict=True)):
            raise ValueError("scenario_envelope requires --low <= --high for every row")
        ax.plot(
            x,
            y,
            marker="o" if len(group) <= 20 else None,
            label=label or None,
            linewidth=args.render_settings["line_width_pt"],
            markersize=args.render_settings["marker_size_pt"],
        )
        ax.fill_between(
            x,
            lower,
            upper,
            alpha=0.18,
            linewidth=0,
            label=args.uncertainty_label if index == 0 else None,
        )
    add_prediction_annotations(ax, rows, args)
def plot_pareto(ax: Any, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    labeled_classes: set[str] = set()
    for row in rows:
        x, y = numeric(row[args.x], args.x), numeric(row[args.y], args.y)
        nondominated = is_truthy(row.get(args.pareto_flag, ""))
        selected = bool(args.selected_flag) and is_truthy(row.get(args.selected_flag, ""))
        if selected:
            classification, size, marker, color, alpha = "Selected decision", 72, "*", "#D55E00", 1.0
        elif nondominated:
            classification, size, marker, color, alpha = "Nondominated", 48, "o", "#0072B2", 0.95
        else:
            classification, size, marker, color, alpha = "Candidate", 26, "x", "#999999", 0.65
        ax.scatter(
            [x],
            [y],
            s=size,
            marker=marker,
            color=color,
            alpha=alpha,
            label=classification if classification not in labeled_classes else None,
        )
        labeled_classes.add(classification)
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
    "dumbbell": plot_dumbbell,
    "slope": plot_slope,
    "distribution": plot_distribution,
    "scatter": plot_scatter,
    "small_multiples": plot_small_multiples,
    "violin": plot_violin,
    "box": plot_box,
    "beeswarm": plot_beeswarm,
    "strip": plot_strip,
    "residual": plot_residual,
    "calibration": plot_calibration,
    "interval_comparison": plot_interval_comparison,
    "scenario_envelope": plot_scenario_envelope,
    "sensitivity": plot_sensitivity,
    "pareto": plot_pareto,
    "heatmap": plot_heatmap,
    "network": plot_network,
}


def validate_arguments(args: argparse.Namespace) -> None:
    required = {
        "line": ("x", "y"),
        "comparison": ("category", "y"),
        "dumbbell": ("category", "x", "y"),
        "slope": ("category", "x", "y"),
        "distribution": ("x",),
        "scatter": ("x", "y"),
        "small_multiples": ("x", "y", "group"),
        "violin": (),
        "box": (),
        "beeswarm": (),
        "strip": (),
        "residual": ("x", "y"),
        "calibration": ("x", "y"),
        "interval_comparison": ("category", "y", "low", "high"),
        "scenario_envelope": ("x", "y", "low", "high"),
        "sensitivity": ("category", "y"),
        "pareto": ("x", "y", "pareto_flag"),
        "heatmap": ("x", "y", "value"),
        "network": ("source", "target"),
    }[args.template]
    missing = [name for name in required if not getattr(args, name)]
    if missing:
        formatted = ", ".join("--" + name.replace("_", "-") for name in missing)
        raise ValueError(f"template {args.template} requires: {formatted}")
    distribution_templates = {"violin", "box", "beeswarm", "strip"}
    if args.template in distribution_templates and not (args.x or args.y):
        raise ValueError(f"template {args.template} requires --y or --x as its numeric value field")
    if args.template == "small_multiples" and args.facet_columns < 1:
        raise ValueError("--facet-columns must be at least 1")
    if bool(args.low) != bool(args.high):
        raise ValueError("--low and --high must be supplied together")
    if args.target_width_mm is not None and args.target_width_mm <= 0:
        raise ValueError("--target-width-mm must be positive")
    if args.target_width_mm is not None and (args.width <= 0 or args.height <= 0):
        raise ValueError("--width and --height must be positive with --target-width-mm")
    if args.annotation_limit is not None and args.annotation_limit < 1:
        raise ValueError("--annotation-limit must be at least 1")
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
    parser.add_argument("--selected-flag")
    parser.add_argument("--label")
    parser.add_argument("--left-label")
    parser.add_argument("--right-label")
    parser.add_argument("--title")
    parser.add_argument("--xlabel")
    parser.add_argument("--ylabel")
    parser.add_argument("--mode", choices=("hist", "ecdf"), default="hist")
    parser.add_argument("--bins", type=int, default=20)
    parser.add_argument("--density", action="store_true")
    parser.add_argument("--sort", action="store_true")
    parser.add_argument("--identity", action="store_true")
    parser.add_argument("--annotate", action="store_true")
    parser.add_argument("--show-points", "--raw-points", dest="show_points", action="store_true")
    parser.add_argument("--point-jitter", type=float, default=0.11)
    parser.add_argument("--facet-columns", type=int, default=3)
    parser.add_argument("--annotation-limit", type=int)
    parser.add_argument("--delta-mode", choices=("percent", "absolute"), default="percent")
    parser.add_argument("--baseline", type=float)
    parser.add_argument("--stable-range", type=float, nargs=2, metavar=("LOW", "HIGH"))
    parser.add_argument("--failure-boundary", type=float)
    parser.add_argument("--train-test-boundary")
    parser.add_argument("--forecast-label", default="Forecast region")
    parser.add_argument("--uncertainty-label")
    parser.add_argument("--cmap", default="viridis")
    parser.add_argument("--directed", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--width", type=float, default=6.4)
    parser.add_argument("--height", type=float, default=3.8)
    sizing = parser.add_mutually_exclusive_group()
    sizing.add_argument(
        "--paper-placement",
        "--placement",
        dest="paper_placement",
        choices=sorted(PAPER_PLACEMENTS),
    )
    sizing.add_argument("--target-width-mm", type=float)
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
        render_settings = resolve_render_settings(args)
        args.render_settings = render_settings
        rows = load_rows(input_path)
        if not rows:
            raise ValueError("input has no rows")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        if style_path.is_file():
            plt.style.use(style_path)
        apply_render_defaults(plt, render_settings)
        figure, ax = plt.subplots(
            figsize=(render_settings["width_in"], render_settings["height_in"]),
            constrained_layout=True,
        )
        rendered_axes = PLOTTERS[args.template](ax, rows, args)
        if args.template == "small_multiples":
            if args.title:
                figure.suptitle(args.title, x=0.01, ha="left", fontweight="semibold")
            for panel in rendered_axes:
                add_annotation_guides(panel, args, args.template)
                set_paper_axes(panel, title=None, xlabel=args.xlabel, ylabel=args.ylabel)
                finalize_legend(panel, render_settings, default_columns=1)
        else:
            add_annotation_guides(ax, args, args.template)
            set_paper_axes(ax, title=args.title, xlabel=args.xlabel, ylabel=args.ylabel)
            finalize_legend(
                ax,
                render_settings,
                default_columns=3 if args.template in {"line", "scenario_envelope"} else 1,
            )
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
            "fields": {
                key: getattr(args, key)
                for key in (
                    "x",
                    "y",
                    "category",
                    "group",
                    "low",
                    "high",
                    "value",
                    "source",
                    "target",
                    "weight",
                    "pareto_flag",
                    "selected_flag",
                    "label",
                )
                if getattr(args, key)
            },
            "render": {**render_settings, "dpi": args.dpi, "seed": args.seed},
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

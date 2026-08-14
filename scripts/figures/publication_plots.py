#!/usr/bin/env python3
"""Publication-Quality Scientific Figures Generator for Math Modeling.

Generates high-DPI and vector PDF charts adhering to the "One Figure = One Message"
rule, SciencePlots aesthetic principles, and self-explanatory LaTeX captions.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# Use non-interactive backend for headless execution
matplotlib.use("Agg")

# Colorblind-safe palette (Tol bright)
PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377", "#BBBBBB"]


def apply_publication_style(ax: plt.Axes) -> None:
    """Apply clean, modern publication style to Matplotlib axis."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.grid(True, linestyle="--", alpha=0.3, color="#888888")
    ax.tick_params(direction="out", length=4, width=0.8)


def plot_time_series_comparison(
    x: Sequence[float | int],
    series_dict: dict[str, Sequence[float]],
    title: str,
    xlabel: str,
    ylabel: str,
    output_path: Path,
) -> Path:
    """Line plot comparing multiple time series or convergence curves."""
    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=300)
    apply_publication_style(ax)

    for i, (name, y_vals) in enumerate(series_dict.items()):
        color = PALETTE[i % len(PALETTE)]
        ax.plot(x, y_vals, label=name, color=color, linewidth=1.8, marker="o" if len(x) <= 20 else None, markersize=4)

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.legend(frameon=True, framealpha=0.9, fontsize=9)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_bar_comparison(
    categories: Sequence[str],
    values_dict: dict[str, Sequence[float]],
    title: str,
    xlabel: str,
    ylabel: str,
    output_path: Path,
) -> Path:
    """Grouped bar chart for baseline vs optimized comparisons."""
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=300)
    apply_publication_style(ax)

    n_groups = len(categories)
    n_bars = len(values_dict)
    bar_width = 0.8 / max(1, n_bars)
    indices = np.arange(n_groups)

    for i, (label, vals) in enumerate(values_dict.items()):
        color = PALETTE[i % len(PALETTE)]
        offset = (i - n_bars / 2 + 0.5) * bar_width
        rects = ax.bar(indices + offset, vals, width=bar_width * 0.9, label=label, color=color, alpha=0.9)
        # Add text labels on bars
        for rect in rects:
            height = rect.get_height()
            if abs(height) > 1e-4:
                ax.annotate(
                    f"{height:.2f}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3 if height >= 0 else -10),
                    textcoords="offset points",
                    ha="center",
                    va="bottom" if height >= 0 else "top",
                    fontsize=7.5,
                )

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_xticks(indices)
    ax.set_xticklabels(categories, fontsize=9)
    ax.legend(frameon=True, framealpha=0.9, fontsize=9)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_sensitivity_heatmap(
    matrix: np.ndarray,
    x_labels: Sequence[str],
    y_labels: Sequence[str],
    title: str,
    xlabel: str,
    ylabel: str,
    output_path: Path,
    cmap: str = "Blues",
) -> Path:
    """Annotated 2D heatmap for parameter sensitivity grid searches."""
    fig, ax = plt.subplots(figsize=(6.5, 5.0), dpi=300)
    cax = ax.matshow(matrix, cmap=cmap)
    fig.colorbar(cax, shrink=0.8)

    ax.set_xticks(range(len(x_labels)))
    ax.set_yticks(range(len(y_labels)))
    ax.set_xticklabels(x_labels, fontsize=9)
    ax.set_yticklabels(y_labels, fontsize=9)
    ax.tick_params(top=False, bottom=True, labeltop=False, labelbottom=True)

    # Text annotations inside cells
    thresh = (matrix.max() + matrix.min()) / 2.0
    for i in range(len(y_labels)):
        for j in range(len(x_labels)):
            val = matrix[i, j]
            text_color = "white" if val > thresh else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=text_color, fontsize=8)

    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


def generate_latex_figure_snippet(
    relative_fig_path: str,
    caption_title: str,
    message: str,
    label: str,
    width: float = 0.85,
) -> str:
    """Generate self-explanatory LaTeX figure block."""
    return (
        "\\begin{figure}[htbp]\n"
        "  \\centering\n"
        f"  \\includegraphics[width={width}\\linewidth]{{{relative_fig_path}}}\n"
        f"  \\caption{{\\textbf{{{caption_title}.}} {message}}}\n"
        f"  \\label{{fig:{label}}}\n"
        "\\end{figure}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Publication plots generator demo.")
    parser.add_argument("--demo", action="store_true", help="Generate sample publication plots")
    parser.add_argument("--output-dir", default="reports/sample_figures", help="Output directory")

    args = parser.parse_args()
    out_dir = Path(args.output_dir)

    # Generate sample bar comparison
    plot_bar_comparison(
        categories=["Scenario A", "Scenario B", "Scenario C"],
        values_dict={
            "Baseline (Rule-based)": [100.0, 142.5, 180.2],
            "Proposed (MILP)": [88.4, 121.0, 155.8],
        },
        title="Cost Comparison Across Scenarios",
        xlabel="Operating Scenarios",
        ylabel="Total System Cost (kCNY)",
        output_path=out_dir / "cost_comparison.pdf",
    )

    print(f"Generated sample publication figure at: {out_dir / 'cost_comparison.pdf'}")
    snippet = generate_latex_figure_snippet(
        relative_fig_path="figures/cost_comparison.pdf",
        caption_title="System Cost Comparison",
        message="The proposed MILP model reduces total cost by 11.6% to 15.1% across all scenarios compared to the baseline rule-based approach.",
        label="cost-comparison",
    )
    print("LaTeX Snippet:\n" + snippet)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

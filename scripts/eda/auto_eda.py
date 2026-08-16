#!/usr/bin/env python3
"""Automated Exploratory Data Analysis (Auto-EDA) for Math Modeling.

Performs data profiling, missingness check, outlier detection,
time-series continuity check, multicollinearity check, and modeling recommendations.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np


TARGET_ALIASES = {
    "target",
    "label",
    "y",
    "objective",
    "目标",
    "标签",
    "得分",
}
TIME_ALIASES = {
    "date",
    "time",
    "timestamp",
    "year",
    "month",
    "day",
    "hour",
    "日期",
    "时间",
    "年份",
}


def _normalized_name(name: str) -> str:
    """Normalize a column name without treating one-letter aliases as substrings."""
    lowered = name.strip().casefold()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "_", lowered).strip("_")


def _has_suffix_alias(normalized: str, aliases: tuple[str, ...]) -> bool:
    return any(normalized.endswith(f"_{alias}") for alias in aliases)


def load_dataset(file_path: Path) -> pd.DataFrame:
    """Load dataset from various tabular formats."""
    ext = file_path.suffix.lower()
    if ext in (".csv", ".txt"):
        try:
            return pd.read_csv(file_path, encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(file_path, encoding="gbk")
    elif ext == ".tsv":
        try:
            return pd.read_csv(file_path, sep="\t", encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(file_path, sep="\t", encoding="gbk")
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    elif ext == ".parquet":
        return pd.read_parquet(file_path)
    elif ext == ".json":
        return pd.read_json(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def infer_semantic_role(col_name: str, series: pd.Series) -> tuple[str, str]:
    """Infer semantic type and role of a column."""
    normalized = _normalized_name(col_name)

    if any(k in normalized.split("_") for k in ("id", "code", "index", "no", "编号", "序号")) and series.nunique() == len(series.dropna()):
        return "identifier", "identifier"
    if normalized in TIME_ALIASES or _has_suffix_alias(normalized, tuple(TIME_ALIASES)):
        return "datetime", "time"
    # Do not use substring matching here: ``city`` and ``quality`` both contain
    # the letter ``y`` but neither is a target.  Explicit target columns still
    # take precedence in ``analyze_dataframe``/the data contract generator.
    if normalized in TARGET_ALIASES or _has_suffix_alias(normalized, tuple(TARGET_ALIASES)):
        return "numerical" if pd.api.types.is_numeric_dtype(series) else "category", "target"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime", "time"
    if pd.api.types.is_bool_dtype(series):
        return "boolean", "feature"
    if pd.api.types.is_numeric_dtype(series):
        if series.nunique() <= 5 and len(series) > 50:
            return "category", "group"
        return "number" if pd.api.types.is_float_dtype(series) else "integer", "feature"
    if series.nunique() <= 20:
        return "category", "group"
    return "string", "feature"


def profile_series(series: pd.Series, name: str) -> dict[str, Any]:
    """Profile an individual column."""
    n_total = len(series)
    n_missing = int(series.isna().sum())
    missing_ratio = float(n_missing / n_total) if n_total > 0 else 0.0
    n_unique = int(series.nunique(dropna=True))
    unique_ratio = float(n_unique / n_total) if n_total > 0 else 0.0

    semantic_type, role = infer_semantic_role(name, series)

    col_profile: dict[str, Any] = {
        "name": name,
        "raw_dtype": str(series.dtype),
        "semantic_type": semantic_type,
        "role": role,
        "total_count": n_total,
        "missing_count": n_missing,
        "missing_ratio": round(missing_ratio, 4),
        "unique_count": n_unique,
        "unique_ratio": round(unique_ratio, 4),
        "is_constant": n_unique <= 1,
        "warnings": [],
    }

    if missing_ratio > 0.3:
        col_profile["warnings"].append(f"High missing rate ({missing_ratio*100:.1f}%)")
    if col_profile["is_constant"]:
        col_profile["warnings"].append("Constant column (zero variance)")

    # Numerical profiling
    if pd.api.types.is_numeric_dtype(series) and not series.dropna().empty:
        clean = series.dropna().astype(float)
        mean_val = float(clean.mean())
        std_val = float(clean.std()) if len(clean) > 1 else 0.0
        q1 = float(clean.quantile(0.25))
        median_val = float(clean.median())
        q3 = float(clean.quantile(0.75))
        iqr = q3 - q1

        # Outlier counts
        iqr_lower, iqr_upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        iqr_outliers = int(((clean < iqr_lower) | (clean > iqr_upper)).sum())

        z_outliers = 0
        if std_val > 1e-9:
            z_scores = np.abs((clean - mean_val) / std_val)
            z_outliers = int((z_scores > 3.0).sum())

        skewness = float(clean.skew()) if len(clean) > 2 else 0.0
        kurt = float(clean.kurt()) if len(clean) > 3 else 0.0

        col_profile.update({
            "min": float(clean.min()),
            "max": float(clean.max()),
            "mean": round(mean_val, 4),
            "std": round(std_val, 4),
            "q25": round(q1, 4),
            "median": round(median_val, 4),
            "q75": round(q3, 4),
            "iqr": round(iqr, 4),
            "skewness": round(skewness, 4),
            "kurtosis": round(kurt, 4),
            "outliers_iqr": iqr_outliers,
            "outliers_3sigma": z_outliers,
        })

        if abs(skewness) > 1.5:
            col_profile["warnings"].append(f"Highly skewed distribution (skewness={skewness:.2f})")
        if iqr_outliers > 0.05 * len(clean):
            col_profile["warnings"].append(f"Frequent outliers detected ({iqr_outliers} records via IQR)")

    return col_profile


def audit_leakage(
    df: pd.DataFrame,
    target_columns: list[str] | None = None,
    split_keys: list[str] | None = None,
    time_boundary: str | None = None,
) -> dict[str, Any]:
    """Run only deterministic leakage checks that can be justified from one table.

    This is intentionally conservative.  A target without a declared split or
    time boundary is ``not_run`` rather than an automatic pass.  Equality with
    a target and obvious future/lead columns are cheap blockers; model-specific
    leakage still requires a separate validation artifact.
    """
    targets = list(target_columns or [])
    missing_targets = [name for name in targets if name not in df.columns]
    if missing_targets:
        return {
            "status": "fail",
            "target_columns": targets,
            "split_keys": list(split_keys or []),
            "time_boundary": time_boundary,
            "forbidden_features": [],
            "checks": {"target_columns_exist": False, "exact_target_duplicates": "not_run", "future_named_features": "not_run"},
            "limitations": [f"target column missing: {name}" for name in missing_targets],
        }
    if not targets:
        return {
            "status": "not_applicable",
            "target_columns": [],
            "split_keys": list(split_keys or []),
            "time_boundary": time_boundary,
            "forbidden_features": [],
            "checks": {"target_columns_exist": "not_applicable", "exact_target_duplicates": "not_applicable", "future_named_features": "not_applicable"},
            "limitations": ["No target column was supplied; target leakage audit is not applicable."],
        }

    forbidden: set[str] = set()
    exact_duplicates: list[str] = []
    future_named: list[str] = []
    feature_columns = [name for name in df.columns if name not in targets]
    for feature in feature_columns:
        normalized = _normalized_name(str(feature))
        if re.search(r"(^|_)(future|next|lead|t\+\d+|forecast|后续|未来)(_|$)", normalized):
            future_named.append(str(feature))
        for target in targets:
            try:
                if df[feature].equals(df[target]):
                    exact_duplicates.append(str(feature))
                    break
            except (TypeError, ValueError):
                continue
    forbidden.update(exact_duplicates)
    forbidden.update(future_named)
    checks = {
        "target_columns_exist": True,
        "exact_target_duplicates": len(exact_duplicates) == 0,
        "future_named_features": len(future_named) == 0,
        "split_or_time_boundary_declared": bool(split_keys or time_boundary),
    }
    if forbidden:
        status = "fail"
    elif not (split_keys or time_boundary):
        status = "not_run"
    else:
        status = "pass"
    limitations = [
        "This audit does not prove absence of feature engineering leakage, group contamination, or label construction leakage.",
    ]
    if status == "not_run":
        limitations.insert(0, "No split key or time boundary was supplied; the leakage audit cannot be promoted to PASS.")
    return {
        "status": status,
        "target_columns": targets,
        "split_keys": list(split_keys or []),
        "time_boundary": time_boundary,
        "forbidden_features": sorted(forbidden),
        "checks": checks,
        "exact_target_duplicates": exact_duplicates,
        "future_named_features": future_named,
        "limitations": limitations,
    }


def infer_entity_key_candidates(
    df: pd.DataFrame,
    explicit_keys: list[str] | None = None,
    excluded_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Suggest statistical-unit candidates without selecting one automatically."""

    explicit = [key for key in (explicit_keys or []) if key in df.columns]
    excluded = set(excluded_columns or [])
    candidates: list[dict[str, Any]] = []
    row_count = len(df)
    name_hints = ("subject", "patient", "person", "entity", "athlete", "team", "group", "school", "country", "region", "id", "code", "编号")
    for column in df.columns:
        name = str(column)
        if name in excluded or name in {"target", "label", "time", "date", "timestamp"}:
            continue
        series = df[column]
        nonmissing = series.dropna()
        unique_count = int(nonmissing.nunique())
        if row_count == 0 or unique_count < 1 or unique_count >= row_count:
            continue
        counts = nonmissing.value_counts()
        max_rows = int(counts.max()) if not counts.empty else 1
        if max_rows < 2:
            continue
        normalized = _normalized_name(name)
        hinted = any(token in normalized.split("_") or token in normalized for token in name_hints)
        repeated_measure = max_rows > 1
        repeat_ratio = min(1.0, max(0.0, (row_count - unique_count) / max(1, row_count - 1)))
        score = 0.55 * repeat_ratio + (0.35 if hinted else 0.0) + (0.1 if name in explicit else 0.0)
        rationale = [f"{unique_count} observed entities across {row_count} rows", f"maximum rows per entity={max_rows}"]
        if hinted:
            rationale.append("column name resembles an entity/group key")
        if name in explicit:
            rationale.append("explicitly supplied as a split key")
        candidates.append({
            "key_columns": [name], "repeated_measure": repeated_measure, "entity_count": unique_count,
            "max_rows_per_entity": max_rows, "score": round(min(1.0, score), 4), "rationale": rationale, "status": "candidate",
        })
    candidates.sort(key=lambda row: (-float(row["score"]), row["key_columns"]))
    return candidates


def analyze_dataframe(
    df: pd.DataFrame,
    source_name: str = "dataset",
    target_columns: list[str] | None = None,
    split_keys: list[str] | None = None,
    time_boundary: str | None = None,
) -> dict[str, Any]:
    """Comprehensive analysis of a dataset."""
    rows, cols = df.shape
    columns_profile = [profile_series(df[col], col) for col in df.columns]
    explicit_targets = set(target_columns or [])
    if explicit_targets:
        for col in columns_profile:
            if col["name"] in explicit_targets:
                col["role"] = "target"
                col["semantic_type"] = "numerical" if pd.api.types.is_numeric_dtype(df[col["name"]]) else "category"

    # Multicollinearity check
    numeric_df = df.select_dtypes(include=[np.number])
    high_correlations = []
    if numeric_df.shape[1] >= 2 and len(numeric_df) > 5:
        corr_matrix = numeric_df.corr().abs()
        corr_values = np.array(corr_matrix, copy=True)
        np.fill_diagonal(corr_values, 0)
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                val = corr_values[i, j]
                if not math.isnan(val) and val > 0.85:
                    c1, c2 = corr_matrix.columns[i], corr_matrix.columns[j]
                    high_correlations.append({
                        "col1": c1,
                        "col2": c2,
                        "correlation": round(float(val), 4),
                        "warning": f"Strong correlation between '{c1}' and '{c2}' (r={val:.3f})"
                    })

    # Time series detection
    time_series_info: dict[str, Any] = {"has_time_series": False}
    date_cols = [c["name"] for c in columns_profile if c["role"] == "time"]
    if date_cols:
        t_col = date_cols[0]
        try:
            ts = pd.to_datetime(df[t_col], errors="coerce")
            valid_ts = ts.dropna()
            if not valid_ts.empty:
                is_monotonic = bool(valid_ts.is_monotonic_increasing)
                time_series_info = {
                    "has_time_series": True,
                    "time_column": t_col,
                    "min_time": str(valid_ts.min()),
                    "max_time": str(valid_ts.max()),
                    "is_monotonic_increasing": is_monotonic,
                    "total_valid_timestamps": len(valid_ts),
                }
        except Exception:
            pass

    # Modeling recommendations based on dataset characteristics
    recommendations = []
    if time_series_info["has_time_series"]:
        recommendations.append("Detected temporal structure: Consider ARIMA, Prophet, LSTM, or State-space models.")
    if high_correlations:
        recommendations.append(f"Found {len(high_correlations)} highly correlated feature pairs: Consider PCA, Ridge/Lasso, or feature selection before modeling.")
    if any(c["warnings"] for c in columns_profile if "High missing rate" in " ".join(c["warnings"])):
        recommendations.append("Missing values present (>30% in some features): Use KNN/MICE imputation or tree-based models with native missing handling (LightGBM/XGBoost).")
    if rows < 100:
        recommendations.append("Small sample size (N < 100): Prioritize analytical, Bayesian, or exact mathematical optimization over deep learning.")

    leakage_audit = audit_leakage(df, target_columns, split_keys, time_boundary)
    observation_structure_candidates = infer_entity_key_candidates(
        df,
        explicit_keys=split_keys,
        excluded_columns=target_columns,
    )
    if leakage_audit["status"] == "not_run":
        recommendations.append("Leakage audit is not promotable yet: declare a split key/time boundary and inspect feature construction before modeling.")
    elif leakage_audit["status"] == "fail":
        recommendations.append("Potential leakage detected: remove or explain forbidden features before using this table for claims.")

    return {
        "source": source_name,
        "row_count": rows,
        "column_count": cols,
        "total_cells": rows * cols,
        "total_missing_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": columns_profile,
        "high_correlations": high_correlations,
        "time_series_info": time_series_info,
        "leakage_audit": leakage_audit,
        "observation_structure_candidates": observation_structure_candidates,
        "recommendations": recommendations,
    }


def generate_markdown_report(eda_result: dict[str, Any]) -> str:
    """Format EDA analysis into a clean Markdown report."""
    lines = [
        f"# Auto-EDA Report: `{eda_result['source']}`",
        "",
        f"- **Rows**: {eda_result['row_count']}",
        f"- **Columns**: {eda_result['column_count']}",
        f"- **Missing Cells**: {eda_result['total_missing_cells']} ({(eda_result['total_missing_cells']/max(1, eda_result['total_cells']))*100:.2f}%)",
        f"- **Duplicate Rows**: {eda_result['duplicate_rows']}",
        f"- **Leakage Audit**: `{eda_result.get('leakage_audit', {}).get('status', 'not_run')}`",
        "",
        "## Column Overview",
        "",
        "| Column | Semantic Type | Role | Missing (%) | Unique | Warnings |",
        "|---|---|---|---|---|---|",
    ]
    for col in eda_result["columns"]:
        warns = "; ".join(col["warnings"]) if col["warnings"] else "-"
        lines.append(
            f"| `{col['name']}` | {col['semantic_type']} | {col['role']} | {col['missing_ratio']*100:.1f}% | {col['unique_count']} | {warns} |"
        )

    if eda_result["high_correlations"]:
        lines.extend([
            "",
            "## Multicollinearity (High Correlations > 0.85)",
            "",
        ])
        for hc in eda_result["high_correlations"]:
            lines.append(f"- `{hc['col1']}` <-> `{hc['col2']}`: **r = {hc['correlation']}**")

    if eda_result["time_series_info"]["has_time_series"]:
        ts = eda_result["time_series_info"]
        lines.extend([
            "",
            "## Time Series Info",
            "",
            f"- **Column**: `{ts['time_column']}`",
            f"- **Range**: `{ts['min_time']}` to `{ts['max_time']}`",
            f"- **Monotonic Increasing**: {ts['is_monotonic_increasing']}",
        ])

    if eda_result["recommendations"]:
        lines.extend([
            "",
            "## Modeling & Preprocessing Recommendations",
            "",
        ])
        for rec in eda_result["recommendations"]:
            lines.append(f"- {rec}")

    candidates = eda_result.get("observation_structure_candidates", [])
    if candidates:
        lines.extend(["", "## Observation-Unit Candidates", "", "These are candidates only; confirm the statistical unit before modeling.", ""])
        lines.append("| Candidate key | Entities | Max rows/entity | Score | Rationale |")
        lines.append("|---|---:|---:|---:|---|")
        for candidate in candidates[:10]:
            lines.append(
                f"| `{','.join(candidate['key_columns'])}` | {candidate['entity_count']} | {candidate['max_rows_per_entity']} | {candidate['score']:.3f} | {'; '.join(candidate['rationale'])} |"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-EDA analyzer for math modeling datasets.")
    parser.add_argument("input", help="Path to tabular file (CSV/Excel/Parquet/JSON) or directory")
    parser.add_argument("--output-json", "-j", help="Path to write JSON profile")
    parser.add_argument("--output-md", "-m", help="Path to write Markdown summary")
    parser.add_argument("--target", action="append", default=[], help="Explicit target column (repeatable)")
    parser.add_argument("--split-key", action="append", default=[], help="Declared split/group key (repeatable)")
    parser.add_argument("--time-boundary", help="Declared train/test time boundary")

    args = parser.parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"ERROR: Input path does not exist: {input_path}", file=sys.stderr)
        return 1

    files_to_process = []
    if input_path.is_dir():
        for ext in ("*.csv", "*.xlsx", "*.xls", "*.parquet", "*.tsv"):
            files_to_process.extend(input_path.glob(ext))
    else:
        files_to_process = [input_path]

    if not files_to_process:
        print(f"No tabular datasets found in {input_path}", file=sys.stderr)
        return 1

    all_reports = []
    failed_files: list[str] = []
    for fp in files_to_process:
        try:
            df = load_dataset(fp)
            report = analyze_dataframe(df, fp.name, args.target, args.split_key, args.time_boundary)
            all_reports.append(report)
            md = generate_markdown_report(report)
            print(md)
        except Exception as exc:
            failed_files.append(str(fp))
            print(f"ERROR analyzing {fp}: {exc}", file=sys.stderr)

    if args.output_json and all_reports:
        out_j = Path(args.output_json)
        out_j.parent.mkdir(parents=True, exist_ok=True)
        out_j.write_text(json.dumps(all_reports[0] if len(all_reports) == 1 else all_reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.output_md and all_reports:
        out_m = Path(args.output_md)
        out_m.parent.mkdir(parents=True, exist_ok=True)
        combined_md = "\n\n---\n\n".join(generate_markdown_report(r) for r in all_reports)
        out_m.write_text(combined_md, encoding="utf-8")

    return 0 if all_reports and not failed_files else 1


if __name__ == "__main__":
    sys.exit(main())

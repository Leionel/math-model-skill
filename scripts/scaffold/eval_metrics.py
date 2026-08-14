#!/usr/bin/env python3
"""Standard Mathematical Modeling Evaluation & Recomputation Metrics.

Provides deterministic, reproducible recomputations for optimization,
forecasting/regression, classification, and multi-criteria decision models (TOPSIS, Entropy Weight).
"""

from __future__ import annotations

import math
from typing import Sequence
import numpy as np


# --- Optimization Metrics ---

def recompute_constraint_violation(
    lhs_values: Sequence[float],
    rhs_values: Sequence[float],
    operators: Sequence[str],
) -> dict[str, float]:
    """Calculate maximum and sum of constraint violations."""
    violations = []
    for lhs, rhs, op in zip(lhs_values, rhs_values, operators):
        viol = 0.0
        if op in ("<=", "=<"):
            viol = max(0.0, lhs - rhs)
        elif op in (">=", "=>"):
            viol = max(0.0, rhs - lhs)
        elif op in ("==", "="):
            viol = abs(lhs - rhs)
        violations.append(viol)

    arr = np.array(violations, dtype=float)
    return {
        "max_violation": float(np.max(arr)) if len(arr) > 0 else 0.0,
        "sum_violation": float(np.sum(arr)) if len(arr) > 0 else 0.0,
        "violation_count": int(np.sum(arr > 1e-6)),
    }


def compute_relative_improvement(baseline_val: float, optimized_val: float, minimize: bool = True) -> float:
    """Compute percentage improvement of optimized result against baseline."""
    if abs(baseline_val) < 1e-12:
        return 0.0
    if minimize:
        return float((baseline_val - optimized_val) / abs(baseline_val) * 100.0)
    else:
        return float((optimized_val - baseline_val) / abs(baseline_val) * 100.0)


# --- Regression & Forecasting Metrics ---

def calculate_regression_metrics(y_true: Sequence[float], y_pred: Sequence[float]) -> dict[str, float]:
    """Compute RMSE, MAE, MAPE, R2 for regression/forecasting models."""
    yt = np.array(y_true, dtype=float)
    yp = np.array(y_pred, dtype=float)

    if len(yt) != len(yp) or len(yt) == 0:
        raise ValueError("y_true and y_pred must be non-empty and have identical length.")

    residuals = yt - yp
    mae = float(np.mean(np.abs(residuals)))
    mse = float(np.mean(residuals ** 2))
    rmse = float(math.sqrt(mse))

    # MAPE (filter zero denominators)
    nonzero_mask = np.abs(yt) > 1e-9
    if np.any(nonzero_mask):
        mape = float(np.mean(np.abs(residuals[nonzero_mask] / yt[nonzero_mask])) * 100.0)
    else:
        mape = 0.0

    # R2
    ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
    ss_res = float(np.sum(residuals ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 1e-9 else 0.0

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape_pct": round(mape, 2),
        "r2": round(r2, 4),
    }


# --- Multi-Criteria Decision Analysis (TOPSIS & Entropy Weight) ---

def entropy_weight_method(decision_matrix: np.ndarray) -> np.ndarray:
    """Calculate attribute weights using the Entropy Weight Method."""
    matrix = np.array(decision_matrix, dtype=float)
    m, n = matrix.shape
    if m <= 1 or n == 0:
        return np.ones(n) / max(1, n)

    # Normalize column-wise (0 to 1)
    mins = matrix.min(axis=0)
    maxs = matrix.max(axis=0)
    ranges = maxs - mins
    ranges[ranges < 1e-12] = 1.0
    normalized = (matrix - mins) / ranges

    # Probability matrix P
    p_sums = normalized.sum(axis=0, keepdims=True)
    p_sums[p_sums < 1e-12] = 1.0
    p = normalized / p_sums

    # Entropy e_j
    k = 1.0 / math.log(m)
    p_log = np.where(p > 1e-12, np.log(p + 1e-15), 0.0)
    e = -k * np.sum(p * p_log, axis=0)

    # Diversity d_j and weights w_j
    d = 1.0 - e
    d_sum = np.sum(d)
    if d_sum < 1e-12:
        return np.ones(n) / n
    return d / d_sum


def topsis_score(
    decision_matrix: np.ndarray,
    weights: Sequence[float] | None = None,
    benefit_mask: Sequence[bool] | None = None,
) -> np.ndarray:
    """Calculate TOPSIS relative closeness score C_i (0 to 1)."""
    matrix = np.array(decision_matrix, dtype=float)
    m, n = matrix.shape
    if weights is None:
        w = np.ones(n) / n
    else:
        w = np.array(weights, dtype=float) / np.sum(weights)

    if benefit_mask is None:
        benefit_mask = [True] * n

    # Vector normalization: r_ij = x_ij / sqrt(sum(x_ij^2))
    norm_factors = np.sqrt(np.sum(matrix ** 2, axis=0))
    norm_factors[norm_factors < 1e-12] = 1.0
    r = matrix / norm_factors

    # Weighted normalized matrix v_ij
    v = r * w

    # Ideal best v+ and worst v-
    v_plus = np.zeros(n)
    v_minus = np.zeros(n)
    for j in range(n):
        if benefit_mask[j]:
            v_plus[j] = np.max(v[:, j])
            v_minus[j] = np.min(v[:, j])
        else:
            v_plus[j] = np.min(v[:, j])
            v_minus[j] = np.max(v[:, j])

    # Euclidean distances d+ and d-
    d_plus = np.sqrt(np.sum((v - v_plus) ** 2, axis=1))
    d_minus = np.sqrt(np.sum((v - v_minus) ** 2, axis=1))

    # Closeness score C_i = d- / (d+ + d-)
    denom = d_plus + d_minus
    denom[denom < 1e-12] = 1.0
    return d_minus / denom

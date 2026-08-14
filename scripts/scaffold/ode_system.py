#!/usr/bin/env python3
"""Ordinary Differential Equation (ODE) System Modeling Scaffold.

Provides clean integration with scipy.integrate.solve_ivp for dynamic systems,
SIR/SEIR epidemic models, population dynamics, and heat/kinetics simulation.
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Sequence, Any
import numpy as np
from scipy.integrate import solve_ivp


def solve_ode_system(
    deriv_fn: Callable[[float, np.ndarray, Sequence[float]], Sequence[float]],
    t_span: tuple[float, float],
    y0: Sequence[float],
    t_eval: Sequence[float] | None = None,
    params: Sequence[float] | tuple = (),
    method: str = "RK45",
) -> dict[str, Any]:
    """Solve system of ODEs: dy/dt = f(t, y, *params)."""
    def wrapper(t: float, y: np.ndarray) -> np.ndarray:
        return np.array(deriv_fn(t, y, *params), dtype=float)

    sol = solve_ivp(
        fun=wrapper,
        t_span=t_span,
        y0=y0,
        t_eval=t_eval,
        method=method,
        rtol=1e-6,
        atol=1e-8,
    )

    return {
        "success": bool(sol.success),
        "status_code": int(sol.status),
        "message": str(sol.message),
        "t": [float(val) for val in sol.t],
        "y": [[float(val) for val in row] for row in sol.y],
        "n_eval": int(sol.nfev),
    }


def sir_model_deriv(t: float, y: np.ndarray, beta: float, gamma: float) -> list[float]:
    """Classic SIR Epidemic Model: S, I, R."""
    susceptible, infected, recovered = y
    N = susceptible + infected + recovered
    dS_dt = -beta * susceptible * infected / N
    dI_dt = beta * susceptible * infected / N - gamma * infected
    dR_dt = gamma * infected
    return [dS_dt, dI_dt, dR_dt]


def main() -> int:
    parser = argparse.ArgumentParser(description="ODE solver scaffold demo.")
    parser.add_argument("--demo", action="store_true", help="Run demo SIR model")
    parser.parse_args()

    # Demo: SIR with N=1000, I0=10, beta=0.3, gamma=0.1 over 100 days
    t_eval = np.linspace(0, 50, 51)
    res = solve_ode_system(
        deriv_fn=sir_model_deriv,
        t_span=(0, 50),
        y0=[990, 10, 0],
        t_eval=t_eval,
        params=(0.3, 0.1),
    )
    print(f"SIR Demo Simulation finished: {len(res['t'])} timesteps, success={res['success']}")
    return 0 if res["success"] else 1


if __name__ == "__main__":
    sys.exit(main())

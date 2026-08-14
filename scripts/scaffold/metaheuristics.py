#!/usr/bin/env python3
"""Metaheuristics Optimization Scaffold (GA & PSO).

Provides reproducible, seeded heuristics for complex non-linear,
combinatorial, or black-box mathematical modeling optimization problems.
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Sequence, Any
import numpy as np


def run_genetic_algorithm(
    fitness_fn: Callable[[np.ndarray], float],
    bounds: Sequence[tuple[float, float]],
    pop_size: int = 50,
    generations: int = 100,
    mutation_rate: float = 0.1,
    crossover_rate: float = 0.8,
    seed: int = 42,
    minimize: bool = True,
) -> dict[str, Any]:
    """Continuous Genetic Algorithm with elitism and tournament selection."""
    rng = np.random.default_rng(seed)
    n_vars = len(bounds)
    lows = np.array([b[0] for b in bounds])
    highs = np.array([b[1] for b in bounds])

    # Initial population
    pop = rng.uniform(lows, highs, size=(pop_size, n_vars))
    fitness = np.array([fitness_fn(ind) for ind in pop])

    best_idx = np.argmin(fitness) if minimize else np.argmax(fitness)
    best_ind = pop[best_idx].copy()
    best_fit = float(fitness[best_idx])
    history = [best_fit]

    for gen in range(generations):
        # Elite
        new_pop = [best_ind.copy()]

        # Generate offspring
        while len(new_pop) < pop_size:
            # Tournament selection (size 3)
            t_idx1 = rng.choice(pop_size, size=3, replace=False)
            p1 = pop[t_idx1[np.argmin(fitness[t_idx1]) if minimize else np.argmax(fitness[t_idx1])]]

            t_idx2 = rng.choice(pop_size, size=3, replace=False)
            p2 = pop[t_idx2[np.argmin(fitness[t_idx2]) if minimize else np.argmax(fitness[t_idx2])]]

            # Crossover
            if rng.random() < crossover_rate:
                alpha = rng.random(n_vars)
                child = alpha * p1 + (1.0 - alpha) * p2
            else:
                child = p1.copy()

            # Mutation
            if rng.random() < mutation_rate:
                noise = rng.normal(0, (highs - lows) * 0.1, size=n_vars)
                child = np.clip(child + noise, lows, highs)

            new_pop.append(child)

        pop = np.array(new_pop[:pop_size])
        fitness = np.array([fitness_fn(ind) for ind in pop])

        cur_best_idx = np.argmin(fitness) if minimize else np.argmax(fitness)
        if (minimize and fitness[cur_best_idx] < best_fit) or (not minimize and fitness[cur_best_idx] > best_fit):
            best_fit = float(fitness[cur_best_idx])
            best_ind = pop[cur_best_idx].copy()

        history.append(best_fit)

    return {
        "success": True,
        "best_solution": [float(x) for x in best_ind],
        "best_fitness": best_fit,
        "history": history,
        "generations": generations,
        "pop_size": pop_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Metaheuristics GA scaffold demo.")
    parser.add_argument("--demo", action="store_true", help="Run Sphere function demo")
    parser.parse_args()

    # Demo: Minimize Sphere function f(x) = sum(x_i^2) in [-5, 5]^5
    res = run_genetic_algorithm(
        fitness_fn=lambda x: float(np.sum(x ** 2)),
        bounds=[(-5.0, 5.0)] * 5,
        pop_size=40,
        generations=50,
        seed=42,
    )
    print(f"GA Demo Best Fitness: {res['best_fitness']:.6f} (Target = 0.0)")
    return 0 if res["best_fitness"] < 0.1 else 1


if __name__ == "__main__":
    sys.exit(main())

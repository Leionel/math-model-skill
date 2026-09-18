# Synthetic demo problem: depot allocation under capacity

This is a synthetic statement. It exists so the Harness chain can be exercised
end to end without borrowing a real contest problem, and so every number in the
demo is reproducible from files in this directory.

## Statement

A company must supply three products from three candidate depots. Each product
is covered by exactly one depot. Depot capacities and per-unit procurement costs
are given in `input.json`.

- `q1`: minimize total procurement cost subject to every capacity limit.

## Data boundary

| Field | Meaning | Unit |
| --- | --- | --- |
| `demand` | required quantity per product | item |
| `capacity` | maximum quantity per depot | item |
| `unit_cost` | per-unit cost, indexed `[depot][product]` | CNY/item |

Nothing outside this table may be assumed. There is no stochastic demand, no
substitution between products, and no second delivery period.

## Deliverable

One validated cost figure for `q1`, its feasibility evidence, and a short paper
whose every numeric statement traces back to the frozen result.

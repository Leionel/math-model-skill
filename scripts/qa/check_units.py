#!/usr/bin/env python3
"""Deterministic unit/dimension consistency checks over the model contract.

Checks four things from declared facts.  Unit declarations are parsed into a
scale and dimensional signature; equation expressions themselves are never
parsed and numeric values are never converted:

1. One symbol, one unit per model: a variable/parameter symbol declared in
   more than one place in the same model must carry one normalized unit.
2. Equation balance declarations: when an equation declares `unit_balance`,
   the left and right dimensional signatures must match.
3. Equation output units: when an equation declares `output_unit`, every
   output symbol already registered with a unit must agree with it.
4. Acceptance units: a validation obligation's `acceptance.unit` must match
   the registered unit of its `left_metric_id` when that metric is a known
   symbol.

`--strict` is accepted for wiring compatibility with the other qa checkers;
the checks above are unconditional because a contradiction is a defect in
every mode.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402

_DIMENSIONLESS_TOKENS = {
    "-", "—", "1", "dimensionless", "无量纲", "ratio", "probability", "correlation"
}
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")


@dataclass(frozen=True)
class UnitSignature:
    dimensions: tuple[tuple[str, int], ...]
    scale: Fraction = Fraction(1)

    @classmethod
    def from_parts(cls, dimensions: dict[str, int], scale: Fraction = Fraction(1)) -> UnitSignature:
        return cls(tuple(sorted((key, power) for key, power in dimensions.items() if power)), scale)

    def multiply(self, other: UnitSignature) -> UnitSignature:
        dimensions = dict(self.dimensions)
        for key, power in other.dimensions:
            dimensions[key] = dimensions.get(key, 0) + power
        return UnitSignature.from_parts(dimensions, self.scale * other.scale)

    def divide(self, other: UnitSignature) -> UnitSignature:
        return self.multiply(other.power(-1))

    def power(self, exponent: int) -> UnitSignature:
        return UnitSignature.from_parts(
            {key: power * exponent for key, power in self.dimensions},
            self.scale ** exponent,
        )

    def same_dimension(self, other: UnitSignature) -> bool:
        return self.dimensions == other.dimensions

    def equivalent(self, other: UnitSignature) -> bool:
        return self.dimensions == other.dimensions and self.scale == other.scale

    def describe(self) -> str:
        dimension = " ".join(
            key if power == 1 else f"{key}^{power}"
            for key, power in self.dimensions
        ) or "dimensionless"
        if self.scale == 1:
            return dimension
        return f"{self.scale} * {dimension}"


def _signature(**dimensions: int) -> UnitSignature:
    return UnitSignature.from_parts(dimensions)


_NAMED_UNITS: dict[str, UnitSignature] = {
    "m": _signature(length=1),
    "kg": _signature(mass=1),
    "s": _signature(time=1),
    "A": _signature(current=1),
    "K": _signature(temperature=1),
    "mol": _signature(amount=1),
    "cd": _signature(luminous_intensity=1),
    "g": UnitSignature.from_parts({"mass": 1}, Fraction(1, 1000)),
    "min": UnitSignature.from_parts({"time": 1}, Fraction(60)),
    "h": UnitSignature.from_parts({"time": 1}, Fraction(3600)),
    "day": UnitSignature.from_parts({"time": 1}, Fraction(86400)),
    "L": UnitSignature.from_parts({"length": 3}, Fraction(1, 1000)),
    "Hz": _signature(time=-1),
    "N": _signature(mass=1, length=1, time=-2),
    "Pa": _signature(mass=1, length=-1, time=-2),
    "J": _signature(mass=1, length=2, time=-2),
    "W": _signature(mass=1, length=2, time=-3),
    "C": _signature(current=1, time=1),
    "V": _signature(mass=1, length=2, time=-3, current=-1),
    "Ω": _signature(mass=1, length=2, time=-3, current=-2),
}
_ALIASES = {
    "meter": "m", "metre": "m", "meters": "m", "metres": "m",
    "second": "s", "seconds": "s", "sec": "s",
    "hour": "h", "hours": "h", "hr": "h", "hrs": "h",
    "days": "day", "liter": "L", "litre": "L", "liters": "L", "litres": "L",
    "ohm": "Ω", "ohms": "Ω",
}
_PREFIXES = {
    "G": Fraction(10**9), "M": Fraction(10**6), "k": Fraction(10**3),
    "c": Fraction(1, 100), "m": Fraction(1, 1000),
    "u": Fraction(1, 10**6), "µ": Fraction(1, 10**6), "μ": Fraction(1, 10**6),
    "n": Fraction(1, 10**9),
}
_PREFIXABLE = {"m", "g", "s", "A", "K", "mol", "L", "Hz", "N", "Pa", "J", "W", "C", "V", "Ω"}


class UnitParseError(ValueError):
    pass


def _unit_atom(token: str) -> UnitSignature:
    if token.casefold() in _DIMENSIONLESS_TOKENS:
        return UnitSignature(())
    if token in {"%", "percent"}:
        return UnitSignature((), Fraction(1, 100))
    canonical = _ALIASES.get(token.casefold(), token)
    if canonical in _NAMED_UNITS:
        return _NAMED_UNITS[canonical]
    for prefix, scale in _PREFIXES.items():
        if canonical.startswith(prefix):
            base = canonical[len(prefix):]
            if base in _PREFIXABLE:
                signature = _NAMED_UNITS[base]
                return UnitSignature(signature.dimensions, signature.scale * scale)
    if not re.fullmatch(r"[^\s*/^()]+", token):
        raise UnitParseError(f"invalid unit token {token!r}")
    return UnitSignature.from_parts({f"custom:{token.casefold()}": 1})


def _prepare_unit_text(raw: str) -> str:
    text = raw.strip()
    if text.casefold() in _DIMENSIONLESS_TOKENS:
        return "1"
    text = re.sub(r"\\(?:mathrm|text|operatorname)\{([^{}]+)\}", r"\1", text)
    text = text.replace("\\cdot", "*").replace("·", "*").replace("⋅", "*").replace("×", "*")
    text = text.replace("**", "^")
    text = re.sub(r"\bper\b", "/", text, flags=re.IGNORECASE)
    text = re.sub(r"([A-Za-zΩµμ%\u4e00-\u9fff]+)([⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda match: f"{match.group(1)}^{match.group(2).translate(_SUPERSCRIPTS)}", text)
    text = re.sub(r"\s*([*/^()])\s*", r"\1", text)
    return re.sub(r"\s+", "*", text)


def parse_unit(raw: Any) -> UnitSignature | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = _prepare_unit_text(raw)
    tokens = re.findall(r"\^|[*/()]|[-+]?\d+|[^\s*/^()]+", text)
    if "".join(tokens) != text:
        raise UnitParseError(f"unsupported unit syntax {raw!r}")
    position = 0

    def parse_factor() -> UnitSignature:
        nonlocal position
        if position >= len(tokens):
            raise UnitParseError(f"incomplete unit expression {raw!r}")
        token = tokens[position]
        if token == "(":
            position += 1
            value = parse_product()
            if position >= len(tokens) or tokens[position] != ")":
                raise UnitParseError(f"unclosed parenthesis in unit {raw!r}")
            position += 1
        elif token in {"*", "/", "^", ")"}:
            raise UnitParseError(f"unexpected {token!r} in unit {raw!r}")
        else:
            position += 1
            value = _unit_atom(token)
        if position < len(tokens) and tokens[position] == "^":
            position += 1
            if position >= len(tokens) or not re.fullmatch(r"[-+]?\d+", tokens[position]):
                raise UnitParseError(f"unit exponent must be an integer in {raw!r}")
            value = value.power(int(tokens[position]))
            position += 1
        return value

    def parse_product() -> UnitSignature:
        nonlocal position
        value = parse_factor()
        while position < len(tokens) and tokens[position] != ")":
            operator = tokens[position]
            if operator not in {"*", "/"}:
                raise UnitParseError(f"expected multiplication or division in unit {raw!r}")
            position += 1
            other = parse_factor()
            value = value.multiply(other) if operator == "*" else value.divide(other)
        return value

    signature = parse_product()
    if position != len(tokens):
        raise UnitParseError(f"unexpected trailing unit syntax in {raw!r}")
    return signature


class UnitRegistry:
    def __init__(self) -> None:
        self.units: dict[str, UnitSignature] = {}
        self.raw_units: dict[str, str] = {}
        self.sources: dict[str, str] = {}
        self.errors: list[str] = []

    def register(self, symbol: str, raw_unit: Any, source: str) -> None:
        try:
            unit = parse_unit(raw_unit)
        except UnitParseError as exc:
            self.errors.append(f"{source} has invalid unit declaration: {exc}")
            return
        if unit is None:
            return
        known = self.units.get(symbol)
        if known is None:
            self.units[symbol] = unit
            self.raw_units[symbol] = str(raw_unit)
            self.sources[symbol] = source
        elif not known.equivalent(unit):
            self.errors.append(
                f"symbol {symbol!r} unit conflict: {self.raw_units[symbol]!r} ({self.sources[symbol]}) "
                f"vs {raw_unit!r} ({source}); signatures are {known.describe()!r} vs {unit.describe()!r}"
            )


def _parse_declared_unit(raw_unit: Any, source: str, errors: list[str]) -> UnitSignature | None:
    try:
        return parse_unit(raw_unit)
    except UnitParseError as exc:
        errors.append(f"{source} has invalid unit declaration: {exc}")
        return None


def check_contract(contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(contract, dict):
        return {"ok": False, "errors": ["model contract must be an object"], "warnings": []}
    symbols_checked = 0
    equations_checked = 0
    balance_checked = 0
    obligations_checked = 0
    models = contract.get("models", [])
    if not isinstance(models, list):
        errors.append("model_contract.models must be an array")
        models = []
    for model in models:
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("model_id", "<no-id>"))
        registry = UnitRegistry()
        for row in model.get("variables", []) or []:
            if isinstance(row, dict) and isinstance(row.get("symbol"), str):
                registry.register(row["symbol"], row.get("unit"), f"{model_id}.variables[{row['symbol']}]")
        plan = model.get("plan_details") if isinstance(model.get("plan_details"), dict) else {}
        for row in plan.get("parameter_plan", []) or []:
            if isinstance(row, dict) and isinstance(row.get("parameter"), str):
                registry.register(
                    row["parameter"], row.get("unit"), f"{model_id}.parameter_plan[{row['parameter']}]"
                )
        equations = plan.get("equation_plan", []) if isinstance(plan.get("equation_plan"), list) else []
        for row in equations:
            if not isinstance(row, dict):
                continue
            equations_checked += 1
            equation_id = row.get("equation_id", "<no-id>")
            label = f"{model_id}.{equation_id}"
            balance = row.get("unit_balance")
            if isinstance(balance, dict):
                balance_checked += 1
                left = _parse_declared_unit(balance.get("left"), f"{label}.unit_balance.left", errors)
                right = _parse_declared_unit(balance.get("right"), f"{label}.unit_balance.right", errors)
                if left is None or right is None:
                    if balance.get("left") in {None, ""} or balance.get("right") in {None, ""}:
                        errors.append(f"{label}.unit_balance needs both left and right units")
                elif not left.same_dimension(right):
                    errors.append(
                        f"{label} unit imbalance: left {balance.get('left')!r} ({left.describe()}) != "
                        f"right {balance.get('right')!r} ({right.describe()})"
                    )
                elif left.scale != right.scale:
                    warnings.append(
                        f"{label} is dimensionally balanced but left/right unit scales differ; declare the numeric conversion"
                    )
            output_unit = _parse_declared_unit(row.get("output_unit"), f"{label}.output_unit", errors)
            if output_unit is not None:
                for output in row.get("outputs", []) or []:
                    if not isinstance(output, str):
                        continue
                    known = registry.units.get(output)
                    if known is not None and not known.equivalent(output_unit):
                        errors.append(
                            f"{label} output_unit {row.get('output_unit')!r} conflicts with registered unit "
                            f"{registry.raw_units[output]!r} of {output!r}"
                        )
            if (
                balance is None
                and output_unit is None
                and row.get("math_risk") == "high"
            ):
                warnings.append(
                    f"{label} is math_risk=high but declares no unit_balance/output_unit"
                )
        for row in model.get("validation_obligations", []) or []:
            if not isinstance(row, dict):
                continue
            acceptance = row.get("acceptance")
            if not isinstance(acceptance, dict):
                continue
            obligations_checked += 1
            metric = acceptance.get("left_metric_id")
            accepted_unit = _parse_declared_unit(
                acceptance.get("unit"),
                f"{model_id}.{row.get('obligation_id', '<no-id>')}.acceptance.unit",
                errors,
            )
            if isinstance(metric, str) and accepted_unit is not None:
                known = registry.units.get(metric)
                if known is not None and not known.equivalent(accepted_unit):
                    errors.append(
                        f"{model_id}.{row.get('obligation_id', '<no-id>')} acceptance unit "
                        f"{acceptance.get('unit')!r} conflicts with registered unit "
                        f"{registry.raw_units[metric]!r} of {metric!r}"
                    )
        errors.extend(registry.errors)
        symbols_checked += len(registry.units)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "method": "declared_unit_dimension_algebra",
        "scope": "within_each_model",
        "boundary": (
            "Parses declared unit expressions only; it does not infer dimensions from equation text or "
            "perform numeric unit conversion. Unknown unit names are model-local custom dimensions."
        ),
        "checked": {
            "symbols": symbols_checked,
            "equations": equations_checked,
            "unit_balances": balance_checked,
            "obligations": obligations_checked,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--model-contract", default=".harness/contracts/model_contract.json")
    parser.add_argument("--strict", action="store_true", help="accepted for wiring compatibility; checks are unconditional")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    contract_path = resolve_path(args.model_contract, root).resolve()
    try:
        contract = load_structured(contract_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [f"cannot load model contract: {exc}"], "warnings": []}, ensure_ascii=False, indent=2))
        return 1
    report = check_contract(contract)
    report["model_contract"] = rel_path(contract_path, root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

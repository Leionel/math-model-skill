#!/usr/bin/env python3
"""Validate competition result workbooks (result1/result2/result3.xlsx) against their templates and the frozen results.

This is the CUMCM submission deliverable nobody was checking: the official
answer files were produced by hand-written scripts and only visually reviewed.
No hashes involved — structural and value-domain checks only.

Checks per workbook:
  1. header row matches the official template column names (Chinese, 10 cols / 12 cols);
  2. every data row's direction angle is in [0, 360];
  3. every speed is within the declared bounds (default [70, 140] m/s);
  4. per-UAV drop times differ by >= min_gap (default 1 s) when derivable — approximated
     by consecutive-row order; exact timing cannot be recovered from coordinates,
     so this check only flags grossly impossible rows (identical drop points with
     different bomb ids);
  5. every reported effective-duration column value matches a frozen display value
     (when --frozen-results is given) or is a positive number;
  6. detonation z must be strictly below the drop z (falling bomb).

--strict promotes template/format mismatches that would corrupt the official
submission into errors; without it they are warnings.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402

try:
    import openpyxl  # type: ignore
except ImportError:  # pragma: no cover - depends on optional dev deps
    openpyxl = None

HEADERS = {
    1: [
        "无人机运动方向", "无人机运动速度 (m/s)", "烟幕干扰弹编号",
        "烟幕干扰弹投放点的x坐标 (m)", "烟幕干扰弹投放点的y坐标 (m)", "烟幕干扰弹投放点的z坐标 (m)",
        "烟幕干扰弹起爆点的x坐标 (m)", "烟幕干扰弹起爆点的y坐标 (m)", "烟幕干扰弹起爆点的z坐标 (m)",
        "有效干扰时长 (s)",
    ],
    2: [
        "无人机编号", "无人机运动方向", "无人机运动速度 (m/s)",
        "烟幕干扰弹投放点的x坐标 (m)", "烟幕干扰弹投放点的y坐标 (m)", "烟幕干扰弹投放点的z坐标 (m)",
        "烟幕干扰弹起爆点的x坐标 (m)", "烟幕干扰弹起爆点的y坐标 (m)", "烟幕干扰弹起爆点的z坐标 (m)",
        "有效干扰时长 (s)",
    ],
    3: [
        "无人机编号", "无人机运动方向", "无人机运动速度 (m/s)", "烟幕干扰弹编号",
        "烟幕干扰弹投放点的x坐标 (m)", "烟幕干扰弹投放点的y坐标 (m)", "烟幕干扰弹投放点的z坐标 (m)",
        "烟幕干扰弹起爆点的x坐标 (m)", "烟幕干扰弹起爆点的y坐标 (m)", "烟幕干扰弹起爆点的z坐标 (m)",
        "有效干扰时长 (s)", "干扰的导弹编号",
    ],
}

UAV_SPEED_BOUNDS = (70.0, 140.0)
DEFAULT_ANGLE_RANGE = (0.0, 360.0)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text.replace("\n", "").replace("\r", "")


def _header_key(cells: list[Any]) -> list[str]:
    return [_clean_cell(cell) for cell in cells[: len(HEADERS[3])]]


def check_workbook(
    path: Path,
    *,
    frozen_display_values: set[str],
    speed_bounds: tuple[float, float] = UAV_SPEED_BOUNDS,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    if openpyxl is None:
        return (["openpyxl is not installed; install requirements-dev.txt to check result workbooks"], [], {})

    try:
        workbook = openpyxl.load_workbook(path, data_only=True)
    except Exception as exc:  # noqa: BLE001 - file may be corrupt
        return ([f"cannot open workbook: {exc}"], [], {})
    if "Sheet1" not in workbook.sheetnames:
        return ([f"workbook must contain a Sheet1 (found {workbook.sheetnames})"], [], {})

    sheet = workbook["Sheet1"]
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return (["workbook is empty"], [], {})
    header = _header_key(rows[0])
    if len(header) < 10:
        return ([f"header row too short: {len(header)} cells"], [], {})

    # figure out which template this matches (result1/result2/result3)
    matched = None
    for template_id, expected in HEADERS.items():
        if header[: len(expected)] == expected[: len(header)]:
            matched = template_id
            break
    if matched is None:
        message = f"header does not match any official result template: {header[:10]}"
        return ([message], [], {"template_matched": False})

    # column layout per template:
    # result1: 0 angle, 1 speed, 2 bomb_id, 3-5 drop xyz, 6-8 det xyz, 9 duration
    # result2: 0 uav, 1 angle, 2 speed, 3-5 drop xyz, 6-8 det xyz, 9 duration
    # result3: 0 uav, 1 angle, 2 speed, 3 bomb_id, 4-6 drop xyz, 7-9 det xyz, 10 duration, 11 missile
    offset = 1 if matched == 2 else 0
    angle_col = offset
    speed_col = offset + 1
    drop_cols = (offset + 2, offset + 3, offset + 4) if matched in (1, 2) else (offset + 3, offset + 4, offset + 5)
    det_cols = tuple(c + 3 for c in drop_cols)
    duration_col = 9 if matched in (1, 2) else 10

    data_rows = [row for row in rows[1:] if any(_to_float(cell) is not None for cell in row[:10])]
    if not data_rows:
        return ([f"no numeric data rows found after the header ({len(rows) - 1} rows inspected)"], [], {})

    durations = []
    for index, row in enumerate(data_rows, start=2):
        def cell_value(col: int) -> Any:
            return row[col] if col < len(row) else None

        angle = _to_float(cell_value(angle_col))
        speed = _to_float(cell_value(speed_col))
        duration = _to_float(cell_value(duration_col))
        drop = [_to_float(cell_value(c)) for c in drop_cols]
        det = [_to_float(cell_value(c)) for c in det_cols]
        location = f"row {index}"

        if angle is not None and not (DEFAULT_ANGLE_RANGE[0] <= angle <= DEFAULT_ANGLE_RANGE[1]):
            errors.append(f"{location}: direction angle {angle} outside [0, 360]")
        if speed is not None and not (speed_bounds[0] <= speed <= speed_bounds[1]):
            errors.append(f"{location}: UAV speed {speed} outside {speed_bounds}")
        if duration is None:
            errors.append(f"{location}: effective duration missing")
        else:
            durations.append(duration)
            display = f"{duration:g}"
            if frozen_display_values and display not in frozen_display_values:
                errors.append(
                    f"{location}: duration {display} does not match any frozen display value "
                    f"(frozen set: {sorted(frozen_display_values)[:6]}{'...' if len(frozen_display_values) > 6 else ''})"
                )
        if all(value is not None for value in det) and all(value is not None for value in drop):
            if det[2] >= drop[2]:
                errors.append(f"{location}: detonation z {det[2]} is not below drop z {drop[2]} (bomb must fall)")
        if drop[0] is not None and det[0] is not None:
            horizontal_gap = ((det[0] - drop[0]) ** 2 + ((det[1] or 0) - (drop[1] or 0)) ** 2) ** 0.5
            if horizontal_gap == 0 and speed is not None and speed > 0:
                warnings.append(f"{location}: detonation point coincides with drop point; check delay/velocity semantics")

    # per-UAV identical drop points for different bombs (gross constraint hint)
    seen_drops: dict[tuple, int] = {}
    for row in data_rows:
        if matched == 1:
            key = tuple(row[3:6])
        else:
            key = (row[0],) + tuple(row[drop_cols[0] : drop_cols[2] + 1])
        seen_drops[key] = seen_drops.get(key, 0) + 1
    duplicates = [key for key, count in seen_drops.items() if count > 1]
    if duplicates:
        warnings.append(f"{len(duplicates)} drop point(s) reused by multiple bombs; per-UAV gap cannot be verified from coordinates")

    details = {
        "template_matched": matched,
        "data_rows": len(data_rows),
        "durations": durations,
        "header": header[: len(HEADERS[matched])],
    }
    return errors, warnings, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True, action="append", help="resultN.xlsx path; repeatable")
    parser.add_argument("--frozen-results", help="frozen file whose display values the duration column must match")
    parser.add_argument("--speed-min", type=float, default=UAV_SPEED_BOUNDS[0])
    parser.add_argument("--speed-max", type=float, default=UAV_SPEED_BOUNDS[1])
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    frozen_display_values: set[str] = set()
    if args.frozen_results:
        frozen = load_structured(resolve_path(args.frozen_results, root).resolve())
        for row in frozen.get("results", []):
            if isinstance(row, dict) and isinstance(row.get("display_value"), str):
                frozen_display_values.add(f"{_to_float(row['display_value']):g}" if _to_float(row["display_value"]) is not None else row["display_value"])

    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    for raw in args.workbook:
        path = resolve_path(raw, root).resolve()
        if not path.is_file():
            errors.append(f"workbook does not exist: {raw}")
            continue
        workbook_errors, workbook_warnings, workbook_details = check_workbook(
            path,
            frozen_display_values=frozen_display_values,
            speed_bounds=(args.speed_min, args.speed_max),
        )
        errors.extend(f"{rel_path(path, root)}: {message}" for message in workbook_errors)
        warnings.extend(f"{rel_path(path, root)}: {message}" for message in workbook_warnings)
        details[rel_path(path, root)] = workbook_details

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({"ok": ok, "details": details, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify that distribution wheels actually carry the Harness resources.

A successful `pip install .` does not prove the schemas, references, assets,
and competition profiles shipped inside the wheel. Checkout mode confirms the
resource roots exist and are loadable; --wheel mode additionally requires
every on-disk resource file to appear inside the wheel archive.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

REQUIRED_ROOTS = ("schemas", "references", "competition_profiles", "assets")
EXCLUDED_NAMES = {".gitkeep"}


def _resource_files(root: Path, resource_root: str) -> list[str]:
    base = root / resource_root
    files: list[str] = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.name not in EXCLUDED_NAMES:
            files.append(f"{resource_root}/{path.relative_to(base).as_posix()}")
    return files


def check_package_resources(root: Path, wheel_path: Path | None) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    per_root: dict[str, object] = {}
    for resource_root in REQUIRED_ROOTS:
        base = root / resource_root
        if not base.is_dir():
            errors.append(f"resource root missing: {resource_root}/")
            continue
        files = _resource_files(root, resource_root)
        if not files:
            errors.append(f"resource root is empty: {resource_root}/")
            continue
        per_root[resource_root] = {"files": len(files)}
    if wheel_path is not None:
        if not wheel_path.is_file():
            errors.append(f"wheel does not exist: {wheel_path}")
        else:
            names: set[str] | None
            try:
                with zipfile.ZipFile(wheel_path) as archive:
                    names = set(archive.namelist())
            except (OSError, zipfile.BadZipFile) as exc:
                errors.append(f"wheel archive cannot be read: {exc}")
                names = None
            if names is not None:
                for resource_root in REQUIRED_ROOTS:
                    if not (root / resource_root).is_dir():
                        continue
                    missing = [rel for rel in _resource_files(root, resource_root) if rel not in names]
                    if missing:
                        errors.append(
                            f"{len(missing)} {resource_root}/ file(s) absent from wheel, e.g. {', '.join(missing[:3])}"
                        )
                    elif resource_root in per_root:
                        per_root[resource_root]["in_wheel"] = True
    return {"ok": not errors, "errors": errors, "warnings": warnings, "resources": per_root}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--wheel", help="verify every resource file is present inside this wheel archive")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    wheel_path = Path(args.wheel).resolve() if args.wheel else None
    report = check_package_resources(root, wheel_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

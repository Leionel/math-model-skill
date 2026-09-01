#!/usr/bin/env python3
"""Verify that a distribution contains the Harness runtime resources.

The checkout is intentionally larger than the distributable package: local
precedents, downloaded papers, screenshots, and generated gallery files are
authoring material, not runtime dependencies.  This checker therefore
validates an explicit resource contract rather than requiring every file on
disk to appear in a wheel.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import zipfile
from pathlib import Path

REQUIRED_ROOTS = ("schemas", "references", "competition_profiles", "assets")

# These are the smallest files that prove each runtime family is usable.  The
# allowlist below deliberately covers the supported resource families without
# making every newly-added reference a packaging obligation.
REQUIRED_SENTINELS = (
    "schemas/model_contract.schema.json",
    "schemas/paper_plan.schema.json",
    "schemas/evidence_registry.schema.json",
    "references/router.md",
    "references/contracts/model_contract.md",
    "references/research/literature_evidence.md",
    "references/validation/validation_obligations.md",
    "references/contracts/figure_contract.md",
    "references/writing/abstract_guidelines.md",
    "references/review/semantic_critic_rubric.md",
    "competition_profiles/cumcm.yaml",
    "competition_profiles/mcm_icm.yaml",
    "assets/styles/mathmodel.mplstyle",
    "assets/styles/palette.json",
    "assets/templates/cumcm-2026-electronic/main.tex",
    "assets/templates/mcm-icm-2026/main.tex",
    "assets/drawio/archetypes/research_framework/example_spec.json",
    "assets/pptx_workflow/README.md",
)

# Runtime resource families are explicit.  In particular, this does not
# include assets/figure-gallery or references/precedents/local-sources.
ALLOWED_PATTERNS = (
    "schemas/*.json",
    "references/router.md",
    "references/cards/*/*.md",
    "references/contracts/*.md",
    "references/precedents/*/index.json",
    "references/precedents/figure-cards/*.md",
    "references/precedents/pattern-cards/*.md",
    "references/research/*.md",
    "references/review/*.md",
    "references/safety/*.md",
    "references/submission/*.md",
    "references/validation/*.md",
    "references/validation/profiles/*.md",
    "references/visualization/*.md",
    "references/workflow/*.md",
    "references/writing/*.md",
    "competition_profiles/*.yaml",
    "assets/drawio/archetypes/*.md",
    "assets/drawio/archetypes/*/*.drawio",
    "assets/drawio/archetypes/*/*.json",
    "assets/drawio/archetypes/*/*.md",
    "assets/pptx_workflow/README.md",
    "assets/pptx_workflow/*.pptx",
    "assets/styles/*.json",
    "assets/styles/*.mplstyle",
    "assets/templates/*/*.json",
    "assets/templates/*/*.tex",
)

DENY_PATTERNS = (
    "references/precedents/local-sources/**",
    "assets/figure-gallery/**",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.pdf",
    "*.zip",
    "*.doc",
    "*.docx",
    "*.pyc",
)


def _normalise(path: str) -> str:
    return path.replace("\\", "/").lstrip("./").lower()


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    value = _normalise(path)
    return any(fnmatch.fnmatchcase(value, _normalise(pattern)) for pattern in patterns)


def _all_resource_files(root: Path) -> list[str]:
    files: list[str] = []
    for resource_root in REQUIRED_ROOTS:
        base = root / resource_root
        if not base.is_dir():
            continue
        files.extend(
            f"{resource_root}/{path.relative_to(base).as_posix()}"
            for path in sorted(base.rglob("*"))
            if path.is_file()
        )
    return files


def _allowed_files(files: list[str]) -> list[str]:
    return [path for path in files if _matches(path, ALLOWED_PATTERNS)]


def _archive_resource_files(names: set[str]) -> list[str]:
    return sorted(
        _normalise(name)
        for name in names
        if not name.endswith("/") and any(_normalise(name).startswith(f"{root}/") for root in REQUIRED_ROOTS)
    )


def check_package_resources(root: Path, wheel_path: Path | None) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    per_root: dict[str, object] = {}
    checkout_files = _all_resource_files(root)

    for resource_root in REQUIRED_ROOTS:
        base = root / resource_root
        if not base.is_dir():
            errors.append(f"resource root missing: {resource_root}/")
            continue
        allowed = [path for path in checkout_files if path.startswith(f"{resource_root}/") and _matches(path, ALLOWED_PATTERNS)]
        if not allowed:
            errors.append(f"no allowlisted runtime resources found under {resource_root}/")
        per_root[resource_root] = {"files": len(allowed)}

    missing_checkout = [path for path in REQUIRED_SENTINELS if not (root / path).is_file()]
    errors.extend(f"required runtime sentinel missing from checkout: {path}" for path in missing_checkout)

    if wheel_path is not None:
        if not wheel_path.is_file():
            errors.append(f"wheel does not exist: {wheel_path}")
        else:
            archive_readable = True
            try:
                with zipfile.ZipFile(wheel_path) as archive:
                    names = {_normalise(name) for name in archive.namelist()}
            except (OSError, zipfile.BadZipFile) as exc:
                errors.append(f"wheel archive cannot be read: {exc}")
                archive_readable = False
                names = set()
            if archive_readable:
                resource_names = _archive_resource_files(names)
                missing = [path for path in REQUIRED_SENTINELS if _normalise(path) not in names]
                errors.extend(f"required runtime sentinel absent from wheel: {path}" for path in missing)

                denied = [path for path in resource_names if _matches(path, DENY_PATTERNS)]
                errors.extend(f"forbidden resource in wheel: {path}" for path in denied)

                unallowlisted = [path for path in resource_names if not _matches(path, ALLOWED_PATTERNS) and path not in denied]
                errors.extend(f"unallowlisted resource in wheel: {path}" for path in unallowlisted)

                for resource_root in REQUIRED_ROOTS:
                    rows = [path for path in resource_names if path.startswith(f"{resource_root}/")]
                    if resource_root in per_root:
                        per_root[resource_root]["files_in_wheel"] = len(rows)
                        per_root[resource_root]["in_wheel"] = any(
                            path.startswith(f"{resource_root}/") and path in names for path in REQUIRED_SENTINELS
                        )

    return {"ok": not errors, "errors": errors, "warnings": warnings, "resources": per_root}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--wheel", help="verify runtime sentinels and deny/unallowlisted patterns in a wheel archive")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    wheel_path = Path(args.wheel).resolve() if args.wheel else None
    report = check_package_resources(root, wheel_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

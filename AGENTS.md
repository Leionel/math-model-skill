# Repository Guidelines

## Project Structure & Module Organization

`scripts/` contains the Python Harness; its public CLI is `scripts/harness.py`, with focused code under `qa/`, `validation/`, `figures/`, and `profiles/`. JSON contracts live in `schemas/`; competition seeds are in `competition_profiles/`. Reusable guidance belongs in `references/`, Draw.io fixtures in `assets/`, tests and fixtures in `tests/`, and design reports in `docs/`. DSH integration assets (agent preset template, MCP facade, future native tool adapters) live in `integration/dsh/`; the deployed preset copy under `%DSH_HOME%\.agent-presets\` is never committed. Keep contest projects in a separate project root.

## Build, Test, and Development Commands

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
python scripts/harness.py --help
python -m unittest discover -s tests -q
python -m unittest tests.test_harness_cli -v
ruff check scripts/harness.py tests/test_harness_cli.py
```

The editable install exposes `harness`. Use targeted tests while iterating, then run full discovery. Apply Ruff to each changed Python file and related test; the command above is an example. For an external project, run `python scripts/harness.py doctor --project <PROJECT_ROOT> --offline --json` before Gate work.

## Coding Style & Naming Conventions

Target Python 3.10+, UTF-8, four-space indentation, type hints on public helpers, and `snake_case` for modules/functions. Use `PascalCase` for test classes and `test_<behavior>` methods. Keep producers deterministic where possible; structured truth belongs in JSON contracts, not generated Markdown. Update the matching schema, checker, tests, and reference documentation when changing a contract.

Avoid defensive writing and programming: do not add speculative guards, fallback branches, disclaimers, or duplicate validation for unobserved failures. Add protection when required by a concrete contract, reproduced risk, or regression test, and state the corrective action directly.

## Testing Guidelines

Every behavior change needs a focused regression test. Exercise CLI exit codes and emitted artifacts, not only helper return values. Preserve legacy-compatibility tests when changing manifest or hash semantics. Visual backend changes require schema/native-XML tests and, when available, an exported paper-scale preview.

## Commit & Pull Request Guidelines

Use short imperative subjects consistent with history, such as `Harden submission hash checks` or `Implement authoring projections`. Keep commits scoped. Pull requests should explain the affected contract or Gate, list exact test commands/results, identify migration or compatibility impact, and link issues when applicable. Attach before/after previews for visual changes.

## Integrity Rules

Never manufacture Gate PASS values, receipts, hashes, review independence, or frozen results. Treat existing user changes as owned work; do not overwrite unrelated files. Start with `README.md` and `SKILL.md` for workflow and truth-boundary details.

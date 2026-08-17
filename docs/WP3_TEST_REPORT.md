# WP3 test report

Evidence date: 2026-08-17. Commands below were actually run. A temporary
Python 3.12 dependency target was used because the default Python lacked
`numpy`/`PyYAML`; no test dependency was written into the repository.

| Check | Command | Result | Notes |
|---|---|---|---|
| Python syntax | `python -m py_compile scripts/harness.py scripts/harness_status.py scripts/qa/run_deterministic_qa.py scripts/runtime_state.py scripts/v2_gate_runtime.py ...` | PASS | CLI, runtime, normalization, capability, and projection modules compile. |
| Skill Creator validation | bundled Python `-X utf8 .../skill-creator/scripts/quick_validate.py .` | PASS | Output: `Skill is valid!`; SKILL has 188 lines and valid frontmatter. |
| metadata prompt | focused assertion over `agents/openai.yaml` | PASS | Default prompt explicitly includes `$math-modeling-skill-sion`. |
| Schema parse | JSON load over `schemas/*.schema.json` | PASS | 29 / 29 parsed. |
| CLI integration | `python -m unittest tests.test_harness_cli -v` | PASS | 7 / 7, including `--profile` assertion and cannot-override negative case. |
| WP1/WP2 focused integrity | `python -m unittest tests.test_wp1_contracts tests.test_wp2_runtime_integrity -v` | PASS | 40 / 40 after critical-rule and cross-owner digest negatives were added. |
| full unittest suite | bundled Python `-X utf8 -m unittest discover -s tests -v` | PASS | Final aggregate: 352 / 352 in 263.939 s. |
| installed CLI boundary | temporary venv, `pip install --no-deps --no-build-isolation -e .`, then `harness --help` and `harness doctor` | PASS | Editable checkout exposes the console entry and all 29 schemas. Standalone wheel resource bundling is explicitly not claimed. |
| diff and CI static checks | `git diff --check` plus YAML parse/field assertions | PASS | CI installs requirements, editable CLI, parses schemas, runs all unittests, and validates SKILL metadata on every push branch/PR. |
| online GitHub Actions run | not invoked | NOT RUN | No commit or push was authorized in this task. |
| real four-type capability benchmark | see `CAPABILITY_BENCHMARK_PLAN.md` | NOT RUN | Regression is not benchmark evidence. |

## Environment issue closed during verification

The first dependency-complete run executed 351 tests and reported nine errors
from one plotting test. The selected Anaconda Python 3.13 child had inherited a
cp312 temporary `PYTHONPATH`; eight chart subprocesses failed and the final
file assertion cascaded. The test boundary now removes `PYTHONPATH` when it
intentionally selects another Python ABI, sets UTF-8, and decodes with
replacement. The plotting test then passed, followed by the 351 / 351 green
run above. This was an environment-isolation defect, not a waived failure.

## Required negative checks covered

- fake `manifest.gates` cannot change the v2 first blocker;
- a copied run-index exit code is ignored while receipt tampering blocks;
- critical submission rules missing from a verified profile block instead of
  being guessed;
- duplicate digest ownership across a receipt and DAG is rejected;
- pending human checkpoints and stale DAG artifacts are surfaced;
- CLI and direct checker preserve failure codes and diagnostic text;
- `--profile` cannot override the manifest-owned preset;
- migration output is separate/non-destructive and init writes only v2 state.

## Final aggregate rerun

After the last CLI compatibility assertion and documentation/CI boundary
changes, the full discovery command ran 352 tests in 263.939 seconds and
returned `OK` with exit code 0.

## Interpretation boundary

Passing this report proves the stated CLI, status, contract, and negative
guardrails. It does not prove mathematical correctness, contest eligibility,
model generalization, PDF visual quality, submission readiness, or a capability
gain on real problems.

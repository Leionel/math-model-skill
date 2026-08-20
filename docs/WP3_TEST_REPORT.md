# WP3 test report

## Historical Manifest-v2 baseline (2026-08-17, before Review Plane)

The commands in this section were actually run on 2026-08-17. A temporary
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

---

# Review Execution Plane (P0) — fresh verification on 2026-08-20

## 1. Existing regression

The GLM claim of **376 / 376** was not accepted as current evidence. On
2026-08-20, its focused review suite reproduced one failure: E2E-B hard-coded
`2026-08-18` as a future timestamp, which was no longer future. After removing
that clock assumption and closing the execution-binding gaps, the actual full
command was:

`C:\ProgramData\anaconda3\python.exe -m unittest discover -s tests -v`

Result: **388 / 388 OK in 336.419 s** (352 historical baseline + 28 review
unit/integration + 8 review E2E). The schema-count assertion is now 30 after
adding `review_report.schema.json`; gate-order behavior remains factual.

## 2. New review unit/integration tests

`python -m unittest tests.test_review_execution -v` — **28 / 28 PASS** as part
of both the focused rerun and full discovery.

Prompt §24 coverage: A missing semantic report fails W2; B open high fails
W2; C resolved finding + current judge review allows pass; D paper change
stales the review; E sprint needs no judge lens; F research requires judge
lens; G submission requires one current L1+ review; H self_critic cannot
claim L1/L2; I frozen-artifact mutation breaks freshness; J hand-edited
manifest `reviewer/semantic_review` fields are ignored; K pass verdict with
open blocker/high/medium rejected; L binding digest mismatch fails; M bundle with a
previous verdict voids independence; N same-context independent_model claim
rejected; O paper change invalidates a previous pass through the full
discovery→summary chain; P `harness status` exposes severity/independence/
freshness/next action; Q `harness review --recheck` validates and registers
the report as a real DAG `review_report` node. Additional negatives: research
L0 fallback without the degraded marker fails; foreign-run evidence cannot
satisfy or poison the current run; malformed current evidence blocks instead
of silently falling back; path traversal, report tampering, invalid receipt
cwd, open medium findings, and unsafe run-id path components are rejected;
`check_gates --gate w2` surfaces review-evidence errors.

## 3. Review E2E

`python -m unittest tests.test_review_e2e -v` — **8 / 8 PASS** as part of both
the focused rerun and full discovery.

Real end-to-end drives `harness review --fresh --backend-cmd` on a complete
minimal sprint project (contract → obligations → freeze → evidence → plan →
draft), with a deterministic stub reviewer executed through
`run_and_record.py --stage review`:

- E2E-A: the stub critic returns one open high finding on an overclaim the
  deterministic QA cannot see; the run fails, and a receipt, bundle, report
  artifact, and DAG node exist; `check_gates --gate w2` prints the finding id.
- E2E-B: author-side revision + re-review with the finding resolved; the
  review plane returns exit 0 with no errors and the newest report is current.
- E2E-C: a paper change after a passing review makes W2 fail with
  "changed since review"/"stale".
- E2E-D: the materialized bundle contains only allow-listed roles; poisoning
  it with a `previous_verdict` role voids the independence claim
  deterministically.
- Backend self-promotion from L1 to L2 is rejected; protected author mutation
  and bundle-input rewriting are detected; invalid output is quarantined and
  a later conforming review recovers without deleting history.
- Human-mode CLI emits live phase progress on stderr.

The E2E proves the Execution Plane (pre-execution input hashing, receipt/cwd/
output binding, materialized bundle integrity, report contract, registration,
gate consumption). It does **not** prove OS-level filesystem isolation or LLM
review quality.

## 4. Skill validation

Fresh static checks on 2026-08-20:

- Skill Creator quick validator: `Skill is valid!` (SKILL.md: 205 lines).
- JSON parse: 30 / 30 schemas.
- `py_compile`: harness/review/receipt/gate modules PASS.
- `git diff --check`: PASS (only Git's expected LF→CRLF warnings).

## 5. Environment limitations

No online GitHub Actions run (no push authorized). The stub reviewer is a
fixture. `--recheck` validates/registers existing review evidence only; run
`harness validate --strict` separately for the full W2 QA set. OS-level
sandboxing, automatic revision loops, finding-history monotonicity, decision
memo generation, and per-finding QA subset selection remain unimplemented.

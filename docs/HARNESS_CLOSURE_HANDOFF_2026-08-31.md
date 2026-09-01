# Harness Closure Handoff

> Updated: 2026-09-01
> Branch: `refactor/human-visible-workflow`
> Scope: S1–S6 from `docs/HARNESS_CLOSURE_PLAN_2026-08-30.md`; S0/S7 real-paper runs remain explicitly excluded.

## Completed slices

| Slice | Outcome | Commit |
|---|---|---|
| Plan | Audited, narrowed implementation plan | `f51753f` |
| S1 | Portable release resources and real-wheel integrity checks | `6eb08f2` |
| S2 | Author-owned Markdown/YAML separated from derived machine views | `73d167c` |
| S3 | Reader-facing marker integrity, figure audience contract, visual opportunity scan | `6785272` |
| S4 | Argument-first writing spine, bounded context/revision, reverse outline | `8960025` |
| S5 | Coverage-driven literature obligations with v1.3 compatibility | `eac6635` |
| S6 | Stable ruleset fingerprint and six-family public CLI surface | `9a90fa0` |

Each slice was root-reviewed and committed separately. User-owned `.qoder/` remains untracked and untouched.

## Verification evidence

- Full suite: `python -m unittest discover -s tests -v` → **660/660 passed** in 762.362 s.
- S5 plus legacy P0: **37/37 passed**; includes v1.3 compatibility and rejection of verified evidence outside `full_text_core`.
- S6 CLI/ruleset/context group: **23/23 passed**; focused ruleset rerun: **4/4 passed**.
- Package-resource group: **7/7 passed**.
- Real wheel built with `python -m pip wheel . --no-deps`; resource checker passed with 31 schemas, 108 references, 5 competition-profile files, and 28 asset files. The temporary wheel was removed after verification.
- `ruff check` passes for every Python file changed in `061ae8e..HEAD`.
- `python scripts/harness.py --help` and `git diff 061ae8e..HEAD --check` pass.

Full-repository Ruff is not green: it reports 19 pre-existing findings outside this change range. They were not mixed into the closure commits.

## Review invariants preserved

- No new top-level Agent, Gate, or canonical artifact.
- No fixed paper/model/figure/query quotas.
- Internal locator/review IDs are rejected only when reader-visible; comments and legitimate labels remain usable.
- Ruleset identity is a cache hint, never a Gate/freshness bypass.
- Generated views remain derived; author sources and compiled Gate truth remain distinct.
- No fabricated PASS, receipt, review independence, hash, result, or citation verification.

## Remaining work

1. Run S0/S7 on one real contest paper with fresh receipts, results, evidence, reviews, and PDF; do not reuse prior Gate state.
2. Have an uninvolved reader inspect only the final PDF for argument clarity, evidence traceability, figure necessity, and residual machine-facing prose.
3. If desired, address the 19 repository-wide Ruff findings in a separate maintenance change.
4. The test suite repeatedly collects inherited/imported P0 cases; optimize test organization only as a separate, measured maintenance task.
5. Push this branch only when explicitly requested; no push is part of this handoff.

# Contributing

## Before you open a change

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
python -m unittest discover -s tests -q          # 729 tests
python scripts/harness.py agents check            # agent contract scope
python evaluation/redteam.py                      # reliability probes
ruff check <every changed .py file>               # repo-wide ruff is not green
```

`harness --help` must keep working, and every existing CLI entry point is a
compatibility surface: prefer adding a façade over renaming a command.

## The three ownership layers

| Layer | Truth | Must never become |
| --- | --- | --- |
| execution fact | `command_receipt` | a manifest command string |
| projection | `run_index`, `.harness/views/**` | a second digest registry or a PASS |
| control decision | `run_manifest.control` | a flat Gate status field |

A change that lets any of these swap roles is a correctness bug even if every
test passes.

## Contracts first, then code

Changing an artifact contract means updating the schema, the producer, the
checker, a focused regression test, and the matching `references/` entry in the
same change. `tests/test_wp1_contracts.py` holds the packaged-schema count, so
add a schema deliberately.

Adding or widening an agent role means editing `agents/<role>/agent.yaml` and
keeping `harness agents check` green. That check exists so a contract cannot
claim a tool, role, schema, reference or Gate the repository does not have.

## What we do not do

- Do not manufacture a Gate PASS, receipt, hash, review verdict, frozen result
  or independence claim. A reviewer/human may create a new schema-valid report;
  nobody rewrites an existing one to force a pass.
- Do not add a Gate or an agent role to make the architecture look more
  complete. Gates are state transitions, not a count.
- Do not describe a plan, demo or green regression suite as a capability
  benchmark. `evaluation/ablation.py` reports `NOT_RUN` until real runs exist,
  and it must keep doing so.
- Do not weaken the safety invariants in `scripts/profiles/capabilities.py`
  (`SAFE_INVARIANTS`) with an override, a preset or a convenience flag.
- Do not commit contest projects, past-paper PDFs you do not have rights to, or
  anything under `battle/`, `tmp/` or `.harness/`.

## Test expectations

Every behavior change needs a focused regression test that exercises the CLI
surface — exit codes and emitted artifacts, not just a helper's return value.
Preserve v1-compatibility coverage when touching manifest or hash semantics.
Visual or figure backend changes need schema tests plus a paper-scale preview
when a backend is available.

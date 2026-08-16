# Question-Scoped Parameter and Event Contract

`scope_contract` is an optional `model_contract` 1.3 extension for problems in which the same symbol, parameter name, time origin, coordinate frame, or event phrase can change meaning across questions.

It addresses a concrete failure mode: a solver uses the value or reference event from one question in another question, while the code, Markdown draft, and rendered PDF silently disagree. The contract is deliberately semantic and local; it does not require SHA-256 during ordinary development.

## Contract shape

The extension has `schema_version: "1.0"` and contains:

- `scopes[]`: one question-scoped namespace, with official parameters, units, values, source locators, and distinctive paper section markers;
- `events[]`: reference events such as a time origin or coordinate frame, with a question, definition, and paper markers;
- `models[].scope_ids` and `models[].event_ids`: explicit bindings from implementation models to the relevant scope and events.

Each parameter can optionally declare `required_tokens` and `forbidden_tokens`. These are not a substitute for mathematical review; they are narrow regression guards for known high-cost mix-ups. For example, a Q4 scope can forbid the Q1 pitch value and a Q4 event can forbid the wrong time origin.

## Checks

Run the contract-only check when the paper is not yet available:

```powershell
python scripts/qa/check_scope_consistency.py `
  --model-contract model_contract.json `
  --require-scope-contract `
  --strict
```

Run the contract plus paper-section check after the draft exists:

```powershell
python scripts/qa/check_scope_consistency.py `
  --model-contract model_contract.json `
  --paper paper/main.tex `
  --require-scope-contract `
  --strict
```

The checker verifies:

1. scope and event IDs are unique and point to known questions;
2. parameter IDs and symbols are unique within a scope;
3. model bindings point to the same question as the model;
4. every ready scope is bound to a model;
5. required and forbidden tokens are evaluated inside the marked paper section, not against the whole document.

An old contract without `scope_contract` remains valid in ordinary development. `run_deterministic_qa.py` checks the extension when present and accepts `--require-scope-contract` for a profile that has migrated to this gate. The extension should become mandatory for multi-question research/submission profiles only after their contract fixtures have been migrated.

## What this does not claim

The checker does not prove that a value was copied from the official attachment, prove algebraic equivalence, or establish global optimality. The `source_locator`, derivation, replay, and independent W2 review remain necessary. It also does not use hashes as a local change detector; submission-level immutable manifests retain that responsibility.

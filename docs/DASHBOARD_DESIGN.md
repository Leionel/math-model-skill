# Dashboard design

Position: an **observability console**, not an operator surface. It is closer to
an MLflow run page than to a CI dashboard — its job is to make one Harness run
legible, and to make a false claim in that run impossible to hide.

```text
python dashboard/server.py --project <ROOT> --port 8765
        │
        ├── GET /                static console (no build step, no dependency)
        ├── GET /api/snapshot    one recomputed view, assembled below
        └── POST /*              405, always
        │
        ▼
snapshot(root)
   ├── mcp:get_run_state     stage · gate_status · blockers · next actions
   ├── mcp:list_artifacts    every DAG node with recomputed freshness
   ├── run_index.json + receipts/*.json     execution facts
   ├── reports/review/*.json                review evidence
   └── run_manifest.json                    preset, checkpoints, AI ledger
```

## Why it reads through MCP

The console calls the same tools an external agent calls
(`docs/MCP_ARCHITECTURE.md`). There is one read path, so a human staring at the
dashboard and an agent calling `get_run_state` cannot see different worlds.
`snapshot()["sources"]` names them, and the console test asserts at least one
`mcp:` source is present.

The console narrows the MCP fail-closed root allowlist to the single project it
was started with (`_narrow_mcp_roots`). If `MATH_HARNESS_ALLOWED_ROOTS` is
already configured, the served project must fall inside it; otherwise the
console refuses. `DASHBOARD_ALLOWED_ROOTS` adds a second, operator-level check
at `serve()` time.

## What it shows

**Gate strip.** `S0 … F1`, each `passed`, `blocked`, `locked` or `boundary`.
S0 and F1 are marked `boundary` because `harness check` only accepts M1, P1, P2,
W1, W2 and S1 — rendering them as "locked" would imply a pending Gate that no
code can recompute. Each Gate also shows whether a human checkpoint exists.

**Blockers with the repair action.** `failures_summary` items already carry a
`next_action`; the console shows message and action together, because an
operator's real question is "what do I run now".

**Run timeline.** Executions and reviews merged and sorted by their recorded
timestamps, each row colored by the receipt's exit code or the report's verdict.
This is the "agents can fail and the Harness stopped it" view.

**Artifact lineage.** An SVG layout computed from `artifact_dag.json`
dependencies at request time: layered columns, node = role + id, red border when
freshness is not `current`. No React Flow and no bundler: a console that needs
`npm install` before an interviewer can look at it is a console that will not be
looked at.

**Receipts and reviews.** Receipt id, stage, whether it is the selected one, its
exit code and argv; review perspective, independence level, verdict and finding
count. Independence is drawn as four pips because `L0_same_context` through
`L3_human` is an ordinal scale, and the console's job is to make the gap between
"L0" and "L2" visible without reading a spec.

## Sheet system

Two surfaces, chosen by the `auto / light / dark` button and remembered in
`localStorage`: a cool paper sheet and a deep slate sheet. Both carry the same
state hues, lifted for contrast in dark rather than swapped, so a passed Gate is
the same fact on either surface. `auto` follows `prefers-color-scheme`; a judge
who never touches the button sees the sheet their own system asked for.

Interface language switches between English and Chinese the same way. Only
interface text is translated: blocker messages, `next_action` strings, artifact
roles, ids and enums stay exactly as the Harness emitted them, because
paraphrasing evidence text would put words in it that the evidence does not say.
Chinese sets the interface roles in Noto Serif SC (Source Han Serif) with a
Latin-and-Han single family, which is the typeface convention of the paper this
Harness audits; technical tokens stay in the mono role at every language.

Type roles are three: a DIN-derived condensed face for Gate ids and the verdict
word, a text face for prose, and a mono face for every identifier, path, exit
code and timestamp (tabular figures). Spacing is a 4px scale; hierarchy comes
from the surface ladder (`field` → `panel` → `chip`) plus 2px ink rules, not from
shadows. The focus ring is its own blue token, never the failure red — in a
console where red means "this claim was refuted", red on focus would be a lie.

The graph paper is confined to the artifact-lineage canvas, where it is the
plotting field rather than wallpaper. The gate chain is the signature device:
S0 and F1 render as hatched open ends because no checker recomputes them, and a
connector is solid only when both of its endpoints passed, so the break in the
chain sits exactly where the Harness actually stopped.

`@media print` forces the paper sheet and drops the controls, because this page
is evidence people will hand to another person.

### Client-only controls

`pause`, the theme button and the language button change only what this browser
renders. None of them sends a request the console could not have sent before,
and `POST` is still refused with 405. `pause` exists because the 5-second poll
otherwise re-renders the page under someone who is mid-sentence copying a
blocker.

## What it does not do

There is no approve button, and that is load-bearing.

```text
POST /api/approve → 405
{ "error": "the console is read-only by design",
  "why":   "a Gate PASS, freeze, receipt or human decision must come from a
            producer command or a control-state record, never from a dashboard button",
  "instead": "harness check <GATE> · harness freeze · harness ai verify · harness review" }
```

Two reasons, both grounded in measurements rather than taste:

1. **A verdict cannot be granted by a view.** Every Gate is recomputed from
   files at read time; a button that "approves" would either call a producer
   command (then it is a thin client, fine) or write state itself (then it is a
   bypass). The first version refuses to be ambiguous about which.
2. **Human identity is not attested today.** `evaluation/redteam.py` runs the
   `fabricated_human_checkpoint` scenario and records its real outcome: dropping
   a W1 checkpoint fails the Gate, and re-adding one under an arbitrary
   `decided_by` passes it. Shipping a friendly "Approve freeze" button on top of
   an unattested field would advertise a control that does not exist.

### What would make an approval path acceptable

Two of the four now hold, and they are what makes an operator mode honest rather
than a shortcut: the write goes through `harness checkpoint approve`, and the ledger
is append-only and hash-linked per entry. Each decision also carries `actor_class`,
and a Gate that needs a human counts only `human` rows — so an agent driving an
`auto` run cannot clear a human Gate silently; it has to claim a human was there,
which is the same lie the next bullet is about.

Still open:

- the record binds an identity the Harness can check (a pre-shared role key, or
  an external identity token) instead of a free-text `decided_by`;
- `scenario_human_checkpoint_is_unattested` flips from `expected: allowed` to
  `expected: blocked` in the same change that closes identity — the suite fails if
  the docs and the code disagree. Its counterpart
  `scenario_agent_checkpoint_cannot_clear_a_human_gate` already asserts `blocked`.

## Testing

`tests/test_dashboard.py` asserts the properties, not the pixels:

- the snapshot reports `read_only`, recomputes the blocked Gate, and labels S0/F1
  as `boundary`;
- `/` and `/api/snapshot` serve; unknown routes 404;
- **serving does not mutate the project** — a SHA-256 over the whole tree must be
  identical before and after;
- `POST` returns 405 with the producer command to use instead;
- `serve()` exits 2 when the project is outside `DASHBOARD_ALLOWED_ROOTS`.

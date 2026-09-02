# Human-Prose Revision

> Scope: editorial diagnosis of evidence-safe draft prose. This reference does
> not detect authorship, assign a humanity score, or authorize a rewrite of
> facts, mathematics, evidence, competition rules, or author files.

## Where it applies

Review prose in section openings and closures, model-selection explanations,
result interpretation, transitions, abstracts, and conclusions. Do not edit
equation bodies, tables, code, bibliography entries, raw evidence, frozen
results, or submission declarations. If a defect concerns those protected
surfaces, emit a finding for semantic/evidence review and stop editing it.

The default context is deliberately local:

- the current draft section;
- its Section Brief and the relevant Writing Spine excerpt;
- this reference and the Human Editorial Naturalness section of
  `editorial_style.md`;
- existing reverse-outline observations.

Read a protected claim, candidate-model decision, or writer-package locator
only when a finding needs it. Do not load all contracts, results, review
history, visualization guidance, or the Sepia repository.

## Diagnose first

Never translate “this sounds generated” into a whole-section rewrite. Use this
sequence:

```text
locate passage
→ name the editorial defect
→ decide whether it is isolated or clustered
→ propose the smallest action
→ list protected content
→ specify rechecks
```

A finding must quote the passage or give an exact section locator. One formal
transition, complete grammar, one long sentence, one three-item list, CEEL, or
one short paragraph is not a finding. Report a pattern only when related moves
cluster locally and materially reduce information or obscure the argument.

## Five checks

### 1. Information gain

Ask what the paragraph adds relative to what the reader already knows. A useful
paragraph contributes a claim, evidence, mechanism, interpretation, boundary,
comparison, decision, or necessary dependency. If it contributes none, prefer
deletion, merging, or compression. A generic recap is not preserved merely
because it closes a section.

### 2. Argument-move sequence

Label neighboring paragraphs with one primary move such as `define`, `derive`,
`compare`, `observe`, `explain`, `validate`, `qualify`, `decide`, or
`transition`. Look for repeated local sequences such as:

```text
result → generic interpretation → recap
result → generic interpretation → recap
result → generic interpretation → recap
```

Do not demand artificial variety. Compress routine observations and retain a
full explanation only where mechanism or validation evidence warrants it.

### 3. Compression opportunity

Ask whether the passage can materially shrink without losing evidence,
mechanism, qualification, or a necessary transition. Prefer removing question
restatement, figure narration, repeated conclusions, generic significance,
generic praise, and nested announce–tell–recap structures. Do not use a fixed
percentage target.

Revision priority is:

```text
delete → merge → replace → reorder → minimally insert
```

Add connective information only when the existing argument requires it. Do not
add “值得注意”“有趣的是”“我们发现” or similar filler as simulated voice.

### 4. Decision and comparison explicitness

When the paper states a model or方案 choice, check whether the prose names the
actual discriminating evidence and, when relevant, the condition under which
the choice would reverse. A list of generic criteria is not a rationale. Use
only comparison evidence already bound to the candidate decision or writer
package; if no comparison exists, do not invent one.

### 5. Rhythmic over-regularity

Review clusters of near-equal paragraph length, repeated sentence frames,
concentrated transitions, identical closure functions, repeated three-part
lists, and fractal summaries at several heading levels. Unevenness should follow
argument importance, difficulty, decision relevance, and evidence richness—not
random perturbation. Formal academic register and stable technical terminology
remain correct.

## CEEL is not a paragraph template

CEEL is a semantic-completeness lens. It does not require every paragraph to
contain four sentences or to repeat Claim → Evidence → Explanation → Limitation
in that order. Accept, according to the actual role:

- a routine result as Claim + Evidence;
- a decisive result followed by a separate mechanism/validation paragraph;
- an interpretation that directly hands off to the next decision;
- an already-established boundary without mechanical restatement, provided the
  current claim does not expand its scope.

Never delete a qualification that is still required to keep a claim true.

## Protected content and escalation

Human-prose revision must preserve frozen numbers, units, rankings, solver and
test status, equations, variable/constraint/objective meaning, model identity,
claim strength, causal direction, robustness and optimality scope, evidence
locators, citations, official rules, AI disclosure, and submission state.

Do not manufacture failed models, experiments, surprises, debugging stories,
parameter searches, rejected candidates, opinions, or personal experience.
Real recorded traces may be retained; missing traces may not be created.

If the proposed edit might alter a claim direction, boundary, formula meaning,
numeric interpretation, or citation meaning, do not edit. Route the finding to
semantic review and require the appropriate consistency/math/evidence recheck.

## Finding contract

Use the existing `review_report` contract with `perspective=human_prose`.
Each finding records:

- one of `low_information_gain`, `repeated_argument_move`, `excessive_recap`,
  `generic_decision_rationale`, `over_regular_rhythm`,
  `transition_concentration`, `redundant_exposition`, or `mechanical_ceel`;
- an exact locator and short quoted passage;
- a diagnosis based on argument readability, never an AI probability;
- the smallest `required_fix`;
- protected content and required rechecks.

Severity is `low` for an isolated edit, `medium` for a clustered local problem,
and `high` only when prose organization materially hides the argument or model
choice. `blocker` is forbidden for this perspective. It has no Gate authority,
does not count as independent mathematical validation, and cannot upgrade its
evidence scope.

Use `review` to diagnose only. Targeted revision consumes the existing bounded
revision package and never overwrites author Markdown automatically. Full
section recreation is disabled by default; when a user explicitly requests it,
rebuild only from bound writer-package facts and rerun consistency, math
writing, claim/evidence, reverse-outline, deterministic QA, and required review.

Mechanism inspiration: Sepia's diagnose-first, cluster-based and minimal-edit
approach. The rules above are adapted specifically for mathematical-modeling
papers and do not import Sepia's fiction or technical-blog prescriptions.

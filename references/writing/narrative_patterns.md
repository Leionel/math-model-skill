# Narrative Writing Patterns

These are positive composition patterns for a math-modeling paper. They guide how
a Writer turns already-approved claims and evidence into a readable argument;
they do not create facts, relax claim boundaries, or replace a review.

Use only the cards selected in the writer package or the card relevant to the
section being revised. Do not turn every card into a separate mandatory chapter.

## Problem Framing

Use before a model when the reader needs to understand why modeling is needed.

```text
task tension
→ decision object
→ known conditions
→ actual difficulty
→ mathematical abstraction
→ paper route
```

State what decision or answer is needed, which conditions matter, and what
makes the task non-trivial. Do not merely repeat the statement or front-load
unverified results.

## Model Exposition

Use when introducing a selected model or a shared mechanism.

```text
real mechanism
→ mathematical object
→ variables and units
→ core relation
→ equation
→ constraints
→ behavior interpretation
```

An equation is the formalization of a mechanism already explained in prose. Say
what each relationship changes in the system and how a constraint affects the
feasible decision; do not begin with a block of unexplained formulas.

## Alternative Rejection

Use when a candidate model was considered and not selected.

```text
candidate capability
→ failure under this task
→ selected candidate's repair
→ selection cost
→ decision rationale
```

Reuse existing candidate-model rationale, failure evidence, complexity, and
validation plan. A rejection must identify a task-specific limitation rather
than describe one model as generically “better”.

## Result Interpretation

Use after a result, table, or evidence figure. The default is CEEL:

```text
Claim → Evidence → Explanation → Limitation
```

For a surprising result, add: observation → why surprising → mechanism →
alternative explanation → validation → boundary.

For a comparison, add: winner or trade-off → exact difference → reason →
condition under which the ranking changes. Do not make a causal, optimality, or
robustness claim beyond its approved evidence.

## Cross-Question Synthesis

Use for global or cross-question material rather than forcing it into one
question chapter.

```text
previous output
→ new decision
→ inherited assumption
→ new constraint
→ downstream consequence
```

Name the interface explicitly: what passes from the earlier question, what is
new here, and how the new result changes a later decision. This pattern is for
real dependency, not a mechanical transition sentence.

## Model Critique and Conclusion

Use when closing a model, a major decision, or the paper.

```text
strength with validation evidence
→ weakness with failure or sensitivity evidence
→ boundary
→ specific extension
```

A strength must cite what was actually validated. A weakness should identify
what the current analysis did not cover. An extension should state which
mechanism, data boundary, or validation duty would change—not use generic
claims of “strong robustness” or “good generalization”.


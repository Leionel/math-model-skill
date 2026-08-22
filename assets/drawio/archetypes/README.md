# Draw.io academic archetype fixtures

These fixtures are visual-regression inputs for the Harness composition engine. They are **not** fixed XML templates with replaceable labels.

This batch covers native XML, schema, geometry, and deterministic-source regression. SVG/PNG previews are exported with draw.io Desktop when needed; they are not checked in as a substitute for target-size paper review.

The implementation borrows only the mechanisms identified in section 16 of `docs/drawio_academic_archetype_upgrade_prompt.md`:

- research-framework skeleton, continuous model pipeline, central method container, and meaningful loop relationships;
- one primary reading order, academic hierarchy, compact labels, semantic grouping, orthogonal routing, and paper-scale QA.

| Section 16 reference | Borrowed mechanism | Local archetype fixture |
|---|---|---|
| `ai-jiaqian/drawio-figure-replicator` | Research Framework skeleton | `research_framework/` |
| `ai-jiaqian/drawio-figure-replicator` | Continuous Model Pipeline | `computational_pipeline/` |
| `ai-jiaqian/drawio-figure-replicator` | Central-container composition with platform semantics removed | `method_architecture/` |
| `ai-jiaqian/drawio-figure-replicator` | Meaningful, evidence-backed cycle rather than a decorative flywheel | `iterative_optimization/` |
| `QIANJINYDX/research-drawio-skill` | One reading order, semantic grouping, compact labels, orthogonal routing, and paper-scale QA | all fixtures, especially `parallel_integration/` |

It does not copy external XML, retain software-platform semantics, depend on another repository at runtime, assume a 16:9 concept-board canvas, or introduce a second palette system.

Each directory contains:

- `example_spec.json`: semantic source used by the planner;
- `README.md`: expected composition grammar and review points;
- `example.drawio`: deterministic native output generated from the spec.

The files are examples and QA fixtures only. Runtime figures must still flow
from `diagram_spec -> archetype resolver -> composition grammar -> primitive
planner -> geometry -> existing semantic styling`; replacing labels inside an
example `.drawio` is not a supported generation path.

Generate the actual figure at its target column/page width and inspect it before submission. A successful Desktop export proves only that the native source can be rendered; it does not certify final paper-scale readability.

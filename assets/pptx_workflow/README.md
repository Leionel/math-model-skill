# PPTX workflow references

These local PPTX files are editable composition references for concept/process/framework
figures. They are not evidence sources, paper templates, or a reason to reproduce
their labels, data, or conclusions.

## Inspection inventory

The repository inspected every source slide with the presentation template-inspection
workflow, including slide render, structural layout, shape, connector, and text
records.

| Reference | Slides | Selected composition patterns |
|---|---:|---|
| 美赛流程图无敌2025.pptx | 24 | slide 1: sectioned overview (49 shapes, 19 connectors); slide 5: decision/action path (8, 1); slide 13: grouped model pipeline (61, 23) |
| 数学建模论文流程图2.pptx | 10 | slide 1: factor-to-mechanism framework (40, 5); slide 4: bounded model structure (47, 14); slide 5: staged method (57, 17) |
| 数学建模论文流程图5.pptx | 1 | alternate four-question board palette |
| 数学建模论文流程图6.pptx | 1 | four-question board (73 shapes, 18 connectors) |
| 数学建模论文流程图7.pptx | 1 | three-phase model board (92 shapes, 20 connectors) |

The imported 24-slide deck emitted connector auto-routing fallback warnings during
inspection. Its rendered slides remain useful as references, but any copied
connector must be visually checked and rebound in PowerPoint if needed.

## Normal route

For a conceptual figure, start with:

```powershell
python scripts/harness.py figure FIG-01 --semantic-type workflow --prepare-pptx --project C:\work\math-q1 --json
```

The command creates a brief, selects a catalogued source slide, and copies the
source deck once to figures/FIG-01/FIG-01.pptx. It never overwrites an existing
copy, so later PowerPoint edits remain owned by the author.

Edit the staged copy in PowerPoint (or through the presentation template-following
workflow), using the selected source slide as a composition starting point. Retain
only evidence-backed nodes, edges, labels, and colors. Create connectors behind
nodes; render an export; then inspect it at the actual paper size.

Use Draw.io only when an editable native-XML/topology contract is specifically
needed:

```powershell
python scripts/harness.py figure FIG-01 --semantic-type workflow --diagram-backend drawio --fallback-reason "native topology QA required" --project C:\work\math-q1 --json
```

Data and result figures remain deterministic plotting artifacts. PPTX concept
figures must not be used to invent quantitative claims or Gate outcomes.

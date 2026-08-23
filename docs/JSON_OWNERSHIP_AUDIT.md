# JSON Ownership Audit

This audit classifies the current 30 schemas by ownership, not by a desire to
make the file count look smaller. It is a migration decision record: no schema
or historical artifact is deleted by this document.

| Artifact | Producer | Consumer | Human edits? | Rebuildable? | Unique truth | Decision |
|---|---|---|---:|---:|---|---|
| `competition_profile` | profile import/maintainer | safety, S1 | yes, verified source only | no | official-rule provenance | KEEP |
| `run_manifest` | init/control producers | every Gate | bounded control edits | no | preset, roots, decisions | KEEP |
| `artifact_dag` | producers | freshness/Gates | no | not safely today | artifact identity/digest owner | KEEP |
| `run_index` | receipt indexer | selection/status | no | yes | none beyond receipt selection projection | REBUILD |
| `command_receipt` | process recorder | P1/P2 | no | no | process fact | KEEP |
| `build_receipt` | build producer | W2/S1 | no | no | build fact | KEEP |
| `submission_receipt` | submission freeze | F1 | no | no | immutable delivery fact | KEEP |
| `model_contract` | model Markdown compiler | M1/validation | no after compile | yes | machine IR only | COMPILE |
| `problem_snapshot` | project brief compiler | M1/review | no after compile | yes | normalized problem IR | COMPILE |
| `data_contract` | research/data compiler | validation | no after compile | yes | normalized data boundary | COMPILE |
| `implementation_map` | solution-report compiler | P1/P2 | no after compile | yes | implementation IR | COMPILE |
| `paper_plan` | paper-plan compiler | W1/writer | no after compile | yes | paper IR | COMPILE |
| `diagram_spec` | figure-brief compiler | Draw.io/topology check | no after compile | yes when a consumer needs it | topology IR | COMPILE |
| `presentation_contract` | paper/figure compiler | W2 | no after compile | yes | layout IR | COMPILE |
| `template_contract` | template importer | build/S1 | no | no | imported-template identity | KEEP |
| `visual_profile` | maintainer/user | figure producer | yes | no | selected visual policy | KEEP |
| `evidence_registry` | evidence producer | W1/review | no | no | verified evidence provenance | KEEP |
| `frozen_results` | result freeze | W1/W2/F1 | no | no | claimable result identity | KEEP |
| `derived_results` | derivation producer | evidence/writer | no | yes from frozen input | derivation provenance while current | KEEP |
| `validation_report` | independent validator | P2/W2 | no | no | validation verdict | KEEP |
| `failure_evidence` | failed-run producer | model/review | no | no | counterexample/failure fact | KEEP |
| `sensitivity_experiment` | experiment producer | validation/writer | no | no | sensitivity run fact | KEEP |
| `oos_artifact` | evaluator | validation | no | no | out-of-sample fact | KEEP |
| `extremum_certificate` | solver/checker | validation | no | no | optimum-bound fact | KEEP |
| `figure_qa` | figure QA | W2 | no | yes from current figure | generated QA view | REBUILD |
| `pdf_visual_qa` | PDF QA | W2/S1 | no | yes from current PDF | generated QA view | REBUILD |
| `visual_review_receipt` | human/visual reviewer | W2 | no | no | review fact | KEEP |
| `review_report` | reviewer execution | W2 | no | no | semantic-review fact | KEEP |
| `claim_inventory` | inventory producer | W2/status | no | yes | none beyond source claims | REBUILD |
| `submission_manifest` | F1 freeze | delivery verification | no | no | immutable package identity | KEEP |

## Migration rules

- `COMPILE` means Markdown/YAML is the authoring source and the existing JSON
  remains a validated machine IR. The vNext `harness model --compile` is the
  first implemented producer; the other entries must not be hand-migrated.
- `REBUILD` artifacts remain generated evidence/projections until their
  consumer migration is complete. Rebuild through the producer; never edit a
  report, index, or inventory to manufacture a favourable state.
- `KEEP` preserves receipts, frozen facts, verified provenance, official rules
  and immutable delivery bindings. This audit does not weaken any Gate.

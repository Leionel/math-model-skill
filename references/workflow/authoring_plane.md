# Authoring Plane

The Authoring Plane makes canonical Harness state readable without creating another truth layer.

## Author sources and compiled IR

`00_PROJECT_BRIEF.md`、研究/模型/求解报告、Paper Director Plan、section briefs 和 figure briefs 都是可编辑的作者源；`init` 与 authoring façade 只在文件缺失时创建它们，`prepare` 不会覆盖人工内容。作者 Markdown 只承载问题理解、理由、假设和叙事；需要机器消费的结构化 source 放在 `.harness/authoring/`。

```text
human Markdown                 .harness/authoring/*.yaml
        │                                  │
        │  authoring migrate (legacy only) │
        └──────────────┬───────────────────┘
                       ▼
                 compile + schema validation
                       ▼
             .harness/contracts/*.json
```

这些命令从 `.harness/authoring/*.yaml` 编译 schema-valid IR；旧项目在显式迁移前仍可从 Markdown 中的 legacy fenced YAML block 读取。它们不核验研究、运行、图形、证据或 Gate。Paper section 可用任意安全 slug，并以 `--role` 记录软性的写作角色；`question`、`cross_question` 与 `global` scope 是论证组织，不会强行改写论文目录。

```powershell
harness authoring check                 # 只读检查 source/output/compiler 是否 stale
harness authoring migrate --dry-run    # 预览旧 Markdown block 的迁移
harness authoring migrate               # 显式移入 YAML，并移除 legacy block
```

迁移会先检查目标 source 是否冲突，以及已有 compiled JSON 的语义是否保持一致；冲突时停止，不覆盖人工内容。重复运行迁移是幂等的。`compile_index.json` 位于 `.harness/authoring/`，只记录 source/output/schema/compiler 的哈希与版本，是可重建的 stale 检测索引，不是 Gate 或新的事实真源。

## JSON ownership

- **KEEP**：profile、receipt、frozen result、validation report、evidence registry、failure evidence 与 submission manifest 是事实或 provenance，继续由既有 producer 管理。
- **COMPILE**：research basis、model contract、implementation map、paper plan 与 diagram spec 从作者 Markdown 的显式 source block 生成；不要直接手写它们的 JSON。
- **REBUILD**：run index、claim inventory、figure/PDF QA 和 authoring compile index 等机器投影可随权威输入重算，不能被人工编辑成事实。

## Commands and outputs

| Command | Deterministic outputs | Canonical inputs |
|---|---|---|
| `harness prepare M1` | `.harness/views/M1_STATE.md`, `PROJECT_BRIEF.md` | model contract, manifest, profile, DAG/index |
| `harness prepare W1` | `.harness/views/W1_STATE.md`, `APPENDIX_PLAN.md`, `PROJECT_BRIEF.md` | paper plan IR, frozen result reference, runtime state |
| `harness prepare W2` | `.harness/views/W2_STATE.md`, refreshed `PROJECT_BRIEF.md` | runtime Gate evaluation, DAG freshness, review evidence |
| `harness prepare S1` | `.harness/views/AI_USAGE_LEDGER.md`, disclosure draft, `SUBMISSION_STATE.md`, staging directories, `PROJECT_BRIEF.md` | profile, AI registry/state, runtime state |

Every projection contains:

```text
Generated projection — factual state remains in Harness contracts/receipts.
```

and a list of source paths with SHA-256. The digest proves which bytes were rendered; it does not prove the source is semantically correct. Editing a projection cannot pass a Gate. Regenerate it after changing the canonical source.

## AI usage tri-state

`run_manifest.ai_usage_state` is one of:

- `unknown`: initial state; S1 must block;
- `none`: allowed only after `harness ai confirm-none` records an explicit human declaration;
- `used`: requires one or more auditable entries. External unobservable uses enter through `harness ai record`; Harness-triggered review backends are recorded automatically as `pending` and must be completed with `harness ai verify`.

The S1 hash binds the state, explicit declaration, and records. Changing `unknown` to `none`, editing the human declaration, or adding/removing a record invalidates a stale S1 report even when the usage list is empty in both cases.

The disclosure renderer uses only the canonical profile and AI registry. It uses `AI工具使用详情` for CUMCM and `Report on Use of AI Tools` for other profiles. It never invents missing prompt, adoption, modification, or verification details.

`--backend-cmd` therefore requires an explicit `--backend-kind`; `ai` additionally requires tool, model, and provider identity, while `non_ai` is not written into the AI registry. The execution receipt is the interaction record, and strict Contest Safety rejects a pending AI record until a human verifies how the report was checked and changed.

## Submission staging

`prepare S1` creates:

```text
submission/
├── staging/
│   ├── support/
│   ├── ai_disclosure/
│   └── official_outputs/
└── final/
```

`staging/` is mutable preparation space. `final/` remains empty until the existing F1 producer freezes a passing package. `prepare` never uploads and always reports `submission_ready: false`.

## Deferred boundaries

R8 的结构性收口已经具备：作者 Markdown 是人读工作面，`.harness/authoring/*.yaml` 是结构化可编辑 source，编译机器 IR，`init` 非覆盖地生成带解释的最小作者模板，`setup/status/prepare` 只展示当前阶段的能力、阻断和投影；31 个 schema 均有脚本消费者，`audit_contract_consumption.py --strict` 不再报告 orphan/test-only schema。该审计仍是静态引用清单，不是运行期调用覆盖率。

仍不宣称“赛时填写负担已显著下降”：这个效果只能由 R1 的真实赛题从 `init` 到 M1/W1 记录字段数和用时来证明。内部文件全量迁入 `.harness/`、自动执行选择性重跑以及 capability benchmark 也不属于 authoring projection 的职责；现有选择性重跑只生成可刷新计划，敏感性 sweep 才执行真实命令。

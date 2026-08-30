"""Human-authored project documents and thin workflow façades.

This module owns only the authoring surface.  It deliberately does not infer
research, model choices, results, receipts, or Gate outcomes.  Those facts
continue to live in the existing Harness producers and contracts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from _common import load_structured, rel_path, resolve_path, write_json_atomic
from project_layout import resolve_control_path, resolve_manifest_path


HARNESS_ROOT = Path(__file__).resolve().parent.parent


HUMAN_DOCUMENTS: dict[str, str] = {
    "00_PROJECT_BRIEF.md": """# 项目简报

> 这是研究工作的作者文档，不是 Gate 状态或机器投影。请在开始调研前填写题目、交付边界和已知约束。

## 题目与目标

题目来源：

真正需要回答：

预期交付：

## 已知输入

- 题面：
- 数据/附件：
- 官方规则快照：

## 约束与风险

- 时间/资源：
- 合规与 AI 使用：
- 当前不确定性：
""",
    "01_RESEARCH_NOTES.md": """# 调研与问题理解

> 这是持续更新的研究工作文档。把来源、发现、解释和建模后果写成一条链；不要把它写成论文目录或检索结果清单。

## 1. 题目到底在要求什么

### Q1

题面要求：

真正需要回答：

输出应该是什么：

## 2. 小问之间的关系

- 哪一问为后续提供输入：
- 哪些任务可以独立：
- 跨题共享的变量或约束：

## 3. 数据初步判断

数据规模：

时间跨度：

变量类型、缺失、异常与可能泄漏：

## 4. 现实 / 数学机制

先解释哪些因素为什么影响结果、哪些约束来自现实、哪些关系可能是线性、非线性、动态、空间或网络结构；此处不要直接跳到模型名。

## 5. 调研方向

### 方向 A

方法是什么：

为什么与本题有关：

查到什么（来源 → 发现 → 对本题的解释 → 建模后果）：

局限：

## 6. 候选方法池

| 小问 | 候选方法 | 保留原因 | 主要风险 |
|---|---|---|---|

## 7. 被排除的方法

说明每个方法为何不适合本题条件，而不是只写“复杂”或“效果可能不好”。

## 8. 调研真正改变了什么决策

- 保留：
- 删除：
- 新增：
- 改变的假设：
- 下一步最需要验证：

## 9. 仍未解决的问题

- [ ]

## Machine contract source (optional)

仅当模型合同或研究审阅实际需要结构化调研基础时填写。只写能被下游消费的检索、候选、排除和未决问题；运行 `harness research --compile` 生成 research-basis IR，不能把它当作文献已核验或模型已通过的证据。

```yaml
# research_basis:
#   status: draft
```
""",
    "02_MODEL_DECISION.md": """# 模型选型报告

> 这是作者的模型决策来源。需要机器消费者时，在末尾的可选 YAML block 中声明合同并运行 `harness model --compile`；不要手工维护平行 JSON。

## 总体建模路线

数据 → 模型 A → 中间结果 → 模型 B → 最终决策 → 验证

## Q1

### 1. 目标

### 2. 核心数学机制

### 3. 候选 A

原理：

为什么适合：

不适合在哪里：

实现复杂度：

验证方式：

### 4. 候选 B

### 5. 候选比较

按数学适配、数据要求、可解释性、稳健性、时间复杂度、求解规模、后续小问支持和竞赛时间成本比较。

### 6. 最终模型

主模型：

Baseline：

为什么这样选：

### 7. 数学定义

决策变量：

目标函数：

关键约束/方程：

### 8. 输入输出接口

输入来自：

输出进入下一小问的方式：

### 9. Validation Plan

### 10. Failure Plan

Plan B：

切换条件：

## Machine contract source (optional)

Only add a complete contract after this decision is ready for a machine consumer.  The compiler accepts either a root mapping or a `model_contract:` mapping in the fenced YAML block below.

```yaml
# model_contract:
#   schema_version: "1.0"
```
""",
    "03_SOLUTION_REPORT.md": """# 模型求解与结果报告

> 在每一次重要 smoke/full run 或模型替换后增量更新。失败是研究证据，不能在这里被抹去；运行事实仍以 Harness receipt 为准。

## 当前状态

哪些问题已完成：

哪些仍在运行：

哪些失败：

## Q1

### 1. 实际实现

实现语言、库、入口，以及与模型选型报告的差异：

### 2. 数据处理

实际数据、清洗和训练/验证边界：

### 3. 参数和配置

### 4. Smoke Run

运行目的、结果与发现的问题：

### 5. Full Run

实际运行、耗时、是否成功和对应 receipt：

### 6. 求解过程中出现的问题

问题、原因、修改和修改理由：

### 7. 最终结果

### 8. Baseline / Candidate Comparison

### 9. Validation

通过与失败的检查：

### 10. 结果解释

解释机制，不要只复述数字：

### 11. 可信边界

### 12. 可以进入论文的结果

### 13. 暂时不能进入论文的结果
## Machine contract source (optional)

仅当现有 implementation-map consumer 需要可追溯的实现映射时填写。这里不复制 receipt、exit code 或冻结结果；真实运行事实继续由 receipt 和 frozen results 负责。运行 `harness solve --compile` 只生成 schema-valid implementation-map IR。

```yaml
# implementation_map:
#   schema_version: "1.0"
```

""",
    "paper/00_PAPER_PLAN.md": """# 论文导演稿 / Paper Director Plan

> 这是正文写作的作者规划，不是 `paper_plan.json` 的人话副本。先用它决定整篇论文如何回答问题、组织论证和暴露薄弱点；需要机器消费者时，才在末尾填入完整 YAML source block 并编译。`paper_plan.json` 仍是机器 IR，二者都不能假装为 Gate 事实。

## 1. 全文中心问题

这篇论文到底要解决什么？

## 2. 中心结论 / Central Thesis

评委读完整篇后最应该记住什么？

## 3. 论证主线

Q1 得到什么 → 如何进入 Q2 → Q2 新增什么决策 → 后续问题如何验证或扩展 → 最终建议如何形成。

## 4. 小问依赖关系

| 小问 | 输入来自 | 主要输出 | 输出流向 |
|---|---|---|---|

## 5. 各章角色

| Section | 为什么存在 | 读完应该相信什么 | 主要证据 |
|---|---|---|---|

## 6. 模型与候选选择

## 7. 决定性结果

## 8. 必须展示的验证

## 9. Figure / Table Narrative

哪些结论靠文字即可，哪些必须由表或图承担；每个 Figure/Table 在全文叙事中解决什么阅读问题。

## 10. Appendix Strategy

正文保留什么；哪些推导、表格或代码移到附录。

## 11. 当前弱点

- 仍缺什么 evidence：
- 哪个 claim 还太弱：
- 哪一节最容易写空：

## Machine contract source (optional)

Machine source 中的每个 `argument_unit` 可用 `depth_priority: {level: core|supporting|compact, rationale: ...}` 标出论证优先级；它服务于叙事取舍，不是前置字数 Gate。

只在 W1/W2 的机器消费者确实需要完整 `paper_plan` IR 时填写。不要直接手写 `.harness/contracts/paper_plan.json`；运行 `harness paper plan --compile` 从本 block 编译。

```yaml
# paper_plan:
#   schema_version: "1.3"
```
""",
}

HIDDEN_DIRECTORIES = (
    ".harness/contracts",
    ".harness/receipts",
    ".harness/evidence",
    ".harness/results",
    ".harness/reports",
    ".harness/indexes",
    ".harness/cache",
    ".harness/views",
)

SECTION_TEMPLATE = """# Section Brief

> Soft structural role: {role}. It guides drafting only and does not create a Gate, claim, or fixed question scope.

## Section role

## Argument scope

- Type: question | cross_question | global
- Question IDs:

## 本节回答什么问题

## 读者读完后应该相信什么

## 前置结论

## 模型

## 必须解释的数学逻辑

## 必须出现的公式

## 可使用结果

## 可使用图表

## 必须解释的结果

## 本节边界

## 禁止声称
"""

DRAFT_TEMPLATE = """# Draft

> 只撰写本节。每个结论都应说明它来自哪项模型、结果或验证；不要用未冻结结果补空白。
"""

REVIEW_TEMPLATE = """# Semantic Review

> Review the current section for reasoning quality. This is not a deterministic QA report and does not create a Gate verdict.

## Blockers

## Logic Gaps

## Empty / Generic Prose

## Missing Mechanism

## Overclaim

## Suggested Revision Order
"""

FIGURE_BRIEF_TEMPLATE = """# {figure_id}

## Purpose

## Main message

## Reader should understand

## Required elements

## Required relations

## Primary reading order

## Visual references

Primary:

Secondary:

Borrow:

Do not copy:

## Source evidence

## Must not include

## Output (choose the route declared for this figure)

- data figure: deterministic plotting script + frozen-result source; never a generated bitmap
- diagram (editable): PPTX reference copy or Draw.io XML source + PDF/SVG/PNG export + preview PNG
- illustration: native image generation when the agent exposes it and the competition profile allows it
  - generation request record (prompt, parameters, DPI) via `harness figure {figure_id} --request-illustration`
  - collected raster + SHA-256 + AI usage entry + scientific/visual/final-size review before any formal use
  - it must not carry quantitative claims, formulas, or fabricated labels

## Machine contract source (optional)

仅在 machine diagram producer 确实需要结构化图规格时填写完整 `diagram_spec`；运行 `harness figure {figure_id} --compile`。探索性草图无需补 JSON，且本 block 不会产生 figure claim、receipt 或 Gate 结论。

```yaml
# diagram_spec:
#   schema_version: "1.0"
```
"""

_SECTION_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SECTION_ROLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")
_FIGURE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _normalize_section_id(section_id: str) -> str:
    normalized = section_id.strip().casefold()
    if not _SECTION_SLUG.fullmatch(normalized):
        raise ValueError("section slug must start with a letter or digit and use only letters, digits, dots, underscores, or hyphens")
    return normalized


def _normalize_section_role(role: str | None) -> str | None:
    if role is None:
        return None
    normalized = role.strip()
    if not normalized or not _SECTION_ROLE.fullmatch(normalized):
        raise ValueError("section role must use only letters, digits, spaces, underscores, or hyphens")
    return normalized


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return True


def ensure_human_surface(root: Path) -> dict[str, list[str]]:
    """Create the non-destructive authoring skeleton for a project root."""

    created: list[str] = []
    existing: list[str] = []
    for directory in HIDDEN_DIRECTORIES:
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "paper" / "sections").mkdir(parents=True, exist_ok=True)
    (root / "figures").mkdir(parents=True, exist_ok=True)
    for relative, content in HUMAN_DOCUMENTS.items():
        path = root / relative
        if _write_if_missing(path, content):
            created.append(relative)
        else:
            existing.append(relative)
    return {"created": created, "existing": existing}


def ensure_section(root: Path, section_id: str, *, role: str | None = None) -> dict[str, Any]:
    normalized = _normalize_section_id(section_id)
    normalized_role = _normalize_section_role(role)
    ensure_human_surface(root)
    section = root / "paper" / "sections" / normalized
    brief = SECTION_TEMPLATE.format(role=normalized_role or "unspecified")
    created = [
        name
        for name, content in (("brief.md", brief), ("draft.md", DRAFT_TEMPLATE), ("review.md", REVIEW_TEMPLATE))
        if _write_if_missing(section / name, content)
    ]
    return {
        "section": normalized,
        "role": normalized_role,
        "path": str(section),
        "created": created,
    }


def ensure_figure_brief(root: Path, figure_id: str) -> dict[str, Any]:
    if not _FIGURE_ID.fullmatch(figure_id):
        raise ValueError("figure id must use only letters, digits, dots, underscores, or hyphens")
    ensure_human_surface(root)
    directory = root / "figures" / figure_id
    created = _write_if_missing(directory / "brief.md", FIGURE_BRIEF_TEMPLATE.format(figure_id=figure_id))
    return {"figure_id": figure_id, "path": str(directory), "created": ["brief.md"] if created else []}


_MACHINE_SOURCE_HEADING = re.compile(
    r"^## Machine contract source(?: \(optional\))?\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)


def _project_relative(path: Path, root: Path, *, label: str) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the project root") from exc


def _resolve_authoring_source(root: Path, source: str | None, default_source: str, *, label: str) -> Path:
    source_path = resolve_path(source or default_source, root).resolve()
    _project_relative(source_path, root, label=label)
    if not source_path.is_file():
        raise ValueError(f"{label} does not exist: {source_path}")
    return source_path


def _resolve_compiled_output(root: Path, output: str | None, default_output: str, *, label: str) -> Path:
    output_path = resolve_path(output or default_output, root).resolve()
    _project_relative(output_path, root, label=label)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _read_contract_source(source: Path, *, root_key: str, source_label: str) -> dict[str, Any]:
    text = source.read_text(encoding="utf-8")
    heading = _MACHINE_SOURCE_HEADING.search(text)
    if heading is None:
        raise ValueError(f"{source_label} is missing the 'Machine contract source' section")
    block = re.search(
        r"```(?:yaml|yml|json)\s*\n(.*?)\n```",
        text[heading.end():],
        flags=re.DOTALL | re.IGNORECASE,
    )
    if block is None:
        raise ValueError("Machine contract source must contain a fenced YAML or JSON block")
    payload = block.group(1)
    if not any(line.strip() and not line.lstrip().startswith("#") for line in payload.splitlines()):
        raise ValueError("Machine contract source is still the empty template")
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - requirements-dev installs PyYAML
        raise RuntimeError("authoring compilation requires PyYAML; install requirements-dev.txt") from exc
    loaded = yaml.safe_load(payload)
    if not isinstance(loaded, Mapping):
        raise ValueError("Machine contract source must be a YAML object")
    candidate = loaded.get(root_key, loaded)
    if not isinstance(candidate, Mapping):
        raise ValueError(f"{root_key} must be an object")
    return dict(candidate)


def _validate_contract(
    contract: Mapping[str, Any],
    schema_path: Path,
    *,
    label: str,
    schema_ref: str | None = None,
) -> None:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - requirements-dev installs jsonschema
        raise RuntimeError("authoring compilation requires jsonschema; install requirements-dev.txt") from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema_ref is not None:
        definitions = schema.get("$defs")
        if not isinstance(definitions, Mapping):
            raise ValueError(f"{schema_path.name} has no definitions for {schema_ref}")
        schema = {
            "$schema": schema.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
            "$defs": definitions,
            "$ref": schema_ref,
        }
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(dict(contract)), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        location = ".".join(str(item) for item in first.absolute_path) or "root"
        raise ValueError(f"{label} schema validation failed at {location}: {first.message}")


def _update_manifest_root(root: Path, manifest_path: Path, role: str, output_path: Path) -> str | None:
    if not manifest_path.is_file():
        return None
    manifest = load_structured(manifest_path)
    if not isinstance(manifest, Mapping):
        raise ValueError("run_manifest must be an object")
    updated = dict(manifest)
    roots = dict(updated.get("roots", {})) if isinstance(updated.get("roots"), Mapping) else {}
    roots[role] = {"path": _project_relative(output_path, root, label="compiled contract")}
    updated["roots"] = roots
    write_json_atomic(manifest_path, updated)
    return rel_path(manifest_path, root)


def _compile_contract(
    root: Path,
    *,
    source: str | None,
    output: str | None,
    default_source: str,
    default_output: str,
    root_key: str,
    source_label: str,
    schema_path: Path,
    schema_ref: str | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    ensure_human_surface(root)
    source_path = _resolve_authoring_source(root, source, default_source, label=source_label)
    contract = _read_contract_source(source_path, root_key=root_key, source_label=source_label)
    _validate_contract(contract, schema_path, label=root_key, schema_ref=schema_ref)
    output_path = _resolve_compiled_output(root, output, default_output, label="compiled contract")
    write_json_atomic(output_path, contract)
    return contract, source_path, output_path


def _research_basis_from_source(source_path: Path, schema_path: Path) -> dict[str, Any]:
    basis = _read_contract_source(
        source_path,
        root_key="research_basis",
        source_label="research notes source",
    )
    _validate_contract(
        basis,
        schema_path,
        label="research_basis",
        schema_ref="#/$defs/research_basis",
    )
    return basis


def compile_research_basis(
    root: Path,
    *,
    source: str | None,
    output: str | None,
    model_schema_path: Path,
) -> dict[str, Any]:
    """Compile the optional research-basis block without asserting research facts."""

    _, source_path, output_path = _compile_contract(
        root,
        source=source,
        output=output,
        default_source="01_RESEARCH_NOTES.md",
        default_output=".harness/contracts/research_basis.json",
        root_key="research_basis",
        source_label="research notes source",
        schema_path=model_schema_path,
        schema_ref="#/$defs/research_basis",
    )
    return {
        "source": _project_relative(source_path, root, label="research notes source"),
        "output": _project_relative(output_path, root, label="compiled research basis"),
        "compiled": True,
        "authority_note": "This is planning IR only; it does not verify literature, create evidence, or pass a Gate.",
    }


def compile_model_contract(
    root: Path,
    *,
    source: str | None,
    output: str | None,
    schema_path: Path,
    manifest_path: Path | None = None,
    research_source: str | None = None,
) -> dict[str, Any]:
    """Compile explicit Markdown/YAML authoring sources to model-contract IR."""

    ensure_human_surface(root)
    source_path = _resolve_authoring_source(root, source, "02_MODEL_DECISION.md", label="model decision source")
    contract = _read_contract_source(source_path, root_key="model_contract", source_label="model decision source")
    research_path: Path | None = None
    if research_source is not None:
        research_path = _resolve_authoring_source(
            root,
            research_source,
            "01_RESEARCH_NOTES.md",
            label="research notes source",
        )
        if "research_basis" in contract:
            raise ValueError("model contract already contains research_basis; use one Markdown source of truth")
        contract["research_basis"] = _research_basis_from_source(research_path, schema_path)
    _validate_contract(contract, schema_path, label="model contract")
    output_path = _resolve_compiled_output(
        root,
        output,
        ".harness/contracts/model_contract.json",
        label="compiled model contract",
    )
    write_json_atomic(output_path, contract)
    active_manifest = manifest_path.resolve() if manifest_path is not None else resolve_manifest_path(root)
    manifest = _update_manifest_root(root, active_manifest, "model_contract", output_path)
    return {
        "source": _project_relative(source_path, root, label="model decision source"),
        "research_source": (
            _project_relative(research_path, root, label="research notes source")
            if research_path is not None
            else None
        ),
        "output": _project_relative(output_path, root, label="compiled model contract"),
        "compiled": True,
        "manifest": manifest,
        "gate_note": "Compilation creates machine IR only; run the existing M1 checker for a factual Gate verdict.",
    }


def compile_paper_plan(
    root: Path,
    *,
    source: str | None,
    output: str | None,
    schema_path: Path,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Compile the Paper Director Plan's explicit YAML block to existing W1 IR."""

    _, source_path, output_path = _compile_contract(
        root,
        source=source,
        output=output,
        default_source="paper/00_PAPER_PLAN.md",
        default_output=".harness/contracts/paper_plan.json",
        root_key="paper_plan",
        source_label="paper plan source",
        schema_path=schema_path,
    )
    active_manifest = manifest_path.resolve() if manifest_path is not None else resolve_manifest_path(root)
    manifest = _update_manifest_root(root, active_manifest, "paper_plan", output_path)
    return {
        "source": _project_relative(source_path, root, label="paper plan source"),
        "output": _project_relative(output_path, root, label="compiled paper plan"),
        "compiled": True,
        "manifest": manifest,
        "gate_note": "Compilation creates paper-plan IR only; evidence, freshness, human review, and W1/W2 verdicts remain separate.",
    }


def compile_solution_implementation_map(
    root: Path,
    *,
    source: str | None,
    output: str | None,
    schema_path: Path,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Compile implementation mapping only; receipts and frozen facts stay authoritative."""

    _, source_path, output_path = _compile_contract(
        root,
        source=source,
        output=output,
        default_source="03_SOLUTION_REPORT.md",
        default_output=".harness/contracts/implementation_map.json",
        root_key="implementation_map",
        source_label="solution report source",
        schema_path=schema_path,
    )
    active_manifest = manifest_path.resolve() if manifest_path is not None else resolve_manifest_path(root)
    manifest = _update_manifest_root(root, active_manifest, "implementation_map", output_path)
    return {
        "source": _project_relative(source_path, root, label="solution report source"),
        "output": _project_relative(output_path, root, label="compiled implementation map"),
        "compiled": True,
        "manifest": manifest,
        "authority_note": "This maps implementation intent only; run receipts, selected runs, validation facts, and frozen results are not copied from this document.",
    }


def compile_figure_diagram_spec(
    root: Path,
    figure_id: str,
    *,
    source: str | None,
    output: str | None,
    schema_path: Path,
) -> dict[str, Any]:
    """Compile a figure brief only when a structured diagram producer needs it."""

    brief = ensure_figure_brief(root, figure_id)
    _, source_path, output_path = _compile_contract(
        root,
        source=source,
        output=output,
        default_source=f"figures/{figure_id}/brief.md",
        default_output=f".harness/contracts/figures/{figure_id}_diagram_spec.json",
        root_key="diagram_spec",
        source_label="figure brief source",
        schema_path=schema_path,
    )
    return {
        "brief": brief,
        "source": _project_relative(source_path, root, label="figure brief source"),
        "output": _project_relative(output_path, root, label="compiled diagram spec"),
        "compiled": True,
        "authority_note": "This is a diagram producer input only; it does not create a figure claim, receipt, rendered artifact, or Gate outcome.",
    }


def authoring_context(root: Path, stage: str) -> dict[str, Any]:
    """Return a deliberately small context manifest for a workflow stage."""

    normalized = stage.casefold()
    rows: list[tuple[str, str, bool]]
    skipped: list[str]
    competition_profile = rel_path(resolve_control_path(root, "competition_profile.json"), root)
    if normalized == "research":
        rows = [
            ("00_PROJECT_BRIEF.md", "scope and delivery boundary", True),
            (competition_profile, "current competition-rule source", True),
            ("01_RESEARCH_NOTES.md", "current research document", True),
            ("references/research/literature_evidence.md", "source/evidence boundary", True),
        ]
        skipped = ["model contracts", "paper plans", "submission references"]
    elif normalized == "model":
        rows = [
            ("00_PROJECT_BRIEF.md", "problem scope", True),
            ("01_RESEARCH_NOTES.md", "research findings and rejected methods", True),
            (".harness/contracts/research_basis.json", "compiled research basis when available", False),
            ("02_MODEL_DECISION.md", "current authoring target", True),
            ("references/research/model_planning.md", "model-selection guidance", True),
        ]
        skipped = ["writing references", "submission references", "unrelated paper sections"]
    elif normalized == "solve":
        rows = [
            ("02_MODEL_DECISION.md", "selected-model rationale and failure plan", True),
            (".harness/contracts/model_contract.json", "compiled machine contract when available", False),
            ("03_SOLUTION_REPORT.md", "run/result narrative to update", True),
            (".harness/contracts/implementation_map.json", "compiled implementation map when available", False),
            ("references/validation/validation_obligations.md", "declared validation duties", True),
        ]
        skipped = ["paper-writing references", "submission references"]
    elif normalized.startswith("paper:"):
        section = _normalize_section_id(normalized.split(":", 1)[1])
        rows = [
            ("paper/00_PAPER_PLAN.md", "paper-wide narrative and section role", True),
            (f"paper/sections/{section}/brief.md", "section scope and evidence boundary", True),
            (f"paper/sections/{section}/draft.md", "only draft allowed to change", True),
            (".harness/reports/writer_package.json", "controlled claim/fact source for formal drafting; prefer it over raw frozen results", False),
            (f".harness/views/sections/{section}_brief.md", "compiled section Writer Brief projection when a plan exists", False),
            (".harness/views/WRITING_SPINE.md", "whole-paper argument-chain projection when a plan exists", False),
            (".harness/contracts/paper_plan.json", "compiled paper plan when available", False),
            (".harness/contracts/model_contract.json", "model definitions when available", False),
            (".harness/results/frozen_results.json", "frozen numbers; only consult when the writer package is absent", False),
            ("references/writing/editorial_style.md", "section-writing guidance", True),
            ("references/writing/narrative_patterns.md", "positive narrative patterns for the current argument", True),
        ]
        skipped = ["other paper sections", "full Harness repository", "submission references"]
    else:
        raise ValueError("context stage must be research, model, solve, or paper:<section>")
    loaded = []
    for path, why, required in rows:
        location = "harness" if path.startswith("references/") else "project"
        base = HARNESS_ROOT if location == "harness" else root
        loaded.append({"path": path, "location": location, "why": why, "required": required, "exists": (base / path).is_file()})
    return {"stage": normalized, "loaded_files": loaded, "optional_files_skipped": skipped}

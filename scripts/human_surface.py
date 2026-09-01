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

from _common import load_structured, rel_path, resolve_path, sha256_file, write_json_atomic
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

""",
    "02_MODEL_DECISION.md": """# 模型选型报告

> 这是作者的模型决策来源。需要机器消费者时，在 `.harness/authoring/model_contract.yaml` 中维护结构化合同并运行 `harness model --compile`；不要手工维护平行 JSON。

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
""",
    "paper/00_PAPER_PLAN.md": """# 论文导演稿 / Paper Director Plan

> 这是正文写作的作者规划，不是 `paper_plan.json` 的人话副本。先用它决定整篇论文如何回答问题、组织论证和暴露薄弱点；需要机器消费者时，在 `.harness/authoring/paper_plan.yaml` 中维护结构化 source 并编译。`paper_plan.json` 仍是机器 IR，二者都不能假装为 Gate 事实。

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

""",
}

AUTHORING_SOURCE_TEMPLATES: dict[str, str] = {
    ".harness/authoring/research_basis.yaml": """# 结构化调研 source：只在下游需要 research_basis IR 时填写。
# 编译：harness research --compile
# research_basis:
#   status: draft
""",
    ".harness/authoring/model_contract.yaml": """# 结构化模型合同 source：由作者维护，禁止直接编辑 compiled JSON。
# 编译：harness model --compile
# model_contract:
#   schema_version: \"1.0\"
""",
    ".harness/authoring/implementation_map.yaml": """# 结构化实现映射 source：不复制 receipt、冻结结果或 Gate 状态。
# 编译：harness solve --compile
# implementation_map:
#   schema_version: \"1.0\"
""",
    ".harness/authoring/paper_plan.yaml": """# 结构化论文规划 source：服务 W1/W2 的机器投影，不是正文草稿。
# 编译：harness paper plan --compile
# paper_plan:
#   schema_version: \"1.3\"
""",
}

HIDDEN_DIRECTORIES = (
    ".harness/authoring",
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
    for relative, content in AUTHORING_SOURCE_TEMPLATES.items():
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
    authoring_path = root / ".harness" / "authoring" / "figures" / f"{figure_id}_diagram_spec.yaml"
    authoring_created = _write_if_missing(
        authoring_path,
        "# 可选 diagram_spec source；只有结构化图生产者需要时才填写。\n"
        f"# 编译：harness figure {figure_id} --compile\n"
        "# diagram_spec:\n"
        "#   schema_version: \"1.0\"\n",
    )
    return {
        "figure_id": figure_id,
        "path": str(directory),
        "created": (["brief.md"] if created else []) + ([".harness/authoring/figures/" + f"{figure_id}_diagram_spec.yaml"] if authoring_created else []),
    }


_MACHINE_SOURCE_HEADING = re.compile(
    r"^## Machine contract source(?: \(optional\))?\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)
_MACHINE_SOURCE_BLOCK = re.compile(
    r"^## Machine contract source(?: \(optional\))?\s*$\n"
    r".*?^```(?:yaml|yml|json)\s*$\n"
    r".*?^```\s*$\n?",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

AUTHORING_INDEX_RELATIVE = ".harness/authoring/compile_index.json"
AUTHORING_INDEX_VERSION = "1.0"
AUTHORING_COMPILER_VERSION = "authoring-1"

AUTHORING_SPECS: dict[str, dict[str, str]] = {
    "research_basis": {
        "source": ".harness/authoring/research_basis.yaml",
        "legacy_source": "01_RESEARCH_NOTES.md",
        "output": ".harness/contracts/research_basis.json",
        "schema": "schemas/model_contract.schema.json",
        "schema_ref": "#/$defs/research_basis",
    },
    "model_contract": {
        "source": ".harness/authoring/model_contract.yaml",
        "legacy_source": "02_MODEL_DECISION.md",
        "output": ".harness/contracts/model_contract.json",
        "schema": "schemas/model_contract.schema.json",
    },
    "implementation_map": {
        "source": ".harness/authoring/implementation_map.yaml",
        "legacy_source": "03_SOLUTION_REPORT.md",
        "output": ".harness/contracts/implementation_map.json",
        "schema": "schemas/implementation_map.schema.json",
    },
    "paper_plan": {
        "source": ".harness/authoring/paper_plan.yaml",
        "legacy_source": "paper/00_PAPER_PLAN.md",
        "output": ".harness/contracts/paper_plan.json",
        "schema": "schemas/paper_plan.schema.json",
    },
}


def _authoring_index_path(root: Path) -> Path:
    return root / AUTHORING_INDEX_RELATIVE


def _source_has_payload(path: Path) -> bool:
    """Return whether a YAML source contains non-comment content."""

    if not path.is_file():
        return False
    return any(line.strip() and not line.lstrip().startswith("#") for line in path.read_text(encoding="utf-8").splitlines())


def _legacy_has_payload(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    heading = _MACHINE_SOURCE_HEADING.search(text)
    if heading is None:
        return False
    block = re.search(
        r"```(?:yaml|yml|json)\s*\n(.*?)\n```",
        text[heading.end():],
        flags=re.DOTALL | re.IGNORECASE,
    )
    return bool(block and any(line.strip() and not line.lstrip().startswith("#") for line in block.group(1).splitlines()))


def _project_relative(path: Path, root: Path, *, label: str) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the project root") from exc


def _resolve_authoring_source(
    root: Path,
    source: str | None,
    default_source: str,
    *,
    legacy_source: str | None = None,
    label: str,
) -> Path:
    """Resolve a new YAML source, with a narrow compatibility fallback.

    A legacy Markdown source wins only when the new source is still the
    untouched comment-only placeholder.  Once a user writes the YAML file,
    parse errors are reported instead of silently falling back to Markdown.
    """

    if source is not None:
        source_path = resolve_path(source, root).resolve()
    else:
        source_path = resolve_path(default_source, root).resolve()
        legacy_path = resolve_path(legacy_source, root).resolve() if legacy_source else None
        if (
            legacy_path is not None
            and _legacy_has_payload(legacy_path)
            and (not source_path.is_file() or not _source_has_payload(source_path))
        ):
            source_path = legacy_path
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
    if source.suffix.lower() in {".yaml", ".yml"}:
        payload = text
    elif source.suffix.lower() == ".json":
        payload = text
    else:
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
        raise ValueError("authoring source is still the empty template")
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - requirements-dev installs PyYAML
        raise RuntimeError("authoring compilation requires PyYAML; install requirements-dev.txt") from exc
    try:
        loaded = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        raise ValueError(f"{source_label} contains invalid YAML: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise ValueError("authoring source must be a YAML object")
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


def _schema_id(schema_path: Path) -> str:
    return _project_relative(schema_path.resolve(), HARNESS_ROOT, label="schema").replace("\\", "/")


def _load_authoring_index(root: Path) -> dict[str, Any] | None:
    path = _authoring_index_path(root)
    if not path.is_file():
        return None
    value = load_structured(path)
    if not isinstance(value, Mapping):
        raise ValueError("authoring compile index must be an object")
    if value.get("schema_version") != AUTHORING_INDEX_VERSION:
        raise ValueError("authoring compile index has an unsupported schema_version")
    entries = value.get("entries")
    if not isinstance(entries, list):
        raise ValueError("authoring compile index entries must be an array")
    return dict(value)


def _source_ref(root: Path, path: Path) -> dict[str, str]:
    return {"path": _project_relative(path, root, label="authoring source"), "sha256": sha256_file(path)}


def _compile_index_entry(
    root: Path,
    *,
    role: str,
    source_paths: list[Path],
    output_path: Path,
    schema_path: Path,
) -> dict[str, Any]:
    if not source_paths or any(not path.is_file() for path in source_paths):
        raise ValueError(f"cannot index {role}: authoring source is missing")
    if not output_path.is_file():
        raise ValueError(f"cannot index {role}: compiled output is missing")
    refs = [_source_ref(root, path) for path in source_paths]
    return {
        "role": role,
        "source_path": refs[0]["path"],
        "source_sha256": refs[0]["sha256"],
        "sources": refs,
        "output_path": _project_relative(output_path, root, label="compiled contract"),
        "output_sha256": sha256_file(output_path),
        "schema_id": _schema_id(schema_path),
        "schema_sha256": sha256_file(schema_path),
        "compiler_version": AUTHORING_COMPILER_VERSION,
    }


def _record_compile_index(
    root: Path,
    *,
    role: str,
    source_paths: list[Path],
    output_path: Path,
    schema_path: Path,
) -> None:
    index = _load_authoring_index(root) or {
        "schema_version": AUTHORING_INDEX_VERSION,
        "compiler_version": AUTHORING_COMPILER_VERSION,
        "entries": [],
    }
    entries = [entry for entry in index["entries"] if isinstance(entry, Mapping) and entry.get("role") != role]
    entries.append(
        _compile_index_entry(
            root,
            role=role,
            source_paths=source_paths,
            output_path=output_path,
            schema_path=schema_path,
        )
    )
    index["compiler_version"] = AUTHORING_COMPILER_VERSION
    index["entries"] = sorted(entries, key=lambda entry: str(entry.get("role", "")))
    write_json_atomic(_authoring_index_path(root), index)


def _authoring_spec_for_role(root: Path, role: str) -> dict[str, str] | None:
    """Return the source/schema mapping for a compiled role."""

    if role in AUTHORING_SPECS:
        return {"role": role, "root_key": role, **AUTHORING_SPECS[role]}
    prefix = "diagram_spec:"
    if role.startswith(prefix):
        figure_id = role[len(prefix):]
        if _FIGURE_ID.fullmatch(figure_id):
            return {
                "role": role,
                "root_key": "diagram_spec",
                "source": f".harness/authoring/figures/{figure_id}_diagram_spec.yaml",
                "legacy_source": f"figures/{figure_id}/brief.md",
                "output": f".harness/contracts/figures/{figure_id}_diagram_spec.json",
                "schema": "schemas/diagram_spec.schema.json",
            }
    return None


def _repair_command(role: str) -> str | None:
    if role == "research_basis":
        return "harness research --compile"
    if role == "model_contract":
        return "harness model --compile"
    if role == "implementation_map":
        return "harness solve --compile"
    if role == "paper_plan":
        return "harness paper plan --compile"
    if role.startswith("diagram_spec:"):
        figure_id = role.split(":", 1)[1]
        if _FIGURE_ID.fullmatch(figure_id):
            return f"harness figure {figure_id} --compile"
    return None


def _project_authoring_specs(root: Path) -> list[dict[str, str]]:
    """List built-in sources, including figure sources already scaffolded."""

    specs = [
        {"role": role, "root_key": role, **spec}
        for role, spec in AUTHORING_SPECS.items()
    ]
    figures_root = root / "figures"
    if figures_root.is_dir():
        for brief in sorted(figures_root.glob("*/brief.md")):
            figure_id = brief.parent.name
            spec = _authoring_spec_for_role(root, f"diagram_spec:{figure_id}")
            if spec is not None:
                specs.append(spec)
    return specs


def _uncompiled_sources(root: Path, indexed_paths: set[str] | None = None) -> tuple[list[str], list[dict[str, str]]]:
    indexed = indexed_paths or set()
    paths: list[str] = []
    repairs: list[dict[str, str]] = []
    for spec in _project_authoring_specs(root):
        source_path = root / spec["source"]
        legacy_path = root / spec["legacy_source"]
        candidates = [source_path] if _source_has_payload(source_path) else [legacy_path]
        if not _source_has_payload(source_path) and not _legacy_has_payload(legacy_path):
            continue
        for path in candidates:
            relative = _project_relative(path, root, label="authoring source")
            if relative in indexed:
                continue
            paths.append(relative)
            command = _repair_command(spec["role"])
            if command is not None:
                repairs.append({"path": relative, "role": spec["role"], "command": command})
    return paths, repairs


def check_authoring_freshness(root: Path) -> dict[str, Any]:
    """Inspect the rebuildable compile index without changing project state."""

    index = _load_authoring_index(root)
    if index is None:
        uncompiled, repairs = _uncompiled_sources(root)
        return {
            "ok": not uncompiled,
            "status": "not_compiled",
            "index": AUTHORING_INDEX_RELATIVE,
            "entries": [],
            "uncompiled_sources": uncompiled,
            "repair_commands": repairs,
        }

    rows: list[dict[str, Any]] = []
    roles: set[str] = set()
    indexed_paths: set[str] = set()
    for raw in index["entries"]:
        if not isinstance(raw, Mapping):
            raise ValueError("authoring compile index entries must be objects")
        role = str(raw.get("role", ""))
        if not role or role in roles:
            raise ValueError("authoring compile index roles must be non-empty and unique")
        roles.add(role)
        reasons: list[str] = []
        spec = _authoring_spec_for_role(root, role)
        if spec is None:
            reasons.append("unknown_role")
        refs = raw.get("sources")
        if not isinstance(refs, list) or not refs:
            refs = [{"path": raw.get("source_path"), "sha256": raw.get("source_sha256")}]
        primary_source: Path | None = None
        for index, ref in enumerate(refs):
            if not isinstance(ref, Mapping) or not isinstance(ref.get("path"), str):
                reasons.append("invalid_source_ref")
                continue
            path = resolve_path(str(ref["path"]), root).resolve()
            try:
                relative = _project_relative(path, root, label="indexed authoring source")
                indexed_paths.add(relative)
            except ValueError:
                reasons.append(f"source_outside_project:{ref['path']}")
                continue
            if not path.is_file():
                reasons.append(f"missing_source:{ref['path']}")
            elif ref.get("sha256") != sha256_file(path):
                reasons.append(f"source_changed:{ref['path']}")
            if index == 0:
                primary_source = path
        output_raw = raw.get("output_path")
        output_path = resolve_path(str(output_raw), root).resolve() if isinstance(output_raw, str) else None
        output_inside_project = False
        if output_path is not None:
            try:
                _project_relative(output_path, root, label="indexed compiled output")
                output_inside_project = True
            except ValueError:
                reasons.append(f"output_outside_project:{output_raw}")
        if output_path is None or not output_inside_project or not output_path.is_file():
            reasons.append(f"missing_output:{output_raw}")
        elif raw.get("output_sha256") != sha256_file(output_path):
            reasons.append(f"output_changed:{output_raw}")
        if raw.get("compiler_version") != AUTHORING_COMPILER_VERSION:
            reasons.append("compiler_changed")
        schema_id = raw.get("schema_id")
        schema_path = (HARNESS_ROOT / str(schema_id)).resolve() if isinstance(schema_id, str) else None
        schema_inside_repo = False
        if schema_path is not None:
            try:
                _project_relative(schema_path, HARNESS_ROOT, label="indexed schema")
                schema_inside_repo = True
            except ValueError:
                reasons.append("schema_outside_harness")
        if schema_path is None or not schema_inside_repo or not schema_path.is_file():
            reasons.append("schema_missing")
        else:
            if raw.get("schema_sha256") != sha256_file(schema_path):
                reasons.append("schema_changed")
            if primary_source is not None and primary_source.is_file() and spec is not None:
                try:
                    contract = _read_contract_source(
                        primary_source,
                        root_key=spec["root_key"],
                        source_label=f"{role} source",
                    )
                    _validate_contract(
                        contract,
                        schema_path,
                        label=role,
                        schema_ref=spec.get("schema_ref"),
                    )
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    reasons.append(f"source_invalid:{exc}")
        row = {
            "role": role,
            "status": "current" if not reasons else "stale",
            "reasons": reasons,
        }
        command = _repair_command(role)
        if command is not None:
            row["repair_command"] = command
        rows.append(row)

    uncompiled, repairs = _uncompiled_sources(root, indexed_paths)
    stale = any(row["status"] == "stale" for row in rows)
    return {
        "ok": not stale and not uncompiled,
        "status": "stale" if stale else ("not_compiled" if uncompiled else "current"),
        "index": AUTHORING_INDEX_RELATIVE,
        "entries": rows,
        "uncompiled_sources": uncompiled,
        "repair_commands": repairs,
    }


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
    legacy_source: str | None = None,
    default_output: str,
    root_key: str,
    source_label: str,
    schema_path: Path,
    role: str,
    schema_ref: str | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    if source is None:
        default_path = resolve_path(default_source, root)
        legacy_path = resolve_path(legacy_source, root) if legacy_source else None
        if not default_path.is_file() and not (legacy_path and _legacy_has_payload(legacy_path)):
            ensure_human_surface(root)
    source_path = _resolve_authoring_source(
        root,
        source,
        default_source,
        legacy_source=legacy_source,
        label=source_label,
    )
    contract = _read_contract_source(source_path, root_key=root_key, source_label=source_label)
    _validate_contract(contract, schema_path, label=root_key, schema_ref=schema_ref)
    _load_authoring_index(root)
    output_path = _resolve_compiled_output(root, output, default_output, label="compiled contract")
    write_json_atomic(output_path, contract)
    _record_compile_index(
        root,
        role=role,
        source_paths=[source_path],
        output_path=output_path,
        schema_path=schema_path,
    )
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
        default_source=".harness/authoring/research_basis.yaml",
        legacy_source="01_RESEARCH_NOTES.md",
        default_output=".harness/contracts/research_basis.json",
        root_key="research_basis",
        source_label="research notes source",
        schema_path=model_schema_path,
        role="research_basis",
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

    if source is None and not (root / ".harness/authoring/model_contract.yaml").is_file():
        ensure_human_surface(root)
    source_path = _resolve_authoring_source(
        root,
        source,
        ".harness/authoring/model_contract.yaml",
        legacy_source="02_MODEL_DECISION.md",
        label="model decision source",
    )
    contract = _read_contract_source(source_path, root_key="model_contract", source_label="model decision source")
    research_path: Path | None = None
    if research_source is not None:
        research_path = _resolve_authoring_source(
            root,
            research_source,
            ".harness/authoring/research_basis.yaml",
            legacy_source="01_RESEARCH_NOTES.md",
            label="research notes source",
        )
        if "research_basis" in contract:
            raise ValueError("model contract already contains research_basis; use one Markdown source of truth")
        contract["research_basis"] = _research_basis_from_source(research_path, schema_path)
    _validate_contract(contract, schema_path, label="model contract")
    _load_authoring_index(root)
    output_path = _resolve_compiled_output(
        root,
        output,
        ".harness/contracts/model_contract.json",
        label="compiled model contract",
    )
    write_json_atomic(output_path, contract)
    _record_compile_index(
        root,
        role="model_contract",
        source_paths=[source_path] + ([research_path] if research_path is not None else []),
        output_path=output_path,
        schema_path=schema_path,
    )
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
        default_source=".harness/authoring/paper_plan.yaml",
        legacy_source="paper/00_PAPER_PLAN.md",
        default_output=".harness/contracts/paper_plan.json",
        root_key="paper_plan",
        source_label="paper plan source",
        schema_path=schema_path,
        role="paper_plan",
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
        default_source=".harness/authoring/implementation_map.yaml",
        legacy_source="03_SOLUTION_REPORT.md",
        default_output=".harness/contracts/implementation_map.json",
        root_key="implementation_map",
        source_label="solution report source",
        schema_path=schema_path,
        role="implementation_map",
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
        default_source=f".harness/authoring/figures/{figure_id}_diagram_spec.yaml",
        legacy_source=f"figures/{figure_id}/brief.md",
        default_output=f".harness/contracts/figures/{figure_id}_diagram_spec.json",
        root_key="diagram_spec",
        source_label="figure brief source",
        schema_path=schema_path,
        role=f"diagram_spec:{figure_id}",
    )
    return {
        "brief": brief,
        "source": _project_relative(source_path, root, label="figure brief source"),
        "output": _project_relative(output_path, root, label="compiled diagram spec"),
        "compiled": True,
        "authority_note": "This is a diagram producer input only; it does not create a figure claim, receipt, rendered artifact, or Gate outcome.",
    }


def _legacy_contract_value(source: Path, *, root_key: str) -> dict[str, Any] | None:
    """Read one legacy Markdown block; ``None`` means the empty template."""

    text = source.read_text(encoding="utf-8")
    heading = _MACHINE_SOURCE_HEADING.search(text)
    if heading is None:
        return None
    block = re.search(
        r"```(?:yaml|yml|json)\s*\n(.*?)\n```",
        text[heading.end():],
        flags=re.DOTALL | re.IGNORECASE,
    )
    if block is None:
        raise ValueError(f"{source} has a Machine contract heading without a fenced source block")
    payload = block.group(1)
    if not any(line.strip() and not line.lstrip().startswith("#") for line in payload.splitlines()):
        return None
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - requirements-dev installs PyYAML
        raise RuntimeError("authoring migration requires PyYAML; install requirements-dev.txt") from exc
    loaded = yaml.safe_load(payload)
    if not isinstance(loaded, Mapping):
        raise ValueError(f"{source} Machine contract source must be a YAML object")
    candidate = loaded.get(root_key, loaded)
    if not isinstance(candidate, Mapping):
        raise ValueError(f"{source} {root_key} must be a YAML object")
    return dict(candidate)


def _authoring_yaml(root_key: str, value: Mapping[str, Any]) -> str:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - requirements-dev installs PyYAML
        raise RuntimeError("authoring migration requires PyYAML; install requirements-dev.txt") from exc
    return yaml.safe_dump(
        {root_key: dict(value)},
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def _migration_specs(root: Path) -> list[dict[str, Any]]:
    return [dict(spec) for spec in _project_authoring_specs(root)]


def _remove_legacy_source_block(source: Path) -> str:
    text = source.read_text(encoding="utf-8")
    updated, count = _MACHINE_SOURCE_BLOCK.subn("", text, count=1)
    if count != 1:
        raise ValueError(f"{source} has a Machine contract heading without a removable fenced source block")
    return updated


def migrate_authoring_sources(root: Path, *, apply: bool = True) -> dict[str, Any]:
    """Move legacy Markdown source blocks into hidden YAML files.

    The operation is explicit and preflights every destination before writing.
    Existing destination YAML is never overwritten when its semantic payload
    differs.  Existing compiled JSON is compared before the Markdown block is
    removed, so migration cannot silently change its meaning.
    """

    project = root.resolve()
    plans: list[dict[str, Any]] = []
    for spec in _migration_specs(project):
        legacy_path = project / spec["legacy_source"]
        if not legacy_path.is_file():
            continue
        legacy_text = legacy_path.read_text(encoding="utf-8")
        if _MACHINE_SOURCE_HEADING.search(legacy_text) is None:
            continue
        candidate = _legacy_contract_value(legacy_path, root_key=spec["root_key"])
        target_path = project / spec["source"]
        target_value: dict[str, Any] | None = None
        if target_path.is_file() and _source_has_payload(target_path):
            target_value = _read_contract_source(
                target_path,
                root_key=spec["root_key"],
                source_label=f"authoring source {spec['source']}",
            )
        if candidate is not None:
            if target_value is not None and target_value != candidate:
                raise ValueError(
                    f"refusing to overwrite divergent authoring source: {spec['source']}"
                )
            output_path = project / spec["output"]
            if output_path.is_file() and load_structured(output_path) != candidate:
                raise ValueError(
                    f"compiled output differs from legacy source; repair before migration: {spec['output']}"
                )
        plans.append({
            "role": spec["role"],
            "root_key": spec["root_key"],
            "legacy_path": legacy_path,
            "source_path": target_path,
            "output_path": project / spec["output"],
            "schema_path": HARNESS_ROOT / spec["schema"],
            "candidate": candidate,
        })

    report_rows = []
    for plan in plans:
        row = {
            "role": plan["role"],
            "from": _project_relative(plan["legacy_path"], project, label="legacy authoring source"),
            "to": _project_relative(plan["source_path"], project, label="authoring source"),
            "payload": "moved" if plan["candidate"] is not None else "empty_template_removed",
            "compiled_output": (
                _project_relative(plan["output_path"], project, label="compiled contract")
                if plan["output_path"].is_file()
                else None
            ),
        }
        report_rows.append(row)

    if apply:
        for plan in plans:
            target = plan["source_path"]
            candidate = plan["candidate"]
            if candidate is not None and (not target.is_file() or not _source_has_payload(target)):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(_authoring_yaml(plan["root_key"], candidate), encoding="utf-8")
            elif not target.is_file():
                template = AUTHORING_SOURCE_TEMPLATES.get(_project_relative(target, project, label="authoring source"))
                if template is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(template.rstrip() + "\n", encoding="utf-8")
            plan["legacy_path"].write_text(_remove_legacy_source_block(plan["legacy_path"]), encoding="utf-8")

        index_path = _authoring_index_path(project)
        old_index = _load_authoring_index(project)
        existing_entries = [] if old_index is None else [
            entry for entry in old_index["entries"]
            if isinstance(entry, Mapping) and entry.get("role") not in {plan["role"] for plan in plans}
        ]
        for plan in plans:
            if plan["candidate"] is not None and plan["output_path"].is_file():
                existing_entries.append(
                    _compile_index_entry(
                        project,
                        role=plan["role"],
                        source_paths=[plan["source_path"]],
                        output_path=plan["output_path"],
                        schema_path=plan["schema_path"],
                    )
                )
        if old_index is not None or existing_entries:
            index = old_index or {
                "schema_version": AUTHORING_INDEX_VERSION,
                "compiler_version": AUTHORING_COMPILER_VERSION,
            }
            index["compiler_version"] = AUTHORING_COMPILER_VERSION
            index["entries"] = sorted(existing_entries, key=lambda entry: str(entry.get("role", "")))
            write_json_atomic(index_path, index)

    return {
        "ok": True,
        "status": "migrated" if apply and plans else ("ready" if plans else "unchanged"),
        "applied": apply,
        "index": AUTHORING_INDEX_RELATIVE,
        "files": report_rows,
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
            (".harness/authoring/research_basis.yaml", "structured research source when a compiler consumer needs it", False),
            ("references/research/literature_evidence.md", "source/evidence boundary", True),
        ]
        skipped = ["model contracts", "paper plans", "submission references"]
    elif normalized == "model":
        rows = [
            ("00_PROJECT_BRIEF.md", "problem scope", True),
            ("01_RESEARCH_NOTES.md", "research findings and rejected methods", True),
            (".harness/authoring/research_basis.yaml", "structured research source when available", False),
            (".harness/contracts/research_basis.json", "compiled research basis when available", False),
            ("02_MODEL_DECISION.md", "current authoring target", True),
            (".harness/authoring/model_contract.yaml", "structured model source for compilation", False),
            ("references/research/model_planning.md", "model-selection guidance", True),
        ]
        skipped = ["writing references", "submission references", "unrelated paper sections"]
    elif normalized == "solve":
        rows = [
            ("02_MODEL_DECISION.md", "selected-model rationale and failure plan", True),
            (".harness/authoring/model_contract.yaml", "structured model source when available", False),
            (".harness/contracts/model_contract.json", "compiled machine contract when available", False),
            ("03_SOLUTION_REPORT.md", "run/result narrative to update", True),
            (".harness/authoring/implementation_map.yaml", "structured implementation source when needed", False),
            (".harness/contracts/implementation_map.json", "compiled implementation map when available", False),
            ("references/validation/validation_obligations.md", "declared validation duties", True),
        ]
        skipped = ["paper-writing references", "submission references"]
    elif normalized.startswith("paper:"):
        section = _normalize_section_id(normalized.split(":", 1)[1])
        guideline = (
            "references/writing/abstract_guidelines.md"
            if "abstract" in section.casefold()
            else "references/writing/manuscript_logic.md"
        )
        rows = [
            (".harness/views/WRITING_SPINE.md", "whole-paper argument chain", True),
            (f".harness/views/sections/{section}_brief.md", "current section Writer Brief", True),
            (f"paper/sections/{section}/draft.md", "only draft allowed to change", True),
            (guideline, "one task-related micro-guideline", True),
        ]
        skipped = [
            "other paper sections",
            "full contracts and frozen results unless an explicit locator is needed",
            "reviewer reasoning and previous verdicts",
            "unrelated writing references",
        ]
    else:
        raise ValueError("context stage must be research, model, solve, or paper:<section>")
    loaded = []
    for path, why, required in rows:
        location = "harness" if path.startswith("references/") else "project"
        base = HARNESS_ROOT if location == "harness" else root
        loaded.append({"path": path, "location": location, "why": why, "required": required, "exists": (base / path).is_file()})
    return {"stage": normalized, "loaded_files": loaded, "optional_files_skipped": skipped}

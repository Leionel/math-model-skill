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
""",
    "paper/00_PAPER_PLAN.md": """# 论文规划

> 这是正文写作的作者规划；`paper_plan.json`（若存在）仍是机器 IR，二者不能互相假装为 Gate 事实。

## 中心主线

这篇论文最终要证明什么？

## 每个小问的主要结论

## 章节安排

## 模型之间的关系

## 最关键结果

## 必须出现的验证

## Figure / Table Plan

## Appendix Plan
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

## Output

- editable PPTX copy by default; editable Draw.io only when explicitly selected
- PDF/SVG/PNG export
- preview PNG
"""

_SECTION_ID = re.compile(r"^(?:q[1-9][0-9]*|validation|discussion|conclusion|appendix|abstract)$", re.IGNORECASE)
_FIGURE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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


def ensure_section(root: Path, section_id: str) -> dict[str, Any]:
    normalized = section_id.casefold()
    if not _SECTION_ID.fullmatch(normalized):
        raise ValueError("section must be q<number>, validation, discussion, conclusion, appendix, or abstract")
    ensure_human_surface(root)
    section = root / "paper" / "sections" / normalized
    created = [
        name
        for name, content in (("brief.md", SECTION_TEMPLATE), ("draft.md", DRAFT_TEMPLATE), ("review.md", REVIEW_TEMPLATE))
        if _write_if_missing(section / name, content)
    ]
    return {"section": normalized, "path": str(section), "created": created}


def ensure_figure_brief(root: Path, figure_id: str) -> dict[str, Any]:
    if not _FIGURE_ID.fullmatch(figure_id):
        raise ValueError("figure id must use only letters, digits, dots, underscores, or hyphens")
    ensure_human_surface(root)
    directory = root / "figures" / figure_id
    created = _write_if_missing(directory / "brief.md", FIGURE_BRIEF_TEMPLATE.format(figure_id=figure_id))
    return {"figure_id": figure_id, "path": str(directory), "created": ["brief.md"] if created else []}


def _read_contract_source(source: Path) -> dict[str, Any]:
    text = source.read_text(encoding="utf-8")
    heading = re.search(r"^## Machine contract source \(optional\)\s*$", text, flags=re.MULTILINE)
    if heading is None:
        raise ValueError("02_MODEL_DECISION.md is missing the 'Machine contract source (optional)' section")
    block = re.search(r"```(?:yaml|yml|json)\s*\n(.*?)\n```", text[heading.end():], flags=re.DOTALL | re.IGNORECASE)
    if block is None:
        raise ValueError("Machine contract source must contain a fenced YAML or JSON block")
    payload = block.group(1)
    if not any(line.strip() and not line.lstrip().startswith("#") for line in payload.splitlines()):
        raise ValueError("Machine contract source is still the empty template")
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - requirements-dev installs PyYAML
        raise RuntimeError("model compilation requires PyYAML; install requirements-dev.txt") from exc
    loaded = yaml.safe_load(payload)
    if not isinstance(loaded, Mapping):
        raise ValueError("Machine contract source must be a YAML object")
    candidate = loaded.get("model_contract", loaded)
    if not isinstance(candidate, Mapping):
        raise ValueError("model_contract must be an object")
    return dict(candidate)


def _validate_model_contract(contract: Mapping[str, Any], schema_path: Path) -> None:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - requirements-dev installs jsonschema
        raise RuntimeError("model compilation requires jsonschema; install requirements-dev.txt") from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(dict(contract)), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        location = ".".join(str(item) for item in first.absolute_path) or "root"
        raise ValueError(f"model contract schema validation failed at {location}: {first.message}")


def compile_model_contract(
    root: Path,
    *,
    source: str | None,
    output: str | None,
    schema_path: Path,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Compile the explicit YAML block from the authoring document to JSON IR."""

    ensure_human_surface(root)
    source_path = resolve_path(source or "02_MODEL_DECISION.md", root).resolve()
    if not source_path.is_file():
        raise ValueError(f"model decision source does not exist: {source_path}")
    contract = _read_contract_source(source_path)
    _validate_model_contract(contract, schema_path)
    manifest_path = manifest_path.resolve() if manifest_path is not None else resolve_manifest_path(root)
    output_path = resolve_path(output or ".harness/contracts/model_contract.json", root).resolve()
    try:
        output_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("compiled model contract must stay inside the project root") from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_path, contract)
    if manifest_path.is_file():
        manifest = load_structured(manifest_path)
        if not isinstance(manifest, Mapping):
            raise ValueError("run_manifest must be an object")
        updated = dict(manifest)
        roots = dict(updated.get("roots", {})) if isinstance(updated.get("roots"), Mapping) else {}
        roots["model_contract"] = {"path": output_path.relative_to(root).as_posix()}
        updated["roots"] = roots
        write_json_atomic(manifest_path, updated)
    return {
        "source": source_path.relative_to(root).as_posix(),
        "output": output_path.relative_to(root).as_posix(),
        "compiled": True,
        "manifest": rel_path(manifest_path, root) if manifest_path.is_file() else None,
        "gate_note": "Compilation creates machine IR only; run the existing M1 checker for a factual Gate verdict.",
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
            ("02_MODEL_DECISION.md", "current authoring target", True),
            ("references/research/model_planning.md", "model-selection guidance", True),
        ]
        skipped = ["writing references", "submission references", "unrelated paper sections"]
    elif normalized == "solve":
        rows = [
            ("02_MODEL_DECISION.md", "selected-model rationale and failure plan", True),
            (".harness/contracts/model_contract.json", "compiled machine contract when available", False),
            ("03_SOLUTION_REPORT.md", "run/result narrative to update", True),
            ("references/validation/validation_obligations.md", "declared validation duties", True),
        ]
        skipped = ["paper-writing references", "submission references"]
    elif normalized.startswith("paper:"):
        section = normalized.split(":", 1)[1]
        if not _SECTION_ID.fullmatch(section):
            raise ValueError("paper context stage must be paper:<q-number|validation|discussion|conclusion|appendix|abstract>")
        rows = [
            (f"paper/sections/{section}/brief.md", "section scope and evidence boundary", True),
            (f"paper/sections/{section}/draft.md", "only draft allowed to change", True),
            (".harness/contracts/model_contract.json", "model definitions when available", False),
            (".harness/results/frozen_results.json", "claimable results when available", False),
            ("references/writing/editorial_style.md", "section-writing guidance", True),
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

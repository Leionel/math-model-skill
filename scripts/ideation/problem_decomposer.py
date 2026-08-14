#!/usr/bin/env python3
"""Problem Decomposer & Socratic Assumption Fork Assistant for Math Modeling (M1).

Parses math competition problem statements, identifies mathematical problem structures,
scans for ambiguous phrasing to generate Assumption Forks, and creates a risk-aware starter model contract.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

# High-risk ambiguous keywords triggering assumption forks
FORK_TRIGGER_KEYWORDS = {
    "消纳": "消纳比例/能力是历史统计均值描述还是逐时物理硬上限？",
    "利用率": "利用率指标是事后评价量还是事前控制约束？",
    "需求": "需求是确定性常数、弹性响应曲线还是随机分布变量？",
    "损耗": "损耗是固定折算系数还是与流速/流量相关的非线性函数？",
    "满意度": "满意度采用线性折算、主观打分函数还是凹效用函数？",
    "风险": "风险度量采用方差、极值、VaR 还是 CVaR 尾部期望损失？",
    "可视为": "该简化假设在极端场景下是否会导致后续问失去边际意义？",
    "近似": "近似误差对优化解的可行性与目标值敏感度如何？",
}

# Mathematical pattern indicators
PATTERN_INDICATORS = {
    "optimization": ["最大", "最小", "最优", "最低成本", "最高利润", "调度", "规划", "配置", "选址", "路径", "MILP", "LP", "NLP"],
    "differential_equations": ["演化", "传播", "速度", "动态", "变化率", "传染病", "温度", "浓度", "轨迹", "ODE", "PDE"],
    "time_series": ["预测", "未来", "历史数据", "趋势", "季节性", "小时级", "日级", "ARIMA", "时序"],
    "evaluation": ["评价", "综合得分", "优选", "排名", "评估", "指标体系", "TOPSIS", "层次分析", "熵权"],
    "metaheuristics": ["复杂组合", "大规模非凸", "黑箱", "遗传算法", "粒子群", "模拟退火", "多目标前沿"],
}


def detect_problem_patterns(text: str) -> list[str]:
    """Detect dominant mathematical modeling pattern families."""
    detected = []
    text_lower = text.lower()
    for pattern, keywords in PATTERN_INDICATORS.items():
        if any(kw.lower() in text_lower for kw in keywords):
            detected.append(pattern)
    return detected or ["optimization"]


def detect_assumption_forks(text: str, question_id: str = "q1") -> list[dict[str, Any]]:
    """Scan text for high-risk ambiguous keywords and generate Assumption Forks."""
    forks = []
    count = 1
    for kw, prompt in FORK_TRIGGER_KEYWORDS.items():
        if kw in text:
            forks.append({
                "fork_id": f"AF-{question_id}-{count:02d}",
                "phrase": kw,
                "question_id": question_id,
                "diagnostic_prompt": prompt,
                "interpretations": [
                    {
                        "id": "A",
                        "meaning": f"基准解释：{kw} 作为宏观/统计描述，不形成破坏性逐时硬约束",
                        "mathematical_effect": "保持全局优化可行域完整，作为参考基线或软约束评估",
                    },
                    {
                        "id": "B",
                        "meaning": f"严格解释：{kw} 作为逐点/逐时硬性物理上限",
                        "mathematical_effect": "显式加入线性/非线性不等式硬约束",
                    },
                ],
                "checks": [
                    "核对题面是否出现逐时/逐点硬约束措辞",
                    "核对附件是否存在容量、上限或边界字段",
                    "比较两种解释对可行域和下游问题的边际影响",
                ],
                "selection_status": "pending_human_review",
                "unresolved_risk": "尚未完成题面、附件和敏感性回测，不能自动选定解释",
            })
            count += 1
    return forks


def decompose_problem(problem_text: str, contest_name: str = "CUMCM/MCM") -> dict[str, Any]:
    """Decompose problem text into subproblems and blueprint."""
    # Split by subproblem markers like 问题一、问题1、Question 1、(1)、1.
    split_pattern = r"(?:问题\s*[一二三四五12345]|Question\s*[12345]|\n\s*[(（][12345一二三四五][)）]|\n\s*[12345][.、])"
    splits = re.split(split_pattern, problem_text)

    # If splitting succeeded
    subproblems = []
    if len(splits) > 1:
        for idx, part in enumerate(splits[1:], start=1):
            q_id = f"q{idx}"
            display_q_id = f"Q{idx}"
            patterns = detect_problem_patterns(part)
            forks = detect_assumption_forks(part, q_id)
            subproblems.append({
                "question_id": q_id,
                "display_question_id": display_q_id,
                "text_snippet": part.strip()[:200] + "..." if len(part.strip()) > 200 else part.strip(),
                "detected_patterns": patterns,
                "depth_budget": "deep" if idx in (2, 3) and len(splits) >= 4 else "normal",
                "recommended_main_model": "MILP Optimization" if "optimization" in patterns else ("ODE Dynamics" if "differential_equations" in patterns else "Time Series Regression"),
                "recommended_baseline": "Rule-based / Greedy Baseline" if "optimization" in patterns else "Seasonal Naive Baseline",
                "model_selection": {
                    "status": "pending_research_and_comparison",
                    "candidates": _candidate_seeds(patterns),
                    "requires_evidence_and_human_choice": True,
                },
                "assumption_forks": forks,
                "math_risk": "high" if len(forks) > 0 else "medium",
            })
    else:
        # Single problem text
        patterns = detect_problem_patterns(problem_text)
        forks = detect_assumption_forks(problem_text, "q1")
        subproblems.append({
            "question_id": "q1",
            "display_question_id": "Q1",
            "text_snippet": problem_text.strip()[:200],
            "detected_patterns": patterns,
            "depth_budget": "normal",
            "recommended_main_model": "MILP Optimization" if "optimization" in patterns else "Time Series Regression",
            "recommended_baseline": "Greedy Baseline",
            "model_selection": {
                "status": "pending_research_and_comparison",
                "candidates": _candidate_seeds(patterns),
                "requires_evidence_and_human_choice": True,
            },
            "assumption_forks": forks,
            "math_risk": "high" if len(forks) > 0 else "medium",
        })

    return {
        "contest": contest_name,
        "total_subproblems": len(subproblems),
        "subproblems": subproblems,
        "global_recommendation": "以上仅是候选方法种子；必须完成 M1 文献检索、候选比较、证据绑定和人工选择后，才能写入 model_contract。",
    }


def _candidate_seeds(patterns: list[str]) -> list[dict[str, str]]:
    """Return research seeds, never a selected model."""
    candidates: list[dict[str, str]] = []
    if "optimization" in patterns:
        candidates.extend([
            {"name": "LP/MILP", "role": "transparent optimization candidate", "selection": "pending"},
            {"name": "heuristic/metaheuristic", "role": "scalability candidate", "selection": "pending"},
        ])
    if "time_series" in patterns:
        candidates.extend([
            {"name": "seasonal naive / statistical baseline", "role": "baseline candidate", "selection": "pending"},
            {"name": "state-space or ARIMA", "role": "dynamic forecasting candidate", "selection": "pending"},
        ])
    if "differential_equations" in patterns:
        candidates.extend([
            {"name": "mechanistic ODE", "role": "mechanism candidate", "selection": "pending"},
            {"name": "data-driven surrogate", "role": "comparison candidate", "selection": "pending"},
        ])
    if "evaluation" in patterns:
        candidates.extend([
            {"name": "weighted utility / TOPSIS", "role": "multi-criteria candidate", "selection": "pending"},
            {"name": "outranking or Pareto analysis", "role": "robustness candidate", "selection": "pending"},
        ])
    return candidates or [
        {"name": "analytical baseline", "role": "transparent candidate", "selection": "pending"},
        {"name": "simulation or statistical comparison", "role": "alternative candidate", "selection": "pending"},
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Decompose math modeling problem and generate Assumption Forks.")
    parser.add_argument("input_file", help="Path to text/markdown file containing problem description")
    parser.add_argument("--contest", default="CUMCM/MCM", help="Contest name")
    parser.add_argument("--output", "-o", help="Output JSON path")

    args = parser.parse_args()
    in_path = Path(args.input_file)
    if not in_path.exists():
        print(f"ERROR: Input file not found: {in_path}", file=sys.stderr)
        return 1

    content = in_path.read_text(encoding="utf-8")
    result = decompose_problem(content, args.contest)
    out_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(out_str + "\n", encoding="utf-8")
        print(f"Generated problem decomposition blueprint at: {out_p}")
    else:
        print(out_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())

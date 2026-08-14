#!/usr/bin/env python3
"""Error Classifier and Diagnostic Boundary Guard for Bounded Reflexion.

Classifies errors into CODE_ERROR, DATA_ERROR, MODEL_INFEASIBLE,
SEMANTIC_MISMATCH, and VALIDATION_FAIL.
Enforces rule: Agent can fix implementation, but CANNOT relax constraints or change problem assumptions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    SUCCESS = "SUCCESS"
    CODE_ERROR = "CODE_ERROR"
    DATA_ERROR = "DATA_ERROR"
    MODEL_INFEASIBLE = "MODEL_INFEASIBLE"
    SEMANTIC_MISMATCH = "SEMANTIC_MISMATCH"
    VALIDATION_FAIL = "VALIDATION_FAIL"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class DiagnosticResult:
    category: ErrorCategory
    root_cause: str
    can_auto_fix: bool
    requires_human_or_m1_review: bool
    remediation_advice: str
    extracted_exception: str | None = None


def classify_error(
    stderr_text: str,
    stdout_text: str = "",
    exit_code: int = 0,
    context: dict[str, Any] | None = None,
) -> DiagnosticResult:
    """Classify execution failure into structured diagnostic categories."""
    if exit_code == 0 and not stderr_text.strip():
        return DiagnosticResult(
            category=ErrorCategory.SUCCESS,
            root_cause="Execution completed successfully with zero exit code.",
            can_auto_fix=False,
            requires_human_or_m1_review=False,
            remediation_advice="Proceed to independent validation and result freeze.",
        )

    combined = f"{stderr_text}\n{stdout_text}"

    # 1. Model Infeasible / Mathematical Singularity
    infeasible_patterns = [
        r"Infeasible",
        r"infeasible",
        r"SolverStatus\.INFEASIBLE",
        r"PulpSolverError",
        r"Singular matrix",
        r"LinAlgError",
        r"Matrix is not positive definite",
        r"Optimization failed to converge",
        r"Maximum number of iterations reached",
        r"IntegrationStepFailed",
        r"Required step size is less than spacing",
    ]
    for pat in infeasible_patterns:
        if re.search(pat, combined, re.IGNORECASE):
            return DiagnosticResult(
                category=ErrorCategory.MODEL_INFEASIBLE,
                root_cause=f"Mathematical model is infeasible or numerically unstable (matched pattern '{pat}').",
                can_auto_fix=False,
                requires_human_or_m1_review=True,
                remediation_advice=(
                    "CRITICAL GUARDRAIL: Do NOT automatically drop constraints or alter problem objectives! "
                    "Analyze dual values / IIS (Irreducible Inconsistent Subsystem), check initial values, "
                    "verify scaling/bounds, or return to M1 to revisit model formulation."
                ),
                extracted_exception=pat,
            )

    # 2. Data Loading & Format Errors
    data_error_patterns = [
        r"FileNotFoundError",
        r"EmptyDataError",
        r"ParserError",
        r"KeyError: '.*'",
        r"Column not found",
        r"UnicodeDecodeError",
        r"No such file or directory",
        r"Empty DataFrame",
    ]
    for pat in data_error_patterns:
        match = re.search(pat, combined)
        if match:
            return DiagnosticResult(
                category=ErrorCategory.DATA_ERROR,
                root_cause=f"Data ingestion or schema mismatch (matched '{match.group(0)}').",
                can_auto_fix=True,
                requires_human_or_m1_review=False,
                remediation_advice="Check data file path, encoding, column names, and missing value pre-handling against data_contract.json.",
                extracted_exception=match.group(0),
            )

    # 3. Timeout
    if "Timed out after" in combined or "TimeoutExpired" in combined:
        return DiagnosticResult(
            category=ErrorCategory.TIMEOUT_ERROR,
            root_cause="Execution exceeded allocated time limit.",
            can_auto_fix=False,
            requires_human_or_m1_review=True,
            remediation_advice="Reduce problem instance size for smoke run, optimize solver parameters (time limit, gap tolerance), or vectorize calculations.",
            extracted_exception="TimeoutExpired",
        )

    # 4. Contract semantics and independent validation failures.  These are
    # deliberately checked before generic ValueError/AssertionError patterns:
    # they must return to M1/P2 rather than be treated as harmless code bugs.
    semantic_patterns = [
        r"semantic mismatch",
        r"meaning mismatch",
        r"objective(?:s)?\s+mismatch",
        r"target(?:\s+column)?\s+mismatch",
        r"model contract.*mismatch",
        r"contract.*semantic",
    ]
    for pat in semantic_patterns:
        match = re.search(pat, combined, re.IGNORECASE)
        if match:
            return DiagnosticResult(
                category=ErrorCategory.SEMANTIC_MISMATCH,
                root_cause=f"Model/data semantic contract mismatch (matched '{match.group(0)}').",
                can_auto_fix=False,
                requires_human_or_m1_review=True,
                remediation_advice=(
                    "Return to M1: compare the problem snapshot, data contract, objective, units, and assumptions. "
                    "Do not patch semantics in the coding round."
                ),
                extracted_exception=match.group(0),
            )

    validation_patterns = [
        r"validation\s+(?:failed|fail)",
        r"acceptance\s+criterion.*(?:failed|fail)",
        r"independent\s+(?:recomputation|recompute).*(?:failed|fail)",
        r"constraint\s+check.*(?:failed|fail)",
        r"objective\s+recomputation.*(?:failed|fail)",
        r"validation_status\s*[:=]\s*['\"]?fail",
    ]
    for pat in validation_patterns:
        match = re.search(pat, combined, re.IGNORECASE)
        if match:
            return DiagnosticResult(
                category=ErrorCategory.VALIDATION_FAIL,
                root_cause=f"Independent validation or acceptance check failed (matched '{match.group(0)}').",
                can_auto_fix=False,
                requires_human_or_m1_review=True,
                remediation_advice=(
                    "Keep the failed receipt, inspect the falsifying metric, and return to the model/validation contract. "
                    "Never turn a failed validation into PASS by editing the receipt."
                ),
                extracted_exception=match.group(0),
            )

    # 5. Standard Python Code Errors
    code_error_patterns = [
        r"SyntaxError:.*",
        r"NameError:.*",
        r"IndexError:.*",
        r"TypeError:.*",
        r"AttributeError:.*",
        r"ImportError:.*",
        r"ModuleNotFoundError:.*",
        r"ZeroDivisionError:.*",
        r"ValueError:.*",
        r"Shape mismatch",
        r"operands could not be broadcast together",
    ]
    for pat in code_error_patterns:
        match = re.search(pat, combined)
        if match:
            return DiagnosticResult(
                category=ErrorCategory.CODE_ERROR,
                root_cause=f"Code implementation exception: {match.group(0)}",
                can_auto_fix=True,
                requires_human_or_m1_review=False,
                remediation_advice="Inspect traceback line number, fix syntax/variable definition/array dimensions. Keep math formulation unchanged.",
                extracted_exception=match.group(0),
            )

    # Default fallback
    return DiagnosticResult(
        category=ErrorCategory.UNKNOWN,
        root_cause="Unclassified non-zero exit code or stderr output.",
        can_auto_fix=False,
        requires_human_or_m1_review=True,
        remediation_advice="Inspect full stderr output to diagnose root cause.",
    )


def assert_no_constraint_relaxation(original_constraints: list[str], modified_constraints: list[str]) -> bool:
    """Guardrail: Returns True if no constraint was removed without authorization."""
    orig_set = set(c.strip() for c in original_constraints if c.strip())
    mod_set = set(c.strip() for c in modified_constraints if c.strip())
    return orig_set.issubset(mod_set)

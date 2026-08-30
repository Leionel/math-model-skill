"""Small provider-neutral redaction boundary for process-facing text.

This module is used only at provider-bound process returns, external-review
diagnostic tails, and derived UI surfaces. Canonical paper, result, receipt,
command, and source artifacts are not rewritten: redaction must not silently
change research evidence or reproducibility records.
"""

from __future__ import annotations

import re
from typing import Any


_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|auth(?:orization)?|password|passwd|secret|client[_-]?secret|private[_-]?key)\b\s*[:=]\s*)([\"']?)([^\s\"'`,;}\]]{8,})(\2)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_TOKEN_PREFIX = re.compile(r"(?i)\b(?:sk|gh[opusr]|xox[baprs]-|AIza)[-_A-Za-z0-9]{12,}\b")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)
_SENSITIVE_KEY = re.compile(
    r"(?i)^(?:api[_-]?key|access[_-]?token|auth(?:orization)?|password|passwd|secret|client[_-]?secret|private[_-]?key)$"
)


def redact_text(value: str) -> str:
    """Replace common credential forms while keeping surrounding diagnostics."""

    text = str(value)
    text = _PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", text)
    text = _ASSIGNMENT.sub(r"\1\2[REDACTED]\4", text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    return _TOKEN_PREFIX.sub("[REDACTED_TOKEN]", text)


def redact_value(value: Any) -> Any:
    """Recursively redact strings in a diagnostic-only mapping/list."""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _SENSITIVE_KEY.fullmatch(str(key)) else redact_value(item)
            for key, item in value.items()
        }
    return value


__all__ = ["redact_text", "redact_value"]

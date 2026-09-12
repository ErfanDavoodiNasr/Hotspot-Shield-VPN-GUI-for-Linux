"""Secret redaction utilities."""

from __future__ import annotations

import re
from collections.abc import Iterable

_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
)

_PASSWORD_ASSIGN = re.compile(
    r"(?i)\b(" + "|".join(_SENSITIVE_KEYS) + r")\b(\s*[:=]\s*)([^\s,;]+)"
)
_PASSWORD_ARG = re.compile(r"(?i)(--(?:password|passwd|token|secret))\s+(\S+)")


def redact_text(text: str, extra_secrets: Iterable[str] | None = None) -> str:
    """Return *text* with known secret patterns replaced."""
    if not text:
        return text
    redacted = _PASSWORD_ASSIGN.sub(r"\1\2***", text)
    redacted = _PASSWORD_ARG.sub(r"\1 ***", redacted)
    if extra_secrets:
        for secret in extra_secrets:
            if secret and len(secret) >= 3:
                redacted = redacted.replace(secret, "***")
    return redacted


def redact_mapping(data: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in data.items():
        if any(s in key.lower() for s in _SENSITIVE_KEYS):
            out[key] = "***"
        elif isinstance(value, str):
            out[key] = redact_text(value)
        else:
            out[key] = value
    return out

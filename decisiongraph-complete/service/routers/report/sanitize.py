"""Language Sanitizer — Narrative sanitation submodule.

Deterministic text transforms for regulator-grade language.
No creativity, no hedging. Declarative only.
"""

import re

# ── Forbidden words → declarative replacements ───────────────────────────────

_FORBIDDEN_WORDS: dict[str, str] = {
    "appears": "indicators present",
    "appears to": "indicators present",
    "suggests": "indicators present",
    "may indicate": "threshold met",
    "potentially": "",          # remove
    "seems": "indicators present",
    "likely": "",               # remove
    "it seems": "indicators present",
    "possibly": "",             # remove
}

# Duplicate uncertainty phrases killed when investigation_state already set
_UNCERTAINTY_PHRASES: list[str] = [
    "Additional review required",
    "Final determination pending",
    "Investigation ongoing",
    "Further review needed",
    "Pending final determination",
]


def sanitize_narrative(text: str) -> str:
    """Final-pass language sanitizer. Declarative only — never speculative."""
    if not text:
        return text
    result = text
    for forbidden, replacement in _FORBIDDEN_WORDS.items():
        pattern = re.compile(re.escape(forbidden), re.IGNORECASE)
        result = pattern.sub(replacement, result)
    result = re.sub(r"  +", " ", result).strip()
    result = re.sub(r"\s+\.", ".", result)
    return result


def kill_duplicate_uncertainty(text: str) -> str:
    """Remove uncertainty phrases when investigation_state already communicates status."""
    if not text:
        return text
    result = text
    for phrase in _UNCERTAINTY_PHRASES:
        result = result.replace(phrase + ".", "").replace(phrase, "")
    return re.sub(r"  +", " ", result).strip() or text

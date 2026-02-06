"""DecisionStore — In-memory decision cache with prefix resolution.

Separates cache mechanics from report logic so neither needs to know about
the other's internals.  In production, swap the implementation for Redis /
Postgres / S3 — the interface stays the same.
"""

import os
from typing import Optional

from fastapi import HTTPException

# ── Configuration ─────────────────────────────────────────────────────────────
MIN_DECISION_PREFIX = int(os.getenv("DG_DECISION_PREFIX_MIN", "12"))
ALLOW_RAW_DECISION = os.getenv("DG_ALLOW_RAW_DECISION", "false").lower() == "true"
_MAX_CACHE_SIZE = 100


# ── In-memory store ──────────────────────────────────────────────────────────
_decision_cache: dict[str, dict] = {}


def put(decision_id: str, decision_pack: dict) -> None:
    """Cache a decision for later report generation."""
    _decision_cache[decision_id] = decision_pack
    if len(_decision_cache) > _MAX_CACHE_SIZE:
        oldest_key = next(iter(_decision_cache))
        del _decision_cache[oldest_key]


def get(decision_id: str) -> Optional[dict]:
    """Get a cached decision by exact ID."""
    return _decision_cache.get(decision_id)


def resolve(decision_id: str) -> dict:
    """Resolve a decision by exact or prefix match (or raise HTTP error)."""
    if decision_id in _decision_cache:
        return _decision_cache[decision_id]

    if len(decision_id) < MIN_DECISION_PREFIX:
        raise HTTPException(
            status_code=400,
            detail=f"Decision id prefix must be at least {MIN_DECISION_PREFIX} characters.",
        )

    matches = [
        cached_decision
        for cached_id, cached_decision in _decision_cache.items()
        if cached_id.startswith(decision_id)
    ]

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"Decision '{decision_id}' not found. Decisions are cached briefly. "
                   f"Re-run the decision and immediately request the report.",
        )
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Decision id prefix is ambiguous. Provide a longer prefix or the full id.",
        )

    return matches[0]


# ── Backward-compat aliases (used in main.py) ────────────────────────────────

def cache_decision(decision_id: str, decision_pack: dict) -> None:
    """Alias for ``put`` — keeps ``report.cache_decision(...)`` working."""
    put(decision_id, decision_pack)


def get_cached_decision(decision_id: str) -> Optional[dict]:
    """Alias for ``get`` — keeps ``report.get_cached_decision(...)`` working."""
    return get(decision_id)

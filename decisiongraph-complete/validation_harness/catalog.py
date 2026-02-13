"""Check registry with @register_check decorator."""
from __future__ import annotations

from typing import Callable

from .types import CheckCategory, CheckDefinition, Severity, Violation

CHECK_CATALOG: dict[str, CheckDefinition] = {}


def register_check(
    id: str,
    category: CheckCategory,
    severity: Severity,
    description: str,
) -> Callable:
    """Decorator that registers a check function in the global catalog."""

    def decorator(fn: Callable[[dict, str], list[Violation]]) -> Callable:
        CHECK_CATALOG[id] = CheckDefinition(
            id=id,
            category=category,
            severity=severity,
            description=description,
            fn=fn,
        )
        return fn

    return decorator


def get_enabled_checks() -> list[CheckDefinition]:
    """Return all registered check definitions."""
    return list(CHECK_CATALOG.values())

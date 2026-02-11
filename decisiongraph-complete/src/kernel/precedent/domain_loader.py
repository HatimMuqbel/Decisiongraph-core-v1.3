"""
Domain Loader — Dynamic domain discovery for the v3 precedent engine.

Loads DomainRegistry instances by domain ID.  Each domain registers itself
as a module under ``domains/<domain_id>/domain.py`` with a
``create_registry()`` factory function.

Usage:
    >>> from kernel.precedent.domain_loader import load_domain, list_domains
    >>> registry = load_domain("insurance_claims")
    >>> assert registry.domain == "insurance_claims"
    >>> domains = list_domains()
    >>> assert "banking_aml" in domains
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.precedent.domain_registry import DomainRegistry


# ---------------------------------------------------------------------------
# Domain registry — maps domain_id → module path
# ---------------------------------------------------------------------------

DOMAINS: dict[str, str] = {
    "banking_aml": "domains.banking_aml.domain",
    "insurance_claims": "domains.insurance_claims.domain",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_domain(domain_id: str) -> DomainRegistry:
    """Load a DomainRegistry by domain identifier.

    Args:
        domain_id: One of the registered domain IDs (e.g., "banking_aml",
                   "insurance_claims").

    Returns:
        A fully-constructed DomainRegistry for the requested domain.

    Raises:
        ValueError: If domain_id is not registered.
        ImportError: If the domain module cannot be imported.
    """
    module_path = DOMAINS.get(domain_id)
    if module_path is None:
        available = ", ".join(sorted(DOMAINS.keys()))
        raise ValueError(
            f"Unknown domain: '{domain_id}'. Available domains: {available}"
        )

    module = import_module(module_path)

    # Each domain module exposes create_registry() or create_<domain>_domain_registry()
    factory = getattr(module, "create_registry", None)
    if factory is None:
        # Fallback: try the domain-specific name
        for attr_name in dir(module):
            if attr_name.startswith("create_") and attr_name.endswith("_registry"):
                factory = getattr(module, attr_name)
                break

    if factory is None:
        raise ImportError(
            f"Domain module '{module_path}' does not expose a create_registry() "
            f"or create_*_registry() factory function."
        )

    return factory()


def list_domains() -> list[str]:
    """Return list of registered domain IDs."""
    return list(DOMAINS.keys())


def register_domain(domain_id: str, module_path: str) -> None:
    """Register a new domain at runtime.

    Args:
        domain_id: Unique domain identifier.
        module_path: Dot-path to module containing create_registry().
    """
    DOMAINS[domain_id] = module_path


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "DOMAINS",
    "load_domain",
    "list_domains",
    "register_domain",
]

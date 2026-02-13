"""Auto-import all check modules to populate the catalog."""
from . import (  # noqa: F401
    math_checks,
    consistency_checks,
    operational_checks,
    regulatory_checks,
    narrative_checks,
    evidence_checks,
)

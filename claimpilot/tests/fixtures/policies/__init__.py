"""
Policy factories for each line of business.

Each policy is created once and cached using lru_cache for performance.
"""
from .auto_oap1 import policy_auto_oap1
from .property_ho3 import policy_property_ho3
from .marine_pleasure import policy_marine_pleasure
from .health_group import policy_health_group
from .wsib_ontario import policy_wsib_ontario
from .cgl import policy_cgl
from .eo import policy_eo
from .travel import policy_travel


def register_all_policies():
    """Register all policy factories with the runner."""
    from ...helpers.runner import register_policy

    register_policy("auto", policy_auto_oap1)
    register_policy("property", policy_property_ho3)
    register_policy("marine", policy_marine_pleasure)
    register_policy("health", policy_health_group)
    register_policy("workers_comp", policy_wsib_ontario)
    register_policy("cgl", policy_cgl)
    register_policy("eo", policy_eo)
    register_policy("travel", policy_travel)


__all__ = [
    "policy_auto_oap1",
    "policy_property_ho3",
    "policy_marine_pleasure",
    "policy_health_group",
    "policy_wsib_ontario",
    "policy_cgl",
    "policy_eo",
    "policy_travel",
    "register_all_policies",
]

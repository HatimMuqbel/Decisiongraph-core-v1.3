"""
Kernel Precedent — domain-portable precedent matching engine.

Re-exports key classes from the 6 precedent modules.
"""

from kernel.precedent.domain_registry import *        # noqa: F401,F403
from kernel.precedent.field_comparators import *       # noqa: F401,F403
from kernel.precedent.comparability_gate import *      # noqa: F401,F403
from kernel.precedent.governed_confidence import *     # noqa: F401,F403
from kernel.precedent.precedent_scorer import *        # noqa: F401,F403
from kernel.precedent.precedent_registry import *      # noqa: F401,F403

"""
Kernel Foundation — domain-portable decision primitives.

Re-exports all public symbols from the 10 foundation modules so that
consumers can do ``from kernel.foundation import DecisionCell, Chain, ...``
"""

from kernel.foundation.cell import *        # noqa: F401,F403
from kernel.foundation.chain import *       # noqa: F401,F403
from kernel.foundation.genesis import *     # noqa: F401,F403
from kernel.foundation.namespace import *   # noqa: F401,F403
from kernel.foundation.scholar import *     # noqa: F401,F403
from kernel.foundation.signing import *     # noqa: F401,F403
from kernel.foundation.wal import *         # noqa: F401,F403
from kernel.foundation.segmented_wal import *  # noqa: F401,F403
from kernel.foundation.judgment import *    # noqa: F401,F403
from kernel.foundation.canon import *       # noqa: F401,F403

"""Backward-compatible shim. Real implementation in kernel.foundation.policyhead."""
import kernel.foundation.policyhead as _mod  # noqa: E402
from kernel.foundation.policyhead import *  # noqa: F401,F403

# Re-export ALL public names (not just __all__)
_names = [_n for _n in dir(_mod) if not _n.startswith("_")]
for _n in _names:
    globals()[_n] = getattr(_mod, _n)
del _names, _n, _mod

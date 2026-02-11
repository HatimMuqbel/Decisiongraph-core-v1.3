"""Backward-compatible shim. Real implementation in domains.banking_aml.seed_generator."""
import domains.banking_aml.seed_generator as _mod  # noqa: E402
from domains.banking_aml.seed_generator import *  # noqa: F401,F403

# Re-export ALL public names (not just __all__)
_names = [_n for _n in dir(_mod) if not _n.startswith("_")]
for _n in _names:
    globals()[_n] = getattr(_mod, _n)
del _names, _n, _mod

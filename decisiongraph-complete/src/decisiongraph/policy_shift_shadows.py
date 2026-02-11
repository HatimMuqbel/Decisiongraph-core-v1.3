"""Backward-compatible shim. Real implementation in domains.banking_aml.policy_shifts."""
import domains.banking_aml.policy_shifts as _mod  # noqa: E402
from domains.banking_aml.policy_shifts import *  # noqa: F401,F403

# Re-export ALL public names (not just __all__)
_names = [_n for _n in dir(_mod) if not _n.startswith("_")]
for _n in _names:
    globals()[_n] = getattr(_mod, _n)

# Re-export underscore-prefixed names used by external callers
_case_facts_to_seed_like = _mod._case_facts_to_seed_like

del _names, _n, _mod

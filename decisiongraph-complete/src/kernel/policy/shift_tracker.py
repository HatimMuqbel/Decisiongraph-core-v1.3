"""
Universal policy shift tracking.
Domain-specific shifts live in domains/<domain>/policy_shifts.py.
This module provides the kernel interface for regime detection,
temporal partitioning, and shadow projection.
"""
# TODO: Extract universal shift tracking from policy_shift_shadows.py
# TODO: Parameterize shadow projection to accept domain-specific shift defs
# TODO: Move temporal partitioning (SHIFT_EFFECTIVE_DATES) logic here

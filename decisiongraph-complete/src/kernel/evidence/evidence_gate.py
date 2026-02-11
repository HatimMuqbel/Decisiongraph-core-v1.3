"""
Universal Two-Stage Evidence Gate Pattern.

The evidence gate enforces a two-stage evidence lifecycle:

  Stage 1 — BLOCKING_RECOMMENDATION
    Missing evidence at this level prevents the system from even
    generating a recommendation.  The case stays in a "needs info"
    queue until the blocking evidence is supplied.

  Stage 2 — BLOCKING_FINALIZATION
    The system can recommend, but a human analyst cannot finalize
    (approve/deny/escalate) until finalization-blocking evidence
    is present.

This pattern is domain-portable:
  - Banking AML: KYC docs block recommendation; source-of-funds
    declarations block finalization of high-value STRs.
  - Insurance: Police report blocks recommendation; signed
    statement of loss blocks finalization.

TODO: Extract the universal gate interface from ClaimPilot's
      EvidenceGate (claimpilot/src/claimpilot/engine/evidence_gate.py).
      The current implementation is tightly coupled to insurance-specific
      models (ClaimContext, DocumentRequirement, EvidenceItem,
      EvidenceRule, GateStrictness, ConditionEvaluator).

      Kernel interface should define:
      - EvidenceRequirement(id, description, strictness, applies_when)
      - EvidenceGateResult(can_recommend, can_finalize, missing_*)
      - AbstractEvidenceGate.evaluate(requirements, facts) -> result
      - Domain adapters map domain models to kernel types
"""
from __future__ import annotations

from enum import Enum


class GateStage(Enum):
    """Evidence gate strictness levels."""
    BLOCKING_RECOMMENDATION = "blocking_recommendation"
    BLOCKING_FINALIZATION = "blocking_finalization"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


__all__ = ["GateStage"]

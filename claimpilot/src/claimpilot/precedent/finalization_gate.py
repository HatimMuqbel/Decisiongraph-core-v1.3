"""
ClaimPilot Precedent System: Finalization Gate Module

This module implements the finalization gate for creating JUDGMENT cells
when a FinalDisposition is sealed.

Key components:
- FinalizationGate: Creates JUDGMENT cells on disposition seal
- FinalizationResult: Result of finalization process

Design Principles:
- Only sealed dispositions become precedents
- Privacy-preserving: case_id is hashed, never stored raw
- Deterministic: Same inputs produce same fingerprint
- Audit trail: Links FinalDisposition to JUDGMENT cell

Integration Point:
This gate is called when FinalDisposition.seal() completes successfully.
It creates a JUDGMENT cell in the chain and updates the disposition
with the judgment_cell_id link.

Example:
    >>> gate = FinalizationGate(chain, fingerprint_registry, salt)
    >>> result = gate.finalize(
    ...     disposition=final_disposition,
    ...     context=claim_context,
    ...     recommendation=recommendation
    ... )
    >>> print(f"Created JUDGMENT cell: {result.judgment_cell_id}")
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

# DecisionGraph imports are optional - the module may not be installed
try:
    from kernel.foundation.judgment import (
        AnchorFact,
        JudgmentPayload,
        create_judgment_cell,
        compute_case_id_hash,
    )
    from kernel.foundation.cell import DecisionCell, get_current_timestamp
    DECISIONGRAPH_AVAILABLE = True
except ImportError:
    # Create stub types for when decisiongraph is not available
    AnchorFact = Any  # type: ignore
    JudgmentPayload = Any  # type: ignore
    DecisionCell = Any  # type: ignore
    def create_judgment_cell(*args, **kwargs) -> Any:  # type: ignore
        return None
    def compute_case_id_hash(*args, **kwargs) -> str:  # type: ignore
        return hashlib.sha256(str(args).encode()).hexdigest()[:16]
    def get_current_timestamp() -> datetime:  # type: ignore
        return datetime.now(timezone.utc)
    DECISIONGRAPH_AVAILABLE = False

from .fingerprint_schema import FingerprintSchemaRegistry

if TYPE_CHECKING:
    from kernel.foundation.chain import Chain
    from ..models.disposition import FinalDisposition
    from ..models.recommendation import RecommendationRecord
    from ..models.claim import ClaimContext


# =============================================================================
# Exceptions
# =============================================================================

class FinalizationError(Exception):
    """Base exception for finalization errors."""
    pass


class DispositionNotSealedError(FinalizationError):
    """Raised when trying to finalize an unsealed disposition."""
    pass


class FinalizationDataError(FinalizationError):
    """Raised when required data is missing for finalization."""
    pass


# =============================================================================
# Finalization Result
# =============================================================================

@dataclass
class FinalizationResult:
    """
    Result of the finalization process.

    Attributes:
        success: Whether finalization succeeded
        judgment_cell_id: ID of the created JUDGMENT cell
        judgment_cell_hash: Hash of the JUDGMENT cell
        precedent_id: Random UUID for the precedent
        fingerprint_hash: Computed fingerprint hash
        error: Error message if finalization failed
        was_override: Whether human overrode engine recommendation
        engine_outcome: Original engine recommendation (if override)
        final_outcome: Final human outcome (always the recorded outcome)
    """
    success: bool
    judgment_cell_id: Optional[str] = None
    judgment_cell_hash: Optional[str] = None
    precedent_id: Optional[str] = None
    fingerprint_hash: Optional[str] = None
    error: Optional[str] = None
    was_override: bool = False
    engine_outcome: Optional[str] = None
    final_outcome: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {"success": self.success}
        if self.judgment_cell_id:
            result["judgment_cell_id"] = self.judgment_cell_id
        if self.judgment_cell_hash:
            result["judgment_cell_hash"] = self.judgment_cell_hash
        if self.precedent_id:
            result["precedent_id"] = self.precedent_id
        if self.fingerprint_hash:
            result["fingerprint_hash"] = self.fingerprint_hash
        if self.error:
            result["error"] = self.error
        return result


# =============================================================================
# Finalization Gate
# =============================================================================

class FinalizationGate:
    """
    Gate for creating JUDGMENT cells when dispositions are sealed.

    The finalization gate ensures that only sealed (immutable) decisions
    become precedents in the chain. It handles:
    - Validation that disposition is sealed
    - Fingerprint computation from claim facts
    - JUDGMENT cell creation with privacy-preserving data
    - Linking the disposition to the JUDGMENT cell

    Usage:
        >>> gate = FinalizationGate(chain, fingerprint_registry, salt)
        >>> result = gate.finalize(disposition, context, recommendation)
        >>> if result.success:
        ...     print(f"Created precedent: {result.precedent_id}")
    """

    def __init__(
        self,
        chain: Chain,
        fingerprint_registry: Optional[FingerprintSchemaRegistry] = None,
        salt: str = "",
        namespace_prefix: str = "claims.precedents",
    ) -> None:
        """
        Initialize the finalization gate.

        Args:
            chain: The DecisionGraph chain to append JUDGMENT cells to
            fingerprint_registry: Registry for fingerprint schemas
            salt: Salt for privacy-preserving hashing
            namespace_prefix: Namespace for JUDGMENT cells
        """
        self.chain = chain
        self.fingerprint_registry = fingerprint_registry or FingerprintSchemaRegistry()
        self.salt = salt
        self.namespace_prefix = namespace_prefix

    def finalize(
        self,
        disposition: FinalDisposition,
        context: ClaimContext,
        recommendation: RecommendationRecord,
        policy_type: str = "auto",
        jurisdiction: str = "CA-ON",
    ) -> FinalizationResult:
        """
        Create a JUDGMENT cell from a sealed disposition.

        This is the main entry point for finalization. It:
        1. Validates the disposition is sealed (WRITE-ONCE PRINCIPLE)
        2. Computes the fingerprint from claim facts
        3. Creates the JUDGMENT payload with FINAL HUMAN OUTCOME (MIRROR RULE)
        4. Appends the JUDGMENT cell to the chain
        5. Returns the result with cell ID

        GOVERNANCE RULES:
        - Write-Once Principle: A JUDGMENT cell can only be created when
          case status moves to FINAL (disposition is sealed)
        - Mirror Rule: If human overrides engine recommendation, the JUDGMENT
          cell records the Final Human Outcome, not the original engine suggestion

        Args:
            disposition: The sealed FinalDisposition
            context: The ClaimContext with facts
            recommendation: The RecommendationRecord that was acted on
            policy_type: Policy type for fingerprint schema lookup
            jurisdiction: Jurisdiction for fingerprint schema lookup

        Returns:
            FinalizationResult with success/failure and cell info

        Raises:
            DispositionNotSealedError: If disposition is not sealed
            FinalizationDataError: If required data is missing
        """
        # =================================================================
        # WRITE-ONCE PRINCIPLE: Only sealed (FINAL) dispositions become
        # precedents. This ensures immutability and audit integrity.
        # =================================================================
        if not disposition.is_sealed:
            raise DispositionNotSealedError(
                f"Disposition {disposition.id} is not sealed. "
                f"Call disposition.seal() before finalization. "
                f"WRITE-ONCE PRINCIPLE: Only FINAL cases become precedents."
            )

        # Validate required data
        if not disposition.claim_id:
            raise FinalizationDataError("Disposition missing claim_id")
        if not recommendation.policy_pack_hash:
            raise FinalizationDataError("Recommendation missing policy_pack_hash")

        try:
            # Get fingerprint schema
            schema = self.fingerprint_registry.get_schema(policy_type, jurisdiction)

            # Extract facts from context for fingerprinting
            facts = self._extract_facts(context)

            # Compute fingerprint
            fingerprint_hash = self.fingerprint_registry.compute_fingerprint(
                schema, facts, self.salt
            )

            # Compute case_id hash
            case_id_hash = compute_case_id_hash(disposition.claim_id, self.salt)

            # Extract anchor facts
            anchor_facts = self._create_anchor_facts(context, schema)

            # =============================================================
            # MIRROR RULE: Record the FINAL HUMAN OUTCOME, not the engine
            # suggestion. If human overrode engine, we track both but the
            # JUDGMENT cell records what actually happened.
            # =============================================================
            final_outcome_code = self._disposition_to_outcome_code(disposition)
            engine_outcome_code = self._recommendation_to_outcome_code(recommendation)

            # Detect override: human chose differently than engine suggested
            was_override = (final_outcome_code != engine_outcome_code)

            # The outcome_code in JUDGMENT is ALWAYS the final human decision
            outcome_code = final_outcome_code

            # Map certainty
            certainty = self._recommendation_certainty_to_string(recommendation)

            # Determine source_type based on override
            if was_override:
                source_type = "human_override"
            else:
                source_type = "system_generated"

            # Create JUDGMENT payload
            payload = JudgmentPayload.create(
                case_id_hash=case_id_hash,
                jurisdiction_code=jurisdiction,
                fingerprint_hash=fingerprint_hash,
                fingerprint_schema_id=schema.schema_id,
                exclusion_codes=recommendation.exclusions_triggered,
                reason_codes=self._extract_reason_codes(recommendation),
                reason_code_registry_id=f"claimpilot:{policy_type}:v1",
                outcome_code=outcome_code,
                certainty=certainty,
                anchor_facts=anchor_facts,
                policy_pack_hash=recommendation.policy_pack_hash,
                policy_pack_id=recommendation.policy_pack_id,
                policy_version=recommendation.policy_pack_version,
                decision_level=disposition.finalizer_role or "adjuster",
                decided_at=disposition.finalized_at.isoformat() + "Z"
                           if not disposition.finalized_at.tzinfo
                           else disposition.finalized_at.isoformat(),
                decided_by_role=disposition.finalizer_role or "adjuster",
                source_type=source_type,
                authority_hashes=[
                    c.excerpt_hash for c in recommendation.authority_hashes
                ],
            )

            # If override, add metadata to payload (if supported)
            if was_override and hasattr(payload, 'metadata'):
                payload.metadata = payload.metadata or {}
                payload.metadata['override'] = {
                    'engine_recommendation': engine_outcome_code,
                    'human_decision': final_outcome_code,
                    'override_reason': getattr(disposition, 'override_reason', None),
                }

            # Create the JUDGMENT cell
            cell = create_judgment_cell(
                payload=payload,
                namespace=self.namespace_prefix,
                graph_id=self.chain.graph_id,
                prev_cell_hash=self.chain.head.cell_id,
            )

            # Append to chain
            self.chain.append(cell)

            return FinalizationResult(
                success=True,
                judgment_cell_id=cell.cell_id,
                judgment_cell_hash=cell.cell_id,
                precedent_id=payload.precedent_id,
                fingerprint_hash=fingerprint_hash,
                was_override=was_override,
                engine_outcome=engine_outcome_code if was_override else None,
                final_outcome=final_outcome_code,
            )

        except Exception as e:
            return FinalizationResult(
                success=False,
                error=str(e),
            )

    def _extract_facts(self, context: ClaimContext) -> dict[str, Any]:
        """Extract facts from ClaimContext for fingerprinting."""
        facts: dict[str, Any] = {}

        # Extract facts from context
        # The context has a facts dict with field_id -> value
        if hasattr(context, "facts") and context.facts:
            for field_id, fact_value in context.facts.items():
                # Handle both raw values and fact objects
                if hasattr(fact_value, "value"):
                    facts[field_id] = fact_value.value
                else:
                    facts[field_id] = fact_value

        return facts

    def _create_anchor_facts(
        self,
        context: ClaimContext,
        schema: Any,
    ) -> list[AnchorFact]:
        """Create AnchorFact list from context for the given schema."""
        anchor_facts: list[AnchorFact] = []

        if not hasattr(context, "facts") or not context.facts:
            return anchor_facts

        # Only include facts relevant to the fingerprint schema
        for field_id in schema.exclusion_relevant_facts:
            if field_id in context.facts:
                fact_value = context.facts[field_id]

                # Get the value
                if hasattr(fact_value, "value"):
                    value = fact_value.value
                else:
                    value = fact_value

                # Get the label
                if hasattr(fact_value, "label"):
                    label = fact_value.label
                else:
                    label = field_id.replace(".", " ").replace("_", " ").title()

                anchor_facts.append(AnchorFact(
                    field_id=field_id,
                    value=value,
                    label=label,
                ))

        return anchor_facts

    def _disposition_to_outcome_code(self, disposition: FinalDisposition) -> str:
        """Map DispositionType to outcome_code string."""
        mapping = {
            "pay": "pay",
            "deny": "deny",
            "partial": "partial",
            "escalate": "escalate",
            "request_info": "escalate",  # Map to escalate
            "hold": "escalate",
            "refer_siu": "deny",  # SIU referral implies deny
            "subrogation": "pay",  # Subrogation implies coverage
            "reserve_only": "escalate",
            "close_no_pay": "deny",
        }
        disposition_value = disposition.disposition.value
        return mapping.get(disposition_value, "escalate")

    def _recommendation_to_outcome_code(
        self,
        recommendation: RecommendationRecord,
    ) -> str:
        """Map RecommendationRecord to outcome_code string (engine suggestion)."""
        # Get the recommended disposition from the engine
        rec_disposition = getattr(recommendation, 'recommended_disposition', None)
        if rec_disposition is None:
            rec_disposition = getattr(recommendation, 'disposition', 'escalate')

        # Handle enum or string
        if hasattr(rec_disposition, 'value'):
            rec_disposition = rec_disposition.value

        mapping = {
            "pay": "pay",
            "deny": "deny",
            "partial": "partial",
            "escalate": "escalate",
            "request_info": "escalate",
            "hold": "escalate",
            "refer_siu": "deny",
            "subrogation": "pay",
            "reserve_only": "escalate",
            "close_no_pay": "deny",
        }
        return mapping.get(str(rec_disposition).lower(), "escalate")

    def _recommendation_certainty_to_string(
        self,
        recommendation: RecommendationRecord,
    ) -> str:
        """Map RecommendationCertainty to certainty string."""
        certainty_value = recommendation.certainty.value
        mapping = {
            "high": "high",
            "medium": "medium",
            "low": "low",
            "requires_judgment": "low",
        }
        return mapping.get(certainty_value, "medium")

    def _extract_reason_codes(
        self,
        recommendation: RecommendationRecord,
    ) -> list[str]:
        """Extract reason codes from recommendation."""
        # Combine exclusions triggered with any other reason codes
        reason_codes: list[str] = []

        # Add exclusion-based reason codes
        for exclusion in recommendation.exclusions_triggered:
            reason_codes.append(f"RC-{exclusion}")

        return reason_codes


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "FinalizationError",
    "DispositionNotSealedError",
    "FinalizationDataError",

    # Data classes
    "FinalizationResult",

    # Gate
    "FinalizationGate",
]

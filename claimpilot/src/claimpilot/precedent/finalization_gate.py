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
    from decisiongraph.judgment import (
        AnchorFact,
        JudgmentPayload,
        create_judgment_cell,
        compute_case_id_hash,
    )
    from decisiongraph.cell import DecisionCell, get_current_timestamp
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
    from decisiongraph.chain import Chain
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
    """
    success: bool
    judgment_cell_id: Optional[str] = None
    judgment_cell_hash: Optional[str] = None
    precedent_id: Optional[str] = None
    fingerprint_hash: Optional[str] = None
    error: Optional[str] = None

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
        1. Validates the disposition is sealed
        2. Computes the fingerprint from claim facts
        3. Creates the JUDGMENT payload
        4. Appends the JUDGMENT cell to the chain
        5. Returns the result with cell ID

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
        # Validate disposition is sealed
        if not disposition.is_sealed:
            raise DispositionNotSealedError(
                f"Disposition {disposition.id} is not sealed. "
                f"Call disposition.seal() before finalization."
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

            # Map disposition to outcome_code
            outcome_code = self._disposition_to_outcome_code(disposition)

            # Map certainty
            certainty = self._recommendation_certainty_to_string(recommendation)

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
                source_type="system_generated",
                authority_hashes=[
                    c.excerpt_hash for c in recommendation.authority_hashes
                ],
            )

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

"""
DecisionGraph Core: Promotion Module (v1.5)

PromotionRequest tracks the lifecycle of a rule promotion from submission
through signature collection to finalization:
- PromotionStatus enum defines the state machine
- PromotionRequest dataclass holds both immutable (what's being promoted)
  and mutable (signature collection) state

Key properties:
- rule_ids is immutable (tuple, not list) - what's being promoted cannot change
- canonical_payload is deterministic (sorted rule_ids, includes promotion_id)
- status and signatures are mutable during the collection phase
- PromotionRequest.create() factory ensures proper initialization

Design rationale:
- NOT frozen=True: status and signatures change during collection
- tuple[str, ...] for rule_ids: prevents mutation even though dataclass isn't frozen
- canonical_payload includes promotion_id: prevents replay attacks across promotions
- Sorted rule_ids in payload: order-independent signature verification
"""

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

from .cell import get_current_timestamp


class PromotionStatus(str, Enum):
    """
    State machine for promotion lifecycle.

    State transitions:
    PENDING → COLLECTING → THRESHOLD_MET → FINALIZED
                ↓
            REJECTED (explicit rejection or expiration)

    States:
        PENDING: PromotionRequest created, no signatures yet
        COLLECTING: Has at least one witness signature
        THRESHOLD_MET: Enough signatures to finalize, ready for PolicyHead creation
        FINALIZED: PolicyHead created, promotion complete
        REJECTED: Explicitly rejected by witnesses or expired without threshold
    """
    PENDING = "pending"
    COLLECTING = "collecting"
    THRESHOLD_MET = "threshold_met"
    FINALIZED = "finalized"
    REJECTED = "rejected"


@dataclass
class PromotionRequest:
    """
    Tracks a promotion request through its lifecycle.

    A PromotionRequest represents an attempt to promote a set of rules to
    become the active policy (PolicyHead) for a namespace. It collects
    witness signatures until threshold is met, then can be finalized.

    Immutable fields (set at creation):
        promotion_id: Unique identifier for this promotion attempt
        namespace: Target namespace for the promotion
        rule_ids: Tuple of rule IDs to promote (immutable - tuple, not list)
        submitter_id: Who initiated this promotion
        created_at: ISO 8601 timestamp when promotion was created
        canonical_payload: Deterministic bytes that witnesses sign
        required_threshold: Number of signatures needed to finalize

    Mutable state (changes during collection):
        status: Current promotion status (default: PENDING)
        signatures: Dict mapping witness_id → signature bytes

    Immutability design:
        - dataclass NOT frozen=True (status/signatures are mutable)
        - rule_ids is tuple[str, ...] to prevent mutation
        - canonical_payload is bytes (immutable)

    Canonical payload format:
        The canonical_payload is what witnesses actually sign. It includes:
        - promotion_id (prevents replay attacks across promotions)
        - namespace (what namespace this affects)
        - rule_ids (sorted list, order-independent)
        - timestamp (when promotion was created)

        JSON is serialized with sort_keys=True and compact separators
        for deterministic, order-independent hashing.

    Examples:
        >>> # Create promotion request
        >>> pr = PromotionRequest.create(
        ...     namespace="corp.hr",
        ...     rule_ids=["rule:vacation", "rule:sick_leave"],
        ...     submitter_id="alice",
        ...     threshold=2,
        ...     created_at="2026-01-15T10:00:00Z"
        ... )

        >>> # Check initial state
        >>> pr.status
        <PromotionStatus.PENDING: 'pending'>

        >>> # rule_ids is immutable (tuple)
        >>> type(pr.rule_ids)
        <class 'tuple'>

        >>> # canonical_payload includes sorted rule_ids
        >>> b'"rule_ids":["rule:sick_leave","rule:vacation"]' in pr.canonical_payload
        True
    """

    # Immutable fields (set at creation)
    promotion_id: str
    namespace: str
    rule_ids: tuple[str, ...]  # tuple ensures immutability
    submitter_id: str
    created_at: str
    canonical_payload: bytes
    required_threshold: int

    # Mutable state (changes during collection)
    status: PromotionStatus = PromotionStatus.PENDING
    signatures: Dict[str, bytes] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        namespace: str,
        rule_ids: list[str],
        submitter_id: str,
        threshold: int,
        created_at: str = None
    ) -> 'PromotionRequest':
        """
        Factory method to create a PromotionRequest with deterministic canonical_payload.

        This factory ensures:
        1. promotion_id is generated as UUID
        2. rule_ids are sorted and stored as tuple (immutable)
        3. canonical_payload is deterministic (sorted rule_ids, consistent JSON)
        4. created_at defaults to current timestamp if not provided

        Args:
            namespace: Target namespace for promotion
            rule_ids: List of rule IDs to promote
            submitter_id: Who initiated this promotion
            threshold: Number of witness signatures required
            created_at: ISO 8601 timestamp (defaults to now if not provided)

        Returns:
            PromotionRequest with generated promotion_id and canonical_payload

        Example:
            >>> pr = PromotionRequest.create(
            ...     namespace="corp",
            ...     rule_ids=["rule:b", "rule:a"],  # order doesn't matter
            ...     submitter_id="alice",
            ...     threshold=2,
            ...     created_at="2026-01-15T10:00:00Z"
            ... )
            >>> # rule_ids are sorted
            >>> pr.rule_ids
            ('rule:a', 'rule:b')
        """
        # Generate unique promotion ID
        promotion_id = str(uuid.uuid4())

        # Use current timestamp if not provided
        if created_at is None:
            created_at = get_current_timestamp()

        # Sort rule_ids for deterministic ordering, store as tuple for immutability
        sorted_rule_ids = tuple(sorted(rule_ids))

        # Create canonical payload (what witnesses sign)
        # Includes promotion_id to prevent replay attacks
        # Sorted rule_ids for order-independence
        payload_dict = {
            "promotion_id": promotion_id,
            "namespace": namespace,
            "rule_ids": list(sorted_rule_ids),  # JSON requires list, not tuple
            "timestamp": created_at
        }

        # Deterministic JSON serialization
        # sort_keys=True: consistent field ordering
        # separators=(',', ':'): compact, no extra whitespace
        canonical_payload = json.dumps(
            payload_dict,
            sort_keys=True,
            separators=(',', ':')
        ).encode('utf-8')

        # Create instance
        return cls(
            promotion_id=promotion_id,
            namespace=namespace,
            rule_ids=sorted_rule_ids,
            submitter_id=submitter_id,
            created_at=created_at,
            canonical_payload=canonical_payload,
            required_threshold=threshold,
            status=PromotionStatus.PENDING,
            signatures={}
        )


# Export public interface
__all__ = [
    'PromotionStatus',
    'PromotionRequest',
]

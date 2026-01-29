"""
Test PromotionRequest and PromotionStatus (v1.5).

These tests validate:
- PromotionStatus enum values
- PromotionRequest.create() factory method
- Immutability of rule_ids (tuple, not list)
- Deterministic canonical_payload generation
- Order-independent canonical_payload (sorted rule_ids)
- Initial state (PENDING status, empty signatures)
- Mutability of status during collection phase
"""

import json
from decisiongraph import PromotionRequest, PromotionStatus

# Fixed timestamp for deterministic tests
T0 = "2026-01-15T10:00:00Z"


def test_promotion_status_values():
    """PromotionStatus enum has correct string values for all 5 states."""
    assert PromotionStatus.PENDING.value == "pending"
    assert PromotionStatus.COLLECTING.value == "collecting"
    assert PromotionStatus.THRESHOLD_MET.value == "threshold_met"
    assert PromotionStatus.FINALIZED.value == "finalized"
    assert PromotionStatus.REJECTED.value == "rejected"


def test_promotion_request_create():
    """Factory creates valid request with UUID promotion_id and all required fields."""
    pr = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a", "rule:b"],
        submitter_id="alice",
        threshold=2,
        created_at=T0
    )

    # Check all fields populated
    assert pr.promotion_id is not None
    assert len(pr.promotion_id) == 36  # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    assert pr.namespace == "corp"
    assert pr.submitter_id == "alice"
    assert pr.created_at == T0
    assert pr.required_threshold == 2
    assert pr.canonical_payload is not None
    assert isinstance(pr.canonical_payload, bytes)


def test_promotion_request_rule_ids_immutable():
    """rule_ids is stored as tuple (immutable), not list."""
    pr = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a", "rule:b", "rule:c"],
        submitter_id="alice",
        threshold=2,
        created_at=T0
    )

    # Check it's a tuple
    assert isinstance(pr.rule_ids, tuple)
    assert pr.rule_ids == ("rule:a", "rule:b", "rule:c")

    # Verify immutability: tuple has no append method
    assert not hasattr(pr.rule_ids, 'append')


def test_promotion_request_canonical_payload_deterministic():
    """canonical_payload includes all promotion details in deterministic JSON format."""
    pr = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a", "rule:b"],
        submitter_id="alice",
        threshold=2,
        created_at=T0
    )

    # Decode payload to verify structure
    payload_str = pr.canonical_payload.decode('utf-8')
    payload_dict = json.loads(payload_str)

    # Check all expected fields are present
    assert "promotion_id" in payload_dict
    assert payload_dict["promotion_id"] == pr.promotion_id
    assert payload_dict["namespace"] == "corp"
    assert payload_dict["rule_ids"] == ["rule:a", "rule:b"]
    assert payload_dict["timestamp"] == T0

    # Verify compact JSON format (no spaces)
    assert " " not in payload_str  # separators=(',', ':') produces compact JSON


def test_promotion_request_canonical_payload_sorted():
    """Different rule_id input order produces same canonical_payload (order-independent)."""
    pr1 = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:z", "rule:a", "rule:m"],
        submitter_id="alice",
        threshold=2,
        created_at=T0
    )

    pr2 = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a", "rule:m", "rule:z"],
        submitter_id="alice",
        threshold=2,
        created_at=T0
    )

    # Both should have sorted rule_ids
    assert pr1.rule_ids == ("rule:a", "rule:m", "rule:z")
    assert pr2.rule_ids == ("rule:a", "rule:m", "rule:z")

    # canonical_payload will differ because promotion_id is different (UUID)
    # But the rule_ids ordering within payload should be the same
    payload1 = json.loads(pr1.canonical_payload.decode('utf-8'))
    payload2 = json.loads(pr2.canonical_payload.decode('utf-8'))

    assert payload1["rule_ids"] == ["rule:a", "rule:m", "rule:z"]
    assert payload2["rule_ids"] == ["rule:a", "rule:m", "rule:z"]


def test_promotion_request_initial_status_pending():
    """Status is PENDING immediately after creation."""
    pr = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a"],
        submitter_id="alice",
        threshold=1,
        created_at=T0
    )

    assert pr.status == PromotionStatus.PENDING


def test_promotion_request_signatures_empty():
    """signatures dict is empty after creation."""
    pr = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a"],
        submitter_id="alice",
        threshold=1,
        created_at=T0
    )

    assert pr.signatures == {}
    assert len(pr.signatures) == 0


def test_promotion_request_status_mutable():
    """Can change status from PENDING to COLLECTING (dataclass is NOT frozen)."""
    pr = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a"],
        submitter_id="alice",
        threshold=1,
        created_at=T0
    )

    # Initial state
    assert pr.status == PromotionStatus.PENDING

    # Change status (should not raise FrozenInstanceError)
    pr.status = PromotionStatus.COLLECTING

    # Verify change took effect
    assert pr.status == PromotionStatus.COLLECTING


def test_promotion_request_signatures_mutable():
    """Can add signatures to the signatures dict (dataclass is NOT frozen)."""
    pr = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a"],
        submitter_id="alice",
        threshold=2,
        created_at=T0
    )

    # Initial state
    assert len(pr.signatures) == 0

    # Add signatures (should not raise FrozenInstanceError)
    pr.signatures["witness:bob"] = b"signature_bytes_bob"
    pr.signatures["witness:charlie"] = b"signature_bytes_charlie"

    # Verify changes took effect
    assert len(pr.signatures) == 2
    assert pr.signatures["witness:bob"] == b"signature_bytes_bob"
    assert pr.signatures["witness:charlie"] == b"signature_bytes_charlie"


def test_promotion_request_canonical_payload_includes_promotion_id():
    """canonical_payload includes promotion_id to prevent replay attacks."""
    pr = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a"],
        submitter_id="alice",
        threshold=1,
        created_at=T0
    )

    # Decode and check promotion_id is in payload
    payload_dict = json.loads(pr.canonical_payload.decode('utf-8'))
    assert payload_dict["promotion_id"] == pr.promotion_id

    # This means each promotion has a unique payload to sign,
    # even if namespace/rule_ids/timestamp are identical


def test_promotion_request_created_at_defaults_to_current_time():
    """If created_at not provided, defaults to current timestamp."""
    pr = PromotionRequest.create(
        namespace="corp",
        rule_ids=["rule:a"],
        submitter_id="alice",
        threshold=1
        # No created_at parameter
    )

    # Should have a timestamp
    assert pr.created_at is not None
    assert isinstance(pr.created_at, str)
    # Basic ISO 8601 format check
    assert "T" in pr.created_at
    assert "Z" in pr.created_at or "+" in pr.created_at or "-" in pr.created_at

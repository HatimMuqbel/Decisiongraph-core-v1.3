"""
Tests for Engine promotion workflow (PRO-01, PRO-02, PRO-05, PRO-06).

Tests cover:
- submit_promotion: Creates PromotionRequest, returns promotion_id
- collect_witness_signature: Authorization check, signature verification, status updates
- Error cases: unauthorized witness, invalid signature, promotion not found
- INT-02: policy_hash verification at finalization
- INT-03: namespace validation for rule_ids
- Race detection: concurrent promotion detection via prev_policy_head
"""
import pytest
from decisiongraph import (
    Engine, Chain, PromotionStatus,
    InputInvalidError, UnauthorizedError, SignatureInvalidError
)
from decisiongraph.genesis import create_genesis_cell_with_witness_set
from decisiongraph.signing import generate_ed25519_keypair, sign_bytes
from decisiongraph.policyhead import get_current_policy_head, parse_policy_data
from decisiongraph.cell import (
    DecisionCell, Header, Fact, LogicAnchor, Proof,
    CellType, SourceQuality, compute_rule_logic_hash, get_current_timestamp
)

# Fixed timestamps for deterministic tests
T0 = "2026-01-15T10:00:00Z"
T1 = "2026-01-15T10:00:01Z"
T2 = "2026-01-15T10:00:02Z"
T3 = "2026-01-15T10:00:03Z"
T4 = "2026-01-15T10:00:04Z"
T5 = "2026-01-15T10:00:05Z"


def create_test_chain_with_witnesses(witnesses, threshold):
    """Create a chain with Genesis containing WitnessSet."""
    chain = Chain()  # Empty chain, no genesis yet
    genesis = create_genesis_cell_with_witness_set(
        graph_name="TestGraph",
        root_namespace="corp",
        witnesses=witnesses,
        threshold=threshold
    )
    chain.append(genesis)
    return chain


def create_rule_cell(chain, namespace, rule_id_suffix, system_time=None):
    """
    Create a rule cell for testing namespace validation.

    Args:
        chain: The chain to append to
        namespace: The namespace for the rule
        rule_id_suffix: A suffix for the rule_id (e.g., "a", "b")
        system_time: Optional timestamp, defaults to current time

    Returns:
        The created DecisionCell (already appended to chain)
    """
    # Use current timestamp to ensure temporal ordering after genesis
    ts = system_time or get_current_timestamp()
    rule_cell = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=chain.graph_id,
            cell_type=CellType.RULE,
            system_time=ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace=namespace,
            subject=f"rule:{rule_id_suffix}",
            predicate="defines",
            object=f"rule_logic_{rule_id_suffix}",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=ts
        ),
        logic_anchor=LogicAnchor(
            rule_id=f"rule:{rule_id_suffix}",
            rule_logic_hash=compute_rule_logic_hash(f"Rule {rule_id_suffix} logic")
        ),
        proof=Proof(signer_id="system:rules")
    )
    chain.append(rule_cell)
    return rule_cell


class TestSubmitPromotion:
    """Tests for Engine.submit_promotion() (PRO-01)"""

    def test_submit_promotion_returns_promotion_id(self):
        """submit_promotion returns a valid promotion_id string."""
        chain = create_test_chain_with_witnesses(["alice", "bob"], 2)
        # Create actual rule cells in the chain
        rule_a = create_rule_cell(chain, "corp", "a")
        rule_b = create_rule_cell(chain, "corp", "b")
        engine = Engine(chain)

        promotion_id = engine.submit_promotion(
            namespace="corp",
            rule_ids=[rule_a.cell_id, rule_b.cell_id],
            submitter_id="alice"
        )

        assert promotion_id is not None
        assert isinstance(promotion_id, str)
        assert len(promotion_id) == 36  # UUID format

    def test_submit_promotion_stores_request(self):
        """Promotion request is stored internally."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)

        promotion_id = engine.submit_promotion(
            namespace="corp",
            rule_ids=[rule_a.cell_id],
            submitter_id="alice"
        )

        assert promotion_id in engine._promotions
        pr = engine._promotions[promotion_id]
        assert pr.namespace == "corp"
        assert pr.rule_ids == (rule_a.cell_id,)  # tuple!
        assert pr.status == PromotionStatus.PENDING

    def test_submit_promotion_uses_witness_threshold(self):
        """Promotion request uses threshold from WitnessSet."""
        chain = create_test_chain_with_witnesses(["alice", "bob", "charlie"], 2)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)

        promotion_id = engine.submit_promotion(
            namespace="corp",
            rule_ids=[rule_a.cell_id],
            submitter_id="alice"
        )

        pr = engine._promotions[promotion_id]
        assert pr.required_threshold == 2

    def test_submit_promotion_invalid_namespace(self):
        """Invalid namespace raises InputInvalidError."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        engine = Engine(chain)

        with pytest.raises(InputInvalidError) as exc_info:
            engine.submit_promotion(
                namespace="INVALID!",
                rule_ids=["rule:a"],
                submitter_id="alice"
            )
        assert exc_info.value.code == "DG_INPUT_INVALID"

    def test_submit_promotion_no_witness_set(self):
        """Namespace without WitnessSet raises InputInvalidError."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        # Create a rule in a different namespace (not "corp")
        rule_a = create_rule_cell(chain, "other", "a")
        engine = Engine(chain)

        with pytest.raises(InputInvalidError) as exc_info:
            engine.submit_promotion(
                namespace="other",  # Not "corp" - no WitnessSet
                rule_ids=[rule_a.cell_id],
                submitter_id="alice"
            )
        assert "No WitnessSet" in exc_info.value.message


class TestCollectWitnessSignature:
    """Tests for Engine.collect_witness_signature() (PRO-02, PRO-05, PRO-06)"""

    def test_collect_signature_stores_signature(self):
        """Signature is stored in promotion.signatures."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "submitter")
        promotion = engine._promotions[promotion_id]
        signature = sign_bytes(priv, promotion.canonical_payload)

        engine.collect_witness_signature(
            promotion_id=promotion_id,
            witness_id="alice",
            signature=signature,
            public_key=pub
        )

        assert "alice" in promotion.signatures
        assert promotion.signatures["alice"] == signature

    def test_collect_signature_updates_status_to_collecting(self):
        """First signature transitions status to COLLECTING."""
        chain = create_test_chain_with_witnesses(["alice", "bob"], 2)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "submitter")
        promotion = engine._promotions[promotion_id]
        signature = sign_bytes(priv, promotion.canonical_payload)

        status = engine.collect_witness_signature(
            promotion_id=promotion_id,
            witness_id="alice",
            signature=signature,
            public_key=pub
        )

        assert status == PromotionStatus.COLLECTING
        assert "alice" in promotion.signatures

    def test_collect_signature_threshold_met(self):
        """Reaching threshold transitions status to THRESHOLD_MET."""
        chain = create_test_chain_with_witnesses(["alice", "bob"], 2)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        alice_priv, alice_pub = generate_ed25519_keypair()
        bob_priv, bob_pub = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "submitter")
        promotion = engine._promotions[promotion_id]

        # First signature
        sig1 = sign_bytes(alice_priv, promotion.canonical_payload)
        engine.collect_witness_signature(promotion_id, "alice", sig1, alice_pub)

        # Second signature - threshold met
        sig2 = sign_bytes(bob_priv, promotion.canonical_payload)
        status = engine.collect_witness_signature(promotion_id, "bob", sig2, bob_pub)

        assert status == PromotionStatus.THRESHOLD_MET

    def test_collect_signature_unauthorized_witness(self):
        """Witness not in WitnessSet raises UnauthorizedError (PRO-05)."""
        chain = create_test_chain_with_witnesses(["alice", "bob"], 2)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "submitter")
        promotion = engine._promotions[promotion_id]
        signature = sign_bytes(priv, promotion.canonical_payload)

        with pytest.raises(UnauthorizedError) as exc_info:
            engine.collect_witness_signature(
                promotion_id=promotion_id,
                witness_id="charlie",  # Not in WitnessSet
                signature=signature,
                public_key=pub
            )
        assert exc_info.value.code == "DG_UNAUTHORIZED"
        assert "charlie" in exc_info.value.message

    def test_collect_signature_invalid_signature(self):
        """Invalid signature raises SignatureInvalidError (PRO-06)."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()
        wrong_priv, _ = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "submitter")
        promotion = engine._promotions[promotion_id]
        # Sign with wrong key
        bad_signature = sign_bytes(wrong_priv, promotion.canonical_payload)

        with pytest.raises(SignatureInvalidError) as exc_info:
            engine.collect_witness_signature(
                promotion_id=promotion_id,
                witness_id="alice",
                signature=bad_signature,
                public_key=pub  # pub doesn't match wrong_priv
            )
        assert exc_info.value.code == "DG_SIGNATURE_INVALID"

    def test_collect_signature_promotion_not_found(self):
        """Unknown promotion_id raises InputInvalidError."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        with pytest.raises(InputInvalidError) as exc_info:
            engine.collect_witness_signature(
                promotion_id="nonexistent-id",
                witness_id="alice",
                signature=b"x" * 64,
                public_key=pub
            )
        assert "not found" in exc_info.value.message

    def test_collect_signature_duplicate_witness_overwrites(self):
        """Same witness submitting again overwrites previous signature."""
        chain = create_test_chain_with_witnesses(["alice", "bob"], 2)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv1, pub1 = generate_ed25519_keypair()
        priv2, pub2 = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "submitter")
        promotion = engine._promotions[promotion_id]

        # First submission
        sig1 = sign_bytes(priv1, promotion.canonical_payload)
        engine.collect_witness_signature(promotion_id, "alice", sig1, pub1)
        first_sig = promotion.signatures["alice"]

        # Second submission with different key (overwrites)
        sig2 = sign_bytes(priv2, promotion.canonical_payload)
        engine.collect_witness_signature(promotion_id, "alice", sig2, pub2)

        assert promotion.signatures["alice"] == sig2
        assert promotion.signatures["alice"] != first_sig
        assert len(promotion.signatures) == 1  # Still just one signature

    def test_collect_signature_single_witness_threshold_met_immediately(self):
        """Single witness reaching threshold=1 goes straight to THRESHOLD_MET."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "submitter")
        promotion = engine._promotions[promotion_id]
        signature = sign_bytes(priv, promotion.canonical_payload)

        # First and only signature - threshold=1, should go to THRESHOLD_MET
        status = engine.collect_witness_signature(
            promotion_id=promotion_id,
            witness_id="alice",
            signature=signature,
            public_key=pub
        )

        # With threshold=1, first signature meets threshold
        assert status == PromotionStatus.THRESHOLD_MET

    def test_authorization_checked_before_signature_verification(self):
        """Unauthorized witness is caught before signature is verified (PRO-05 before PRO-06)."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "submitter")

        # Use completely invalid signature data - if authorization is checked first,
        # we should get UnauthorizedError, not SignatureInvalidError
        with pytest.raises(UnauthorizedError) as exc_info:
            engine.collect_witness_signature(
                promotion_id=promotion_id,
                witness_id="unauthorized_witness",
                signature=b"garbage_signature_data",  # Would fail signature format check
                public_key=b"garbage_public_key"  # Would fail key format check
            )
        # Should be UnauthorizedError, not SignatureInvalidError
        assert exc_info.value.code == "DG_UNAUTHORIZED"


class TestFinalizePromotion:
    """Tests for Engine.finalize_promotion() (PRO-04)"""

    def test_finalize_creates_policy_head(self):
        """finalize_promotion creates PolicyHead on chain."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        rule_b = create_rule_cell(chain, "corp", "b")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        # Submit and collect
        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id, rule_b.cell_id], "alice")
        promotion = engine._promotions[promotion_id]
        sig = sign_bytes(priv, promotion.canonical_payload)
        engine.collect_witness_signature(promotion_id, "alice", sig, pub)

        # Finalize
        cell_id = engine.finalize_promotion(promotion_id)

        # Verify PolicyHead exists
        assert cell_id is not None
        policy_head = get_current_policy_head(chain, "corp")
        assert policy_head is not None
        assert policy_head.cell_id == cell_id

    def test_finalize_policy_head_has_correct_data(self):
        """PolicyHead contains correct promoted_rule_ids."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        rule_b = create_rule_cell(chain, "corp", "b")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        # Submit with rule_b first, then rule_a - they should be sorted in result
        promotion_id = engine.submit_promotion("corp", [rule_b.cell_id, rule_a.cell_id], "alice")
        promotion = engine._promotions[promotion_id]
        sig = sign_bytes(priv, promotion.canonical_payload)
        engine.collect_witness_signature(promotion_id, "alice", sig, pub)
        engine.finalize_promotion(promotion_id)

        policy_head = get_current_policy_head(chain, "corp")
        policy_data = parse_policy_data(policy_head)
        # Rule IDs should be sorted
        assert sorted(policy_data["promoted_rule_ids"]) == sorted([rule_a.cell_id, rule_b.cell_id])

    def test_finalize_updates_status_to_finalized(self):
        """Status updates to FINALIZED after finalization."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "alice")
        promotion = engine._promotions[promotion_id]
        sig = sign_bytes(priv, promotion.canonical_payload)
        engine.collect_witness_signature(promotion_id, "alice", sig, pub)
        engine.finalize_promotion(promotion_id)

        assert promotion.status == PromotionStatus.FINALIZED

    def test_finalize_requires_threshold_met(self):
        """Finalization fails if threshold not met (INT-04)."""
        chain = create_test_chain_with_witnesses(["alice", "bob"], 2)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "alice")
        promotion = engine._promotions[promotion_id]
        # Only one signature, need two
        sig = sign_bytes(priv, promotion.canonical_payload)
        engine.collect_witness_signature(promotion_id, "alice", sig, pub)

        with pytest.raises(UnauthorizedError) as exc_info:
            engine.finalize_promotion(promotion_id)
        assert "THRESHOLD_MET" in exc_info.value.message
        assert exc_info.value.code == "DG_UNAUTHORIZED"

    def test_finalize_promotion_not_found(self):
        """Unknown promotion_id raises InputInvalidError."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        engine = Engine(chain)

        with pytest.raises(InputInvalidError) as exc_info:
            engine.finalize_promotion("nonexistent-id")
        assert "not found" in exc_info.value.message


class TestEndToEndPromotionWorkflow:
    """End-to-end tests for complete promotion workflow (PRO-01 through PRO-06)"""

    def test_full_workflow_single_witness(self):
        """Complete workflow: submit -> collect -> finalize (1-of-1)."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_salary = create_rule_cell(chain, "corp", "salary_v2")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        # PRO-01: Submit
        promotion_id = engine.submit_promotion(
            namespace="corp",
            rule_ids=[rule_salary.cell_id],
            submitter_id="admin"
        )
        assert promotion_id is not None

        # PRO-02 + PRO-03: Collect (PENDING -> THRESHOLD_MET)
        promotion = engine._promotions[promotion_id]
        assert promotion.status == PromotionStatus.PENDING

        sig = sign_bytes(priv, promotion.canonical_payload)
        status = engine.collect_witness_signature(promotion_id, "alice", sig, pub)
        assert status == PromotionStatus.THRESHOLD_MET  # 1-of-1

        # PRO-04: Finalize
        cell_id = engine.finalize_promotion(promotion_id)
        assert cell_id is not None
        assert promotion.status == PromotionStatus.FINALIZED

        # Verify on chain
        policy_head = get_current_policy_head(chain, "corp")
        assert policy_head.cell_id == cell_id

    def test_full_workflow_multi_witness(self):
        """Complete workflow with 2-of-3 threshold."""
        chain = create_test_chain_with_witnesses(["alice", "bob", "charlie"], 2)
        rule_a = create_rule_cell(chain, "corp", "a")
        rule_b = create_rule_cell(chain, "corp", "b")
        engine = Engine(chain)
        alice_priv, alice_pub = generate_ed25519_keypair()
        bob_priv, bob_pub = generate_ed25519_keypair()

        # Submit
        promotion_id = engine.submit_promotion(
            namespace="corp",
            rule_ids=[rule_a.cell_id, rule_b.cell_id],
            submitter_id="admin"
        )
        promotion = engine._promotions[promotion_id]

        # First signature: PENDING -> COLLECTING
        sig1 = sign_bytes(alice_priv, promotion.canonical_payload)
        status1 = engine.collect_witness_signature(promotion_id, "alice", sig1, alice_pub)
        assert status1 == PromotionStatus.COLLECTING

        # Second signature: COLLECTING -> THRESHOLD_MET
        sig2 = sign_bytes(bob_priv, promotion.canonical_payload)
        status2 = engine.collect_witness_signature(promotion_id, "bob", sig2, bob_pub)
        assert status2 == PromotionStatus.THRESHOLD_MET

        # Finalize
        cell_id = engine.finalize_promotion(promotion_id)
        assert promotion.status == PromotionStatus.FINALIZED

        # Verify rules in PolicyHead
        policy_head = get_current_policy_head(chain, "corp")
        policy_data = parse_policy_data(policy_head)
        # Both rule IDs should be in the promoted list (sorted)
        assert sorted(policy_data["promoted_rule_ids"]) == sorted([rule_a.cell_id, rule_b.cell_id])

    def test_multiple_promotions_chain_correctly(self):
        """Multiple promotions create linked PolicyHead chain."""
        import time
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_v1 = create_rule_cell(chain, "corp", "v1")
        rule_v2 = create_rule_cell(chain, "corp", "v2")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        # First promotion
        pid1 = engine.submit_promotion("corp", [rule_v1.cell_id], "admin")
        pr1 = engine._promotions[pid1]
        sig1 = sign_bytes(priv, pr1.canonical_payload)
        engine.collect_witness_signature(pid1, "alice", sig1, pub)
        cell_id1 = engine.finalize_promotion(pid1)

        # Small delay to ensure different timestamp (get_current_policy_head uses max by time)
        time.sleep(0.002)

        # Second promotion
        pid2 = engine.submit_promotion("corp", [rule_v1.cell_id, rule_v2.cell_id], "admin")
        pr2 = engine._promotions[pid2]
        sig2 = sign_bytes(priv, pr2.canonical_payload)
        engine.collect_witness_signature(pid2, "alice", sig2, pub)
        cell_id2 = engine.finalize_promotion(pid2)

        # Verify chain linkage
        policy_head = get_current_policy_head(chain, "corp")
        assert policy_head.cell_id == cell_id2
        policy_data = parse_policy_data(policy_head)
        assert policy_data["prev_policy_head"] == cell_id1


class TestPolicyIntegrity:
    """Tests for INT-02, INT-03, and race condition detection."""

    # =========================================================================
    # INT-03: Namespace validation for rule_ids
    # =========================================================================

    def test_submit_promotion_rule_not_found(self):
        """Rule ID not in chain raises InputInvalidError (INT-03)."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        engine = Engine(chain)

        with pytest.raises(InputInvalidError) as exc_info:
            engine.submit_promotion(
                namespace="corp",
                rule_ids=["nonexistent_rule_id"],  # Not in chain
                submitter_id="alice"
            )
        assert "not found" in exc_info.value.message
        assert exc_info.value.code == "DG_INPUT_INVALID"

    def test_submit_promotion_rule_wrong_namespace(self):
        """Rule from wrong namespace raises InputInvalidError (INT-03)."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        # Create a rule in "other" namespace (not "corp")
        rule_other = create_rule_cell(chain, "other", "other_rule")
        engine = Engine(chain)

        with pytest.raises(InputInvalidError) as exc_info:
            engine.submit_promotion(
                namespace="corp",  # Target namespace
                rule_ids=[rule_other.cell_id],  # Rule from "other" namespace
                submitter_id="alice"
            )
        assert "other" in exc_info.value.message
        assert "corp" in exc_info.value.message
        assert exc_info.value.code == "DG_INPUT_INVALID"

    def test_submit_promotion_mixed_namespaces(self):
        """Some rules from correct namespace, one from wrong, raises InputInvalidError (INT-03)."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        # Create rules in different namespaces
        rule_corp = create_rule_cell(chain, "corp", "good_rule")
        rule_other = create_rule_cell(chain, "other", "bad_rule")
        engine = Engine(chain)

        with pytest.raises(InputInvalidError) as exc_info:
            engine.submit_promotion(
                namespace="corp",
                rule_ids=[rule_corp.cell_id, rule_other.cell_id],  # Mixed namespaces
                submitter_id="alice"
            )
        assert "other" in exc_info.value.message
        assert exc_info.value.code == "DG_INPUT_INVALID"

    def test_submit_promotion_all_rules_correct_namespace(self):
        """All rules from correct namespace succeeds (INT-03 happy path)."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        rule_b = create_rule_cell(chain, "corp", "b")
        engine = Engine(chain)

        # Should succeed - all rules are from "corp" namespace
        promotion_id = engine.submit_promotion(
            namespace="corp",
            rule_ids=[rule_a.cell_id, rule_b.cell_id],
            submitter_id="alice"
        )

        assert promotion_id is not None
        assert len(promotion_id) == 36

    # =========================================================================
    # Race condition detection via prev_policy_head
    # =========================================================================

    def test_concurrent_promotion_race_detected(self):
        """Concurrent promotions detected via prev_policy_head mismatch."""
        import time
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        rule_b = create_rule_cell(chain, "corp", "b")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        # Submit promotion A
        pid_a = engine.submit_promotion("corp", [rule_a.cell_id], "alice")
        pr_a = engine._promotions[pid_a]
        sig_a = sign_bytes(priv, pr_a.canonical_payload)
        engine.collect_witness_signature(pid_a, "alice", sig_a, pub)
        # Don't finalize A yet

        # Submit promotion B
        pid_b = engine.submit_promotion("corp", [rule_b.cell_id], "alice")
        pr_b = engine._promotions[pid_b]
        sig_b = sign_bytes(priv, pr_b.canonical_payload)
        engine.collect_witness_signature(pid_b, "alice", sig_b, pub)

        # Finalize B first (this changes the current policy head)
        time.sleep(0.002)
        engine.finalize_promotion(pid_b)

        # Now try to finalize A - should fail because prev_policy_head changed
        with pytest.raises(InputInvalidError) as exc_info:
            engine.finalize_promotion(pid_a)
        assert "Concurrent promotion detected" in exc_info.value.message
        assert exc_info.value.code == "DG_INPUT_INVALID"

    def test_first_promotion_no_race_false_positive(self):
        """First promotion for namespace succeeds (no false positive race detection)."""
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        # First promotion for namespace - no prev_policy_head
        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "alice")
        promotion = engine._promotions[promotion_id]
        sig = sign_bytes(priv, promotion.canonical_payload)
        engine.collect_witness_signature(promotion_id, "alice", sig, pub)

        # Should succeed - expected prev_policy_head is None, current is also None
        cell_id = engine.finalize_promotion(promotion_id)
        assert cell_id is not None

    def test_sequential_promotions_no_race(self):
        """Sequential promotions (finalize before next submit) work correctly."""
        import time
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        rule_b = create_rule_cell(chain, "corp", "b")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        # First promotion - submit, collect, finalize
        pid1 = engine.submit_promotion("corp", [rule_a.cell_id], "admin")
        pr1 = engine._promotions[pid1]
        sig1 = sign_bytes(priv, pr1.canonical_payload)
        engine.collect_witness_signature(pid1, "alice", sig1, pub)
        cell_id1 = engine.finalize_promotion(pid1)
        assert cell_id1 is not None

        time.sleep(0.002)

        # Second promotion - submitted AFTER first finalized
        pid2 = engine.submit_promotion("corp", [rule_a.cell_id, rule_b.cell_id], "admin")
        pr2 = engine._promotions[pid2]
        sig2 = sign_bytes(priv, pr2.canonical_payload)
        engine.collect_witness_signature(pid2, "alice", sig2, pub)
        # Should succeed - expected prev_policy_head matches current
        cell_id2 = engine.finalize_promotion(pid2)
        assert cell_id2 is not None

        # Verify chain linkage
        policy_head = get_current_policy_head(chain, "corp")
        policy_data = parse_policy_data(policy_head)
        assert policy_data["prev_policy_head"] == cell_id1

    def test_race_detected_when_no_prev_becomes_some(self):
        """Race detected when expected no prev_policy_head but one now exists."""
        import time
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        rule_b = create_rule_cell(chain, "corp", "b")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        # Submit both promotions while no PolicyHead exists
        pid_a = engine.submit_promotion("corp", [rule_a.cell_id], "alice")
        pr_a = engine._promotions[pid_a]
        sig_a = sign_bytes(priv, pr_a.canonical_payload)
        engine.collect_witness_signature(pid_a, "alice", sig_a, pub)

        pid_b = engine.submit_promotion("corp", [rule_b.cell_id], "alice")
        pr_b = engine._promotions[pid_b]
        sig_b = sign_bytes(priv, pr_b.canonical_payload)
        engine.collect_witness_signature(pid_b, "alice", sig_b, pub)

        # Both expect no prev_policy_head
        assert engine._expected_prev_policy_head[pid_a] is None
        assert engine._expected_prev_policy_head[pid_b] is None

        # Finalize A first
        time.sleep(0.002)
        engine.finalize_promotion(pid_a)

        # Now try to finalize B - should fail
        with pytest.raises(InputInvalidError) as exc_info:
            engine.finalize_promotion(pid_b)
        assert "Concurrent promotion detected" in exc_info.value.message
        assert "Expected no previous policy" in exc_info.value.message

    # =========================================================================
    # INT-02: policy_hash verification (implicitly tested)
    # =========================================================================

    def test_finalize_verifies_policy_hash_implicit(self):
        """policy_hash verification is called at finalization (implicit test).

        Note: Testing hash verification failure would require tampering with
        internals after create_policy_head() but before append(), which is
        not possible without mocking. The existence of verify_policy_hash()
        call is verified by code inspection.

        This test verifies that valid promotions pass hash verification.
        """
        chain = create_test_chain_with_witnesses(["alice"], 1)
        rule_a = create_rule_cell(chain, "corp", "a")
        engine = Engine(chain)
        priv, pub = generate_ed25519_keypair()

        promotion_id = engine.submit_promotion("corp", [rule_a.cell_id], "alice")
        promotion = engine._promotions[promotion_id]
        sig = sign_bytes(priv, promotion.canonical_payload)
        engine.collect_witness_signature(promotion_id, "alice", sig, pub)

        # Finalize - includes policy_hash verification
        cell_id = engine.finalize_promotion(promotion_id)
        assert cell_id is not None

        # Verify the PolicyHead was created with valid hash
        from decisiongraph.policyhead import verify_policy_hash
        policy_head = get_current_policy_head(chain, "corp")
        assert verify_policy_hash(policy_head) is True

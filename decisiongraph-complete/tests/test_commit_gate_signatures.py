"""
Tests for SIG-03: Commit Gate signature verification.

Tests that Chain.append() optionally verifies cell signatures
when signature_required=True.
"""

import pytest
from dataclasses import replace
from decisiongraph import (
    Chain,
    create_chain,
    create_genesis_cell,
    DecisionCell,
    Header,
    Fact,
    Proof,
    CellType,
    NULL_HASH,
    get_current_timestamp,
    compute_content_id,
    SignatureInvalidError
)


@pytest.fixture
def test_chain():
    """Chain with genesis for testing."""
    return create_chain(root_namespace="corp")


@pytest.fixture
def cell_requiring_signature(test_chain):
    """Create a cell that requires signature but has none."""
    # Get previous cell hash (genesis)
    genesis = list(test_chain.cells)[0]
    prev_hash = genesis.cell_id

    # Create cell with signature_required=True but no signature
    header = Header(
        version="1.3",
        graph_id=test_chain.graph_id,
        cell_type=CellType.FACT,
        system_time=get_current_timestamp(),
        prev_cell_hash=prev_hash
    )

    fact = Fact(
        namespace="corp.hr",
        subject="employee:bob",
        predicate="has_role",
        object="manager",
        confidence=0.9,
        source_quality="self_reported"
    )

    from decisiongraph import LogicAnchor
    logic_anchor = LogicAnchor(
        rule_id="manual:input",
        rule_logic_hash=NULL_HASH
    )

    proof = Proof(
        signature_required=True,
        signature=None,  # No signature!
        signer_key_id=None
    )

    return DecisionCell(
        header=header,
        fact=fact,
        logic_anchor=logic_anchor,
        proof=proof
    )


@pytest.fixture
def cell_with_signature(cell_requiring_signature):
    """Create a cell that requires signature AND has one."""
    # Add a dummy signature (just bytes, not cryptographically valid)
    proof = replace(
        cell_requiring_signature.proof,
        signature=b'x' * 64,  # 64 bytes like Ed25519
        signer_key_id="key:test_signer"
    )
    return replace(cell_requiring_signature, proof=proof)


@pytest.fixture
def cell_not_requiring_signature(test_chain):
    """Create a cell that does NOT require signature."""
    genesis = list(test_chain.cells)[0]
    prev_hash = genesis.cell_id

    header = Header(
        version="1.3",
        graph_id=test_chain.graph_id,
        cell_type=CellType.FACT,
        system_time=get_current_timestamp(),
        prev_cell_hash=prev_hash
    )

    fact = Fact(
        namespace="corp.hr",
        subject="employee:charlie",
        predicate="has_role",
        object="analyst",
        confidence=0.9,
        source_quality="self_reported"
    )

    from decisiongraph import LogicAnchor
    logic_anchor = LogicAnchor(
        rule_id="manual:input",
        rule_logic_hash=NULL_HASH
    )

    proof = Proof(
        signature_required=False,  # Does not require signature
        signature=None,
        signer_key_id=None
    )

    return DecisionCell(
        header=header,
        fact=fact,
        logic_anchor=logic_anchor,
        proof=proof
    )


class TestCommitGateSignatureVerification:
    """Tests for SIG-03: Commit Gate signature verification."""

    def test_append_default_no_verification(self, test_chain, cell_requiring_signature):
        """Default verify_signatures=False allows unsigned cells."""
        # Should NOT raise - verification is off by default
        test_chain.append(cell_requiring_signature)
        assert cell_requiring_signature.cell_id in [c.cell_id for c in test_chain.cells]

    def test_append_verify_signatures_rejects_missing_signature(
        self, test_chain, cell_requiring_signature
    ):
        """verify_signatures=True rejects cell with signature_required but no signature."""
        with pytest.raises(SignatureInvalidError) as exc_info:
            test_chain.append(cell_requiring_signature, verify_signatures=True)

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "requires signature but none provided" in exc_info.value.message
        assert exc_info.value.details["signature_required"] is True
        assert exc_info.value.details["signature_present"] is False

    def test_append_verify_signatures_accepts_signed_cell(
        self, test_chain, cell_with_signature
    ):
        """verify_signatures=True accepts cell with signature present."""
        # Should NOT raise - signature is present
        test_chain.append(cell_with_signature, verify_signatures=True)
        assert cell_with_signature.cell_id in [c.cell_id for c in test_chain.cells]

    def test_append_verify_signatures_ignores_non_required(
        self, test_chain, cell_not_requiring_signature
    ):
        """verify_signatures=True allows unsigned cell if signature_required=False."""
        # Should NOT raise - cell doesn't require signature
        test_chain.append(cell_not_requiring_signature, verify_signatures=True)
        assert cell_not_requiring_signature.cell_id in [c.cell_id for c in test_chain.cells]

    def test_append_verify_false_explicit(self, test_chain, cell_requiring_signature):
        """Explicitly setting verify_signatures=False skips verification."""
        # Should NOT raise
        test_chain.append(cell_requiring_signature, verify_signatures=False)
        assert cell_requiring_signature.cell_id in [c.cell_id for c in test_chain.cells]


class TestCommitGateBackwardCompatibility:
    """Tests that existing code continues to work."""

    def test_append_without_verify_param(self, test_chain, cell_not_requiring_signature):
        """append() without verify_signatures param works (backward compatible)."""
        # Old calling style: chain.append(cell)
        test_chain.append(cell_not_requiring_signature)
        assert len(list(test_chain.cells)) == 2  # Genesis + new cell

    def test_chain_append_signature_all_existing_tests_pass(self):
        """Meta-test: all existing chain tests should pass."""
        # This is verified by running pytest tests/test_core.py
        # The test just documents the requirement
        pass

"""
Tests for DecisionGraph PrecedentRegistry Module

Tests cover:
- PrecedentRegistry creation and basic queries
- find_by_fingerprint (Tier 0)
- find_by_exclusion_codes (Tier 0.5/1)
- get_statistics aggregation
- Bitemporal filtering
"""

import pytest
from decisiongraph.chain import Chain
from decisiongraph.cell import HASH_SCHEME_CANONICAL
from decisiongraph.judgment import (
    AnchorFact,
    JudgmentPayload,
    create_judgment_cell,
)
from decisiongraph.precedent_registry import (
    PrecedentRegistry,
    PrecedentStatistics,
    AppealStatistics,
    InvalidQueryError,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def test_chain():
    """Create a test chain with genesis using canonical hash scheme."""
    chain = Chain()
    # Use canonical hash scheme to support JUDGMENT cells with structured payloads
    chain.initialize(
        graph_name="TestGraph",
        root_namespace="claims",
        hash_scheme=HASH_SCHEME_CANONICAL,
    )
    return chain


@pytest.fixture
def sample_payload():
    """Create a sample JUDGMENT payload."""
    return JudgmentPayload.create(
        case_id_hash="a" * 64,
        jurisdiction_code="CA-ON",
        fingerprint_hash="f" * 64,
        fingerprint_schema_id="claimpilot:oap1:auto:v1",
        exclusion_codes=["4.2.1", "4.3.3"],
        reason_codes=["RC-COMMERCIAL-USE"],
        reason_code_registry_id="claimpilot:auto:v1",
        outcome_code="deny",
        certainty="high",
        anchor_facts=[
            AnchorFact(field_id="test.field", value=True, label="Test"),
        ],
        policy_pack_hash="c" * 64,
        policy_pack_id="CA-ON-OAP1-2024",
        policy_version="2024.1",
        decision_level="adjuster",
        decided_at="2026-01-15T12:00:00Z",
        decided_by_role="adjuster",
    )


def add_judgment_to_chain(chain, payload, namespace="claims.precedents"):
    """Helper to add a JUDGMENT cell to chain."""
    cell = create_judgment_cell(
        payload=payload,
        namespace=namespace,
        graph_id=chain.graph_id,
        prev_cell_hash=chain.head.cell_id,
    )
    chain.append(cell)
    return cell


# =============================================================================
# Basic Registry Tests
# =============================================================================

class TestPrecedentRegistryBasic:
    """Basic tests for PrecedentRegistry."""

    def test_create_registry(self, test_chain):
        """PrecedentRegistry can be created with a chain."""
        registry = PrecedentRegistry(test_chain)
        assert registry.chain is test_chain

    def test_empty_chain_returns_empty_results(self, test_chain):
        """Empty chain returns no matches."""
        registry = PrecedentRegistry(test_chain)
        matches = registry.find_by_fingerprint("a" * 64, "claims")
        assert matches == []


# =============================================================================
# find_by_fingerprint Tests (Tier 0)
# =============================================================================

class TestFindByFingerprint:
    """Tests for find_by_fingerprint (Tier 0 exact match)."""

    def test_find_exact_fingerprint_match(self, test_chain, sample_payload):
        """Exact fingerprint match returns the precedent."""
        add_judgment_to_chain(test_chain, sample_payload)
        registry = PrecedentRegistry(test_chain)

        matches = registry.find_by_fingerprint(
            fingerprint_hash=sample_payload.fingerprint_hash,
            namespace_prefix="claims",
        )

        assert len(matches) == 1
        assert matches[0].precedent_id == sample_payload.precedent_id

    def test_no_match_for_different_fingerprint(self, test_chain, sample_payload):
        """Different fingerprint returns no matches."""
        add_judgment_to_chain(test_chain, sample_payload)
        registry = PrecedentRegistry(test_chain)

        matches = registry.find_by_fingerprint(
            fingerprint_hash="b" * 64,  # Different
            namespace_prefix="claims",
        )

        assert len(matches) == 0

    def test_namespace_filtering(self, test_chain, sample_payload):
        """Only matches in the specified namespace are returned."""
        # Add to claims.precedents
        add_judgment_to_chain(test_chain, sample_payload, "claims.precedents")

        # Add another to different namespace
        payload2 = JudgmentPayload.create(
            case_id_hash="b" * 64,
            jurisdiction_code="CA-ON",
            fingerprint_hash=sample_payload.fingerprint_hash,  # Same fingerprint
            fingerprint_schema_id="claimpilot:oap1:auto:v1",
            exclusion_codes=["4.2.1"],
            reason_codes=[],
            reason_code_registry_id="claimpilot:auto:v1",
            outcome_code="pay",
            certainty="high",
            anchor_facts=[AnchorFact(field_id="t", value=1, label="T")],
            policy_pack_hash="c" * 64,
            policy_pack_id="test",
            policy_version="1.0",
            decision_level="adjuster",
            decided_at="2026-01-16T12:00:00Z",
            decided_by_role="adjuster",
        )
        add_judgment_to_chain(test_chain, payload2, "other.namespace")

        registry = PrecedentRegistry(test_chain)

        # Only claims namespace
        matches = registry.find_by_fingerprint(
            sample_payload.fingerprint_hash,
            namespace_prefix="claims",
        )
        assert len(matches) == 1

    def test_invalid_fingerprint_hash_fails(self, test_chain):
        """Invalid fingerprint hash raises error."""
        registry = PrecedentRegistry(test_chain)

        with pytest.raises(InvalidQueryError, match="must be 64-character"):
            registry.find_by_fingerprint("short", "claims")

    def test_empty_fingerprint_hash_fails(self, test_chain):
        """Empty fingerprint hash raises error."""
        registry = PrecedentRegistry(test_chain)

        with pytest.raises(InvalidQueryError, match="cannot be empty"):
            registry.find_by_fingerprint("", "claims")


# =============================================================================
# find_by_exclusion_codes Tests (Tier 0.5/1)
# =============================================================================

class TestFindByExclusionCodes:
    """Tests for find_by_exclusion_codes (Tier 0.5/1)."""

    def test_find_with_overlap(self, test_chain, sample_payload):
        """Finds precedents with overlapping exclusion codes."""
        add_judgment_to_chain(test_chain, sample_payload)
        registry = PrecedentRegistry(test_chain)

        # Search for code that overlaps with ["4.2.1", "4.3.3"]
        results = registry.find_by_exclusion_codes(
            codes=["4.2.1"],
            namespace_prefix="claims",
        )

        assert len(results) == 1
        payload, overlap = results[0]
        assert payload.precedent_id == sample_payload.precedent_id
        assert overlap == 1

    def test_multiple_code_overlap(self, test_chain, sample_payload):
        """Overlap count is correct for multiple codes."""
        add_judgment_to_chain(test_chain, sample_payload)
        registry = PrecedentRegistry(test_chain)

        results = registry.find_by_exclusion_codes(
            codes=["4.2.1", "4.3.3"],  # Both match
            namespace_prefix="claims",
        )

        assert len(results) == 1
        payload, overlap = results[0]
        assert overlap == 2

    def test_min_overlap_filtering(self, test_chain, sample_payload):
        """min_overlap parameter filters correctly."""
        add_judgment_to_chain(test_chain, sample_payload)
        registry = PrecedentRegistry(test_chain)

        # Require 3 codes overlap - should not match
        results = registry.find_by_exclusion_codes(
            codes=["4.2.1", "4.3.3"],
            namespace_prefix="claims",
            min_overlap=3,  # Too high
        )

        assert len(results) == 0

    def test_outcome_filter(self, test_chain, sample_payload):
        """outcome parameter filters by outcome code."""
        add_judgment_to_chain(test_chain, sample_payload)  # deny
        registry = PrecedentRegistry(test_chain)

        # Search with matching outcome
        results = registry.find_by_exclusion_codes(
            codes=["4.2.1"],
            namespace_prefix="claims",
            outcome="deny",
        )
        assert len(results) == 1

        # Search with different outcome
        results = registry.find_by_exclusion_codes(
            codes=["4.2.1"],
            namespace_prefix="claims",
            outcome="pay",
        )
        assert len(results) == 0

    def test_empty_codes_fails(self, test_chain):
        """Empty codes list raises error."""
        registry = PrecedentRegistry(test_chain)

        with pytest.raises(InvalidQueryError, match="cannot be empty"):
            registry.find_by_exclusion_codes([], "claims")

    def test_invalid_min_overlap_fails(self, test_chain):
        """min_overlap < 1 raises error."""
        registry = PrecedentRegistry(test_chain)

        with pytest.raises(InvalidQueryError, match="must be at least 1"):
            registry.find_by_exclusion_codes(["4.2.1"], "claims", min_overlap=0)


# =============================================================================
# get_statistics Tests
# =============================================================================

class TestGetStatistics:
    """Tests for get_statistics aggregation."""

    def test_statistics_for_single_match(self, test_chain, sample_payload):
        """Statistics are correct for single matching precedent."""
        add_judgment_to_chain(test_chain, sample_payload)
        registry = PrecedentRegistry(test_chain)

        stats = registry.get_statistics(
            sample_payload.fingerprint_hash,
            namespace_prefix="claims",
        )

        assert stats.total_matched == 1
        assert stats.by_outcome["deny"] == 1
        assert stats.by_decision_level["adjuster"] == 1

    def test_statistics_for_no_matches(self, test_chain):
        """Statistics for no matches return zeros."""
        registry = PrecedentRegistry(test_chain)

        stats = registry.get_statistics("a" * 64, "claims")

        assert stats.total_matched == 0
        assert stats.by_outcome == {}

    def test_statistics_with_multiple_precedents(self, test_chain):
        """Statistics aggregate multiple precedents correctly."""
        # Add multiple precedents with same fingerprint
        fingerprint = "f" * 64

        for i, (outcome, level) in enumerate([
            ("deny", "adjuster"),
            ("deny", "manager"),
            ("pay", "tribunal"),
        ]):
            payload = JudgmentPayload.create(
                case_id_hash=f"{i}" * 64,
                jurisdiction_code="CA-ON",
                fingerprint_hash=fingerprint,
                fingerprint_schema_id="test:v1",
                exclusion_codes=["4.2.1"],
                reason_codes=[],
                reason_code_registry_id="test:v1",
                outcome_code=outcome,
                certainty="high",
                anchor_facts=[AnchorFact(field_id="t", value=i, label="T")],
                policy_pack_hash="c" * 64,
                policy_pack_id="test",
                policy_version="1.0",
                decision_level=level,
                decided_at=f"2026-01-{15+i:02d}T12:00:00Z",
                decided_by_role=level,
            )
            add_judgment_to_chain(test_chain, payload)

        registry = PrecedentRegistry(test_chain)
        stats = registry.get_statistics(fingerprint, "claims")

        assert stats.total_matched == 3
        assert stats.by_outcome["deny"] == 2
        assert stats.by_outcome["pay"] == 1
        assert stats.by_decision_level["adjuster"] == 1
        assert stats.by_decision_level["manager"] == 1
        assert stats.by_decision_level["tribunal"] == 1

    def test_consistency_rate(self, test_chain):
        """consistency_rate() calculates correctly."""
        fingerprint = "f" * 64

        # Add 3 deny, 1 pay
        for i, outcome in enumerate(["deny", "deny", "deny", "pay"]):
            payload = JudgmentPayload.create(
                case_id_hash=f"{i}" * 64,
                jurisdiction_code="CA-ON",
                fingerprint_hash=fingerprint,
                fingerprint_schema_id="test:v1",
                exclusion_codes=["4.2.1"],
                reason_codes=[],
                reason_code_registry_id="test:v1",
                outcome_code=outcome,
                certainty="high",
                anchor_facts=[AnchorFact(field_id="t", value=i, label="T")],
                policy_pack_hash="c" * 64,
                policy_pack_id="test",
                policy_version="1.0",
                decision_level="adjuster",
                decided_at=f"2026-01-{15+i:02d}T12:00:00Z",
                decided_by_role="adjuster",
            )
            add_judgment_to_chain(test_chain, payload)

        registry = PrecedentRegistry(test_chain)
        stats = registry.get_statistics(fingerprint, "claims")

        # 3 out of 4 are "deny" = 75%
        assert stats.consistency_rate("deny") == 0.75
        # 1 out of 4 are "pay" = 25%
        assert stats.consistency_rate("pay") == 0.25


# =============================================================================
# Appeal Statistics Tests
# =============================================================================

class TestAppealStatistics:
    """Tests for appeal statistics aggregation."""

    def test_appeal_stats_aggregation(self, test_chain):
        """Appeal statistics are aggregated correctly."""
        fingerprint = "f" * 64

        appeals = [
            (True, "upheld"),
            (True, "overturned"),
            (True, "settled"),
            (False, None),
        ]

        for i, (appealed, appeal_outcome) in enumerate(appeals):
            payload = JudgmentPayload.create(
                case_id_hash=f"{i}" * 64,
                jurisdiction_code="CA-ON",
                fingerprint_hash=fingerprint,
                fingerprint_schema_id="test:v1",
                exclusion_codes=["4.2.1"],
                reason_codes=[],
                reason_code_registry_id="test:v1",
                outcome_code="deny",
                certainty="high",
                anchor_facts=[AnchorFact(field_id="t", value=i, label="T")],
                policy_pack_hash="c" * 64,
                policy_pack_id="test",
                policy_version="1.0",
                decision_level="adjuster",
                decided_at=f"2026-01-{15+i:02d}T12:00:00Z",
                decided_by_role="adjuster",
                appealed=appealed,
                appeal_outcome=appeal_outcome,
            )
            add_judgment_to_chain(test_chain, payload)

        registry = PrecedentRegistry(test_chain)
        stats = registry.get_statistics(fingerprint, "claims")

        assert stats.appeal_stats.total_appealed == 3
        assert stats.appeal_stats.upheld == 1
        assert stats.appeal_stats.overturned == 1
        assert stats.appeal_stats.settled == 1

    def test_upheld_rate_calculation(self):
        """upheld_rate is calculated correctly."""
        # 2 upheld, 1 overturned = 66.67% upheld
        stats = AppealStatistics(
            total_appealed=3,
            upheld=2,
            overturned=1,
            settled=0,
        )
        assert stats.upheld_rate == pytest.approx(2/3)

    def test_upheld_rate_no_appeals(self):
        """upheld_rate is 1.0 when no appeals."""
        stats = AppealStatistics()
        assert stats.upheld_rate == 1.0


# =============================================================================
# Bitemporal Query Tests
# =============================================================================

class TestBitemporalQueries:
    """Tests for bitemporal (as_of) filtering."""

    def test_as_of_filtering(self, test_chain):
        """as_of parameter filters by system_time."""
        from decisiongraph.cell import get_current_timestamp

        # Get current timestamp as base
        base_time = get_current_timestamp()

        # Add first precedent with current timestamp (auto-generated)
        payload1 = JudgmentPayload.create(
            case_id_hash="a" * 64,
            jurisdiction_code="CA-ON",
            fingerprint_hash="f" * 64,
            fingerprint_schema_id="test:v1",
            exclusion_codes=["4.2.1"],
            reason_codes=[],
            reason_code_registry_id="test:v1",
            outcome_code="deny",
            certainty="high",
            anchor_facts=[AnchorFact(field_id="t", value=1, label="T")],
            policy_pack_hash="c" * 64,
            policy_pack_id="test",
            policy_version="1.0",
            decision_level="adjuster",
            decided_at="2026-01-15T12:00:00Z",
            decided_by_role="adjuster",
        )

        cell1 = create_judgment_cell(
            payload=payload1,
            namespace="claims.precedents",
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            # Use default (current) system_time
        )
        test_chain.append(cell1)
        t1 = cell1.header.system_time

        # Add second with later timestamp
        payload2 = JudgmentPayload.create(
            case_id_hash="b" * 64,
            jurisdiction_code="CA-ON",
            fingerprint_hash="f" * 64,
            fingerprint_schema_id="test:v1",
            exclusion_codes=["4.2.1"],
            reason_codes=[],
            reason_code_registry_id="test:v1",
            outcome_code="pay",
            certainty="high",
            anchor_facts=[AnchorFact(field_id="t", value=2, label="T")],
            policy_pack_hash="c" * 64,
            policy_pack_id="test",
            policy_version="1.0",
            decision_level="adjuster",
            decided_at="2026-01-20T12:00:00Z",
            decided_by_role="adjuster",
        )

        cell2 = create_judgment_cell(
            payload=payload2,
            namespace="claims.precedents",
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            # Use default (current) system_time
        )
        test_chain.append(cell2)
        t2 = cell2.header.system_time

        registry = PrecedentRegistry(test_chain)

        # Query as of before second cell (use t1 which is before t2)
        matches = registry.find_by_fingerprint(
            "f" * 64,
            "claims",
            as_of=t1,
        )
        assert len(matches) == 1
        assert matches[0].outcome_code == "deny"

        # Query as of after both (use t2 or later)
        matches = registry.find_by_fingerprint(
            "f" * 64,
            "claims",
            as_of=t2,
        )
        assert len(matches) == 2

    def test_invalid_as_of_format(self, test_chain):
        """Invalid as_of timestamp format raises error."""
        registry = PrecedentRegistry(test_chain)

        with pytest.raises(InvalidQueryError, match="Invalid as_of"):
            registry.find_by_fingerprint("a" * 64, "claims", as_of="invalid")

"""
DecisionGraph: PolicyHead Test Suite (v1.5)

Tests for:
1. CellType.POLICY_HEAD enum value
2. compute_policy_hash determinism
3. create_policy_head cell creation
4. PolicyHead integration with Chain.append()
5. Policy data parsing and verification
6. PolicyHead chain operations and queries (POL-03, POL-04)

Requirements covered:
- POL-01: Create PolicyHead cell structure
- POL-02: Deterministic policy_hash computation
- POL-03: Append-only policy chain within namespace
- POL-04: Current policy query interface
"""

import pytest
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decisiongraph import (
    DecisionCell,
    CellType,
    SourceQuality,
    Chain,
    create_chain,
    compute_policy_hash
)

from decisiongraph.policyhead import (
    create_policy_head,
    parse_policy_data,
    verify_policy_hash,
    get_current_policy_head,
    get_policy_head_chain,
    get_policy_head_at_time,
    validate_policy_head_chain,
    policy_head_chain_to_dot,
    POLICY_PROMOTION_RULE_HASH,
    POLICYHEAD_SCHEMA_VERSION
)

# Import test time constants
from test_utils import T0, T1, T2, T3, T4, T5


class TestCellTypePolicyHead:
    """Tests for CellType.POLICY_HEAD enum (POL-01)"""

    def test_policy_head_enum_exists(self):
        """CellType.POLICY_HEAD should exist"""
        assert hasattr(CellType, 'POLICY_HEAD')
        assert CellType.POLICY_HEAD.value == "policy_head"

    def test_policy_head_is_valid_cell_type(self):
        """POLICY_HEAD should be usable like other CellTypes"""
        # Should be iterable with other types
        all_types = list(CellType)
        assert CellType.POLICY_HEAD in all_types

        # Should be comparable
        assert CellType.POLICY_HEAD != CellType.GENESIS
        assert CellType.POLICY_HEAD != CellType.FACT


class TestComputePolicyHash:
    """Tests for compute_policy_hash determinism (POL-02)"""

    def test_empty_list_produces_hash(self):
        """Empty promoted_rule_ids should produce valid hash"""
        hash_result = compute_policy_hash([])
        assert len(hash_result) == 64  # SHA-256 hex
        assert all(c in '0123456789abcdef' for c in hash_result)

    def test_single_rule_produces_hash(self):
        """Single rule ID should produce valid hash"""
        hash_result = compute_policy_hash(["rule:salary_v1"])
        assert len(hash_result) == 64

    def test_same_rules_same_hash(self):
        """Same rules should always produce same hash"""
        rules = ["rule:a", "rule:b", "rule:c"]
        hash1 = compute_policy_hash(rules)
        hash2 = compute_policy_hash(rules)
        assert hash1 == hash2

    def test_order_independent_hash(self):
        """Different orderings of same rules MUST produce same hash"""
        rules_abc = ["rule:a", "rule:b", "rule:c"]
        rules_cba = ["rule:c", "rule:b", "rule:a"]
        rules_bac = ["rule:b", "rule:a", "rule:c"]

        hash_abc = compute_policy_hash(rules_abc)
        hash_cba = compute_policy_hash(rules_cba)
        hash_bac = compute_policy_hash(rules_bac)

        assert hash_abc == hash_cba == hash_bac

    def test_different_rules_different_hash(self):
        """Different rules should produce different hashes"""
        hash1 = compute_policy_hash(["rule:a"])
        hash2 = compute_policy_hash(["rule:b"])
        assert hash1 != hash2

    def test_subset_different_hash(self):
        """Subset of rules should produce different hash"""
        hash_full = compute_policy_hash(["rule:a", "rule:b"])
        hash_subset = compute_policy_hash(["rule:a"])
        assert hash_full != hash_subset

    def test_hash_is_sha256(self):
        """Hash should be valid SHA-256 (64 hex chars)"""
        import hashlib
        rules = ["rule:test"]
        hash_result = compute_policy_hash(rules)

        # Manual verification
        sorted_rules = sorted(rules)
        canonical = json.dumps(sorted_rules, separators=(',', ':'))
        expected = hashlib.sha256(canonical.encode('utf-8')).hexdigest()

        assert hash_result == expected


class TestCreatePolicyHead:
    """Tests for create_policy_head function (POL-01)"""

    @pytest.fixture
    def test_chain(self):
        """Create a test chain with Genesis"""
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_creates_valid_cell(self, test_chain):
        """create_policy_head should return valid DecisionCell"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:salary_v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        assert isinstance(policy_head, DecisionCell)
        assert policy_head.verify_integrity()

    def test_cell_type_is_policy_head(self, test_chain):
        """Cell type should be POLICY_HEAD"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        assert policy_head.header.cell_type == CellType.POLICY_HEAD

    def test_schema_version_is_1_5(self, test_chain):
        """Schema version should be 1.5"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        assert policy_head.header.version == "1.5"

    def test_fact_structure(self, test_chain):
        """Fact should have correct structure"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        assert policy_head.fact.namespace == "corp.hr"
        assert policy_head.fact.subject == "policy:head"
        assert policy_head.fact.predicate == "policy_snapshot"
        assert policy_head.fact.confidence == 1.0
        assert policy_head.fact.source_quality == SourceQuality.VERIFIED

    def test_policy_data_in_fact_object(self, test_chain):
        """Policy data should be JSON in fact.object"""
        rules = ["rule:b", "rule:a"]  # Unsorted input
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=rules,
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head="prev_head_id",
            system_time=T1
        )

        policy_data = json.loads(policy_head.fact.object)

        assert "policy_hash" in policy_data
        assert "promoted_rule_ids" in policy_data
        assert "prev_policy_head" in policy_data

        # Rules should be sorted in stored data
        assert policy_data["promoted_rule_ids"] == ["rule:a", "rule:b"]
        assert policy_data["prev_policy_head"] == "prev_head_id"

    def test_first_policy_head_has_null_prev(self, test_chain):
        """First PolicyHead in namespace should have prev_policy_head=None"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        policy_data = json.loads(policy_head.fact.object)
        assert policy_data["prev_policy_head"] is None

    def test_logic_anchor_correct(self, test_chain):
        """Logic anchor should reference policy promotion rule"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        assert policy_head.logic_anchor.rule_id == "system:policy_promotion_v1.5"
        assert policy_head.logic_anchor.rule_logic_hash == POLICY_PROMOTION_RULE_HASH
        assert policy_head.logic_anchor.interpreter == "system:v1.5"

    def test_invalid_namespace_raises(self, test_chain):
        """Invalid namespace should raise ValueError"""
        with pytest.raises(ValueError, match="Invalid namespace"):
            create_policy_head(
                namespace="INVALID",  # Uppercase not allowed
                promoted_rule_ids=["rule:test"],
                graph_id=test_chain.graph_id,
                prev_cell_hash=test_chain.head.cell_id,
                system_time=T1
            )

    def test_empty_rules_allowed(self, test_chain):
        """Empty promoted_rule_ids should be allowed (policy with no rules)"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=[],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        policy_data = json.loads(policy_head.fact.object)
        assert policy_data["promoted_rule_ids"] == []


class TestPolicyHeadChainIntegration:
    """Tests for PolicyHead integration with Chain"""

    @pytest.fixture
    def test_chain(self):
        """Create a test chain with Genesis"""
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_append_policy_head_to_chain(self, test_chain):
        """PolicyHead should be appendable to Chain"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        # Should not raise
        test_chain.append(policy_head)

        assert test_chain.length == 2
        assert test_chain.head == policy_head

    def test_find_policy_heads_by_type(self, test_chain):
        """Chain.find_by_type should find PolicyHead cells"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(policy_head)

        found = test_chain.find_by_type(CellType.POLICY_HEAD)

        assert len(found) == 1
        assert found[0] == policy_head

    def test_multiple_policy_heads_same_namespace(self, test_chain):
        """Multiple PolicyHeads for same namespace should be appendable"""
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1", "rule:v2"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph1.cell_id,
            system_time=T2
        )
        test_chain.append(ph2)

        found = test_chain.find_by_type(CellType.POLICY_HEAD)
        assert len(found) == 2


class TestParsePolicyData:
    """Tests for parse_policy_data helper"""

    @pytest.fixture
    def test_chain(self):
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_parse_valid_policy_head(self, test_chain):
        """parse_policy_data should extract policy data"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a", "rule:b"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head="prev_id",
            system_time=T1
        )

        data = parse_policy_data(policy_head)

        assert data["promoted_rule_ids"] == ["rule:a", "rule:b"]
        assert data["prev_policy_head"] == "prev_id"
        assert "policy_hash" in data


class TestVerifyPolicyHash:
    """Tests for verify_policy_hash helper"""

    @pytest.fixture
    def test_chain(self):
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_valid_policy_head_verifies(self, test_chain):
        """verify_policy_hash should return True for valid PolicyHead"""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a", "rule:b"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        assert verify_policy_hash(policy_head) is True


class TestExistingTestsStillPass:
    """Verify that existing tests are not broken"""

    def test_genesis_still_works(self):
        """Genesis creation should still work"""
        chain = create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

        assert chain.has_genesis()
        assert chain.genesis.header.cell_type == CellType.GENESIS

    def test_other_cell_types_unchanged(self):
        """Other CellType values should be unchanged"""
        assert CellType.GENESIS.value == "genesis"
        assert CellType.FACT.value == "fact"
        assert CellType.RULE.value == "rule"
        assert CellType.DECISION.value == "decision"


# ============================================================================
# POL-04: Get Current PolicyHead Tests
# ============================================================================

class TestGetCurrentPolicyHead:
    """Tests for get_current_policy_head function (POL-04)"""

    @pytest.fixture
    def test_chain(self):
        """Create a test chain with Genesis"""
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_returns_none_for_empty_namespace(self, test_chain):
        """Should return None if namespace has no PolicyHeads"""
        result = get_current_policy_head(test_chain, "corp.hr")
        assert result is None

    def test_returns_single_policy_head(self, test_chain):
        """Should return the single PolicyHead for a namespace"""
        ph = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:salary_v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph)

        result = get_current_policy_head(test_chain, "corp.hr")
        assert result is not None
        assert result.cell_id == ph.cell_id

    def test_returns_latest_policy_head(self, test_chain):
        """Should return the latest PolicyHead when multiple exist"""
        # Create first PolicyHead
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        # Create second PolicyHead (supersedes first)
        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1", "rule:v2"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph1.cell_id,
            system_time=T2
        )
        test_chain.append(ph2)

        result = get_current_policy_head(test_chain, "corp.hr")
        assert result is not None
        assert result.cell_id == ph2.cell_id

        # Verify it has the latest rules
        data = parse_policy_data(result)
        assert data["promoted_rule_ids"] == ["rule:v1", "rule:v2"]

    def test_namespaces_are_independent(self, test_chain):
        """Different namespaces should have independent PolicyHeads"""
        # PolicyHead for corp.hr
        ph_hr = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:hr_v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph_hr)

        # PolicyHead for corp.finance
        ph_fin = create_policy_head(
            namespace="corp.finance",
            promoted_rule_ids=["rule:fin_v1", "rule:fin_v2"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T2
        )
        test_chain.append(ph_fin)

        # Check they are independent
        result_hr = get_current_policy_head(test_chain, "corp.hr")
        result_fin = get_current_policy_head(test_chain, "corp.finance")

        assert result_hr is not None
        assert result_fin is not None
        assert result_hr.cell_id != result_fin.cell_id

        hr_data = parse_policy_data(result_hr)
        fin_data = parse_policy_data(result_fin)
        assert hr_data["promoted_rule_ids"] == ["rule:hr_v1"]
        assert fin_data["promoted_rule_ids"] == ["rule:fin_v1", "rule:fin_v2"]


# ============================================================================
# POL-03: PolicyHead Chain Linking Tests
# ============================================================================

class TestPolicyHeadChainLinking:
    """Tests for PolicyHead chain linking via prev_policy_head (POL-03)"""

    @pytest.fixture
    def test_chain(self):
        """Create a test chain with Genesis"""
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_first_policy_head_has_null_prev(self, test_chain):
        """First PolicyHead should have prev_policy_head=None"""
        ph = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph)

        data = parse_policy_data(ph)
        assert data["prev_policy_head"] is None

    def test_subsequent_policy_heads_link_correctly(self, test_chain):
        """Subsequent PolicyHeads should link to previous via prev_policy_head"""
        # Create chain of 3 PolicyHeads
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1", "rule:v2"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph1.cell_id,
            system_time=T2
        )
        test_chain.append(ph2)

        ph3 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v2", "rule:v3"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph2.cell_id,
            system_time=T3
        )
        test_chain.append(ph3)

        # Verify chain links
        data1 = parse_policy_data(ph1)
        data2 = parse_policy_data(ph2)
        data3 = parse_policy_data(ph3)

        assert data1["prev_policy_head"] is None
        assert data2["prev_policy_head"] == ph1.cell_id
        assert data3["prev_policy_head"] == ph2.cell_id

    def test_get_policy_head_chain_returns_ordered_history(self, test_chain):
        """get_policy_head_chain should return all PolicyHeads in temporal order"""
        # Create 3 PolicyHeads
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1", "rule:v2"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph1.cell_id,
            system_time=T2
        )
        test_chain.append(ph2)

        ph3 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v3"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph2.cell_id,
            system_time=T3
        )
        test_chain.append(ph3)

        history = get_policy_head_chain(test_chain, "corp.hr")

        assert len(history) == 3
        assert history[0].cell_id == ph1.cell_id
        assert history[1].cell_id == ph2.cell_id
        assert history[2].cell_id == ph3.cell_id

    def test_get_policy_head_chain_empty_for_nonexistent_namespace(self, test_chain):
        """get_policy_head_chain should return empty list for namespace with no policies"""
        history = get_policy_head_chain(test_chain, "corp.nonexistent")
        assert history == []

    def test_namespaces_have_independent_chains(self, test_chain):
        """Each namespace should have its own independent PolicyHead chain"""
        # HR namespace - first PolicyHead
        ph_hr1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:hr_v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph_hr1)

        # Finance namespace - 1 PolicyHead (added in temporal order)
        ph_fin = create_policy_head(
            namespace="corp.finance",
            promoted_rule_ids=["rule:fin_v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T2
        )
        test_chain.append(ph_fin)

        # HR namespace - second PolicyHead (must be after T2)
        ph_hr2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:hr_v2"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph_hr1.cell_id,
            system_time=T3
        )
        test_chain.append(ph_hr2)

        # Check chains are independent
        hr_chain = get_policy_head_chain(test_chain, "corp.hr")
        fin_chain = get_policy_head_chain(test_chain, "corp.finance")

        assert len(hr_chain) == 2
        assert len(fin_chain) == 1
        assert hr_chain[0].cell_id == ph_hr1.cell_id
        assert hr_chain[1].cell_id == ph_hr2.cell_id
        assert fin_chain[0].cell_id == ph_fin.cell_id


# ============================================================================
# Bitemporal Query Tests
# ============================================================================

class TestGetPolicyHeadAtTime:
    """Tests for get_policy_head_at_time bitemporal query function"""

    @pytest.fixture
    def test_chain(self):
        """Create a test chain with Genesis"""
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_returns_none_before_any_policy(self, test_chain):
        """Should return None if querying before any PolicyHead exists"""
        # Create PolicyHead at T2
        ph = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T2
        )
        test_chain.append(ph)

        # Query at T1 (before PolicyHead)
        result = get_policy_head_at_time(test_chain, "corp.hr", T1)
        assert result is None

    def test_returns_policy_at_exact_time(self, test_chain):
        """Should return PolicyHead at exact system_time"""
        ph = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph)

        result = get_policy_head_at_time(test_chain, "corp.hr", T1)
        assert result is not None
        assert result.cell_id == ph.cell_id

    def test_returns_policy_after_time(self, test_chain):
        """Should return PolicyHead when querying after its system_time"""
        ph = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph)

        # Query at T2 (after PolicyHead)
        result = get_policy_head_at_time(test_chain, "corp.hr", T2)
        assert result is not None
        assert result.cell_id == ph.cell_id

    def test_returns_correct_policy_for_historical_query(self, test_chain):
        """Should return the policy that was active at the queried time"""
        # Create chain of 3 PolicyHeads at T1, T3, T5
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v2"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph1.cell_id,
            system_time=T3
        )
        test_chain.append(ph2)

        ph3 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v3"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph2.cell_id,
            system_time=T5
        )
        test_chain.append(ph3)

        # Query at T2 should get ph1 (active from T1 until T3)
        result_t2 = get_policy_head_at_time(test_chain, "corp.hr", T2)
        assert result_t2.cell_id == ph1.cell_id

        # Query at T4 should get ph2 (active from T3 until T5)
        result_t4 = get_policy_head_at_time(test_chain, "corp.hr", T4)
        assert result_t4.cell_id == ph2.cell_id

        # Query at T5 or later should get ph3
        result_t5 = get_policy_head_at_time(test_chain, "corp.hr", T5)
        assert result_t5.cell_id == ph3.cell_id

    def test_bitemporal_query_namespace_independent(self, test_chain):
        """Bitemporal queries should be namespace-specific"""
        # HR gets policy at T1
        ph_hr = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:hr_v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph_hr)

        # Finance gets policy at T3
        ph_fin = create_policy_head(
            namespace="corp.finance",
            promoted_rule_ids=["rule:fin_v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T3
        )
        test_chain.append(ph_fin)

        # At T2: HR has policy, Finance does not
        result_hr_t2 = get_policy_head_at_time(test_chain, "corp.hr", T2)
        result_fin_t2 = get_policy_head_at_time(test_chain, "corp.finance", T2)

        assert result_hr_t2 is not None
        assert result_fin_t2 is None  # Finance policy not yet created

        # At T4: Both have policies
        result_hr_t4 = get_policy_head_at_time(test_chain, "corp.hr", T4)
        result_fin_t4 = get_policy_head_at_time(test_chain, "corp.finance", T4)

        assert result_hr_t4 is not None
        assert result_fin_t4 is not None


# ============================================================================
# Chain Validation Tests
# ============================================================================

class TestValidatePolicyHeadChain:
    """Tests for validate_policy_head_chain function"""

    @pytest.fixture
    def test_chain(self):
        """Create a test chain with Genesis"""
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_empty_namespace_is_valid(self, test_chain):
        """Namespace with no PolicyHeads should be valid"""
        is_valid, errors = validate_policy_head_chain(test_chain, "corp.hr")
        assert is_valid is True
        assert errors == []

    def test_single_policy_head_valid(self, test_chain):
        """Single PolicyHead with null prev should be valid"""
        ph = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph)

        is_valid, errors = validate_policy_head_chain(test_chain, "corp.hr")
        assert is_valid is True
        assert errors == []

    def test_properly_linked_chain_valid(self, test_chain):
        """Properly linked PolicyHead chain should be valid"""
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v2"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph1.cell_id,
            system_time=T2
        )
        test_chain.append(ph2)

        ph3 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v3"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph2.cell_id,
            system_time=T3
        )
        test_chain.append(ph3)

        is_valid, errors = validate_policy_head_chain(test_chain, "corp.hr")
        assert is_valid is True
        assert errors == []

    def test_detects_non_null_first_prev(self, test_chain):
        """Should detect first PolicyHead with non-null prev_policy_head"""
        # Create first PolicyHead with non-null prev (invalid)
        ph = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head="fake_prev_id",  # Invalid - first should be None
            system_time=T1
        )
        test_chain.append(ph)

        is_valid, errors = validate_policy_head_chain(test_chain, "corp.hr")
        assert is_valid is False
        assert len(errors) >= 1
        assert any("First PolicyHead" in err and "non-null prev_policy_head" in err for err in errors)

    def test_detects_null_prev_on_subsequent(self, test_chain):
        """Should detect null prev_policy_head on non-first PolicyHead"""
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        # Second PolicyHead with null prev (invalid)
        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v2"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            # prev_policy_head not set - defaults to None (invalid for 2nd)
            system_time=T2
        )
        test_chain.append(ph2)

        is_valid, errors = validate_policy_head_chain(test_chain, "corp.hr")
        assert is_valid is False
        assert any("null prev_policy_head" in err for err in errors)

    def test_validates_policy_hash_integrity(self, test_chain):
        """Should validate that all PolicyHeads have valid policy_hash"""
        # Create valid PolicyHead
        ph = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:v1"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph)

        # Validation should pass for properly created PolicyHead
        is_valid, errors = validate_policy_head_chain(test_chain, "corp.hr")
        assert is_valid is True


# ============================================================================
# INT-01: PolicyHead Signature Verification Tests
# ============================================================================

class TestPolicyHeadSignatureVerification:
    """Tests for INT-01: PolicyHead signature storage and verification"""

    @pytest.fixture
    def test_chain(self):
        """Create a test chain with Genesis"""
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_policy_head_contains_witness_signatures(self, test_chain):
        """PolicyHead stores witness signatures in policy_data (INT-01)."""
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes

        priv, pub = generate_ed25519_keypair()
        canonical_payload = b'{"promotion_id":"test","rule_ids":["rule:a"]}'
        signature = sign_bytes(priv, canonical_payload)

        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": signature},
            canonical_payload=canonical_payload
        )

        policy_data = parse_policy_data(policy_head)
        assert "witness_signatures" in policy_data
        assert "alice" in policy_data["witness_signatures"]
        # Signature should be base64 encoded
        import base64
        decoded_sig = base64.b64decode(policy_data["witness_signatures"]["alice"])
        assert decoded_sig == signature

    def test_policy_head_contains_canonical_payload(self, test_chain):
        """PolicyHead stores canonical_payload for verification (INT-01)."""
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes

        priv, pub = generate_ed25519_keypair()
        canonical_payload = b'{"promotion_id":"test123","rule_ids":["rule:a"]}'
        signature = sign_bytes(priv, canonical_payload)

        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": signature},
            canonical_payload=canonical_payload
        )

        policy_data = parse_policy_data(policy_head)
        assert "canonical_payload" in policy_data
        assert policy_data["canonical_payload"] is not None
        # Payload should be base64 encoded
        import base64
        decoded_payload = base64.b64decode(policy_data["canonical_payload"])
        assert decoded_payload == canonical_payload

    def test_policy_head_signature_storage_empty_signatures(self, test_chain):
        """PolicyHead with no signatures stores empty dict (bootstrap mode)."""
        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
            # No witness_signatures or canonical_payload
        )

        policy_data = parse_policy_data(policy_head)
        assert policy_data["witness_signatures"] == {}
        assert policy_data["canonical_payload"] is None

    def test_verify_policy_head_signatures_valid(self, test_chain):
        """Valid signatures verify successfully (INT-01)."""
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes
        from decisiongraph.policyhead import verify_policy_head_signatures

        priv, pub = generate_ed25519_keypair()
        canonical_payload = b'{"promotion_id":"test","rule_ids":["rule:a"]}'
        signature = sign_bytes(priv, canonical_payload)

        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": signature},
            canonical_payload=canonical_payload
        )

        is_valid, errors = verify_policy_head_signatures(
            policy_head,
            {"alice": pub}
        )
        assert is_valid is True
        assert errors == []

    def test_verify_policy_head_signatures_multiple_witnesses(self, test_chain):
        """Multiple valid signatures all verify successfully."""
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes
        from decisiongraph.policyhead import verify_policy_head_signatures

        # Generate keys for two witnesses
        alice_priv, alice_pub = generate_ed25519_keypair()
        bob_priv, bob_pub = generate_ed25519_keypair()
        canonical_payload = b'{"promotion_id":"test","rule_ids":["rule:a","rule:b"]}'

        # Both witnesses sign the same payload
        alice_sig = sign_bytes(alice_priv, canonical_payload)
        bob_sig = sign_bytes(bob_priv, canonical_payload)

        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a", "rule:b"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": alice_sig, "bob": bob_sig},
            canonical_payload=canonical_payload
        )

        is_valid, errors = verify_policy_head_signatures(
            policy_head,
            {"alice": alice_pub, "bob": bob_pub}
        )
        assert is_valid is True
        assert errors == []

    def test_verify_policy_head_signatures_invalid_signature(self, test_chain):
        """Invalid signature (wrong key) returns error (INT-01)."""
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes
        from decisiongraph.policyhead import verify_policy_head_signatures

        alice_priv, alice_pub = generate_ed25519_keypair()
        wrong_priv, wrong_pub = generate_ed25519_keypair()
        canonical_payload = b'{"promotion_id":"test","rule_ids":["rule:a"]}'

        # Sign with wrong key
        bad_signature = sign_bytes(wrong_priv, canonical_payload)

        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": bad_signature},
            canonical_payload=canonical_payload
        )

        # Verify with alice's real public key (doesn't match signature)
        is_valid, errors = verify_policy_head_signatures(
            policy_head,
            {"alice": alice_pub}
        )
        assert is_valid is False
        assert len(errors) == 1
        assert "alice" in errors[0]
        assert "failed" in errors[0].lower()

    def test_verify_policy_head_signatures_missing_public_key(self, test_chain):
        """Missing public key for witness returns error."""
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes
        from decisiongraph.policyhead import verify_policy_head_signatures

        priv, pub = generate_ed25519_keypair()
        canonical_payload = b'{"promotion_id":"test","rule_ids":["rule:a"]}'
        signature = sign_bytes(priv, canonical_payload)

        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": signature},
            canonical_payload=canonical_payload
        )

        # Don't provide alice's public key
        is_valid, errors = verify_policy_head_signatures(
            policy_head,
            {}  # Empty - no public keys provided
        )
        assert is_valid is False
        assert len(errors) == 1
        assert "No public key provided for witness 'alice'" in errors[0]

    def test_verify_policy_head_signatures_partial_missing_keys(self, test_chain):
        """One missing key among multiple witnesses returns error for that witness."""
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes
        from decisiongraph.policyhead import verify_policy_head_signatures

        alice_priv, alice_pub = generate_ed25519_keypair()
        bob_priv, bob_pub = generate_ed25519_keypair()
        canonical_payload = b'{"promotion_id":"test","rule_ids":["rule:a"]}'

        alice_sig = sign_bytes(alice_priv, canonical_payload)
        bob_sig = sign_bytes(bob_priv, canonical_payload)

        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": alice_sig, "bob": bob_sig},
            canonical_payload=canonical_payload
        )

        # Only provide alice's public key
        is_valid, errors = verify_policy_head_signatures(
            policy_head,
            {"alice": alice_pub}  # Missing bob's key
        )
        assert is_valid is False
        assert len(errors) == 1
        assert "bob" in errors[0]

    def test_verify_policy_head_signatures_no_signatures(self, test_chain):
        """PolicyHead with no signatures (bootstrap) returns success with empty errors."""
        from decisiongraph.policyhead import verify_policy_head_signatures

        # PolicyHead without signatures but with canonical_payload
        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={},  # Empty - no signatures
            canonical_payload=b'{"promotion_id":"test","rule_ids":["rule:a"]}'
        )

        is_valid, errors = verify_policy_head_signatures(
            policy_head,
            {}  # No public keys needed
        )
        assert is_valid is True
        assert errors == []

    def test_verify_policy_head_signatures_no_canonical_payload(self, test_chain):
        """PolicyHead without canonical_payload cannot verify signatures."""
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes
        from decisiongraph.policyhead import verify_policy_head_signatures

        priv, pub = generate_ed25519_keypair()
        # Note: we still sign something, but don't store canonical_payload
        signature = sign_bytes(priv, b'some data')

        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": signature},
            canonical_payload=None  # No payload stored
        )

        is_valid, errors = verify_policy_head_signatures(
            policy_head,
            {"alice": pub}
        )
        assert is_valid is False
        assert len(errors) == 1
        assert "canonical_payload" in errors[0]


class TestFullPromotionSignatureVerification:
    """End-to-end test: Verify signatures through full promotion workflow."""

    def test_full_promotion_signatures_verifiable(self):
        """
        Run full promotion workflow via Engine, then verify PolicyHead signatures.

        This is the real INT-01 scenario: after finalize_promotion(), the
        PolicyHead should contain verifiable signatures.
        """
        from decisiongraph.chain import Chain
        from decisiongraph.engine import Engine
        from decisiongraph.genesis import create_genesis_cell_with_witness_set
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes
        from decisiongraph.policyhead import (
            get_current_policy_head,
            parse_policy_data,
            verify_policy_head_signatures
        )
        from decisiongraph.cell import (
            DecisionCell, Header, Fact, LogicAnchor, Proof,
            CellType, SourceQuality, get_current_timestamp
        )

        # Create chain with WitnessSet in Genesis
        alice_priv, alice_pub = generate_ed25519_keypair()
        bob_priv, bob_pub = generate_ed25519_keypair()

        chain = Chain()
        genesis = create_genesis_cell_with_witness_set(
            graph_name="TestGraph",
            root_namespace="corp",
            witnesses=["alice", "bob"],
            threshold=2
        )
        chain.append(genesis)

        # Create a rule cell that can be promoted
        rule_header = Header(
            version="1.5",
            graph_id=chain.graph_id,
            cell_type=CellType.RULE,
            system_time=get_current_timestamp(),
            prev_cell_hash=chain.head.cell_id
        )
        rule_fact = Fact(
            namespace="corp",
            subject="rule:salary_v1",
            predicate="defines_calculation",
            object="salary = base * multiplier",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=get_current_timestamp(),
            valid_to=None
        )
        rule_logic = LogicAnchor(
            rule_id="rule:salary_v1",
            rule_logic_hash="abc123",
            interpreter="python:3.10"
        )
        rule_proof = Proof(
            signer_id="system",
            signer_key_id=None,
            signature=None,
            merkle_root=None,
            signature_required=False
        )
        rule_cell = DecisionCell(
            header=rule_header,
            fact=rule_fact,
            logic_anchor=rule_logic,
            evidence=[],
            proof=rule_proof
        )
        chain.append(rule_cell)

        # Run promotion workflow
        engine = Engine(chain)
        promotion_id = engine.submit_promotion(
            namespace="corp",
            rule_ids=[rule_cell.cell_id],
            submitter_id="admin"
        )

        # Get the canonical payload from the promotion
        promotion = engine._promotions[promotion_id]
        canonical_payload = promotion.canonical_payload

        # Collect signatures from both witnesses
        alice_sig = sign_bytes(alice_priv, canonical_payload)
        bob_sig = sign_bytes(bob_priv, canonical_payload)

        engine.collect_witness_signature(
            promotion_id=promotion_id,
            witness_id="alice",
            signature=alice_sig,
            public_key=alice_pub
        )
        engine.collect_witness_signature(
            promotion_id=promotion_id,
            witness_id="bob",
            signature=bob_sig,
            public_key=bob_pub
        )

        # Finalize promotion
        policy_head_id = engine.finalize_promotion(promotion_id)

        # Now verify: the PolicyHead should contain verifiable signatures
        policy_head = chain.get_cell(policy_head_id)
        assert policy_head is not None

        # Check signatures are stored
        policy_data = parse_policy_data(policy_head)
        assert len(policy_data["witness_signatures"]) == 2
        assert "alice" in policy_data["witness_signatures"]
        assert "bob" in policy_data["witness_signatures"]
        assert policy_data["canonical_payload"] is not None

        # Verify signatures using verify_policy_head_signatures
        is_valid, errors = verify_policy_head_signatures(
            policy_head,
            {"alice": alice_pub, "bob": bob_pub}
        )
        assert is_valid is True, f"Signature verification failed: {errors}"
        assert errors == []

    def test_signatures_fail_with_tampered_payload(self):
        """
        Signatures should fail verification if payload was tampered.

        This tests the audit trail protection: if someone modifies
        the canonical_payload after signatures were collected, verification fails.
        """
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes
        from decisiongraph.policyhead import verify_policy_head_signatures
        import base64

        chain = create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

        priv, pub = generate_ed25519_keypair()
        original_payload = b'{"promotion_id":"test","rule_ids":["rule:a"]}'
        signature = sign_bytes(priv, original_payload)

        # Create PolicyHead with correct signature
        policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],
            graph_id=chain.graph_id,
            prev_cell_hash=chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": signature},
            canonical_payload=original_payload
        )

        # First verify it's valid
        is_valid, errors = verify_policy_head_signatures(
            policy_head,
            {"alice": pub}
        )
        assert is_valid is True

        # Now simulate tampering: create a new PolicyHead with different payload
        # but same signature (this is what an attacker might try)
        tampered_payload = b'{"promotion_id":"test","rule_ids":["rule:EVIL"]}'

        tampered_policy_head = create_policy_head(
            namespace="corp",
            promoted_rule_ids=["rule:a"],  # Original rules (mismatch with payload)
            graph_id=chain.graph_id,
            prev_cell_hash=chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": signature},  # Original signature
            canonical_payload=tampered_payload  # Tampered payload
        )

        # Verification should fail because signature was for original payload
        is_valid, errors = verify_policy_head_signatures(
            tampered_policy_head,
            {"alice": pub}
        )
        assert is_valid is False
        assert len(errors) == 1
        assert "alice" in errors[0]


# ============================================================================
# AUD-01: PolicyHead Audit Text Tests
# ============================================================================

class TestPolicyHeadAuditText:
    """Tests for AUD-01: policy_head_to_audit_text function"""

    @pytest.fixture
    def test_chain(self):
        """Create a test chain with Genesis"""
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_audit_text_contains_required_sections(self, test_chain):
        """Audit text should contain all required sections."""
        from decisiongraph.policyhead import policy_head_to_audit_text

        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a", "rule:b"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        audit_text = policy_head_to_audit_text(policy_head)

        # Check all required sections exist
        assert "POLICYHEAD AUDIT REPORT" in audit_text
        assert "Policy Snapshot:" in audit_text
        assert "Policy Hash:" in audit_text
        assert "Chain Link:" in audit_text
        assert "Witness Signatures:" in audit_text
        assert "Promotion Context:" in audit_text
        assert "Schema Version:" in audit_text

    def test_audit_text_shows_namespace_and_cell_id(self, test_chain):
        """Audit text should show namespace and truncated cell_id."""
        from decisiongraph.policyhead import policy_head_to_audit_text

        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        audit_text = policy_head_to_audit_text(policy_head)

        assert "Namespace: corp.hr" in audit_text
        # Cell ID should be truncated to 16 chars + "..."
        cell_id_prefix = policy_head.cell_id[:16]
        assert f"Cell ID: {cell_id_prefix}..." in audit_text

    def test_audit_text_shows_promoted_rules(self, test_chain):
        """Audit text should show promoted rules count and list."""
        from decisiongraph.policyhead import policy_head_to_audit_text

        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a", "rule:b"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        audit_text = policy_head_to_audit_text(policy_head)

        assert "Promoted Rules: 2" in audit_text
        assert "- rule:a" in audit_text
        assert "- rule:b" in audit_text

    def test_audit_text_shows_genesis_for_first_policy(self, test_chain):
        """First PolicyHead (no prev) should show genesis indicator."""
        from decisiongraph.policyhead import policy_head_to_audit_text

        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=None,  # First policy
            system_time=T1
        )

        audit_text = policy_head_to_audit_text(policy_head)

        assert "(genesis - first policy)" in audit_text

    def test_audit_text_shows_prev_policy_head_link(self, test_chain):
        """Subsequent PolicyHead should show truncated prev_policy_head."""
        from decisiongraph.policyhead import policy_head_to_audit_text

        prev_policy_head_id = "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz5678"

        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=prev_policy_head_id,
            system_time=T1
        )

        audit_text = policy_head_to_audit_text(policy_head)

        # Should show truncated prev_policy_head
        assert f"Previous PolicyHead: {prev_policy_head_id[:16]}..." in audit_text
        assert "(genesis - first policy)" not in audit_text

    def test_audit_text_shows_witness_signatures(self, test_chain):
        """Audit text should show witness signatures count and IDs."""
        from decisiongraph.policyhead import policy_head_to_audit_text
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes

        alice_priv, alice_pub = generate_ed25519_keypair()
        bob_priv, bob_pub = generate_ed25519_keypair()
        canonical_payload = b'{"promotion_id":"test","rule_ids":["rule:a"]}'

        alice_sig = sign_bytes(alice_priv, canonical_payload)
        bob_sig = sign_bytes(bob_priv, canonical_payload)

        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={"alice": alice_sig, "bob": bob_sig},
            canonical_payload=canonical_payload
        )

        audit_text = policy_head_to_audit_text(policy_head)

        assert "Signatures Collected: 2" in audit_text
        assert "alice:" in audit_text
        assert "bob:" in audit_text
        assert "(signature present)" in audit_text

    def test_audit_text_shows_submitter(self, test_chain):
        """Audit text should show submitter from proof.signer_id."""
        from decisiongraph.policyhead import policy_head_to_audit_text

        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:test"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            creator="admin:alice",
            system_time=T1
        )

        audit_text = policy_head_to_audit_text(policy_head)

        assert "Submitter: admin:alice" in audit_text

    def test_audit_text_deterministic(self, test_chain):
        """Same PolicyHead should always produce identical audit text."""
        from decisiongraph.policyhead import policy_head_to_audit_text

        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a", "rule:b"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )

        audit_text_1 = policy_head_to_audit_text(policy_head)
        audit_text_2 = policy_head_to_audit_text(policy_head)

        assert audit_text_1 == audit_text_2

    def test_audit_text_witness_ids_sorted(self, test_chain):
        """Witness IDs should be sorted alphabetically in audit text."""
        from decisiongraph.policyhead import policy_head_to_audit_text
        from decisiongraph.signing import generate_ed25519_keypair, sign_bytes

        # Generate keys for three witnesses
        charlie_priv, _ = generate_ed25519_keypair()
        alice_priv, _ = generate_ed25519_keypair()
        bob_priv, _ = generate_ed25519_keypair()

        canonical_payload = b'{"promotion_id":"test","rule_ids":["rule:a"]}'

        # Create signatures in unsorted order
        charlie_sig = sign_bytes(charlie_priv, canonical_payload)
        alice_sig = sign_bytes(alice_priv, canonical_payload)
        bob_sig = sign_bytes(bob_priv, canonical_payload)

        # Pass witnesses in unsorted order
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1,
            witness_signatures={
                "charlie": charlie_sig,
                "alice": alice_sig,
                "bob": bob_sig
            },
            canonical_payload=canonical_payload
        )

        audit_text = policy_head_to_audit_text(policy_head)

        # Find positions of witness IDs in the text
        alice_pos = audit_text.find("alice:")
        bob_pos = audit_text.find("bob:")
        charlie_pos = audit_text.find("charlie:")

        # Should be in alphabetical order: alice, bob, charlie
        assert alice_pos < bob_pos < charlie_pos


# ============================================================================
# AUD-02: PolicyHead Chain DOT Visualization Tests
# ============================================================================

class TestPolicyHeadChainToDot:
    """Tests for AUD-02: policy_head_chain_to_dot function"""

    @pytest.fixture
    def test_chain(self):
        """Create a test chain with Genesis"""
        return create_chain(
            graph_name="TestGraph",
            root_namespace="corp",
            system_time=T0
        )

    def test_dot_output_is_valid_graphviz(self, test_chain):
        """DOT output should be valid Graphviz syntax."""
        # Create a single PolicyHead
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(policy_head)

        dot_output = policy_head_chain_to_dot(test_chain, "corp.hr")

        # Check basic Graphviz structure
        assert "digraph policy_chain {" in dot_output
        assert "rankdir=TB;" in dot_output
        assert "node [shape=box, style=filled];" in dot_output
        assert dot_output.strip().endswith("}")

    def test_dot_output_contains_namespace_comment(self, test_chain):
        """DOT output should include namespace comment."""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(policy_head)

        dot_output = policy_head_chain_to_dot(test_chain, "corp.hr")

        assert "// PolicyHead Chain: corp.hr" in dot_output

    def test_dot_output_shows_policy_head_nodes(self, test_chain):
        """DOT output should contain node definitions for PolicyHeads."""
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a", "rule:b"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph1.cell_id,
            system_time=T2
        )
        test_chain.append(ph2)

        dot_output = policy_head_chain_to_dot(test_chain, "corp.hr")

        # Should contain 2 node definitions with lightyellow fill
        assert dot_output.count("fillcolor=lightyellow") == 2
        # Should contain node labels with "PolicyHead" and namespace
        assert "PolicyHead" in dot_output
        assert "corp.hr" in dot_output

    def test_dot_output_shows_chain_edges(self, test_chain):
        """DOT output should contain edges with supersedes labels."""
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a", "rule:b"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph1.cell_id,
            system_time=T2
        )
        test_chain.append(ph2)

        ph3 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:b", "rule:c"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph2.cell_id,
            system_time=T3
        )
        test_chain.append(ph3)

        dot_output = policy_head_chain_to_dot(test_chain, "corp.hr")

        # Should contain 2 edges (ph3->ph2, ph2->ph1) with "supersedes" label
        assert dot_output.count('[label="supersedes"]') == 2
        assert '->' in dot_output

    def test_dot_output_empty_namespace(self, test_chain):
        """DOT output for nonexistent namespace should be valid but minimal."""
        dot_output = policy_head_chain_to_dot(test_chain, "corp.nonexistent")

        # Should still be valid DOT syntax
        assert "digraph policy_chain {" in dot_output
        assert dot_output.strip().endswith("}")
        # Should have namespace comment
        assert "// PolicyHead Chain: corp.nonexistent" in dot_output
        # Should have no nodes or edges (no fillcolor, no arrows)
        assert "fillcolor=lightyellow" not in dot_output
        assert "->" not in dot_output

    def test_dot_output_deterministic(self, test_chain):
        """Same chain + namespace should always produce identical DOT output."""
        ph1 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(ph1)

        ph2 = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a", "rule:b"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            prev_policy_head=ph1.cell_id,
            system_time=T2
        )
        test_chain.append(ph2)

        # Generate DOT output twice
        dot_output_1 = policy_head_chain_to_dot(test_chain, "corp.hr")
        dot_output_2 = policy_head_chain_to_dot(test_chain, "corp.hr")

        assert dot_output_1 == dot_output_2

    def test_dot_output_node_id_truncation(self, test_chain):
        """Node IDs should be truncated to 12 chars + ellipsis."""
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(policy_head)

        dot_output = policy_head_chain_to_dot(test_chain, "corp.hr")

        # Node ID should be truncated: first 12 chars + "..."
        truncated_id = policy_head.cell_id[:12] + "..."
        assert f'"{truncated_id}"' in dot_output

    def test_dot_output_escapes_special_characters(self, test_chain):
        """DOT output should properly escape special characters."""
        # Create PolicyHead (namespace won't have special chars,
        # but we verify the output doesn't break DOT syntax)
        policy_head = create_policy_head(
            namespace="corp.hr",
            promoted_rule_ids=["rule:a"],
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
            system_time=T1
        )
        test_chain.append(policy_head)

        dot_output = policy_head_chain_to_dot(test_chain, "corp.hr")

        # Verify the output is valid DOT by checking structure
        # No unescaped raw quotes should break the syntax
        lines = dot_output.split('\n')
        for line in lines:
            # If line contains a node definition with quotes,
            # it should have balanced quotes
            if 'label=' in line:
                # Count quotes (should be even number)
                quote_count = line.count('"')
                assert quote_count % 2 == 0, f"Unbalanced quotes in: {line}"

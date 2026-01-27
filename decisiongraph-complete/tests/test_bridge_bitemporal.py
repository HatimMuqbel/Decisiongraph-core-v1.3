"""
DecisionGraph v1.3: Bridge Bitemporal Permission Tests

These tests verify the "time-travel permissions" invariant:
- Bridges must be effective at BOTH bitemporal coordinates
- Clock A (knowledge): bridge.system_time <= as_of_system_time
- Clock B (validity): bridge.valid_from <= at_valid_time < bridge.valid_to

This prevents a class of integrity bugs where bridges are used at times
when they weren't known or weren't valid.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest

from test_utils import T0, T1, T2, T_FUTURE

from decisiongraph import (
    # Cell primitives
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    CellType,
    SourceQuality,
    NULL_HASH,
    compute_rule_logic_hash,
    generate_graph_id,

    # Genesis
    create_genesis_cell,

    # Chain
    Chain,

    # Namespace
    NamespaceMetadata,

    # Scholar
    Scholar,
    create_scholar,
    BridgeEffectivenessReason,
    is_bridge_effective,
)


def create_chain_with_genesis(root_namespace: str, system_time: str) -> Chain:
    """Create a chain with a genesis cell at the specified system_time."""
    genesis = create_genesis_cell(
        graph_name="TestGraph",
        root_namespace=root_namespace,
        system_time=system_time
    )
    chain = Chain()
    chain.append(genesis)
    return chain


def create_namespace_cell(
    chain: Chain,
    namespace: str,
    owner: str,
    system_time: str,
    prev_cell_hash: str
) -> DecisionCell:
    """Create a namespace definition cell with explicit system_time."""
    metadata = NamespaceMetadata(
        owner=owner,
        sensitivity="internal",
        description=f"Test namespace: {namespace}"
    )

    return DecisionCell(
        header=Header(
            graph_id=chain.graph_id,
            version="1.3",
            cell_type=CellType.NAMESPACE_DEF,
            system_time=system_time,
            prev_cell_hash=prev_cell_hash
        ),
        fact=Fact(
            namespace="system.namespaces",
            subject=namespace,
            predicate="has_metadata",
            object=str(metadata.to_dict()),
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=system_time
        ),
        logic_anchor=LogicAnchor(
            rule_id="system:namespace_create",
            rule_logic_hash=compute_rule_logic_hash(f"NAMESPACE_CREATE: {namespace}")
        )
    )


def create_bridge_cell(
    chain: Chain,
    from_namespace: str,
    to_namespace: str,
    system_time: str,
    valid_from: str,
    valid_to: str,
    prev_cell_hash: str
) -> DecisionCell:
    """Create a bridge rule cell with explicit bitemporal coordinates."""
    rule_content = f"BRIDGE: {from_namespace} -> {to_namespace}"

    return DecisionCell(
        header=Header(
            graph_id=chain.graph_id,
            version="1.3",
            cell_type=CellType.BRIDGE_RULE,
            system_time=system_time,
            prev_cell_hash=prev_cell_hash
        ),
        fact=Fact(
            namespace="system.bridges",
            subject=from_namespace,
            predicate="can_query",
            object=to_namespace,
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=valid_from,
            valid_to=valid_to
        ),
        logic_anchor=LogicAnchor(
            rule_id="system:bridge_creation",
            rule_logic_hash=compute_rule_logic_hash(rule_content)
        )
    )


class TestBridgeBitemporal:
    """
    Test suite for bridge bitemporal permission validation.

    These tests "seal" the time-travel invariant by verifying:
    1. Bridge not yet known (system_time check)
    2. Bridge known but not active yet (valid_from check)
    3. Bridge expired (valid_to check)
    4. Bridge known and active (success case)
    """

    def _setup_two_namespace_chain(
        self,
        bridge_system_time: str,
        bridge_valid_from: str,
        bridge_valid_to: str = None
    ) -> tuple:
        """
        Create a chain with two namespaces (corp, partner) and a bridge between them.

        Returns (chain, bridge_cell_id)
        """
        # Create chain with root namespace at T0
        chain = create_chain_with_genesis("corp", T0)

        # Create partner namespace at T0
        partner_ns_cell = create_namespace_cell(
            chain=chain,
            namespace="partner",
            owner="corp",
            system_time=T0,
            prev_cell_hash=chain.cells[-1].cell_id
        )
        chain.append(partner_ns_cell)

        # Create bridge with specified timing
        bridge_cell = create_bridge_cell(
            chain=chain,
            from_namespace="corp",
            to_namespace="partner",
            system_time=bridge_system_time,
            valid_from=bridge_valid_from,
            valid_to=bridge_valid_to,
            prev_cell_hash=chain.cells[-1].cell_id
        )
        chain.append(bridge_cell)

        return chain, bridge_cell.cell_id

    def test_bridge_not_yet_known(self):
        """
        Test 1: Bridge cell system_time > query system_time

        Bridge recorded at T2, query at T1.
        At T1, the bridge wasn't known yet.

        Expected: not authorized, reason = bridge_not_yet_known
        """
        chain, bridge_cell_id = self._setup_two_namespace_chain(
            bridge_system_time=T2,      # Bridge recorded at T2
            bridge_valid_from=T0,       # Valid from T0
            bridge_valid_to=None        # Open-ended
        )

        scholar = create_scholar(chain)

        # Query at T1 (before bridge was recorded)
        result = scholar.check_visibility(
            requester_namespace="corp",
            target_namespace="partner",
            at_valid_time=T1,
            as_of_system_time=T1        # At T1, bridge wasn't known
        )

        # Bridge exists but wasn't known at query time
        assert result.allowed is False
        assert result.reason == "no_access"
        assert len(result.bridge_effectiveness) == 1
        assert result.bridge_effectiveness[0].bridge_cell_id == bridge_cell_id
        assert result.bridge_effectiveness[0].effective is False
        assert result.bridge_effectiveness[0].reason == BridgeEffectivenessReason.BRIDGE_NOT_YET_KNOWN

    def test_bridge_not_active_yet(self):
        """
        Test 2: Bridge known but valid_from > query valid_time

        Bridge recorded at T0, valid_from=T2, query at T1.
        Bridge was known but not yet active at the query's valid_time.

        Expected: not authorized, reason = bridge_not_active
        """
        chain, bridge_cell_id = self._setup_two_namespace_chain(
            bridge_system_time=T0,      # Bridge recorded at T0 (known)
            bridge_valid_from=T2,       # But only valid starting T2
            bridge_valid_to=None        # Open-ended
        )

        scholar = create_scholar(chain)

        # Query at T1 (bridge known but not yet active)
        result = scholar.check_visibility(
            requester_namespace="corp",
            target_namespace="partner",
            at_valid_time=T1,           # Before valid_from
            as_of_system_time=T2        # After system_time (bridge is known)
        )

        assert result.allowed is False
        assert result.reason == "no_access"
        assert len(result.bridge_effectiveness) == 1
        assert result.bridge_effectiveness[0].bridge_cell_id == bridge_cell_id
        assert result.bridge_effectiveness[0].effective is False
        assert result.bridge_effectiveness[0].reason == BridgeEffectivenessReason.BRIDGE_NOT_ACTIVE

    def test_bridge_known_and_active(self):
        """
        Test 3: Bridge known AND active at query time

        Bridge recorded at T0, valid_from=T0, query at T1.
        Both clocks are satisfied.

        Expected: authorized, bridges_used contains bridge cell_id
        """
        chain, bridge_cell_id = self._setup_two_namespace_chain(
            bridge_system_time=T0,      # Bridge recorded at T0
            bridge_valid_from=T0,       # Valid from T0
            bridge_valid_to=None        # Open-ended
        )

        scholar = create_scholar(chain)

        # Query at T1 (bridge known and active)
        result = scholar.check_visibility(
            requester_namespace="corp",
            target_namespace="partner",
            at_valid_time=T1,
            as_of_system_time=T1
        )

        assert result.allowed is True
        assert result.reason == "bridge"
        assert bridge_cell_id in result.bridges_used
        assert len(result.bridge_effectiveness) == 1
        assert result.bridge_effectiveness[0].bridge_cell_id == bridge_cell_id
        assert result.bridge_effectiveness[0].effective is True
        assert result.bridge_effectiveness[0].reason == BridgeEffectivenessReason.AUTHORIZED

    def test_bridge_expired(self):
        """
        Test 4: Bridge valid_to <= query valid_time (expired)

        Bridge valid_from=T0, valid_to=T1, query at T2.
        Bridge was valid but has expired.

        Expected: not authorized, reason = bridge_expired
        """
        chain, bridge_cell_id = self._setup_two_namespace_chain(
            bridge_system_time=T0,      # Bridge recorded at T0
            bridge_valid_from=T0,       # Valid from T0
            bridge_valid_to=T1          # Valid until T1 (exclusive)
        )

        scholar = create_scholar(chain)

        # Query at T2 (after bridge expired)
        result = scholar.check_visibility(
            requester_namespace="corp",
            target_namespace="partner",
            at_valid_time=T2,           # After valid_to
            as_of_system_time=T2        # Bridge is known
        )

        assert result.allowed is False
        assert result.reason == "no_access"
        assert len(result.bridge_effectiveness) == 1
        assert result.bridge_effectiveness[0].bridge_cell_id == bridge_cell_id
        assert result.bridge_effectiveness[0].effective is False
        assert result.bridge_effectiveness[0].reason == BridgeEffectivenessReason.BRIDGE_EXPIRED


class TestBridgeEffectivenessFunction:
    """
    Unit tests for is_bridge_effective() function in isolation.
    """

    def _create_mock_bridge_cell(
        self,
        system_time: str,
        valid_from: str,
        valid_to: str = None
    ) -> DecisionCell:
        """Create a minimal bridge cell for testing."""
        return DecisionCell(
            header=Header(
                graph_id="graph:test-123",
                version="1.3",
                cell_type=CellType.BRIDGE_RULE,
                system_time=system_time,
                prev_cell_hash=NULL_HASH
            ),
            fact=Fact(
                namespace="corp",
                subject="bridge:corp->partner",
                predicate="grants_access",
                object="partner",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=valid_from,
                valid_to=valid_to
            ),
            logic_anchor=LogicAnchor(
                rule_id="bridge_rule",
                rule_logic_hash=compute_rule_logic_hash("bridge grant")
            )
        )

    def test_effective_open_ended_bridge(self):
        """Bridge with no valid_to (open-ended) should be effective."""
        bridge = self._create_mock_bridge_cell(
            system_time=T0,
            valid_from=T0,
            valid_to=None
        )
        effective, reason = is_bridge_effective(bridge, T1, T1, is_revoked=False)
        assert effective is True
        assert reason == BridgeEffectivenessReason.AUTHORIZED

    def test_revoked_bridge(self):
        """Revoked bridge should not be effective."""
        bridge = self._create_mock_bridge_cell(
            system_time=T0,
            valid_from=T0,
            valid_to=None
        )
        effective, reason = is_bridge_effective(bridge, T1, T1, is_revoked=True)
        assert effective is False
        assert reason == BridgeEffectivenessReason.BRIDGE_REVOKED

    def test_not_yet_known(self):
        """Bridge recorded after query system_time should not be effective."""
        bridge = self._create_mock_bridge_cell(
            system_time=T2,
            valid_from=T0,
            valid_to=None
        )
        effective, reason = is_bridge_effective(bridge, T1, T1, is_revoked=False)
        assert effective is False
        assert reason == BridgeEffectivenessReason.BRIDGE_NOT_YET_KNOWN

    def test_not_active(self):
        """Bridge with valid_from after query valid_time should not be effective."""
        bridge = self._create_mock_bridge_cell(
            system_time=T0,
            valid_from=T2,
            valid_to=None
        )
        effective, reason = is_bridge_effective(bridge, T1, T2, is_revoked=False)
        assert effective is False
        assert reason == BridgeEffectivenessReason.BRIDGE_NOT_ACTIVE

    def test_expired(self):
        """Bridge with valid_to <= query valid_time should not be effective."""
        bridge = self._create_mock_bridge_cell(
            system_time=T0,
            valid_from=T0,
            valid_to=T1
        )
        # Query at exactly valid_to - should be expired (exclusive)
        effective, reason = is_bridge_effective(bridge, T1, T2, is_revoked=False)
        assert effective is False
        assert reason == BridgeEffectivenessReason.BRIDGE_EXPIRED

    def test_expired_after_valid_to(self):
        """Bridge with valid_to < query valid_time should not be effective."""
        bridge = self._create_mock_bridge_cell(
            system_time=T0,
            valid_from=T0,
            valid_to=T1
        )
        effective, reason = is_bridge_effective(bridge, T2, T2, is_revoked=False)
        assert effective is False
        assert reason == BridgeEffectivenessReason.BRIDGE_EXPIRED


class TestQueryFactsWithBridgeBitemporal:
    """
    Integration tests verifying query_facts() respects bitemporal bridge permissions.
    """

    def _setup_chain_with_bridge_and_fact(
        self,
        bridge_system_time: str,
        bridge_valid_from: str,
        bridge_valid_to: str = None,
        fact_system_time: str = T0
    ) -> Chain:
        """
        Create chain with bridge and a fact in the partner namespace.

        Chain order: genesis -> namespace -> fact -> bridge
        This allows fact to be at T0 even when bridge is at T2 (monotonic timestamps).
        """
        # Create chain with genesis at T0
        chain = create_chain_with_genesis("corp", T0)

        # Create partner namespace at T0
        partner_ns_cell = create_namespace_cell(
            chain=chain,
            namespace="partner",
            owner="corp",
            system_time=T0,
            prev_cell_hash=chain.cells[-1].cell_id
        )
        chain.append(partner_ns_cell)

        # Add a fact in partner namespace BEFORE the bridge
        # This allows the fact to exist at T0 even if bridge comes later
        fact_cell = DecisionCell(
            header=Header(
                graph_id=chain.graph_id,
                version="1.3",
                cell_type=CellType.FACT,
                system_time=fact_system_time,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="partner",
                subject="entity:partner_data",
                predicate="has_value",
                object="secret_info",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T0
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:fact_rule",
                rule_logic_hash=compute_rule_logic_hash("fact creation")
            )
        )
        chain.append(fact_cell)

        # Create bridge with specified timing (can be later than fact)
        bridge_cell = create_bridge_cell(
            chain=chain,
            from_namespace="corp",
            to_namespace="partner",
            system_time=bridge_system_time,
            valid_from=bridge_valid_from,
            valid_to=bridge_valid_to,
            prev_cell_hash=chain.cells[-1].cell_id
        )
        chain.append(bridge_cell)

        return chain

    def test_query_denied_when_bridge_not_yet_known(self):
        """Query should return no facts if bridge wasn't known at system_time."""
        chain = self._setup_chain_with_bridge_and_fact(
            bridge_system_time=T2,
            bridge_valid_from=T0
        )
        scholar = create_scholar(chain)

        # Query at T1 (bridge not yet known)
        result = scholar.query_facts(
            requester_namespace="corp",
            namespace="partner",
            subject="entity:partner_data",
            predicate="has_value",
            at_valid_time=T1,
            as_of_system_time=T1,
            requester_id="principal:corp"
        )

        assert result.authorization.allowed is False
        assert result.authorization.reason == "no_access"
        assert len(result.facts) == 0
        # Proof bundle should reflect the denial
        proof = result.to_proof_bundle()
        assert proof["authorization_basis"]["allowed"] is False
        assert len(proof["authorization_basis"]["bridge_effectiveness"]) == 1
        assert proof["authorization_basis"]["bridge_effectiveness"][0]["reason"] == "bridge_not_yet_known"

    def test_query_allowed_when_bridge_effective(self):
        """Query should return facts when bridge is known and active."""
        chain = self._setup_chain_with_bridge_and_fact(
            bridge_system_time=T0,
            bridge_valid_from=T0
        )
        scholar = create_scholar(chain)

        # Query at T1 (bridge known and active)
        result = scholar.query_facts(
            requester_namespace="corp",
            namespace="partner",
            subject="entity:partner_data",
            predicate="has_value",
            at_valid_time=T1,
            as_of_system_time=T2,
            requester_id="principal:corp"
        )

        assert result.authorization.allowed is True
        assert result.authorization.reason == "bridge"
        assert len(result.facts) == 1
        assert result.facts[0].fact.object == "secret_info"

        # Proof bundle should reflect authorization
        proof = result.to_proof_bundle()
        assert proof["authorization_basis"]["allowed"] is True
        assert proof["authorization_basis"]["bridge_effectiveness"][0]["effective"] is True
        assert proof["authorization_basis"]["bridge_effectiveness"][0]["reason"] == "authorized"


class TestProofBundleCanonical:
    """
    Tests ensuring proof bundles are byte-stable and canonical.
    """

    def test_proof_bundle_identical_across_calls(self):
        """Calling to_proof_bundle() twice should yield identical output."""
        chain = create_chain_with_genesis("corp", T0)
        scholar = create_scholar(chain)

        result = scholar.query_facts(
            requester_namespace="corp",
            namespace="corp",
            at_valid_time=T1,
            as_of_system_time=T1,
            requester_id="principal:corp"
        )

        proof1 = result.to_proof_bundle()
        proof2 = result.to_proof_bundle()

        assert proof1 == proof2

    def test_proof_bundle_has_required_v13_fields(self):
        """Proof bundle should include v1.3 required fields."""
        chain = create_chain_with_genesis("corp", T0)
        scholar = create_scholar(chain)

        result = scholar.query_facts(
            requester_namespace="corp",
            namespace="corp",
            at_valid_time=T1,
            as_of_system_time=T1,
            requester_id="principal:corp"
        )

        proof = result.to_proof_bundle()

        # v1.3 required fields
        assert "time_filters" in proof
        assert "at_valid_time" in proof["time_filters"]
        assert "as_of_system_time" in proof["time_filters"]
        assert proof["time_filters"]["at_valid_time"] == T1
        assert proof["time_filters"]["as_of_system_time"] == T1

        assert "bridge_effectiveness" in proof["authorization_basis"]
        assert proof["scholar_version"] == "1.3"

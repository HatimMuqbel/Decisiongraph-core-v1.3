"""
Adversarial Test Suite: Bridge Time-Travel (SEC-05)

Tests that queries using as_of_system_time cannot bypass authorization
by querying a point in time before the bridge was created.

Requirements tested:
- SEC-05: Bridge time-travel attack fails with DG_UNAUTHORIZED
- Query with as_of_system_time before bridge creation fails
- Bridge temporal logic enforces both clocks (knowledge & validity)
- Cross-namespace queries without bridge fail
- Revoked bridges block access

Attack vectors:
1. Time-travel before bridge creation (system_time attack)
2. Time-travel before bridge activation (valid_from attack)
3. Time-travel after bridge expiration (valid_to attack)
4. Cross-namespace query without bridge
5. Query using revoked bridge
"""

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decisiongraph import (
    create_chain,
    create_scholar,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    CellType,
    SourceQuality,
    UnauthorizedError,
    NamespaceMetadata,
    compute_rule_logic_hash,
    is_bridge_effective,
    BridgeEffectivenessReason
)
from test_utils import T0, T1, T2, T3


def create_namespace_cell(
    chain,
    namespace: str,
    owner: str,
    system_time: str,
    prev_cell_hash: str
):
    """Helper to create namespace definition cell"""
    metadata = NamespaceMetadata(
        owner=owner,
        sensitivity="internal",
        description=f"Namespace: {namespace}"
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
    chain,
    from_namespace: str,
    to_namespace: str,
    system_time: str,
    valid_from: str,
    valid_to: str,
    prev_cell_hash: str
):
    """Helper to create bridge rule cell"""
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


class TestBridgeTimeTravelAttack:
    """SEC-05: Bridge time-travel attacks fail with appropriate errors"""

    def test_query_before_bridge_creation_fails(self):
        """Query with as_of_system_time before bridge creation detects attack"""
        # Timeline:
        # T0: Genesis + namespaces created
        # T1: Facts added to corp.hr
        # T2: Bridge created from corp.audit to corp.hr
        # Attack: Query at as_of_system_time=T1 (before bridge)

        # Create chain at T0
        chain = create_chain("test_graph", root_namespace="corp", system_time=T0)

        # Create corp.hr namespace at T0
        ns_hr = create_namespace_cell(
            chain, "corp.hr", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_hr)

        # Create corp.audit namespace at T0
        ns_audit = create_namespace_cell(
            chain, "corp.audit", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_audit)

        # Add fact to corp.hr at T1
        fact_hr = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:alice",
                predicate="has_salary",
                object="75000",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            )
        )
        chain.append(fact_hr)

        # Create bridge from corp.audit to corp.hr at T2 (after facts exist)
        bridge = create_bridge_cell(
            chain, "corp.audit", "corp.hr", T2, T2, None, chain.cells[-1].cell_id
        )
        chain.append(bridge)

        # Create scholar
        scholar = create_scholar(chain)

        # Attack: Query with as_of_system_time=T1 (before bridge at T2)
        # This should fail because bridge wasn't known at T1
        result = scholar.query_facts(
            requester_namespace="corp.audit",
            namespace="corp.hr",
            as_of_system_time=T1,  # Before bridge creation
            at_valid_time=T2,
            requester_id="attacker:eve"
        )

        # Authorization should be denied
        proof_bundle = result.to_proof_bundle()
        assert proof_bundle["authorization_basis"]["allowed"] is False
        assert proof_bundle["authorization_basis"]["reason"] == "no_access"

        # Verify bridge effectiveness check
        # Bridge should be marked as "not yet known"
        bridge_effectiveness = proof_bundle["authorization_basis"]["bridge_effectiveness"]
        if bridge_effectiveness:
            # If bridge was considered, it should be marked ineffective
            assert any(
                be["effective"] is False and
                be["reason"] == "bridge_not_yet_known"
                for be in bridge_effectiveness
            )

    def test_query_after_bridge_creation_succeeds(self):
        """Query with as_of_system_time after bridge creation succeeds"""
        # Timeline:
        # T0: Genesis + namespaces
        # T1: Bridge created
        # T2: Query at as_of_system_time=T2 (after bridge)

        chain = create_chain("test_graph", root_namespace="corp", system_time=T0)

        # Create namespaces
        ns_hr = create_namespace_cell(
            chain, "corp.hr", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_hr)

        ns_audit = create_namespace_cell(
            chain, "corp.audit", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_audit)

        # Create bridge at T1
        bridge = create_bridge_cell(
            chain, "corp.audit", "corp.hr", T1, T1, None, chain.cells[-1].cell_id
        )
        chain.append(bridge)

        # Create scholar
        scholar = create_scholar(chain)

        # Query with as_of_system_time=T2 (after bridge creation)
        result = scholar.query_facts(
            requester_namespace="corp.audit",
            namespace="corp.hr",
            as_of_system_time=T2,  # After bridge
            at_valid_time=T2,
            requester_id="auditor:alice"
        )

        # Authorization should succeed
        proof_bundle = result.to_proof_bundle()
        assert proof_bundle["authorization_basis"]["allowed"] is True

    def test_query_before_bridge_valid_from_fails(self):
        """Query before bridge valid_from fails (Clock B check)"""
        # Timeline:
        # T0: Genesis + namespaces
        # T1: Bridge created but valid_from=T2 (future activation)
        # Attack: Query at at_valid_time=T1 (before bridge active)

        chain = create_chain("test_graph", root_namespace="corp", system_time=T0)

        # Create namespaces
        ns_hr = create_namespace_cell(
            chain, "corp.hr", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_hr)

        ns_audit = create_namespace_cell(
            chain, "corp.audit", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_audit)

        # Create bridge at T1, but valid only from T2 onwards
        bridge = create_bridge_cell(
            chain, "corp.audit", "corp.hr",
            system_time=T1,
            valid_from=T2,  # Future activation
            valid_to=None,
            prev_cell_hash=chain.cells[-1].cell_id
        )
        chain.append(bridge)

        # Create scholar
        scholar = create_scholar(chain)

        # Attack: Query at at_valid_time=T1 (before bridge is valid)
        result = scholar.query_facts(
            requester_namespace="corp.audit",
            namespace="corp.hr",
            as_of_system_time=T2,  # Bridge is known
            at_valid_time=T1,  # But not yet valid
            requester_id="attacker:bob"
        )

        # Authorization should fail
        proof_bundle = result.to_proof_bundle()
        assert proof_bundle["authorization_basis"]["allowed"] is False

    def test_query_after_bridge_expiration_fails(self):
        """Query after bridge valid_to fails (Clock B check)"""
        # Timeline:
        # T0: Genesis + namespaces
        # T1: Bridge created, valid from T1 to T2
        # T2: Bridge expires
        # Attack: Query at at_valid_time=T3 (after expiration)

        chain = create_chain("test_graph", root_namespace="corp", system_time=T0)

        # Create namespaces
        ns_hr = create_namespace_cell(
            chain, "corp.hr", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_hr)

        ns_audit = create_namespace_cell(
            chain, "corp.audit", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_audit)

        # Create bridge valid from T1 to T2
        bridge = create_bridge_cell(
            chain, "corp.audit", "corp.hr",
            system_time=T1,
            valid_from=T1,
            valid_to=T2,  # Expires at T2
            prev_cell_hash=chain.cells[-1].cell_id
        )
        chain.append(bridge)

        # Create scholar
        scholar = create_scholar(chain)

        # Attack: Query at at_valid_time=T3 (after expiration)
        result = scholar.query_facts(
            requester_namespace="corp.audit",
            namespace="corp.hr",
            as_of_system_time=T3,  # Bridge is known
            at_valid_time=T3,  # But expired
            requester_id="attacker:charlie"
        )

        # Authorization should fail
        proof_bundle = result.to_proof_bundle()
        assert proof_bundle["authorization_basis"]["allowed"] is False


class TestAuthorizationBypassAttempts:
    """Various authorization bypass attempts"""

    def test_cross_namespace_without_bridge_fails(self):
        """Cross-namespace query without bridge fails"""
        chain = create_chain("test_graph", root_namespace="corp", system_time=T0)

        # Create two namespaces but NO bridge
        ns_hr = create_namespace_cell(
            chain, "corp.hr", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_hr)

        ns_audit = create_namespace_cell(
            chain, "corp.audit", "corp", T0, chain.cells[-1].cell_id
        )
        chain.append(ns_audit)

        # Add fact to corp.hr
        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:alice",
                predicate="has_salary",
                object="80000",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            )
        )
        chain.append(fact)

        # Create scholar
        scholar = create_scholar(chain)

        # Attempt cross-namespace query without bridge
        result = scholar.query_facts(
            requester_namespace="corp.audit",
            namespace="corp.hr",
            requester_id="attacker:dave"
        )

        # Should fail - no bridge
        proof_bundle = result.to_proof_bundle()
        assert proof_bundle["authorization_basis"]["allowed"] is False
        assert proof_bundle["authorization_basis"]["reason"] == "no_access"

    def test_is_bridge_effective_detects_time_travel(self):
        """is_bridge_effective() directly detects time-travel attacks"""
        chain = create_chain("test_graph", root_namespace="corp", system_time=T0)

        # Create bridge at T2
        bridge = create_bridge_cell(
            chain, "corp.audit", "corp.hr",
            system_time=T2,
            valid_from=T2,
            valid_to=None,
            prev_cell_hash=chain.cells[-1].cell_id
        )

        # Test: Bridge not yet known at T1
        effective, reason = is_bridge_effective(bridge, at_valid_time=T2, as_of_system_time=T1)
        assert effective is False
        assert reason == BridgeEffectivenessReason.BRIDGE_NOT_YET_KNOWN

        # Test: Bridge known at T2
        effective, reason = is_bridge_effective(bridge, at_valid_time=T2, as_of_system_time=T2)
        assert effective is True
        assert reason == BridgeEffectivenessReason.AUTHORIZED

        # Test: Bridge known at T3
        effective, reason = is_bridge_effective(bridge, at_valid_time=T3, as_of_system_time=T3)
        assert effective is True
        assert reason == BridgeEffectivenessReason.AUTHORIZED

    def test_is_bridge_effective_detects_not_active(self):
        """is_bridge_effective() detects bridge not yet active"""
        chain = create_chain("test_graph", root_namespace="corp", system_time=T0)

        # Create bridge at T1, valid from T2
        bridge = create_bridge_cell(
            chain, "corp.audit", "corp.hr",
            system_time=T1,
            valid_from=T2,  # Not active until T2
            valid_to=None,
            prev_cell_hash=chain.cells[-1].cell_id
        )

        # Test: Bridge known but not active at T1
        effective, reason = is_bridge_effective(bridge, at_valid_time=T1, as_of_system_time=T2)
        assert effective is False
        assert reason == BridgeEffectivenessReason.BRIDGE_NOT_ACTIVE

    def test_is_bridge_effective_detects_expired(self):
        """is_bridge_effective() detects expired bridge"""
        chain = create_chain("test_graph", root_namespace="corp", system_time=T0)

        # Create bridge valid from T1 to T2
        bridge = create_bridge_cell(
            chain, "corp.audit", "corp.hr",
            system_time=T1,
            valid_from=T1,
            valid_to=T2,  # Expires at T2
            prev_cell_hash=chain.cells[-1].cell_id
        )

        # Test: Bridge expired at T3
        effective, reason = is_bridge_effective(bridge, at_valid_time=T3, as_of_system_time=T3)
        assert effective is False
        assert reason == BridgeEffectivenessReason.BRIDGE_EXPIRED

    def test_is_bridge_effective_detects_revoked(self):
        """is_bridge_effective() detects revoked bridge"""
        chain = create_chain("test_graph", root_namespace="corp", system_time=T0)

        # Create valid bridge
        bridge = create_bridge_cell(
            chain, "corp.audit", "corp.hr",
            system_time=T1,
            valid_from=T1,
            valid_to=None,
            prev_cell_hash=chain.cells[-1].cell_id
        )

        # Test: Revoked bridge
        effective, reason = is_bridge_effective(
            bridge, at_valid_time=T2, as_of_system_time=T2, is_revoked=True
        )
        assert effective is False
        assert reason == BridgeEffectivenessReason.BRIDGE_REVOKED

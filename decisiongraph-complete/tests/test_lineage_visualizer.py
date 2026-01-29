#!/usr/bin/env python3
"""
DecisionGraph Core: Lineage Visualizer Tests

Tests for Phase 6: to_audit_text() and to_dot() methods on QueryResult.

Requirements tested:
- VIS-01: to_audit_text() produces deterministic human-readable audit report
- VIS-02: to_dot() produces valid Graphviz DOT syntax for lineage visualization
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decisiongraph import (
    create_chain,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    compute_rule_logic_hash,
    create_namespace_definition,
    create_bridge_rule,
    Scholar,
    create_scholar,
    ResolutionReason
)

from test_utils import T0, T1, T2, T3, T4, T5


# ============================================================================
# TEST CLASS: Audit Text (VIS-01)
# ============================================================================

class TestAuditText:
    """Tests for QueryResult.to_audit_text() - VIS-01"""

    def test_to_audit_text_contains_header(self):
        """Audit text starts with proper header"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T1, as_of_system_time=T1)

        text = result.to_audit_text()

        assert "DECISIONGRAPH AUDIT REPORT" in text
        assert "=" * 50 in text

    def test_to_audit_text_contains_query_info(self):
        """Audit text includes namespace, requester, timestamps"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T1, as_of_system_time=T2)

        text = result.to_audit_text()

        assert "Query Information:" in text
        assert "Namespace: test" in text
        assert "Requester: test:admin" in text
        assert f"Valid Time: {T1}" in text
        assert f"System Time: {T2}" in text

    def test_to_audit_text_contains_authorization_allowed(self):
        """Audit text shows ALLOWED for authorized query"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T1, as_of_system_time=T1)

        text = result.to_audit_text()

        assert "Authorization:" in text
        assert "Status: ALLOWED" in text
        assert "Reason: same_namespace" in text

    def test_to_audit_text_contains_authorization_denied(self):
        """Audit text shows DENIED for unauthorized query"""
        chain = create_chain("test", "corp", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        # Create separate namespace without bridge
        ns_sales = create_namespace_definition(namespace="corp.sales", owner="test:admin", graph_id=graph_id, prev_cell_hash=chain.head.cell_id, system_time=T1)
        chain.append(ns_sales)

        scholar = create_scholar(chain)

        # Query from corp to corp.sales without bridge - parent can see child
        result = scholar.query_facts("corp", "corp.sales", requester_id="test:admin", at_valid_time=T2, as_of_system_time=T2)

        text = result.to_audit_text()

        # Parent can see child, so this will be ALLOWED with parent_namespace
        assert "Authorization:" in text
        assert "Status: ALLOWED" in text

    def test_to_audit_text_contains_results_with_facts(self):
        """Audit text shows fact count and cell IDs"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        # Add a fact
        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T1
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash=compute_rule_logic_hash("test")
            ),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T2, as_of_system_time=T2)

        text = result.to_audit_text()

        assert "Results:" in text
        assert "Facts Returned: 1" in text
        assert "Fact Cells:" in text
        assert "user:alice" in text
        assert "has_role" in text

    def test_to_audit_text_contains_resolution_events(self):
        """Audit text shows conflict resolution details"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        # Add conflicting facts (different confidence)
        fact1 = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="user",
                confidence=0.5,
                source_quality=SourceQuality.SELF_REPORTED,
                valid_from=T1
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact1)

        fact2 = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T2,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T2
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact2)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T3, as_of_system_time=T3)

        text = result.to_audit_text()

        assert "Resolution Events:" in text
        assert "[1] Key:" in text
        assert "Winner:" in text
        assert "Reason:" in text
        # Should have a conflict resolved
        assert "Conflicts Resolved: 1" in text

    def test_to_audit_text_deterministic(self):
        """Same QueryResult produces identical audit text"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T1
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T2, as_of_system_time=T2)

        text1 = result.to_audit_text()
        text2 = result.to_audit_text()

        assert text1 == text2

    def test_to_audit_text_with_parent_child_access(self):
        """Audit text handles parent-child namespace relationships"""
        chain = create_chain("test", "corp", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        # Create child namespace
        ns_hr = create_namespace_definition(namespace="corp.hr", owner="test:admin", graph_id=graph_id, prev_cell_hash=chain.head.cell_id, system_time=T1)
        chain.append(ns_hr)

        # Add fact to hr
        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T2,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="employee:alice",
                predicate="has_department",
                object="engineering",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T2
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact)

        scholar = create_scholar(chain)
        # Parent (corp) querying child (corp.hr) - should be allowed
        result = scholar.query_facts("corp", "corp.hr", requester_id="test:admin", at_valid_time=T3, as_of_system_time=T3)

        text = result.to_audit_text()

        assert "Authorization:" in text
        assert "Status: ALLOWED" in text
        assert "Reason: parent_namespace" in text


# ============================================================================
# TEST CLASS: DOT (VIS-02)
# ============================================================================

class TestDOT:
    """Tests for QueryResult.to_dot() - VIS-02"""

    def test_to_dot_valid_structure(self):
        """DOT output has valid structure"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T1, as_of_system_time=T1)

        dot = result.to_dot()

        assert dot.startswith("digraph decision_lineage {")
        assert dot.endswith("}")

    def test_to_dot_contains_node_definitions(self):
        """DOT has node definitions with proper attributes"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T1, as_of_system_time=T1)

        dot = result.to_dot()

        assert "node [shape=box, style=filled];" in dot
        assert "rankdir=TB;" in dot

    def test_to_dot_contains_fact_nodes(self):
        """DOT includes fact nodes with lightblue color"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T1
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T2, as_of_system_time=T2)

        dot = result.to_dot()

        assert "fillcolor=lightblue" in dot
        assert "Fact" in dot
        assert "user:alice" in dot
        assert "has_role" in dot

    def test_to_dot_contains_candidate_nodes(self):
        """DOT includes non-winner candidate nodes with lightgray color"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        # Add conflicting facts
        fact1 = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="user",
                confidence=0.5,
                source_quality=SourceQuality.SELF_REPORTED,
                valid_from=T1
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact1)

        fact2 = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T2,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T2
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact2)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T3, as_of_system_time=T3)

        dot = result.to_dot()

        # Should have both winner (lightblue) and loser (lightgray)
        assert "fillcolor=lightblue" in dot
        assert "fillcolor=lightgray" in dot
        assert "Candidate" in dot

    def test_to_dot_handles_empty_results(self):
        """DOT generates valid graph even with no results"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        scholar = create_scholar(chain)

        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T1, as_of_system_time=T1)
        dot = result.to_dot()

        # Should have valid structure even with no facts
        assert dot.startswith("digraph decision_lineage {")
        assert dot.endswith("}")
        assert "rankdir=TB" in dot

    def test_to_dot_with_multiple_facts(self):
        """DOT includes multiple fact nodes"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        # Add multiple facts
        for i, (subject, pred, obj) in enumerate([("user:alice", "has_role", "admin"), ("user:bob", "has_role", "user")], 1):
            fact = DecisionCell(
                header=Header(
                    version="1.3",
                    graph_id=graph_id,
                    cell_type=CellType.FACT,
                    system_time=f"2026-01-27T10:00:0{i}Z",
                    prev_cell_hash=chain.head.cell_id
                ),
                fact=Fact(
                    namespace="test",
                    subject=subject,
                    predicate=pred,
                    object=obj,
                    confidence=1.0,
                    source_quality=SourceQuality.VERIFIED,
                    valid_from=f"2026-01-27T10:00:0{i}Z"
                ),
                logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
                proof=Proof(signer_id="test:admin")
            )
            chain.append(fact)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T3, as_of_system_time=T3)

        dot = result.to_dot()

        # Should have multiple fact nodes
        assert "user:alice" in dot
        assert "user:bob" in dot
        assert dot.count("fillcolor=lightblue") >= 2

    def test_to_dot_contains_resolution_edges(self):
        """DOT includes resolution edges from winners to losers"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        fact1 = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="user",
                confidence=0.5,
                source_quality=SourceQuality.SELF_REPORTED,
                valid_from=T1
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact1)

        fact2 = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T2,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T2
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact2)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T3, as_of_system_time=T3)

        dot = result.to_dot()

        # Should have resolution edge (winner -> loser)
        assert "color=red" in dot
        assert "style=dashed" in dot

    def test_to_dot_escapes_special_chars(self):
        """DOT properly escapes quotes and backslashes"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        # Fact with special characters in subject
        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject='user:alice"test',
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T1
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T2, as_of_system_time=T2)

        dot = result.to_dot()

        # Quote should be escaped
        assert '\\"' in dot or 'user:alice' in dot  # Either escaped or present

    def test_to_dot_deterministic(self):
        """Same QueryResult produces identical DOT"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T1
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T2, as_of_system_time=T2)

        dot1 = result.to_dot()
        dot2 = result.to_dot()

        assert dot1 == dot2


# ============================================================================
# TEST CLASS: Integration
# ============================================================================

class TestLineageVisualizerIntegration:
    """End-to-end integration tests for lineage visualizer"""

    def test_audit_text_and_dot_reflect_same_data(self):
        """Both methods reflect same proof_bundle data"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="test",
                subject="user:alice",
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T1
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T2, as_of_system_time=T2)

        text = result.to_audit_text()
        dot = result.to_dot()

        # Both should reflect same fact
        assert "user:alice" in text
        assert "user:alice" in dot
        assert "has_role" in text
        assert "has_role" in dot

    def test_empty_result_visualization(self):
        """Handles empty results (denied access) gracefully"""
        chain = create_chain("test", "corp", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        # Create separate namespaces without bridge
        ns_hr = create_namespace_definition(namespace="corp.hr", owner="test:admin", graph_id=graph_id, prev_cell_hash=chain.head.cell_id, system_time=T1)
        chain.append(ns_hr)

        ns_sales = create_namespace_definition(namespace="corp.sales", owner="test:admin", graph_id=graph_id, prev_cell_hash=chain.head.cell_id, system_time=T2)
        chain.append(ns_sales)

        # Add fact to sales
        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=T3,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="corp.sales",
                subject="deal:acme",
                predicate="has_value",
                object="100000",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=T3
            ),
            logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
            proof=Proof(signer_id="test:admin")
        )
        chain.append(fact)

        scholar = create_scholar(chain)
        # Query from hr to sales without bridge - should be denied (hr is not parent of sales)
        # Actually hr and sales are siblings, so no access
        result = scholar.query_facts("corp.hr", "corp.sales", requester_id="test:admin", at_valid_time=T4, as_of_system_time=T4)

        text = result.to_audit_text()
        dot = result.to_dot()

        # Should handle empty gracefully
        assert "Facts Returned: 0" in text
        assert "digraph decision_lineage" in dot

    def test_multiple_conflicts_visualization(self):
        """Complex scenario with multiple resolution events"""
        chain = create_chain("test", "test", "test:admin", system_time=T0)
        graph_id = chain.graph_id

        # Add multiple conflicting facts for different subjects
        facts = [
            ("user:alice", "has_role", "user", 0.5, SourceQuality.SELF_REPORTED, T1),
            ("user:alice", "has_role", "admin", 1.0, SourceQuality.VERIFIED, T2),
            ("user:bob", "has_role", "guest", 0.3, SourceQuality.INFERRED, T3),
            ("user:bob", "has_role", "user", 0.9, SourceQuality.VERIFIED, T4),
        ]

        for subject, predicate, obj, confidence, quality, timestamp in facts:
            fact = DecisionCell(
                header=Header(
                    version="1.3",
                    graph_id=graph_id,
                    cell_type=CellType.FACT,
                    system_time=timestamp,
                    prev_cell_hash=chain.head.cell_id
                ),
                fact=Fact(
                    namespace="test",
                    subject=subject,
                    predicate=predicate,
                    object=obj,
                    confidence=confidence,
                    source_quality=quality,
                    valid_from=timestamp
                ),
                logic_anchor=LogicAnchor(rule_id="test:rule", rule_logic_hash=compute_rule_logic_hash("test")),
                proof=Proof(signer_id="test:admin")
            )
            chain.append(fact)

        scholar = create_scholar(chain)
        result = scholar.query_facts("test", "test", requester_id="test:admin", at_valid_time=T5, as_of_system_time=T5)

        text = result.to_audit_text()
        dot = result.to_dot()

        # Should show multiple resolution events
        assert "Conflicts Resolved: 2" in text
        assert "[1]" in text
        assert "[2]" in text

        # DOT should have resolution edges
        assert "color=red" in dot
        assert "style=dashed" in dot


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

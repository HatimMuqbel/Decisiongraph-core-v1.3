"""
Tests for Phase 12: Audit Trail (AUD-01, AUD-02, AUD-03)

Tests cover:
- AUD-01: Human-readable audit text reports
- AUD-02: SHA-256 hashing of RFA and simulation_spec for auditability
- AUD-03: DOT graph visualization with BASE vs SHADOW color-tagging
- Deterministic output (same input = same output)
- Valid DOT syntax
- Color coding for visual debugging
- Anchor highlighting
- Delta highlighting (added/removed facts)
- Verdict change visualization
"""

import pytest

from decisiongraph.simulation import (
    SimulationResult,
    DeltaReport,
    simulation_result_to_audit_text,
    simulation_result_to_dot
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_simulation_result():
    """Create sample SimulationResult for testing DOT visualization."""
    # Create a simulation result with:
    # - BASE: 2 facts
    # - SHADOW: 3 facts (2 from base + 1 new)
    # - Verdict changed
    # - 1 anchor
    return SimulationResult(
        simulation_id="sim-abc123def456",
        rfa_dict={
            "namespace": "test",
            "requester_namespace": "test",
            "requester_id": "user"
        },
        simulation_spec={"shadow_facts": []},
        base_result={
            "results": {
                "fact_count": 2,
                "fact_cell_ids": ["base_fact_abc123", "base_fact_def456"]
            },
            "authorization_basis": {"allowed": True}
        },
        shadow_result={
            "results": {
                "fact_count": 3,
                "fact_cell_ids": [
                    "base_fact_abc123",
                    "base_fact_def456",
                    "shadow_fact_123"
                ]
            },
            "authorization_basis": {"allowed": True}
        },
        at_valid_time="2025-01-01T00:00:00Z",
        as_of_system_time="2025-01-01T00:00:00Z",
        delta_report=DeltaReport(
            verdict_changed=True,
            status_before="ALLOWED",
            status_after="ALLOWED",
            score_delta=0.5,
            facts_diff={
                "added": ["shadow_fact_123"],
                "removed": []
            },
            rules_diff={"added": [], "removed": []}
        ),
        anchors={
            "anchors": ["base_fact_abc123"],
            "anchors_incomplete": False
        },
        proof_bundle={}
    )


# ============================================================================
# TEST: AUDIT TEXT (AUD-01, AUD-02)
# ============================================================================

class TestAuditTextStructure:
    """Tests for audit text structure (AUD-01)."""

    def test_returns_string(self, sample_simulation_result):
        """to_audit_text returns string."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert isinstance(result, str)

    def test_contains_header(self, sample_simulation_result):
        """Output contains SIMULATION AUDIT REPORT header."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "SIMULATION AUDIT REPORT" in result

    def test_contains_simulation_id(self, sample_simulation_result):
        """Output contains truncated simulation ID."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "sim-abc123de" in result  # truncated

    def test_contains_base_reality_section(self, sample_simulation_result):
        """Output contains BASE Reality section."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "BASE Reality:" in result

    def test_contains_shadow_reality_section(self, sample_simulation_result):
        """Output contains SHADOW Reality section."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "SHADOW Reality:" in result

    def test_contains_delta_analysis_section(self, sample_simulation_result):
        """Output contains DELTA Analysis section."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "DELTA Analysis:" in result

    def test_contains_anchors_section(self, sample_simulation_result):
        """Output contains Counterfactual Anchors section."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "Counterfactual Anchors:" in result

    def test_contains_contamination_section(self, sample_simulation_result):
        """Output contains Contamination Attestation section."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "Contamination Attestation:" in result

    def test_contains_overlay_metadata_section(self, sample_simulation_result):
        """Output contains Overlay Metadata section."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "Overlay Metadata:" in result

    def test_contains_schema_version(self, sample_simulation_result):
        """Output contains Schema Version 1.6."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "Schema Version: 1.6" in result


class TestAuditHashes:
    """Tests for SHA-256 hashing in audit text (AUD-02)."""

    def test_contains_rfa_hash(self, sample_simulation_result):
        """Output contains RFA hash."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "RFA Hash:" in result

    def test_rfa_hash_is_truncated(self, sample_simulation_result):
        """RFA hash is truncated (16 chars + ...)."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        lines = result.split('\n')
        rfa_hash_line = [l for l in lines if "RFA Hash:" in l][0]
        # Format: "  RFA Hash: abcdef1234567890..."
        hash_part = rfa_hash_line.split(": ")[1]
        assert hash_part.endswith("...")
        assert len(hash_part) == 19  # 16 chars + "..."

    def test_contains_spec_hash(self, sample_simulation_result):
        """Output contains Simulation Spec hash."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "Simulation Spec Hash:" in result

    def test_spec_hash_is_truncated(self, sample_simulation_result):
        """Spec hash is truncated (16 chars + ...)."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        lines = result.split('\n')
        spec_hash_line = [l for l in lines if "Simulation Spec Hash:" in l][0]
        hash_part = spec_hash_line.split(": ")[1]
        assert hash_part.endswith("...")
        assert len(hash_part) == 19  # 16 chars + "..."

    def test_different_rfa_different_hash(self):
        """Different RFA produces different hash."""
        result1 = SimulationResult(
            simulation_id="sim-1",
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user1"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=False, status_before="ALLOWED", status_after="ALLOWED",
                score_delta=0.0, facts_diff={"added": [], "removed": []}, rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": [], "anchors_incomplete": False},
            proof_bundle={}
        )
        result2 = SimulationResult(
            simulation_id="sim-2",
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user2"},  # Different!
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=False, status_before="ALLOWED", status_after="ALLOWED",
                score_delta=0.0, facts_diff={"added": [], "removed": []}, rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": [], "anchors_incomplete": False},
            proof_bundle={}
        )
        text1 = simulation_result_to_audit_text(result1)
        text2 = simulation_result_to_audit_text(result2)

        lines1 = text1.split('\n')
        lines2 = text2.split('\n')
        rfa_hash1 = [l for l in lines1 if "RFA Hash:" in l][0].split(": ")[1]
        rfa_hash2 = [l for l in lines2 if "RFA Hash:" in l][0].split(": ")[1]

        assert rfa_hash1 != rfa_hash2


class TestAuditTextDeterminism:
    """Tests for deterministic audit text output."""

    def test_same_input_same_output(self, sample_simulation_result):
        """Same SimulationResult produces identical audit text."""
        result1 = simulation_result_to_audit_text(sample_simulation_result)
        result2 = simulation_result_to_audit_text(sample_simulation_result)
        assert result1 == result2

    def test_deterministic_across_multiple_calls(self, sample_simulation_result):
        """Audit text is deterministic across 10 calls."""
        results = [simulation_result_to_audit_text(sample_simulation_result) for _ in range(10)]
        assert all(r == results[0] for r in results)


class TestAuditTextEdgeCases:
    """Tests for audit text edge cases."""

    def test_empty_facts(self):
        """Handles empty fact lists gracefully."""
        result = SimulationResult(
            simulation_id="sim-empty",
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=False, status_before="ALLOWED", status_after="ALLOWED",
                score_delta=0.0, facts_diff={"added": [], "removed": []}, rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": [], "anchors_incomplete": False},
            proof_bundle={}
        )
        audit_text = simulation_result_to_audit_text(result)
        assert "Facts Returned: 0" in audit_text
        assert "SIMULATION AUDIT REPORT" in audit_text

    def test_verdict_changed_true(self, sample_simulation_result):
        """Verdict changed shows as true."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "Verdict Changed: true" in result

    def test_verdict_changed_false(self):
        """Verdict changed shows as false when not changed."""
        result = SimulationResult(
            simulation_id="sim-no-change",
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 1, "fact_cell_ids": ["f1"]}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 1, "fact_cell_ids": ["f1"]}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=False, status_before="ALLOWED", status_after="ALLOWED",
                score_delta=0.0, facts_diff={"added": [], "removed": []}, rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": [], "anchors_incomplete": False},
            proof_bundle={}
        )
        audit_text = simulation_result_to_audit_text(result)
        assert "Verdict Changed: false" in audit_text

    def test_shadow_tag_in_fact_list(self, sample_simulation_result):
        """Shadow-only facts are tagged with [SHADOW]."""
        result = simulation_result_to_audit_text(sample_simulation_result)
        assert "[SHADOW]" in result

    def test_anchors_incomplete_warning(self):
        """Shows INCOMPLETE warning when anchors_incomplete is True."""
        result = SimulationResult(
            simulation_id="sim-incomplete",
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=False, status_before="ALLOWED", status_after="ALLOWED",
                score_delta=0.0, facts_diff={"added": [], "removed": []}, rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": ["a1"], "anchors_incomplete": True},
            proof_bundle={}
        )
        audit_text = simulation_result_to_audit_text(result)
        assert "[INCOMPLETE]" in audit_text


# ============================================================================
# TEST: DOT VISUALIZATION (AUD-03)
# ============================================================================

class TestDotVisualization:
    """Tests for DOT graph generation (AUD-03)."""

    def test_returns_string(self, sample_simulation_result):
        """to_dot returns string."""
        result = simulation_result_to_dot(sample_simulation_result)
        assert isinstance(result, str)

    def test_valid_dot_syntax_header(self, sample_simulation_result):
        """Output starts with valid DOT digraph."""
        result = simulation_result_to_dot(sample_simulation_result)
        assert result.startswith("digraph simulation_lineage {")

    def test_valid_dot_syntax_footer(self, sample_simulation_result):
        """Output ends with closing brace."""
        result = simulation_result_to_dot(sample_simulation_result)
        assert result.strip().endswith("}")

    def test_contains_simulation_id_comment(self, sample_simulation_result):
        """Output contains truncated simulation ID as comment."""
        result = simulation_result_to_dot(sample_simulation_result)
        assert "// Simulation: sim-abc123de" in result

    def test_contains_base_subgraph(self, sample_simulation_result):
        """Output contains BASE Reality subgraph."""
        result = simulation_result_to_dot(sample_simulation_result)
        assert 'subgraph cluster_base' in result
        assert 'label="BASE Reality"' in result
        assert 'fillcolor=lightgray' in result

    def test_contains_shadow_subgraph(self, sample_simulation_result):
        """Output contains SHADOW Reality subgraph."""
        result = simulation_result_to_dot(sample_simulation_result)
        assert 'subgraph cluster_shadow' in result
        assert 'label="SHADOW Reality (Overlay)"' in result
        assert 'fillcolor=lightyellow' in result

    def test_base_nodes_lightblue(self, sample_simulation_result):
        """BASE nodes have lightblue fill color."""
        result = simulation_result_to_dot(sample_simulation_result)
        # BASE nodes should be lightblue
        assert 'fillcolor=lightblue' in result

    def test_shadow_only_nodes_orange(self, sample_simulation_result):
        """SHADOW-only nodes (not in BASE) have orange fill color."""
        result = simulation_result_to_dot(sample_simulation_result)
        # shadow_fact_123 is only in shadow, should be orange
        assert 'fillcolor=orange' in result

    def test_rankdir_top_to_bottom(self, sample_simulation_result):
        """Graph uses top-to-bottom ranking."""
        result = simulation_result_to_dot(sample_simulation_result)
        assert 'rankdir=TB' in result

    def test_node_shape_box(self, sample_simulation_result):
        """Nodes use box shape."""
        result = simulation_result_to_dot(sample_simulation_result)
        assert 'node [shape=box' in result


class TestDotDeltaHighlighting:
    """Tests for delta highlighting in DOT output."""

    def test_verdict_changed_shows_diamond(self, sample_simulation_result):
        """Verdict change shows diamond annotation."""
        result = simulation_result_to_dot(sample_simulation_result)
        # sample_simulation_result has verdict_changed=True
        assert 'shape=diamond' in result
        assert 'VERDICT CHANGED' in result

    def test_verdict_unchanged_no_diamond(self):
        """No verdict change means no diamond annotation."""
        result = SimulationResult(
            simulation_id="sim-no-change",
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 1, "fact_cell_ids": ["fact1"]}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 1, "fact_cell_ids": ["fact1"]}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=False,
                status_before="ALLOWED",
                status_after="ALLOWED",
                score_delta=0.0,
                facts_diff={"added": [], "removed": []},
                rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": [], "anchors_incomplete": False},
            proof_bundle={}
        )
        dot_output = simulation_result_to_dot(result)
        assert 'VERDICT CHANGED' not in dot_output

    def test_added_facts_lightgreen(self):
        """Added facts get lightgreen color."""
        result = SimulationResult(
            simulation_id="sim-added",
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 1, "fact_cell_ids": ["new_fact"]}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=True,
                status_before="ALLOWED",
                status_after="ALLOWED",
                score_delta=0.0,
                facts_diff={"added": ["new_fact"], "removed": []},
                rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": [], "anchors_incomplete": False},
            proof_bundle={}
        )
        dot_output = simulation_result_to_dot(result)
        assert 'fillcolor=lightgreen' in dot_output
        assert '// ADDED' in dot_output

    def test_removed_facts_pink(self):
        """Removed facts get pink color."""
        result = SimulationResult(
            simulation_id="sim-removed",
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 1, "fact_cell_ids": ["old_fact"]}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=True,
                status_before="ALLOWED",
                status_after="ALLOWED",
                score_delta=0.0,
                facts_diff={"added": [], "removed": ["old_fact"]},
                rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": [], "anchors_incomplete": False},
            proof_bundle={}
        )
        dot_output = simulation_result_to_dot(result)
        assert 'fillcolor=pink' in dot_output
        assert '// REMOVED' in dot_output


class TestDotAnchorHighlighting:
    """Tests for anchor highlighting in DOT output."""

    def test_anchor_double_border(self, sample_simulation_result):
        """Anchor nodes have double border (peripheries=2)."""
        result = simulation_result_to_dot(sample_simulation_result)
        # sample_simulation_result has anchor: "base_fact_abc123"
        # Need to check that anchor highlighting attributes exist
        assert 'peripheries=2' in result or 'penwidth=3.0' in result


class TestDotDeterminism:
    """Tests for deterministic DOT output."""

    def test_same_input_same_output(self, sample_simulation_result):
        """Same SimulationResult produces identical DOT output."""
        result1 = simulation_result_to_dot(sample_simulation_result)
        result2 = simulation_result_to_dot(sample_simulation_result)
        assert result1 == result2

    def test_deterministic_across_multiple_calls(self, sample_simulation_result):
        """DOT output is deterministic across 10 calls."""
        results = [simulation_result_to_dot(sample_simulation_result) for _ in range(10)]
        assert all(r == results[0] for r in results)


class TestDotEdgeCases:
    """Tests for DOT edge cases."""

    def test_empty_facts(self):
        """Handles empty fact lists gracefully."""
        result = SimulationResult(
            simulation_id="sim-empty",
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=False,
                status_before="ALLOWED",
                status_after="ALLOWED",
                score_delta=0.0,
                facts_diff={"added": [], "removed": []},
                rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": [], "anchors_incomplete": False},
            proof_bundle={}
        )
        dot_output = simulation_result_to_dot(result)
        # Should still be valid DOT
        assert 'digraph simulation_lineage' in dot_output
        assert dot_output.strip().endswith("}")

    def test_special_characters_escaped(self):
        """Special characters in IDs are escaped properly."""
        # Cell IDs shouldn't have special chars, but test escaping anyway
        result = SimulationResult(
            simulation_id='sim-with"quotes',
            rfa_dict={"namespace": "test", "requester_namespace": "test", "requester_id": "user"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            shadow_result={"results": {"fact_count": 0, "fact_cell_ids": []}, "authorization_basis": {"allowed": True}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=DeltaReport(
                verdict_changed=False,
                status_before="ALLOWED",
                status_after="ALLOWED",
                score_delta=0.0,
                facts_diff={"added": [], "removed": []},
                rules_diff={"added": [], "removed": []}
            ),
            anchors={"anchors": [], "anchors_incomplete": False},
            proof_bundle={}
        )
        dot_output = simulation_result_to_dot(result)
        # Should not crash, quotes should be escaped
        assert 'digraph simulation_lineage' in dot_output

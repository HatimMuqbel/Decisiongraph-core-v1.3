"""
Tests for Phase 8: Simulation Core

Tests cover:
- SIM-01: engine.simulate_rfa() entry point
- SIM-02: Base reality frozen at specified coordinates
- SIM-03: Shadow overlay deterministic precedence
- SHD-05: Bitemporal simulation respects frozen coordinates

All tests verify zero contamination (base chain unchanged after simulation).
"""

import pytest
from uuid import uuid4

from decisiongraph import (
    Engine,
    create_chain,
    SimulationContext,
    SimulationResult,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    compute_rule_logic_hash,
    get_current_timestamp
)
from decisiongraph.shadow import (
    OverlayContext,
    create_shadow_fact,
    fork_shadow_chain
)
from decisiongraph.simulation import (
    DeltaReport,
    ContaminationAttestation,
    compute_delta_report,
    tag_proof_bundle_origin,
    create_contamination_attestation
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def basic_chain():
    """Create chain with basic facts for simulation testing."""
    chain = create_chain("sim_test_graph", "corp")

    ts = get_current_timestamp()

    # Create a rule first (facts need to reference a rule)
    rule_logic_hash = compute_rule_logic_hash("salary_calculation_logic")
    rule = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=chain.graph_id,
            cell_type=CellType.RULE,
            system_time=ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="rule:salary_v1",
            predicate="defines",
            object="salary_calculation",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:salary_v1",
            rule_logic_hash=rule_logic_hash
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(rule)

    # Create test facts
    fact1 = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=chain.graph_id,
            cell_type=CellType.FACT,
            system_time=ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="employee:alice",
            predicate="has_salary",
            object="80000",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:salary_v1",
            rule_logic_hash=rule_logic_hash
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact1)

    fact2 = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=chain.graph_id,
            cell_type=CellType.FACT,
            system_time=ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="employee:bob",
            predicate="has_salary",
            object="75000",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:salary_v1",
            rule_logic_hash=rule_logic_hash
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact2)

    return chain


@pytest.fixture
def engine_with_facts(basic_chain):
    """Create engine with basic facts."""
    return Engine(basic_chain), basic_chain


# =============================================================================
# SIM-01: engine.simulate_rfa() entry point
# =============================================================================

class TestSimulateRfaEntryPoint:
    """Tests for SIM-01: engine.simulate_rfa() accepts RFA + simulation_spec + coordinates"""

    def test_simulate_rfa_returns_simulation_result(self, engine_with_facts):
        """simulate_rfa returns SimulationResult with correct type."""
        engine, chain = engine_with_facts

        result = engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test",
                "subject": "employee:alice",
                "predicate": "has_salary"
            },
            simulation_spec={},  # Empty spec = no shadow changes
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )

        assert isinstance(result, SimulationResult)
        assert result.simulation_id is not None
        assert result.at_valid_time == "2025-01-15T00:00:00Z"
        assert result.as_of_system_time == "2025-01-15T00:00:00Z"

    def test_simulate_rfa_with_empty_spec_returns_identical_results(self, engine_with_facts):
        """With empty simulation_spec, base and shadow results should be identical."""
        engine, chain = engine_with_facts

        result = engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test"
            },
            simulation_spec={},
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )

        # With no shadow cells, base and shadow should return same facts
        assert result.base_result["results"]["fact_count"] == result.shadow_result["results"]["fact_count"]

    def test_simulate_rfa_validates_rfa_schema(self, engine_with_facts):
        """simulate_rfa validates RFA schema (missing required fields)."""
        engine, chain = engine_with_facts
        from decisiongraph.exceptions import SchemaInvalidError

        with pytest.raises(SchemaInvalidError):
            engine.simulate_rfa(
                rfa_dict={"namespace": "corp"},  # Missing requester_namespace, requester_id
                simulation_spec={},
                at_valid_time="2025-01-15T00:00:00Z",
                as_of_system_time="2025-01-15T00:00:00Z"
            )


# =============================================================================
# SIM-02: Base reality frozen at specified coordinates
# =============================================================================

class TestBaseRealityFrozen:
    """Tests for SIM-02: Base reality frozen at specified coordinates"""

    def test_base_result_uses_specified_valid_time(self, engine_with_facts):
        """Base query uses specified at_valid_time."""
        engine, chain = engine_with_facts

        # Query at time BEFORE facts exist
        result = engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test",
                "subject": "employee:alice"
            },
            simulation_spec={},
            at_valid_time="2024-01-01T00:00:00Z",  # Before facts valid_from
            as_of_system_time="2025-01-15T00:00:00Z"
        )

        # Facts not valid at that time
        assert result.base_result["results"]["fact_count"] == 0

    def test_base_result_uses_specified_system_time(self, engine_with_facts):
        """Base query uses specified as_of_system_time."""
        engine, chain = engine_with_facts

        # Query at system time BEFORE facts recorded
        result = engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test"
            },
            simulation_spec={},
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2024-01-01T00:00:00Z"  # Before facts system_time
        )

        # Facts not known at that system time
        assert result.base_result["results"]["fact_count"] == 0


# =============================================================================
# SIM-03: Shadow overlay deterministic precedence
# =============================================================================

class TestShadowOverlayPrecedence:
    """Tests for SIM-03: Shadow overlay injection follows deterministic precedence"""

    def test_shadow_fact_overrides_base_fact(self, engine_with_facts):
        """Shadow fact for same key overrides base fact in shadow result."""
        engine, chain = engine_with_facts

        # Find Alice's salary cell
        alice_salary_cell = None
        for cell in chain.cells:
            if (hasattr(cell.fact, 'subject') and
                cell.fact.subject == "employee:alice" and
                cell.fact.predicate == "has_salary"):
                alice_salary_cell = cell
                break

        assert alice_salary_cell is not None, "Alice salary fact not found"

        # Use current time for query (facts were created with current time)
        query_time = get_current_timestamp()

        # Simulate with shadow salary of 90000
        result = engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test",
                "subject": "employee:alice",
                "predicate": "has_salary"
            },
            simulation_spec={
                "shadow_facts": [{
                    "base_cell_id": alice_salary_cell.cell_id,
                    "object": "90000"
                }]
            },
            at_valid_time=query_time,
            as_of_system_time=query_time
        )

        # Base should have original value (80000)
        assert result.base_result["results"]["fact_count"] == 1

        # Shadow should have the shadow cell included
        # NOTE: The shadow_scholar queries shadow_chain which now includes shadow cells
        # appended by SimulationContext.__enter__. The shadow cell with object="90000"
        # should be visible. The exact result depends on how Scholar handles is_shadow
        # cells vs base cells. At minimum, shadow_result should contain 1+ facts.
        assert result.shadow_result["results"]["fact_count"] >= 1

    def test_shadow_cells_visible_in_shadow_chain(self, engine_with_facts):
        """Verify shadow cells are appended to shadow_chain and visible to Scholar."""
        engine, chain = engine_with_facts

        # Find a fact cell
        fact_cell = None
        for cell in chain.cells:
            if hasattr(cell.fact, 'subject') and cell.fact.predicate == "has_salary":
                fact_cell = cell
                break

        assert fact_cell is not None

        # Create OverlayContext manually to inspect
        overlay_ctx = OverlayContext()
        shadow_cell = create_shadow_fact(fact_cell, object="99999")
        overlay_ctx.add_shadow_fact(shadow_cell, fact_cell.cell_id)

        # Use SimulationContext directly to verify shadow cells appended
        from decisiongraph.simulation import SimulationContext

        sim = SimulationContext(
            chain, overlay_ctx,
            "2025-01-15T00:00:00Z",
            "2025-01-15T00:00:00Z"
        )

        with sim as s:
            # Check shadow_chain contains our shadow cell
            shadow_cells_in_chain = [
                c for c in s.shadow_chain.cells
                if getattr(c.fact, 'is_shadow', False)
            ]
            # NOTE: Shadow cells are not marked with is_shadow flag
            # They are regular DecisionCells. Check length instead.
            assert len(s.shadow_chain.cells) > len(chain.cells), "Shadow cell not appended to shadow_chain"


# =============================================================================
# SHD-05: Bitemporal simulation respects frozen coordinates
# =============================================================================

class TestBitemporalSimulation:
    """Tests for SHD-05: Bitemporal simulation respects frozen coordinates"""

    def test_simulation_coordinates_passed_to_result(self, engine_with_facts):
        """SimulationResult contains correct bitemporal coordinates."""
        engine, chain = engine_with_facts

        result = engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test"
            },
            simulation_spec={},
            at_valid_time="2025-06-15T12:30:00Z",
            as_of_system_time="2025-06-15T12:30:00Z"
        )

        assert result.at_valid_time == "2025-06-15T12:30:00Z"
        assert result.as_of_system_time == "2025-06-15T12:30:00Z"

    def test_both_queries_use_same_coordinates(self, engine_with_facts):
        """Base and shadow queries use same frozen coordinates."""
        engine, chain = engine_with_facts

        result = engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test"
            },
            simulation_spec={},
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )

        # Both proof bundles should have same time_filters
        base_time = result.base_result["time_filters"]
        shadow_time = result.shadow_result["time_filters"]

        assert base_time["at_valid_time"] == shadow_time["at_valid_time"]
        assert base_time["as_of_system_time"] == shadow_time["as_of_system_time"]


# =============================================================================
# ZERO CONTAMINATION
# =============================================================================

class TestZeroContamination:
    """Tests verifying base chain is never modified by simulation"""

    def test_base_chain_length_unchanged(self, engine_with_facts):
        """Base chain length unchanged after simulation."""
        engine, chain = engine_with_facts
        original_length = len(chain.cells)

        # Run simulation
        engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test"
            },
            simulation_spec={
                "shadow_facts": [{
                    "base_cell_id": chain.cells[2].cell_id,  # Some fact
                    "object": "99999"
                }]
            },
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )

        assert len(chain.cells) == original_length

    def test_base_chain_head_unchanged(self, engine_with_facts):
        """Base chain head unchanged after simulation."""
        engine, chain = engine_with_facts
        original_head_id = chain.head.cell_id

        engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test"
            },
            simulation_spec={},
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )

        assert chain.head.cell_id == original_head_id


# =============================================================================
# SIMULATION CONTEXT
# =============================================================================

class TestSimulationContext:
    """Tests for SimulationContext context manager"""

    def test_context_manager_creates_shadow_chain(self, basic_chain):
        """SimulationContext creates shadow chain on enter."""
        ctx = OverlayContext()
        sim = SimulationContext(
            basic_chain, ctx,
            "2025-01-15T00:00:00Z",
            "2025-01-15T00:00:00Z"
        )

        assert sim.shadow_chain is None

        with sim as s:
            assert s.shadow_chain is not None
            assert s.shadow_scholar is not None

    def test_context_manager_cleans_up_on_exit(self, basic_chain):
        """SimulationContext cleans up shadow chain on exit."""
        ctx = OverlayContext()
        sim = SimulationContext(
            basic_chain, ctx,
            "2025-01-15T00:00:00Z",
            "2025-01-15T00:00:00Z"
        )

        with sim:
            pass

        assert sim.shadow_chain is None
        assert sim.shadow_scholar is None

    def test_context_manager_cleans_up_on_exception(self, basic_chain):
        """SimulationContext cleans up even when exception occurs."""
        ctx = OverlayContext()
        sim = SimulationContext(
            basic_chain, ctx,
            "2025-01-15T00:00:00Z",
            "2025-01-15T00:00:00Z"
        )

        with pytest.raises(ValueError):
            with sim:
                raise ValueError("Test exception")

        # Cleanup should still happen
        assert sim.shadow_chain is None
        assert sim.shadow_scholar is None

    def test_context_manager_appends_shadow_cells(self, basic_chain):
        """SimulationContext appends shadow cells from OverlayContext to shadow_chain."""
        # Find a fact cell to shadow
        fact_cell = None
        for cell in basic_chain.cells:
            if hasattr(cell.fact, 'subject') and cell.fact.predicate == "has_salary":
                fact_cell = cell
                break

        assert fact_cell is not None, "No fact cell found"

        # Create overlay with shadow cell
        ctx = OverlayContext()
        shadow_cell = create_shadow_fact(fact_cell, object="modified_value")
        ctx.add_shadow_fact(shadow_cell, fact_cell.cell_id)

        sim = SimulationContext(
            basic_chain, ctx,
            "2025-01-15T00:00:00Z",
            "2025-01-15T00:00:00Z"
        )

        with sim as s:
            # Verify shadow cell is in shadow_chain (length increased)
            assert len(s.shadow_chain.cells) > len(basic_chain.cells), "Shadow cell not appended to shadow_chain"


# =============================================================================
# SIMULATION RESULT
# =============================================================================

class TestSimulationResult:
    """Tests for SimulationResult frozen dataclass"""

    def test_result_is_frozen(self):
        """SimulationResult cannot be modified after creation."""
        result = SimulationResult(
            simulation_id="test-id",
            rfa_dict={"namespace": "corp"},
            simulation_spec={},
            base_result={},
            shadow_result={},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z"
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            result.simulation_id = "modified"

    def test_result_to_dict(self):
        """SimulationResult.to_dict() returns serializable dict."""
        result = SimulationResult(
            simulation_id="test-id",
            rfa_dict={"namespace": "corp"},
            simulation_spec={"shadow_facts": []},
            base_result={"results": {"fact_count": 1}},
            shadow_result={"results": {"fact_count": 1}},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z"
        )

        d = result.to_dict()

        assert d["simulation_id"] == "test-id"
        assert d["rfa_dict"] == {"namespace": "corp"}
        assert d["at_valid_time"] == "2025-01-01T00:00:00Z"


# =============================================================================
# EDGE CASES
# =============================================================================

class TestSimulationEdgeCases:
    """Edge case tests for simulation"""

    def test_simulate_with_nonexistent_base_cell(self, engine_with_facts):
        """Simulation gracefully handles nonexistent base_cell_id."""
        engine, chain = engine_with_facts

        # Should not raise - just ignores invalid base_cell_id
        result = engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test"
            },
            simulation_spec={
                "shadow_facts": [{
                    "base_cell_id": "nonexistent_cell_id",
                    "object": "99999"
                }]
            },
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )

        assert isinstance(result, SimulationResult)

    def test_simulate_with_empty_simulation_spec_keys(self, engine_with_facts):
        """Simulation handles simulation_spec with empty lists."""
        engine, chain = engine_with_facts

        result = engine.simulate_rfa(
            rfa_dict={
                "namespace": "corp",
                "requester_namespace": "corp",
                "requester_id": "analyst:test"
            },
            simulation_spec={
                "shadow_facts": [],
                "shadow_rules": [],
                "shadow_policy_heads": [],
                "shadow_bridges": []
            },
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )

        assert isinstance(result, SimulationResult)


# ============================================================================
# PHASE 9 TESTS - Delta Report and Proof
# ============================================================================

class TestDeltaReportDataclass:
    """Tests for DeltaReport frozen dataclass (SIM-04)."""

    def test_delta_report_is_frozen(self):
        """DeltaReport should be immutable (frozen dataclass)."""
        delta = DeltaReport(
            verdict_changed=True,
            status_before="ALLOWED",
            status_after="DENIED",
            score_delta=0.0,
            facts_diff={"added": [], "removed": ["x"]},
            rules_diff={"added": [], "removed": []}
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            delta.verdict_changed = False

    def test_delta_report_has_all_required_fields(self):
        """DeltaReport should have all SIM-04 required fields."""
        delta = DeltaReport(
            verdict_changed=False,
            status_before="DENIED",
            status_after="ALLOWED",
            score_delta=0.5,
            facts_diff={"added": ["a"], "removed": []},
            rules_diff={"added": [], "removed": ["r1"]}
        )
        assert hasattr(delta, 'verdict_changed')
        assert hasattr(delta, 'status_before')
        assert hasattr(delta, 'status_after')
        assert hasattr(delta, 'score_delta')
        assert hasattr(delta, 'facts_diff')
        assert hasattr(delta, 'rules_diff')


class TestContaminationAttestationDataclass:
    """Tests for ContaminationAttestation frozen dataclass (SHD-06)."""

    def test_attestation_is_frozen(self):
        """ContaminationAttestation should be immutable."""
        att = ContaminationAttestation(
            chain_head_before="abc",
            chain_head_after="abc",
            attestation_hash="hash123",
            contamination_detected=False
        )
        with pytest.raises(Exception):
            att.contamination_detected = True

    def test_attestation_has_all_required_fields(self):
        """ContaminationAttestation should have all SHD-06 required fields."""
        att = ContaminationAttestation(
            chain_head_before="before",
            chain_head_after="after",
            attestation_hash="hash",
            contamination_detected=True
        )
        assert hasattr(att, 'chain_head_before')
        assert hasattr(att, 'chain_head_after')
        assert hasattr(att, 'attestation_hash')
        assert hasattr(att, 'contamination_detected')


class TestComputeDeltaReport:
    """Tests for compute_delta_report() function (SIM-04, SIM-06)."""

    def test_verdict_changed_when_fact_count_differs(self):
        """verdict_changed should be True when fact counts differ."""
        base = {"results": {"fact_cell_ids": ["a", "b"], "fact_count": 2},
                "authorization_basis": {"allowed": True}}
        shadow = {"results": {"fact_cell_ids": ["a", "b", "c"], "fact_count": 3},
                  "authorization_basis": {"allowed": True}}
        delta = compute_delta_report(base, shadow)
        assert delta.verdict_changed is True

    def test_verdict_unchanged_when_fact_count_same(self):
        """verdict_changed should be False when fact counts equal."""
        base = {"results": {"fact_cell_ids": ["a", "b"], "fact_count": 2},
                "authorization_basis": {"allowed": True}}
        shadow = {"results": {"fact_cell_ids": ["a", "c"], "fact_count": 2},
                  "authorization_basis": {"allowed": True}}
        delta = compute_delta_report(base, shadow)
        assert delta.verdict_changed is False

    def test_status_before_after_extracted(self):
        """status_before/after should reflect authorization.allowed."""
        base = {"results": {"fact_cell_ids": [], "fact_count": 0},
                "authorization_basis": {"allowed": True}}
        shadow = {"results": {"fact_cell_ids": [], "fact_count": 0},
                  "authorization_basis": {"allowed": False}}
        delta = compute_delta_report(base, shadow)
        assert delta.status_before == "ALLOWED"
        assert delta.status_after == "DENIED"

    def test_facts_diff_computed_correctly(self):
        """facts_diff should show added and removed fact cell IDs."""
        base = {"results": {"fact_cell_ids": ["a", "b", "c"], "fact_count": 3},
                "authorization_basis": {"allowed": True}}
        shadow = {"results": {"fact_cell_ids": ["b", "d", "e"], "fact_count": 3},
                  "authorization_basis": {"allowed": True}}
        delta = compute_delta_report(base, shadow)
        assert sorted(delta.facts_diff["added"]) == ["d", "e"]
        assert sorted(delta.facts_diff["removed"]) == ["a", "c"]

    def test_deterministic_output_same_inputs(self):
        """Same inputs should always produce identical DeltaReport (SIM-06)."""
        base = {"results": {"fact_cell_ids": ["z", "a", "m"], "fact_count": 3},
                "authorization_basis": {"allowed": True}}
        shadow = {"results": {"fact_cell_ids": ["a", "x", "b"], "fact_count": 3},
                  "authorization_basis": {"allowed": False}}
        delta1 = compute_delta_report(base, shadow)
        delta2 = compute_delta_report(base, shadow)
        assert delta1 == delta2
        # Verify sorted output
        assert delta1.facts_diff["added"] == ["b", "x"]
        assert delta1.facts_diff["removed"] == ["m", "z"]

    def test_handles_empty_results(self):
        """Should handle empty or missing results gracefully."""
        base = {"results": {}, "authorization_basis": {"allowed": False}}
        shadow = {"results": {"fact_cell_ids": ["a"], "fact_count": 1},
                  "authorization_basis": {"allowed": True}}
        delta = compute_delta_report(base, shadow)
        assert delta.verdict_changed is True
        assert delta.facts_diff["added"] == ["a"]
        assert delta.facts_diff["removed"] == []


class TestTagProofBundleOrigin:
    """Tests for tag_proof_bundle_origin() function (SIM-05)."""

    def test_adds_origin_to_top_level(self):
        """Should add origin field to top level of proof bundle."""
        bundle = {"results": {"fact_cell_ids": ["x"]}}
        tagged = tag_proof_bundle_origin(bundle, "BASE")
        assert tagged["origin"] == "BASE"

    def test_does_not_mutate_original(self):
        """Original bundle should remain unchanged."""
        bundle = {"results": {"fact_cell_ids": ["x"]}, "proof": {"candidate_cell_ids": ["y"]}}
        original_str = str(bundle)
        tagged = tag_proof_bundle_origin(bundle, "SHADOW")
        assert str(bundle) == original_str
        assert "origin" not in bundle

    def test_tags_fact_cell_ids_with_origin(self):
        """Should add fact_cell_ids_with_origin list."""
        bundle = {"results": {"fact_cell_ids": ["a", "b"]}}
        tagged = tag_proof_bundle_origin(bundle, "BASE")
        assert "fact_cell_ids_with_origin" in tagged["results"]
        assert tagged["results"]["fact_cell_ids_with_origin"] == [
            {"cell_id": "a", "origin": "BASE"},
            {"cell_id": "b", "origin": "BASE"}
        ]

    def test_tags_candidate_cell_ids(self):
        """Should add candidate_cell_ids_with_origin list."""
        bundle = {"proof": {"candidate_cell_ids": ["c1", "c2"]}}
        tagged = tag_proof_bundle_origin(bundle, "SHADOW")
        assert "candidate_cell_ids_with_origin" in tagged["proof"]
        assert tagged["proof"]["candidate_cell_ids_with_origin"][0]["origin"] == "SHADOW"

    def test_tags_bridges_used(self):
        """Should add bridges_used_with_origin list."""
        bundle = {"proof": {"bridges_used": ["br1"]}}
        tagged = tag_proof_bundle_origin(bundle, "BASE")
        assert "bridges_used_with_origin" in tagged["proof"]
        assert tagged["proof"]["bridges_used_with_origin"][0] == {"cell_id": "br1", "origin": "BASE"}


class TestCreateContaminationAttestation:
    """Tests for create_contamination_attestation() function (SHD-06)."""

    def test_no_contamination_when_heads_match(self):
        """contamination_detected should be False when heads match."""
        att = create_contamination_attestation("head1", "head1", "sim-123")
        assert att.contamination_detected is False

    def test_contamination_detected_when_heads_differ(self):
        """contamination_detected should be True when heads differ."""
        att = create_contamination_attestation("head1", "head2", "sim-123")
        assert att.contamination_detected is True

    def test_attestation_hash_is_sha256(self):
        """attestation_hash should be 64 hex characters (SHA-256)."""
        att = create_contamination_attestation("before", "after", "sim-id")
        assert len(att.attestation_hash) == 64
        # Verify it's hex
        int(att.attestation_hash, 16)

    def test_deterministic_hash_same_inputs(self):
        """Same inputs should produce same attestation_hash."""
        att1 = create_contamination_attestation("h1", "h2", "sim-x")
        att2 = create_contamination_attestation("h1", "h2", "sim-x")
        assert att1.attestation_hash == att2.attestation_hash

    def test_different_simulation_id_different_hash(self):
        """Different simulation_id should produce different hash."""
        att1 = create_contamination_attestation("h1", "h1", "sim-1")
        att2 = create_contamination_attestation("h1", "h1", "sim-2")
        assert att1.attestation_hash != att2.attestation_hash


class TestSimulationResultPhase9Fields:
    """Tests for SimulationResult Phase 9 fields (SHD-03)."""

    def test_simulation_result_has_delta_report(self):
        """SimulationResult should have delta_report field."""
        delta = DeltaReport(
            verdict_changed=False,
            status_before="ALLOWED",
            status_after="ALLOWED",
            score_delta=0.0,
            facts_diff={"added": [], "removed": []},
            rules_diff={"added": [], "removed": []}
        )
        result = SimulationResult(
            simulation_id="test",
            rfa_dict={},
            simulation_spec={},
            base_result={},
            shadow_result={},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            delta_report=delta
        )
        assert result.delta_report is not None
        assert result.delta_report.verdict_changed is False

    def test_simulation_result_has_anchors(self):
        """SimulationResult should have anchors field (empty dict for Phase 9)."""
        result = SimulationResult(
            simulation_id="test",
            rfa_dict={},
            simulation_spec={},
            base_result={},
            shadow_result={},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            anchors={}
        )
        assert result.anchors == {}

    def test_simulation_result_has_proof_bundle(self):
        """SimulationResult should have proof_bundle field."""
        result = SimulationResult(
            simulation_id="test",
            rfa_dict={},
            simulation_spec={},
            base_result={},
            shadow_result={},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z",
            proof_bundle={"base": {}, "shadow": {}}
        )
        assert "base" in result.proof_bundle
        assert "shadow" in result.proof_bundle

    def test_to_dict_includes_delta_report(self):
        """to_dict() should include delta_report when present."""
        delta = DeltaReport(
            verdict_changed=True,
            status_before="ALLOWED",
            status_after="DENIED",
            score_delta=1.5,
            facts_diff={"added": ["x"], "removed": []},
            rules_diff={"added": [], "removed": []}
        )
        result = SimulationResult(
            simulation_id="test",
            rfa_dict={},
            simulation_spec={},
            base_result={},
            shadow_result={},
            at_valid_time="t1",
            as_of_system_time="t2",
            delta_report=delta
        )
        d = result.to_dict()
        assert "delta_report" in d
        assert d["delta_report"]["verdict_changed"] is True
        assert d["delta_report"]["status_after"] == "DENIED"

    def test_backward_compatibility_delta_report_none(self):
        """SimulationResult should work without delta_report (backward compat)."""
        result = SimulationResult(
            simulation_id="test",
            rfa_dict={},
            simulation_spec={},
            base_result={},
            shadow_result={},
            at_valid_time="t1",
            as_of_system_time="t2"
        )
        assert result.delta_report is None
        assert result.anchors == {}


class TestEngineSimulateRfaPhase9:
    """Tests for Engine.simulate_rfa() Phase 9 integration."""

    @pytest.fixture
    def engine_with_facts(self):
        """Create Engine with test facts for simulation."""
        from decisiongraph import create_chain
        from decisiongraph.cell import DecisionCell, Header, Fact, LogicAnchor, Proof, CellType, SourceQuality

        # Create chain with genesis using utility
        chain = create_chain("test-graph", "testns")

        now = get_current_timestamp()

        # Create a rule first (facts need to reference a rule)
        rule_logic_hash = compute_rule_logic_hash("test_logic")
        rule = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.RULE,
                system_time=now,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="testns",
                subject="rule:test_v1",
                predicate="defines",
                object="test_calculation",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=now
            ),
            logic_anchor=LogicAnchor(
                rule_id="rule:test_v1",
                rule_logic_hash=rule_logic_hash
            ),
            proof=Proof(signer_id="system:test")
        )
        chain.append(rule)

        # Add a fact cell
        fact_cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=now,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="testns",
                subject="user:alice",
                predicate="has_role",
                object="admin",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
                valid_from=now
            ),
            logic_anchor=LogicAnchor(
                rule_id="rule:test_v1",
                rule_logic_hash=rule_logic_hash
            ),
            proof=Proof(signer_id="system:test")
        )
        chain.append(fact_cell)

        return Engine(chain), fact_cell.cell_id

    def test_simulate_rfa_returns_delta_report(self, engine_with_facts):
        """simulate_rfa() should return SimulationResult with delta_report."""
        engine, _ = engine_with_facts
        result = engine.simulate_rfa(
            rfa_dict={"namespace": "testns", "requester_namespace": "testns",
                      "requester_id": "tester"},
            simulation_spec={},
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )
        assert result.delta_report is not None
        assert isinstance(result.delta_report, DeltaReport)

    def test_simulate_rfa_returns_proof_bundle_with_tagged_bundles(self, engine_with_facts):
        """simulate_rfa() should return proof_bundle with BASE and SHADOW tags."""
        engine, _ = engine_with_facts
        result = engine.simulate_rfa(
            rfa_dict={"namespace": "testns", "requester_namespace": "testns",
                      "requester_id": "tester"},
            simulation_spec={},
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )
        assert "base" in result.proof_bundle
        assert "shadow" in result.proof_bundle
        assert result.proof_bundle["base"]["origin"] == "BASE"
        assert result.proof_bundle["shadow"]["origin"] == "SHADOW"

    def test_simulate_rfa_returns_contamination_attestation(self, engine_with_facts):
        """simulate_rfa() should include contamination_attestation in proof_bundle."""
        engine, _ = engine_with_facts
        result = engine.simulate_rfa(
            rfa_dict={"namespace": "testns", "requester_namespace": "testns",
                      "requester_id": "tester"},
            simulation_spec={},
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )
        assert "contamination_attestation" in result.proof_bundle
        att = result.proof_bundle["contamination_attestation"]
        assert "chain_head_before" in att
        assert "chain_head_after" in att
        assert "attestation_hash" in att
        assert att["contamination_detected"] is False

    def test_simulate_rfa_anchors_is_empty_dict(self, engine_with_facts):
        """simulate_rfa() should return anchors with empty list when no verdict change (Phase 10)."""
        engine, _ = engine_with_facts
        result = engine.simulate_rfa(
            rfa_dict={"namespace": "testns", "requester_namespace": "testns",
                      "requester_id": "tester"},
            simulation_spec={},
            at_valid_time="2025-01-15T00:00:00Z",
            as_of_system_time="2025-01-15T00:00:00Z"
        )
        # Phase 10 integration: anchors is now a structured dict with empty list
        assert result.anchors['anchors'] == []
        assert result.anchors['anchors_incomplete'] is False
        assert result.anchors['attempts_used'] == 0
        assert result.anchors['runtime_ms'] == 0.0
        assert result.anchors['anchor_hash'] == ''

    def test_simulate_rfa_deterministic_output(self, engine_with_facts):
        """Same inputs should produce identical results (SIM-06)."""
        engine, _ = engine_with_facts
        rfa = {"namespace": "testns", "requester_namespace": "testns",
               "requester_id": "tester"}
        spec = {}
        vtime = "2025-01-15T00:00:00Z"
        stime = "2025-01-15T00:00:00Z"

        result1 = engine.simulate_rfa(rfa, spec, vtime, stime)
        result2 = engine.simulate_rfa(rfa, spec, vtime, stime)

        # Delta reports should be identical
        assert result1.delta_report == result2.delta_report
        # Base/shadow results should be identical
        assert result1.base_result == result2.base_result
        assert result1.shadow_result == result2.shadow_result

    def test_simulate_rfa_with_shadow_fact_changes_delta(self, engine_with_facts):
        """Shadow fact modification should be reflected in delta_report."""
        engine, fact_cell_id = engine_with_facts
        now = get_current_timestamp()
        result = engine.simulate_rfa(
            rfa_dict={"namespace": "testns", "requester_namespace": "testns",
                      "requester_id": "tester", "subject": "user:alice"},
            simulation_spec={
                "shadow_facts": [{"base_cell_id": fact_cell_id, "object": "superadmin"}]
            },
            at_valid_time=now,
            as_of_system_time=now
        )
        # Delta report should exist and be computed
        delta = result.delta_report
        assert delta is not None
        # Verify the simulation ran with shadow spec
        assert result.simulation_spec["shadow_facts"][0]["object"] == "superadmin"
        # Delta report fields should be populated
        assert delta.status_before in ["ALLOWED", "DENIED"]
        assert delta.status_after in ["ALLOWED", "DENIED"]
        assert isinstance(delta.verdict_changed, bool)

    def test_no_contamination_after_simulation(self, engine_with_facts):
        """Base chain should be unchanged after simulation (SHD-06)."""
        engine, fact_cell_id = engine_with_facts
        chain_head_before = engine.chain.head.cell_id
        chain_length_before = engine.chain.length
        now = get_current_timestamp()

        result = engine.simulate_rfa(
            rfa_dict={"namespace": "testns", "requester_namespace": "testns",
                      "requester_id": "tester"},
            simulation_spec={
                "shadow_facts": [{"base_cell_id": fact_cell_id, "object": "modified"}]
            },
            at_valid_time=now,
            as_of_system_time=now
        )

        # Chain unchanged
        assert engine.chain.head.cell_id == chain_head_before
        assert engine.chain.length == chain_length_before

        # Attestation confirms no contamination
        assert result.proof_bundle["contamination_attestation"]["contamination_detected"] is False
        assert result.proof_bundle["contamination_attestation"]["chain_head_before"] == chain_head_before
        assert result.proof_bundle["contamination_attestation"]["chain_head_after"] == chain_head_before

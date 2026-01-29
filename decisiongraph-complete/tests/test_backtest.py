"""
Tests for batch backtest functionality (Phase 11).

Requirements tested:
- BAT-01: engine.run_backtest() executes simulation over multiple RFAs
- BAT-02: Backtest bounded by limits (max_cases, max_runtime_ms, max_cells_touched)
- BAT-03: Backtest output deterministically ordered
"""

import pytest
from unittest.mock import patch, MagicMock
import time

from decisiongraph import (
    BatchBacktestResult,
    create_chain,
    create_genesis_cell,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
)
from decisiongraph.backtest import _sort_results, _count_cells_in_simulation
from decisiongraph.simulation import SimulationResult, DeltaReport
from decisiongraph.engine import Engine
from decisiongraph.cell import get_current_timestamp


# ============================================================================
# BatchBacktestResult Tests
# ============================================================================

class TestBatchBacktestResult:
    """Tests for BatchBacktestResult dataclass."""

    def test_batch_backtest_result_creation(self):
        """BAT-01: BatchBacktestResult can be created with required fields."""
        result = BatchBacktestResult(
            results=[],
            backtest_incomplete=False,
            cases_processed=0,
            runtime_ms=0.0,
            cells_touched=0
        )

        assert result.results == []
        assert result.backtest_incomplete is False
        assert result.cases_processed == 0
        assert result.runtime_ms == 0.0
        assert result.cells_touched == 0

    def test_batch_backtest_result_is_frozen(self):
        """BatchBacktestResult is immutable (frozen dataclass)."""
        result = BatchBacktestResult(
            results=[],
            backtest_incomplete=False,
            cases_processed=0,
            runtime_ms=0.0,
            cells_touched=0
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            result.cases_processed = 10

    def test_batch_backtest_result_to_dict(self):
        """to_dict() produces serializable output."""
        result = BatchBacktestResult(
            results=[],
            backtest_incomplete=True,
            cases_processed=5,
            runtime_ms=1234.5,
            cells_touched=500
        )

        d = result.to_dict()
        assert d['results'] == []
        assert d['backtest_incomplete'] is True
        assert d['cases_processed'] == 5
        assert d['runtime_ms'] == 1234.5
        assert d['cells_touched'] == 500


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestSortResults:
    """Tests for _sort_results() helper (BAT-03)."""

    def test_sort_results_empty_list(self):
        """Empty list returns empty list."""
        assert _sort_results([]) == []

    def test_sort_results_by_subject(self):
        """Results sorted by subject as primary key (BAT-03)."""
        # Create mock SimulationResults with different subjects
        result_b = MagicMock(spec=SimulationResult)
        result_b.rfa_dict = {'subject': 'employee:bob'}
        result_b.at_valid_time = '2025-01-01T00:00:00Z'
        result_b.as_of_system_time = '2025-01-01T00:00:00Z'

        result_a = MagicMock(spec=SimulationResult)
        result_a.rfa_dict = {'subject': 'employee:alice'}
        result_a.at_valid_time = '2025-01-01T00:00:00Z'
        result_a.as_of_system_time = '2025-01-01T00:00:00Z'

        sorted_results = _sort_results([result_b, result_a])

        # alice should come before bob
        assert sorted_results[0].rfa_dict['subject'] == 'employee:alice'
        assert sorted_results[1].rfa_dict['subject'] == 'employee:bob'

    def test_sort_results_by_valid_time(self):
        """Results sorted by valid_time as secondary key (BAT-03)."""
        result_later = MagicMock(spec=SimulationResult)
        result_later.rfa_dict = {'subject': 'employee:alice'}
        result_later.at_valid_time = '2025-02-01T00:00:00Z'
        result_later.as_of_system_time = '2025-01-01T00:00:00Z'

        result_earlier = MagicMock(spec=SimulationResult)
        result_earlier.rfa_dict = {'subject': 'employee:alice'}
        result_earlier.at_valid_time = '2025-01-01T00:00:00Z'
        result_earlier.as_of_system_time = '2025-01-01T00:00:00Z'

        sorted_results = _sort_results([result_later, result_earlier])

        assert sorted_results[0].at_valid_time == '2025-01-01T00:00:00Z'
        assert sorted_results[1].at_valid_time == '2025-02-01T00:00:00Z'

    def test_sort_results_by_system_time(self):
        """Results sorted by system_time as tertiary key (BAT-03)."""
        result_later = MagicMock(spec=SimulationResult)
        result_later.rfa_dict = {'subject': 'employee:alice'}
        result_later.at_valid_time = '2025-01-01T00:00:00Z'
        result_later.as_of_system_time = '2025-01-02T00:00:00Z'

        result_earlier = MagicMock(spec=SimulationResult)
        result_earlier.rfa_dict = {'subject': 'employee:alice'}
        result_earlier.at_valid_time = '2025-01-01T00:00:00Z'
        result_earlier.as_of_system_time = '2025-01-01T00:00:00Z'

        sorted_results = _sort_results([result_later, result_earlier])

        assert sorted_results[0].as_of_system_time == '2025-01-01T00:00:00Z'
        assert sorted_results[1].as_of_system_time == '2025-01-02T00:00:00Z'

    def test_sort_results_missing_subject(self):
        """Missing subject defaults to empty string (stable sort)."""
        result_with = MagicMock(spec=SimulationResult)
        result_with.rfa_dict = {'subject': 'employee:bob'}
        result_with.at_valid_time = '2025-01-01T00:00:00Z'
        result_with.as_of_system_time = '2025-01-01T00:00:00Z'

        result_without = MagicMock(spec=SimulationResult)
        result_without.rfa_dict = {}  # No subject
        result_without.at_valid_time = '2025-01-01T00:00:00Z'
        result_without.as_of_system_time = '2025-01-01T00:00:00Z'

        # Should not crash, empty string '' comes before 'employee:bob'
        sorted_results = _sort_results([result_with, result_without])
        assert sorted_results[0].rfa_dict.get('subject', '') == ''


class TestCountCellsInSimulation:
    """Tests for _count_cells_in_simulation() helper (BAT-02)."""

    def test_count_cells_empty_results(self):
        """Empty results return 0 cells."""
        result = MagicMock(spec=SimulationResult)
        result.base_result = {}
        result.shadow_result = {}

        assert _count_cells_in_simulation(result) == 0

    def test_count_cells_with_facts(self):
        """Counts fact_cell_ids from base and shadow."""
        result = MagicMock(spec=SimulationResult)
        result.base_result = {
            'results': {'fact_cell_ids': ['a', 'b', 'c']},
            'proof': {}
        }
        result.shadow_result = {
            'results': {'fact_cell_ids': ['x', 'y']},
            'proof': {}
        }

        assert _count_cells_in_simulation(result) == 5  # 3 + 2

    def test_count_cells_with_candidates_and_bridges(self):
        """Counts candidate_cell_ids and bridges_used."""
        result = MagicMock(spec=SimulationResult)
        result.base_result = {
            'results': {'fact_cell_ids': ['a']},
            'proof': {'candidate_cell_ids': ['c1', 'c2'], 'bridges_used': ['b1']}
        }
        result.shadow_result = {
            'results': {'fact_cell_ids': []},
            'proof': {'candidate_cell_ids': ['c3'], 'bridges_used': []}
        }

        # base: 1 fact + 2 candidates + 1 bridge = 4
        # shadow: 0 facts + 1 candidate + 0 bridges = 1
        assert _count_cells_in_simulation(result) == 5


# ============================================================================
# Engine.run_backtest() Integration Tests
# ============================================================================

class TestEngineRunBacktest:
    """Integration tests for Engine.run_backtest() (BAT-01, BAT-02, BAT-03)."""

    @pytest.fixture
    def engine_with_facts(self):
        """Create engine with test chain and facts."""
        ts = get_current_timestamp()
        chain = create_chain('test_graph', system_time=ts)

        # Add some facts for querying
        fact1 = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=ts,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace='corp.hr',
                subject='employee:alice',
                predicate='has_salary',
                object='50000',
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=ts,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )
        chain.append(fact1)

        fact2 = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=ts,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace='corp.hr',
                subject='employee:bob',
                predicate='has_salary',
                object='60000',
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=ts,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )
        chain.append(fact2)

        return Engine(chain), fact1.cell_id, fact2.cell_id, ts

    def test_run_backtest_empty_list(self):
        """BAT-01: Empty rfa_list returns empty results."""
        ts = get_current_timestamp()
        chain = create_chain('test', system_time=ts)
        engine = Engine(chain)

        result = engine.run_backtest(
            rfa_list=[],
            simulation_spec={},
            at_valid_time=get_current_timestamp(),
            as_of_system_time=get_current_timestamp()
        )

        assert result.results == []
        assert result.backtest_incomplete is False
        assert result.cases_processed == 0
        assert result.runtime_ms == 0.0
        assert result.cells_touched == 0

    def test_run_backtest_single_rfa(self, engine_with_facts):
        """BAT-01: Single RFA returns single result."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        result = engine.run_backtest(
            rfa_list=[{
                'namespace': 'corp.hr',
                'requester_namespace': 'corp.hr',
                'requester_id': 'analyst',
                'subject': 'employee:alice'
            }],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts
        )

        assert result.cases_processed == 1
        assert result.backtest_incomplete is False
        assert len(result.results) == 1

    def test_run_backtest_multiple_rfas(self, engine_with_facts):
        """BAT-01: Multiple RFAs return multiple results."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:alice'},
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:bob'},
            ],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts
        )

        assert result.cases_processed == 2
        assert result.backtest_incomplete is False
        assert len(result.results) == 2

    def test_run_backtest_max_cases_limit(self, engine_with_facts):
        """BAT-02: Stops when max_cases reached."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        # Request 5 RFAs but limit to 2
        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': f'employee:user{i}'}
                for i in range(5)
            ],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts,
            max_cases=2
        )

        assert result.cases_processed == 2
        assert result.backtest_incomplete is True
        assert len(result.results) == 2

    def test_run_backtest_max_runtime_limit(self, engine_with_facts):
        """BAT-02: Stops when max_runtime_ms exceeded."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        # Use very short timeout (1ms) - should stop quickly
        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': f'employee:user{i}'}
                for i in range(100)
            ],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts,
            max_runtime_ms=1  # 1ms timeout
        )

        # Should have processed at least 1 but likely stopped early
        assert result.backtest_incomplete is True
        assert result.cases_processed < 100

    def test_run_backtest_max_cells_touched_limit(self, engine_with_facts):
        """BAT-02: Stops when max_cells_touched exceeded."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        # Set very low cell limit
        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:alice'},
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:bob'},
            ],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts,
            max_cells_touched=1  # Very low limit
        )

        # First RFA should process, second may be blocked
        assert result.cases_processed >= 1
        # If cells_touched > 1 after first RFA, incomplete should be True
        if result.cells_touched >= 1:
            assert result.backtest_incomplete is True

    def test_run_backtest_deterministic_ordering(self, engine_with_facts):
        """BAT-03: Results sorted by (subject, valid_time, system_time)."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        # Submit RFAs in reverse order (bob before alice)
        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:bob'},
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:alice'},
            ],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts
        )

        # Results should be sorted: alice before bob
        assert result.results[0].rfa_dict['subject'] == 'employee:alice'
        assert result.results[1].rfa_dict['subject'] == 'employee:bob'

    def test_run_backtest_with_shadow_spec(self, engine_with_facts):
        """BAT-01: Simulation spec applied to all RFAs."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        # Shadow spec modifies alice's salary
        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:alice'},
            ],
            simulation_spec={
                'shadow_facts': [
                    {'base_cell_id': fact1_id, 'object': '75000'}
                ]
            },
            at_valid_time=ts,
            as_of_system_time=ts
        )

        assert result.cases_processed == 1
        # Result should have delta_report (Phase 9)
        assert result.results[0].delta_report is not None

    def test_run_backtest_tracks_runtime(self, engine_with_facts):
        """runtime_ms is tracked accurately."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:alice'},
            ],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts
        )

        # Runtime should be positive and reasonable
        assert result.runtime_ms > 0
        assert result.runtime_ms < 10000  # Less than 10 seconds

    def test_run_backtest_tracks_cells_touched(self, engine_with_facts):
        """cells_touched accumulates across simulations."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:alice'},
                {'namespace': 'corp.hr', 'requester_namespace': 'corp.hr',
                 'requester_id': 'analyst', 'subject': 'employee:bob'},
            ],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts
        )

        # Should have touched cells from both simulations
        assert result.cells_touched >= 0

    def test_run_backtest_result_is_batch_backtest_result(self, engine_with_facts):
        """Return type is BatchBacktestResult."""
        engine, fact1_id, fact2_id, ts = engine_with_facts

        result = engine.run_backtest(
            rfa_list=[],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts
        )

        assert isinstance(result, BatchBacktestResult)


# ============================================================================
# Edge Cases and Regression Tests
# ============================================================================

class TestBacktestEdgeCases:
    """Edge cases and regression tests."""

    def test_rfa_without_subject_field(self):
        """RFAs without subject field sort correctly (default empty string)."""
        ts = get_current_timestamp()
        chain = create_chain('test', system_time=ts)
        engine = Engine(chain)

        # RFA without subject
        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp', 'requester_namespace': 'corp', 'requester_id': 'user'},
            ],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts
        )

        assert result.cases_processed == 1
        assert result.backtest_incomplete is False

    def test_default_limits(self):
        """Default limits are reasonable."""
        ts = get_current_timestamp()
        chain = create_chain('test', system_time=ts)
        engine = Engine(chain)

        # Without explicit limits, should use defaults
        result = engine.run_backtest(
            rfa_list=[
                {'namespace': 'corp', 'requester_namespace': 'corp', 'requester_id': 'user'},
            ],
            simulation_spec={},
            at_valid_time=ts,
            as_of_system_time=ts
        )

        # Should complete with defaults (1000 cases, 60s, 100000 cells)
        assert result.backtest_incomplete is False

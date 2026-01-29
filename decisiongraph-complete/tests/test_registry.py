"""
Tests for WitnessRegistry (v1.5 Phase 2)

Test Coverage:
1. TestRegistryCreation: Basic construction and chain binding
2. TestGenesisWitnessSetExtraction: WIT-03 runtime - extract from Genesis
3. TestRegistryQueries: get_witness_set, get_all_witness_sets, has_witness_set
4. TestRegistryStateless: Verify rebuilds from chain each query
5. TestRegistryWithEmptyChain: Legacy genesis, empty registry
6. TestRegistryIntegration: Usable after extraction, deterministic ordering
"""

import pytest
from decisiongraph import (
    Chain,
    WitnessSet,
    WitnessRegistry,
)
from decisiongraph.genesis import (
    create_genesis_cell_with_witness_set,
    create_genesis_cell,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def chain_with_witnessset():
    """Chain with Genesis that has WitnessSet (2-of-3)"""
    chain = Chain()
    genesis = create_genesis_cell_with_witness_set(
        graph_name="TestGraph",
        root_namespace="corp",
        witnesses=["alice", "bob", "charlie"],
        threshold=2,
        system_time="2026-01-28T00:00:00Z"
    )
    chain.append(genesis)
    return chain


@pytest.fixture
def chain_without_witnessset():
    """Chain with legacy Genesis (no WitnessSet)"""
    chain = Chain()
    genesis = create_genesis_cell(
        graph_name="LegacyGraph",
        root_namespace="acme",
        system_time="2026-01-28T00:00:00Z"
    )
    chain.append(genesis)
    return chain


@pytest.fixture
def registry(chain_with_witnessset):
    """WitnessRegistry bound to chain_with_witnessset"""
    return WitnessRegistry(chain_with_witnessset)


# ============================================================================
# TEST CLASSES
# ============================================================================

class TestRegistryCreation:
    """Test WitnessRegistry construction and basic properties"""

    def test_create_registry_with_chain(self, chain_with_witnessset):
        """Can create WitnessRegistry with a Chain"""
        registry = WitnessRegistry(chain_with_witnessset)
        assert registry is not None
        assert registry.chain is chain_with_witnessset

    def test_registry_stores_chain_reference(self, chain_with_witnessset):
        """Registry stores reference to chain (not a copy)"""
        registry = WitnessRegistry(chain_with_witnessset)
        assert registry.chain is chain_with_witnessset  # Same object


class TestGenesisWitnessSetExtraction:
    """Test Genesis WitnessSet extraction (WIT-03 runtime)"""

    def test_extract_witnessset_from_genesis(self, registry):
        """Extract WitnessSet from Genesis with embedded config"""
        ws = registry.get_witness_set("corp")

        assert ws is not None
        assert ws.namespace == "corp"
        assert ws.threshold == 2
        assert len(ws.witnesses) == 3

    def test_witnesses_extracted_correctly(self, registry):
        """Witnesses list is extracted from Genesis"""
        ws = registry.get_witness_set("corp")

        # Witnesses should be sorted (deterministic)
        assert ws.witnesses == ("alice", "bob", "charlie")

    def test_threshold_extracted_correctly(self, registry):
        """Threshold is extracted from Genesis"""
        ws = registry.get_witness_set("corp")
        assert ws.threshold == 2

    def test_namespace_matches_root_namespace(self, registry):
        """WitnessSet namespace matches Genesis root namespace"""
        ws = registry.get_witness_set("corp")
        assert ws.namespace == "corp"

    def test_legacy_genesis_returns_none(self):
        """Legacy Genesis without WitnessSet returns None"""
        chain = Chain()
        genesis = create_genesis_cell(
            graph_name="LegacyGraph",
            root_namespace="acme",
            system_time="2026-01-28T00:00:00Z"
        )
        chain.append(genesis)
        registry = WitnessRegistry(chain)

        ws = registry.get_witness_set("acme")
        assert ws is None


class TestRegistryQueries:
    """Test registry query methods"""

    def test_get_witness_set_existing_namespace(self, registry):
        """get_witness_set returns WitnessSet for existing namespace"""
        ws = registry.get_witness_set("corp")
        assert ws is not None
        assert isinstance(ws, WitnessSet)

    def test_get_witness_set_nonexistent_namespace(self, registry):
        """get_witness_set returns None for namespace without WitnessSet"""
        ws = registry.get_witness_set("nonexistent")
        assert ws is None

    def test_get_all_witness_sets_returns_dict(self, registry):
        """get_all_witness_sets returns dict"""
        all_ws = registry.get_all_witness_sets()
        assert isinstance(all_ws, dict)

    def test_get_all_witness_sets_contains_genesis_ws(self, registry):
        """get_all_witness_sets includes Genesis WitnessSet"""
        all_ws = registry.get_all_witness_sets()

        assert "corp" in all_ws
        assert all_ws["corp"].threshold == 2
        assert len(all_ws["corp"].witnesses) == 3

    def test_get_all_witness_sets_empty_for_legacy(self, chain_without_witnessset):
        """get_all_witness_sets returns empty dict for legacy Genesis"""
        registry = WitnessRegistry(chain_without_witnessset)
        all_ws = registry.get_all_witness_sets()

        assert all_ws == {}

    def test_has_witness_set_returns_true_for_existing(self, registry):
        """has_witness_set returns True for namespace with WitnessSet"""
        assert registry.has_witness_set("corp") is True

    def test_has_witness_set_returns_false_for_nonexistent(self, registry):
        """has_witness_set returns False for namespace without WitnessSet"""
        assert registry.has_witness_set("nonexistent") is False

    def test_has_witness_set_returns_false_for_legacy(self, chain_without_witnessset):
        """has_witness_set returns False for legacy Genesis"""
        registry = WitnessRegistry(chain_without_witnessset)
        assert registry.has_witness_set("acme") is False


class TestRegistryStateless:
    """Test that registry rebuilds from chain each query (no caching)"""

    def test_registry_rebuilds_on_each_query(self):
        """Registry rebuilds from chain state on each query"""
        chain = Chain()
        genesis = create_genesis_cell_with_witness_set(
            graph_name="TestGraph",
            root_namespace="corp",
            witnesses=["alice", "bob"],
            threshold=2,
            system_time="2026-01-28T00:00:00Z"
        )
        chain.append(genesis)
        registry = WitnessRegistry(chain)

        # First query
        ws1 = registry.get_witness_set("corp")
        assert ws1 is not None

        # Second query - should rebuild (not cached)
        ws2 = registry.get_witness_set("corp")
        assert ws2 is not None

        # Both should have same values (deterministic rebuild)
        assert ws1.namespace == ws2.namespace
        assert ws1.witnesses == ws2.witnesses
        assert ws1.threshold == ws2.threshold

    def test_registry_no_internal_cache(self, registry):
        """Registry has no _cache or similar attribute"""
        # Registry should only have chain reference, no cache
        assert hasattr(registry, 'chain')
        assert not hasattr(registry, '_cache')
        assert not hasattr(registry, '_witness_sets')


class TestRegistryWithEmptyChain:
    """Test registry behavior with empty chain"""

    def test_empty_chain_returns_none(self):
        """Empty chain (no Genesis) returns None for any namespace"""
        chain = Chain()
        registry = WitnessRegistry(chain)

        ws = registry.get_witness_set("corp")
        assert ws is None

    def test_empty_chain_get_all_returns_empty_dict(self):
        """Empty chain returns empty dict from get_all_witness_sets"""
        chain = Chain()
        registry = WitnessRegistry(chain)

        all_ws = registry.get_all_witness_sets()
        assert all_ws == {}

    def test_empty_chain_has_returns_false(self):
        """Empty chain returns False from has_witness_set"""
        chain = Chain()
        registry = WitnessRegistry(chain)

        assert registry.has_witness_set("corp") is False


class TestRegistryIntegration:
    """Test registry integration and real-world usage"""

    def test_witnessset_usable_after_extraction(self, registry):
        """WitnessSet extracted from registry is fully functional"""
        ws = registry.get_witness_set("corp")

        # WitnessSet should be frozen (immutable)
        with pytest.raises(Exception):  # FrozenInstanceError
            ws.threshold = 3

        # WitnessSet should be hashable
        ws_set = {ws}
        assert ws in ws_set

    def test_deterministic_ordering_in_witnessset(self):
        """Same witnesses in different order produce same WitnessSet"""
        # Create Genesis with unsorted witnesses
        chain1 = Chain()
        genesis1 = create_genesis_cell_with_witness_set(
            graph_name="Graph1",
            root_namespace="corp",
            witnesses=["charlie", "alice", "bob"],  # Unsorted
            threshold=2,
            system_time="2026-01-28T00:00:00Z"
        )
        chain1.append(genesis1)
        registry1 = WitnessRegistry(chain1)

        # Create Genesis with sorted witnesses
        chain2 = Chain()
        genesis2 = create_genesis_cell_with_witness_set(
            graph_name="Graph2",
            root_namespace="corp",
            witnesses=["alice", "bob", "charlie"],  # Sorted
            threshold=2,
            system_time="2026-01-28T00:00:00Z"
        )
        chain2.append(genesis2)
        registry2 = WitnessRegistry(chain2)

        # Both should produce identical WitnessSet
        ws1 = registry1.get_witness_set("corp")
        ws2 = registry2.get_witness_set("corp")

        assert ws1.witnesses == ws2.witnesses
        assert ws1.witnesses == ("alice", "bob", "charlie")  # Sorted

    def test_bootstrap_mode_1_of_1(self):
        """Registry works with bootstrap mode (1-of-1)"""
        chain = Chain()
        genesis = create_genesis_cell_with_witness_set(
            graph_name="DevGraph",
            root_namespace="dev",
            witnesses=["alice"],
            threshold=1,
            system_time="2026-01-28T00:00:00Z"
        )
        chain.append(genesis)
        registry = WitnessRegistry(chain)

        ws = registry.get_witness_set("dev")
        assert ws is not None
        assert ws.threshold == 1
        assert ws.witnesses == ("alice",)

    def test_production_mode_3_of_5(self):
        """Registry works with production mode (3-of-5)"""
        chain = Chain()
        genesis = create_genesis_cell_with_witness_set(
            graph_name="ProdGraph",
            root_namespace="prod",
            witnesses=["alice", "bob", "charlie", "diana", "eve"],
            threshold=3,
            system_time="2026-01-28T00:00:00Z"
        )
        chain.append(genesis)
        registry = WitnessRegistry(chain)

        ws = registry.get_witness_set("prod")
        assert ws is not None
        assert ws.threshold == 3
        assert len(ws.witnesses) == 5

    def test_registry_multiple_queries_same_result(self, registry):
        """Multiple queries return equivalent WitnessSets"""
        ws1 = registry.get_witness_set("corp")
        ws2 = registry.get_witness_set("corp")
        ws3 = registry.get_witness_set("corp")

        # All should have same values
        assert ws1.namespace == ws2.namespace == ws3.namespace
        assert ws1.witnesses == ws2.witnesses == ws3.witnesses
        assert ws1.threshold == ws2.threshold == ws3.threshold


# ============================================================================
# TEST EXECUTION
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])

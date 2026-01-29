"""
DecisionGraph Core: WitnessRegistry Module (v1.5)

WitnessRegistry provides a stateless query layer for namespace to WitnessSet lookups.

Purpose:
- Runtime lookup mechanism for determining which witnesses control a namespace
- Extracts initial WitnessSet from Genesis cell (solves bootstrap paradox BOT-01)
- Foundation for WitnessSet change tracking (future WIT-04 implementation)
- Stateless design prevents cache/chain divergence

Design Principles:
- NO CACHING: Always rebuild from Chain state on query
- Chain is source of truth
- Genesis WitnessSet extraction provides bootstrap configuration
- Deterministic ordering ensures same witnesses = same WitnessSet

Usage Example:
    >>> from decisiongraph import create_chain, WitnessRegistry
    >>> from decisiongraph.genesis import create_genesis_cell_with_witness_set
    >>>
    >>> # Create chain with Genesis that has WitnessSet
    >>> chain = Chain()
    >>> genesis = create_genesis_cell_with_witness_set(
    ...     graph_name="ProdGraph",
    ...     root_namespace="corp",
    ...     witnesses=["alice", "bob", "charlie"],
    ...     threshold=2
    ... )
    >>> chain.append(genesis)
    >>>
    >>> # Query the registry
    >>> registry = WitnessRegistry(chain)
    >>> ws = registry.get_witness_set("corp")
    >>> print(f"Namespace: {ws.namespace}, Threshold: {ws.threshold}")
    >>> print(f"Witnesses: {ws.witnesses}")

Extension Point:
This module will be extended in WIT-04 to track WitnessSet changes via
PolicyHead cells. For now, it only extracts the Genesis WitnessSet.
"""

from typing import Optional, Dict, TYPE_CHECKING

from .witnessset import WitnessSet
from .genesis import parse_genesis_witness_set, has_witness_set

if TYPE_CHECKING:
    from .chain import Chain


class WitnessRegistry:
    """
    Stateless query layer for namespace to WitnessSet lookups.

    WitnessRegistry provides runtime access to WitnessSet configurations
    without maintaining an in-memory cache. It always rebuilds from Chain
    state to ensure consistency.

    Current Implementation (v1.5 Phase 2):
    - Extracts WitnessSet from Genesis cell (WIT-03)
    - Returns None for namespaces without WitnessSet
    - Stateless: rebuilds registry on each query

    Future Extensions (WIT-04):
    - Track WitnessSet changes via PolicyHead cells
    - Support WitnessSet history (which witnesses were active when)
    - Bitemporal queries for "what WitnessSet was active at time T"

    Attributes:
        chain: The Chain instance to query (stored as reference)

    Examples:
        >>> # Create registry bound to chain
        >>> registry = WitnessRegistry(chain)
        >>>
        >>> # Get WitnessSet for a namespace
        >>> ws = registry.get_witness_set("corp")
        >>> if ws:
        ...     print(f"Found {ws.threshold}-of-{len(ws.witnesses)} WitnessSet")
        ... else:
        ...     print("No WitnessSet configured")
        >>>
        >>> # Get all WitnessSets
        >>> all_ws = registry.get_all_witness_sets()
        >>> for namespace, ws in all_ws.items():
        ...     print(f"{namespace}: {ws.threshold}-of-{len(ws.witnesses)}")
        >>>
        >>> # Check if namespace has WitnessSet
        >>> if registry.has_witness_set("corp"):
        ...     print("WitnessSet configured")
    """

    def __init__(self, chain: 'Chain'):
        """
        Create a WitnessRegistry bound to a Chain.

        The registry does NOT store WitnessSets - it rebuilds from chain state
        on each query. This ensures the registry always reflects current chain
        state without cache invalidation complexity.

        Args:
            chain: The Chain instance to query

        Examples:
            >>> from decisiongraph import create_chain
            >>> chain = create_chain()
            >>> registry = WitnessRegistry(chain)
        """
        self.chain = chain

    def get_witness_set(self, namespace: str) -> Optional[WitnessSet]:
        """
        Get the current WitnessSet for a namespace.

        Rebuilds registry from Chain state and returns the WitnessSet for
        the given namespace, or None if no WitnessSet is configured.

        Current Implementation (v1.5 Phase 2):
        - Only looks at Genesis WitnessSet
        - Returns WitnessSet if Genesis has one and namespace matches root_namespace
        - Returns None otherwise

        Future Extensions (WIT-04):
        - Check for WitnessSet changes in PolicyHead cells
        - Return most recent WitnessSet for the namespace
        - Support hierarchical namespace matching

        Args:
            namespace: The namespace to query

        Returns:
            WitnessSet for the namespace, or None if not configured

        Examples:
            >>> ws = registry.get_witness_set("corp")
            >>> if ws:
            ...     print(f"Threshold: {ws.threshold}")
            ...     print(f"Witnesses: {', '.join(ws.witnesses)}")
            ... else:
            ...     print("No WitnessSet configured for 'corp'")
        """
        # Build registry from chain state
        witness_sets = self._build_registry()

        # Return WitnessSet for namespace (or None)
        return witness_sets.get(namespace)

    def get_all_witness_sets(self) -> Dict[str, WitnessSet]:
        """
        Get all configured WitnessSets.

        Rebuilds registry from Chain state and returns all namespace to
        WitnessSet mappings.

        Returns:
            Dict mapping namespace to WitnessSet

        Examples:
            >>> all_ws = registry.get_all_witness_sets()
            >>> for namespace, ws in all_ws.items():
            ...     print(f"{namespace}:")
            ...     print(f"  Threshold: {ws.threshold}")
            ...     print(f"  Witnesses: {', '.join(ws.witnesses)}")
        """
        return self._build_registry()

    def has_witness_set(self, namespace: str) -> bool:
        """
        Check if a namespace has a WitnessSet configured.

        This is a convenience method that returns True if get_witness_set()
        would return a WitnessSet, False otherwise.

        Args:
            namespace: The namespace to check

        Returns:
            True if WitnessSet exists, False otherwise

        Examples:
            >>> if registry.has_witness_set("corp"):
            ...     ws = registry.get_witness_set("corp")
            ...     # Process WitnessSet
        """
        return self.get_witness_set(namespace) is not None

    def _build_registry(self) -> Dict[str, WitnessSet]:
        """
        Build namespace -> WitnessSet mapping from Chain state.

        This is the core stateless rebuild logic. It extracts WitnessSet
        configurations from the Chain and returns them as a dictionary.

        Current Implementation (v1.5 Phase 2):
        - Extracts Genesis WitnessSet if present
        - Returns single-entry dict mapping root_namespace to WitnessSet
        - Returns empty dict if no Genesis or no WitnessSet in Genesis

        Future Extensions (WIT-04):
        - Scan PolicyHead cells for WitnessSet changes
        - Track WitnessSet history for bitemporal queries
        - Support multiple namespaces with different WitnessSets

        Returns:
            Dict mapping namespace to WitnessSet

        Design Notes:
        - Witnesses are sorted in Genesis, so WitnessSet creation is deterministic
        - Same witnesses in different order = same WitnessSet (via tuple equality)
        - Chain is source of truth (no cache invalidation needed)
        """
        witness_sets: Dict[str, WitnessSet] = {}

        # Check if chain has Genesis
        if not self.chain.has_genesis():
            return witness_sets

        genesis = self.chain.genesis
        if genesis is None:
            return witness_sets

        # Extract WitnessSet from Genesis if present
        if has_witness_set(genesis):
            ws_data = parse_genesis_witness_set(genesis)
            if ws_data:
                # Create WitnessSet from Genesis data
                # Witnesses are already sorted in Genesis, convert list to tuple
                witness_set = WitnessSet(
                    namespace=genesis.fact.namespace,  # root_namespace
                    witnesses=tuple(ws_data['witnesses']),
                    threshold=ws_data['threshold']
                )
                witness_sets[witness_set.namespace] = witness_set

        # Future: Scan PolicyHead cells for WitnessSet changes (WIT-04)
        # for cell in self.chain.find_by_type(CellType.POLICYHEAD):
        #     if is_witnessset_change(cell):
        #         ws = extract_witnessset_from_policyhead(cell)
        #         witness_sets[ws.namespace] = ws

        return witness_sets


# Export public interface
__all__ = [
    'WitnessRegistry',
]

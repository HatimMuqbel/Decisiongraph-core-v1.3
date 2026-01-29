"""
DecisionGraph Core: Shadow Cell Module (v1.6)

Shadow cells are hypothetical variants of base cells created via dataclasses.replace().
They are the foundation of the Oracle layer simulation system.

Purpose:
- Create "what-if" scenarios without mutating original cells
- Enable counterfactual queries against historical data
- Support policy/rule change simulation without contamination

Key properties:
- Shadow cells are valid DecisionCells (pass verify_integrity())
- Shadow cells have distinct cell_id when content changes (SHA-256 recomputed)
- Base cells remain unchanged (immutability preserved via frozen dataclasses)
- Uses dataclasses.replace() - zero new dependencies

Architecture:
- dataclasses.replace() calls __post_init__, automatically recomputing cell_id
- cell_id field is init=False, excluded from replace() arguments
- Nested field replacement requires nested replace() calls
- Shadow cells never appended to base Chain (structural isolation)

Example:
    >>> from decisiongraph import DecisionCell, create_shadow_fact
    >>> # Base reality: Alice's salary is 80000
    >>> base_cell = ...  # existing DecisionCell
    >>> # Shadow reality: What if Alice's salary was 90000?
    >>> shadow_cell = create_shadow_fact(base_cell, object="90000")
    >>> assert shadow_cell.cell_id != base_cell.cell_id  # Different content = different hash
    >>> assert base_cell.fact.object == "80000"  # Original unchanged
"""

from dataclasses import dataclass, field, replace
from typing import Optional, Any, Dict, List, Set, Tuple
import json

from .cell import (
    DecisionCell,
    CellType,
    Fact,
    Header,
    LogicAnchor,
    compute_policy_hash
)
from .chain import Chain


def _replace_fact_fields(base_fact: Fact, **kwargs) -> Fact:
    """
    Replace specific fields in a Fact using dataclasses.replace().

    Helper function for convenience shadow cell creation functions.
    Filters out None values to preserve existing values.

    Args:
        base_fact: Original Fact to create variant from
        **kwargs: Field name -> new value mappings (None values filtered)

    Returns:
        New Fact instance with replaced fields

    Example:
        >>> new_fact = _replace_fact_fields(base_fact, object="new_value", confidence=0.9)
    """
    # Filter out None values - preserve existing values for unspecified fields
    non_none_kwargs = {k: v for k, v in kwargs.items() if v is not None}
    if not non_none_kwargs:
        return base_fact
    return replace(base_fact, **non_none_kwargs)


def create_shadow_cell(
    base_cell: DecisionCell,
    fact: Optional[Fact] = None,
    header: Optional[Header] = None,
    logic_anchor: Optional[LogicAnchor] = None
) -> DecisionCell:
    """
    Create a shadow variant of a DecisionCell using dataclasses.replace().

    Shadow cells are hypothetical variants used for simulation.
    The cell_id is automatically recomputed in __post_init__ based on
    modified content, ensuring shadow cells have distinct identities.

    Args:
        base_cell: The original cell to create a shadow from
        fact: Optional replacement Fact (use replace() for nested field changes)
        header: Optional replacement Header
        logic_anchor: Optional replacement LogicAnchor

    Returns:
        New DecisionCell with replaced fields and recomputed cell_id

    Note:
        - Base cell is NEVER modified (frozen dataclass)
        - Shadow cell has DIFFERENT cell_id if any content changed
        - cell_id field is init=False, so replace() triggers __post_init__
        - NEVER pass cell_id to replace() - it will raise TypeError

    Example:
        >>> # Modify fact.object value
        >>> new_fact = replace(base_cell.fact, object="90000")
        >>> shadow = create_shadow_cell(base_cell, fact=new_fact)
        >>> assert shadow.cell_id != base_cell.cell_id
    """
    # Build kwargs dict with only non-None values
    kwargs = {}
    if fact is not None:
        kwargs['fact'] = fact
    if header is not None:
        kwargs['header'] = header
    if logic_anchor is not None:
        kwargs['logic_anchor'] = logic_anchor

    # Use dataclasses.replace() to create new cell
    # This calls __post_init__, which recomputes cell_id
    shadow_cell = replace(base_cell, **kwargs)

    return shadow_cell


def create_shadow_fact(
    base_cell: DecisionCell,
    object: Optional[str] = None,
    confidence: Optional[float] = None,
    valid_from: Optional[str] = None,
    valid_to: Optional[str] = None
) -> DecisionCell:
    """
    Convenience function: Create shadow cell with modified Fact fields.

    Most common shadow case: changing fact.object value for "what-if" scenarios.

    Args:
        base_cell: Original cell to create shadow from
        object: Optional new fact.object value (e.g., "90000" for salary)
        confidence: Optional new confidence value (0.0 to 1.0)
        valid_from: Optional new valid_from timestamp (ISO 8601 UTC)
        valid_to: Optional new valid_to timestamp (ISO 8601 UTC)

    Returns:
        New DecisionCell with modified Fact and recomputed cell_id

    Example:
        >>> # What if Alice's salary was 90000?
        >>> shadow = create_shadow_fact(base_cell, object="90000")
        >>> assert shadow.fact.object == "90000"
        >>> assert base_cell.fact.object == "80000"  # Original unchanged
    """
    # Create new fact with replaced fields
    new_fact = _replace_fact_fields(
        base_cell.fact,
        object=object,
        confidence=confidence,
        valid_from=valid_from,
        valid_to=valid_to
    )

    # Create shadow cell with new fact
    return create_shadow_cell(base_cell, fact=new_fact)


def create_shadow_rule(
    base_cell: DecisionCell,
    rule_logic_hash: Optional[str] = None
) -> DecisionCell:
    """
    Convenience function: Create shadow cell with modified rule logic hash.

    Used for "what-if this rule used different logic?" simulations.

    Args:
        base_cell: Original rule cell to create shadow from
        rule_logic_hash: Optional new rule_logic_hash (SHA-256 hex string)

    Returns:
        New DecisionCell with modified LogicAnchor and recomputed cell_id

    Example:
        >>> # What if rule used different logic?
        >>> shadow = create_shadow_rule(base_cell, rule_logic_hash="abc123...")
        >>> assert shadow.logic_anchor.rule_logic_hash == "abc123..."
    """
    if rule_logic_hash is None:
        # No change - return cell unchanged
        return base_cell

    # Create new logic anchor with replaced rule_logic_hash
    new_logic_anchor = replace(
        base_cell.logic_anchor,
        rule_logic_hash=rule_logic_hash
    )

    # Create shadow cell with new logic anchor
    return create_shadow_cell(base_cell, logic_anchor=new_logic_anchor)


def create_shadow_policy_head(
    base_cell: DecisionCell,
    promoted_rule_ids: Optional[List[str]] = None
) -> DecisionCell:
    """
    Convenience function: Create shadow PolicyHead with different promoted rules.

    Used for "what-if these rules were promoted?" simulations.
    Automatically recomputes policy_hash from new promoted_rule_ids.

    Args:
        base_cell: Original PolicyHead cell to create shadow from
        promoted_rule_ids: Optional new list of promoted rule IDs

    Returns:
        New DecisionCell with modified policy data and recomputed cell_id

    Example:
        >>> # What if different rules were promoted?
        >>> shadow = create_shadow_policy_head(
        ...     base_policyhead,
        ...     promoted_rule_ids=["rule:new_v1", "rule:new_v2"]
        ... )
        >>> data = json.loads(shadow.fact.object)
        >>> assert data["promoted_rule_ids"] == ["rule:new_v1", "rule:new_v2"]

    Note:
        This function assumes base_cell is a PolicyHead cell (CellType.POLICY_HEAD).
        policy_hash is recomputed from promoted_rule_ids for consistency.
    """
    if promoted_rule_ids is None:
        # No change - return cell unchanged
        return base_cell

    # Parse existing policy data
    policy_data = json.loads(base_cell.fact.object)

    # Compute new policy_hash for new rule set
    new_policy_hash = compute_policy_hash(promoted_rule_ids)

    # Update policy data with new rules and hash
    new_policy_data = {
        **policy_data,  # Preserve other fields (prev_policy_head, witness_signatures, etc.)
        "promoted_rule_ids": sorted(promoted_rule_ids),  # Deterministic ordering
        "policy_hash": new_policy_hash
    }

    # Create new fact with updated policy data
    new_fact = replace(
        base_cell.fact,
        object=json.dumps(new_policy_data, separators=(',', ':'), sort_keys=True)
    )

    # Create shadow cell with new fact
    return create_shadow_cell(base_cell, fact=new_fact)


def create_shadow_bridge(
    base_cell: DecisionCell,
    object: Optional[str] = None
) -> DecisionCell:
    """
    Convenience function: Create shadow bridge cell with modified target namespace.

    Used for "what-if bridge targeted different namespace?" simulations.

    Args:
        base_cell: Original bridge cell to create shadow from
        object: Optional new target namespace (fact.object contains target)

    Returns:
        New DecisionCell with modified target namespace and recomputed cell_id

    Example:
        >>> # What if bridge targeted different namespace?
        >>> shadow = create_shadow_bridge(base_bridge, object="corp.finance")
        >>> assert shadow.fact.object == "corp.finance"

    Note:
        This function assumes base_cell is a bridge cell (CellType.BRIDGE_RULE).
        fact.object contains the target namespace for bridge rules.
    """
    if object is None:
        # No change - return cell unchanged
        return base_cell

    # Create new fact with replaced target namespace
    new_fact = replace(base_cell.fact, object=object)

    # Create shadow cell with new fact
    return create_shadow_cell(base_cell, fact=new_fact)


# =============================================================================
# OverlayContext Container (v1.6 - 07-02)
# =============================================================================

@dataclass
class OverlayContext:
    """
    Container for shadow cells with deterministic precedence rules.

    OverlayContext holds shadow cells indexed for efficient lookup during
    simulation. It is NOT a registry (no persistent storage) - it's a
    snapshot of hypothetical cells for a single simulation run.

    Precedence rule: When querying with OverlayContext, shadow cells
    override base cells for the same fact key. If no shadow exists for
    a key, the base cell is used.

    Attributes:
        shadow_facts: Dict mapping (namespace, subject, predicate) -> List[DecisionCell]
        shadow_rules: Dict mapping rule_id -> DecisionCell
        shadow_bridges: Dict mapping (source_ns, target_ns) -> DecisionCell
        shadow_policy_heads: Dict mapping namespace -> DecisionCell
        overridden_base_cells: Set of base cell_ids that have shadow overrides

    Usage:
        ctx = OverlayContext()
        ctx.add_shadow_fact(shadow_cell)
        facts = ctx.get_shadow_facts("corp.hr", "employee:alice", "salary")
    """
    shadow_facts: Dict[Tuple[str, str, str], List[DecisionCell]] = field(default_factory=dict)
    shadow_rules: Dict[str, DecisionCell] = field(default_factory=dict)
    shadow_bridges: Dict[Tuple[str, str], DecisionCell] = field(default_factory=dict)
    shadow_policy_heads: Dict[str, DecisionCell] = field(default_factory=dict)
    overridden_base_cells: Set[str] = field(default_factory=set)

    def add_shadow_fact(self, cell: DecisionCell, base_cell_id: Optional[str] = None) -> None:
        """
        Add a shadow fact cell to the context.

        Args:
            cell: Shadow fact cell to add
            base_cell_id: Optional ID of base cell being overridden
        """
        key = (cell.fact.namespace, cell.fact.subject, cell.fact.predicate)
        if key not in self.shadow_facts:
            self.shadow_facts[key] = []
        self.shadow_facts[key].append(cell)

        if base_cell_id:
            self.overridden_base_cells.add(base_cell_id)

    def add_shadow_rule(self, cell: DecisionCell, base_cell_id: Optional[str] = None) -> None:
        """
        Add a shadow rule cell to the context.

        Args:
            cell: Shadow rule cell to add
            base_cell_id: Optional ID of base cell being overridden
        """
        key = cell.logic_anchor.rule_id
        self.shadow_rules[key] = cell

        if base_cell_id:
            self.overridden_base_cells.add(base_cell_id)

    def add_shadow_bridge(self, cell: DecisionCell, base_cell_id: Optional[str] = None) -> None:
        """
        Add a shadow bridge cell to the context.

        Args:
            cell: Shadow bridge cell to add
            base_cell_id: Optional ID of base cell being overridden
        """
        # Bridge key: (source_ns, target_ns)
        # source_ns is in fact.subject, target_ns is in fact.object
        key = (cell.fact.subject, cell.fact.object)
        self.shadow_bridges[key] = cell

        if base_cell_id:
            self.overridden_base_cells.add(base_cell_id)

    def add_shadow_policy_head(self, cell: DecisionCell, base_cell_id: Optional[str] = None) -> None:
        """
        Add a shadow PolicyHead cell to the context.

        Args:
            cell: Shadow PolicyHead cell to add
            base_cell_id: Optional ID of base cell being overridden
        """
        key = cell.fact.namespace
        self.shadow_policy_heads[key] = cell

        if base_cell_id:
            self.overridden_base_cells.add(base_cell_id)

    def get_shadow_facts(self, namespace: str, subject: str, predicate: str) -> List[DecisionCell]:
        """
        Get shadow facts for a given key.

        Args:
            namespace: Fact namespace
            subject: Fact subject
            predicate: Fact predicate

        Returns:
            List of shadow cells (empty if none exist)
        """
        key = (namespace, subject, predicate)
        return self.shadow_facts.get(key, [])

    def get_shadow_rule(self, rule_id: str) -> Optional[DecisionCell]:
        """
        Get shadow rule cell by rule_id.

        Args:
            rule_id: Rule identifier

        Returns:
            Shadow rule cell or None
        """
        return self.shadow_rules.get(rule_id)

    def get_shadow_bridge(self, source_ns: str, target_ns: str) -> Optional[DecisionCell]:
        """
        Get shadow bridge cell.

        Args:
            source_ns: Source namespace
            target_ns: Target namespace

        Returns:
            Shadow bridge cell or None
        """
        key = (source_ns, target_ns)
        return self.shadow_bridges.get(key)

    def get_shadow_policy_head(self, namespace: str) -> Optional[DecisionCell]:
        """
        Get shadow PolicyHead cell for namespace.

        Args:
            namespace: Namespace to query

        Returns:
            Shadow PolicyHead cell or None
        """
        return self.shadow_policy_heads.get(namespace)

    def has_shadow_override(self, namespace: str, subject: str, predicate: str) -> bool:
        """
        Check if a shadow override exists for this fact key.

        Args:
            namespace: Fact namespace
            subject: Fact subject
            predicate: Fact predicate

        Returns:
            True if shadow facts exist for this key
        """
        key = (namespace, subject, predicate)
        return key in self.shadow_facts

    @classmethod
    def from_shadow_cells(cls, shadow_cells: List[DecisionCell]) -> 'OverlayContext':
        """
        Factory method to create OverlayContext from list of shadow cells.

        Categorizes cells by type and adds to appropriate index.

        Args:
            shadow_cells: List of shadow cells to index

        Returns:
            OverlayContext with all cells indexed
        """
        ctx = cls()

        for cell in shadow_cells:
            cell_type = cell.header.cell_type

            if cell_type == CellType.FACT:
                ctx.add_shadow_fact(cell)
            elif cell_type == CellType.RULE:
                ctx.add_shadow_rule(cell)
            elif cell_type == CellType.BRIDGE_RULE:
                ctx.add_shadow_bridge(cell)
            elif cell_type == CellType.POLICY_HEAD:
                ctx.add_shadow_policy_head(cell)
            # Other types are ignored (Genesis, Decision, etc.)

        return ctx


# =============================================================================
# Structural Contamination Prevention (v1.6 - 07-02)
# =============================================================================

def fork_shadow_chain(base_chain: Chain) -> Chain:
    """
    Create a shadow chain as a structural copy of the base chain.

    This is the core contamination prevention mechanism. The shadow chain
    is a SEPARATE Chain instance that shares cell references with the base
    chain (memory-efficient) but has its own cells list and index.

    Structural isolation means:
    - shadow_chain.append() modifies shadow_chain.cells
    - base_chain.cells is NEVER modified by shadow operations
    - Impossible to contaminate base chain because it's a different object

    Args:
        base_chain: The production chain to fork from

    Returns:
        New Chain instance with shallow copy of cells and index

    Example:
        shadow_chain = fork_shadow_chain(base_chain)
        shadow_chain.append(shadow_cell)  # Only affects shadow_chain
        assert len(base_chain.cells) == original_length  # Base unchanged

    Note:
        Uses shallow copy of cells list - individual Cell objects are shared
        (they're immutable frozen dataclasses). Only the list container is new.
    """
    return Chain(
        cells=list(base_chain.cells),  # New list, shared cell references
        index=dict(base_chain.index),  # New dict, same mappings
        _graph_id=base_chain.graph_id,
        _root_namespace=base_chain.root_namespace
    )


# Export public interface
__all__ = [
    # Shadow cell creation (07-01)
    'create_shadow_cell',
    'create_shadow_fact',
    'create_shadow_rule',
    'create_shadow_policy_head',
    'create_shadow_bridge',

    # OverlayContext container (07-02)
    'OverlayContext',

    # Contamination prevention (07-02)
    'fork_shadow_chain'
]

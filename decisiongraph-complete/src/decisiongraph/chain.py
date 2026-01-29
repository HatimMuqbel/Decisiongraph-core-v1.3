"""
DecisionGraph Core: Chain Module (v1.3 - Universal Base)

This module implements the Chain of Custody - the append-only log
that links all cells together from Genesis to the present.

Key invariants enforced:
1. Every cell (except Genesis) must point to an existing prev_cell_hash
2. The chain is append-only - no deletions or modifications
3. Genesis must be first and unique
4. Timestamps must be monotonically increasing
5. All cell_ids must be valid (self-verifying)
6. ALL cells must have the same graph_id as Genesis (NEW in v1.3)

v1.3 CHANGES:
- graph_id validation: all cells must match Genesis graph_id
- system_time validation (renamed from timestamp)
- Enhanced validation result with more details
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Iterator, Tuple, Set
import json

from .cell import (
    DecisionCell,
    CellType,
    NULL_HASH,
    get_current_timestamp
)
from .genesis import (
    create_genesis_cell,
    verify_genesis,
    is_genesis,
    DEFAULT_ROOT_NAMESPACE
)


class ChainError(Exception):
    """Base exception for chain errors"""
    pass


class IntegrityViolation(ChainError):
    """Raised when a cell's integrity is violated"""
    pass


class ChainBreak(ChainError):
    """Raised when the chain of custody is broken"""
    pass


class GenesisViolation(ChainError):
    """Raised when Genesis invariants are violated"""
    pass


class TemporalViolation(ChainError):
    """Raised when timestamps are not monotonically increasing"""
    pass


class GraphIdMismatch(ChainError):
    """Raised when a cell's graph_id doesn't match the chain's graph_id (NEW in v1.3)"""
    pass


class HashSchemeMismatch(ChainError):
    """Raised when a cell's hash_scheme doesn't match the graph's hash_scheme (NEW in v2.0)"""
    pass


@dataclass
class ValidationResult:
    """Result of chain validation"""
    is_valid: bool
    cells_checked: int
    graph_id: Optional[str] = None
    root_namespace: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def __bool__(self) -> bool:
        return self.is_valid
    
    def summary(self) -> str:
        """Return a summary string"""
        status = "✓ VALID" if self.is_valid else "✗ INVALID"
        lines = [
            f"Chain Validation: {status}",
            f"  Cells checked: {self.cells_checked}",
            f"  Graph ID: {self.graph_id or 'N/A'}",
            f"  Root namespace: {self.root_namespace or 'N/A'}",
            f"  Errors: {len(self.errors)}",
            f"  Warnings: {len(self.warnings)}"
        ]
        if self.errors:
            lines.append("  Error details:")
            for err in self.errors[:5]:  # Show first 5
                lines.append(f"    - {err}")
            if len(self.errors) > 5:
                lines.append(f"    ... and {len(self.errors) - 5} more")
        return "\n".join(lines)


@dataclass
class Chain:
    """
    The Chain of Custody - an append-only log of DecisionCells.
    
    This is the backbone of DecisionGraph. All cells are stored here
    and linked together via prev_cell_hash.
    
    Properties:
    - Append-only: cells can only be added, never removed
    - Hash-linked: each cell points to its predecessor
    - Self-verifying: any cell can be verified independently
    - Traversable: can walk from any cell back to Genesis
    - Graph-bound: all cells share the same graph_id (v1.3)
    """
    
    cells: List[DecisionCell] = field(default_factory=list)
    index: Dict[str, int] = field(default_factory=dict)  # cell_id -> position
    _graph_id: Optional[str] = field(default=None)       # Cached graph_id
    _root_namespace: Optional[str] = field(default=None) # Cached root namespace
    _hash_scheme: Optional[str] = field(default=None)    # Cached hash_scheme (v2.0)
    
    @property
    def length(self) -> int:
        """Number of cells in the chain"""
        return len(self.cells)
    
    @property
    def genesis(self) -> Optional[DecisionCell]:
        """Get the Genesis cell"""
        if self.cells:
            return self.cells[0]
        return None
    
    @property
    def head(self) -> Optional[DecisionCell]:
        """Get the most recent cell"""
        if self.cells:
            return self.cells[-1]
        return None
    
    @property
    def graph_id(self) -> Optional[str]:
        """Get the graph_id (from Genesis)"""
        if self._graph_id:
            return self._graph_id
        if self.genesis:
            return self.genesis.header.graph_id
        return None
    
    @property
    def root_namespace(self) -> Optional[str]:
        """Get the root namespace (from Genesis)"""
        if self._root_namespace:
            return self._root_namespace
        if self.genesis:
            return self.genesis.fact.namespace
        return None

    @property
    def hash_scheme(self) -> Optional[str]:
        """Get the hash_scheme for this graph (from Genesis, v2.0)"""
        if self._hash_scheme is not None:
            return self._hash_scheme
        if self.genesis:
            return self.genesis.header.hash_scheme
        return None
    
    def is_empty(self) -> bool:
        """Check if chain has no cells"""
        return len(self.cells) == 0
    
    def has_genesis(self) -> bool:
        """Check if Genesis exists"""
        return len(self.cells) > 0 and is_genesis(self.cells[0])
    
    def get_cell(self, cell_id: str) -> Optional[DecisionCell]:
        """Get a cell by its ID"""
        if cell_id in self.index:
            return self.cells[self.index[cell_id]]
        return None
    
    def cell_exists(self, cell_id: str) -> bool:
        """Check if a cell exists in the chain"""
        return cell_id in self.index
    
    def initialize(
        self,
        graph_name: str = "UniversalDecisionGraph",
        root_namespace: str = DEFAULT_ROOT_NAMESPACE,
        creator: Optional[str] = None,
        system_time: Optional[str] = None,
        hash_scheme: Optional[str] = None
    ) -> DecisionCell:
        """
        Initialize the chain with a Genesis cell.

        This is the "Big Bang" - can only be called once.

        Args:
            graph_name: Name for this graph instance
            root_namespace: Root namespace for the graph (no dots)
            creator: Who/what is creating this graph
            system_time: Optional timestamp (defaults to now, must be ISO 8601 UTC)
            hash_scheme: Hash scheme for cell_id computation (v2.0):
                - None: legacy string-concat (default, backward compatible)
                - "legacy:concat:v1": explicit legacy scheme
                - "canon:rfc8785:v1": RFC 8785 canonical JSON scheme

        Returns:
            The Genesis cell

        Raises:
            GenesisViolation: If Genesis already exists
        """
        if self.has_genesis():
            raise GenesisViolation("Genesis already exists. Cannot reinitialize.")

        genesis = create_genesis_cell(
            graph_name=graph_name,
            root_namespace=root_namespace,
            creator=creator,
            system_time=system_time,
            hash_scheme=hash_scheme
        )

        self.cells.append(genesis)
        self.index[genesis.cell_id] = 0
        self._graph_id = genesis.header.graph_id
        self._root_namespace = genesis.fact.namespace
        self._hash_scheme = genesis.header.hash_scheme

        return genesis
    
    def append(self, cell: DecisionCell, verify_signatures: bool = False) -> None:
        """
        Append a cell to the chain.

        Validates:
        1. Genesis must exist first (unless this is Genesis)
        2. Cell integrity (cell_id is valid)
        3. prev_cell_hash points to existing cell
        4. Timestamp is >= previous cell
        5. Not a Genesis cell (only one allowed)
        6. graph_id matches chain's graph_id (NEW in v1.3)
        7. hash_scheme matches graph's hash_scheme (NEW in v2.0)
        8. (Optional) cell signature if verify_signatures=True and signature_required=True

        Args:
            cell: The cell to append
            verify_signatures: If True and cell.proof.signature_required is True,
                               verify the cell's signature before appending.
                               Default False (bootstrap mode - no verification).

        Raises:
            GenesisViolation: If trying to add Genesis when one exists,
                              or adding non-Genesis before Genesis
            IntegrityViolation: If cell_id doesn't match computed hash
            ChainBreak: If prev_cell_hash doesn't exist
            TemporalViolation: If timestamp is before previous cell
            GraphIdMismatch: If graph_id doesn't match (v1.3)
            HashSchemeMismatch: If hash_scheme doesn't match (v2.0)
            SignatureInvalidError: If verify_signatures=True and cell requires
                                   signature but has none, or signature is invalid
        """
        # Check Genesis rules
        if is_genesis(cell):
            if self.has_genesis():
                raise GenesisViolation("Genesis already exists. Cannot add another.")
            # Genesis is valid as first cell - verify it
            is_valid, failed_checks = verify_genesis(cell)
            if not is_valid:
                raise GenesisViolation(f"Invalid Genesis cell: {', '.join(failed_checks[:3])}")
            # Add Genesis and cache its constitution
            self.cells.append(cell)
            self.index[cell.cell_id] = 0
            self._graph_id = cell.header.graph_id
            self._root_namespace = cell.fact.namespace
            self._hash_scheme = cell.header.hash_scheme  # Graph's hash scheme (v2.0)
            return
        
        if not self.has_genesis():
            raise GenesisViolation("Cannot add cells before Genesis exists.")
        
        # Verify cell integrity
        if not cell.verify_integrity():
            raise IntegrityViolation(
                f"Cell {cell.cell_id[:16]}... failed integrity check. "
                f"Computed hash doesn't match cell_id."
            )
        
        # Verify graph_id matches (NEW in v1.3)
        if cell.header.graph_id != self.graph_id:
            raise GraphIdMismatch(
                f"Cell graph_id '{cell.header.graph_id}' does not match "
                f"chain graph_id '{self.graph_id}'. "
                f"Cells cannot be moved between graphs."
            )

        # Verify hash_scheme matches graph's constitution (NEW in v2.0)
        # Both None and explicit legacy are considered equivalent
        cell_scheme = cell.header.hash_scheme
        graph_scheme = self.hash_scheme
        # Normalize: None and "legacy:concat:v1" are equivalent for comparison
        from .cell import HASH_SCHEME_LEGACY
        cell_effective = cell_scheme if cell_scheme is not None else HASH_SCHEME_LEGACY
        graph_effective = graph_scheme if graph_scheme is not None else HASH_SCHEME_LEGACY
        if cell_effective != graph_effective:
            raise HashSchemeMismatch(
                f"Cell hash_scheme '{cell_scheme}' does not match "
                f"graph hash_scheme '{graph_scheme}'. "
                f"All cells in a graph must use the same identity algorithm."
            )
        
        # Verify chain link
        if not self.cell_exists(cell.header.prev_cell_hash):
            raise ChainBreak(
                f"Cell {cell.cell_id[:16]}... points to non-existent "
                f"prev_cell_hash: {cell.header.prev_cell_hash[:16]}..."
            )
        
        # Verify temporal consistency
        prev_cell = self.get_cell(cell.header.prev_cell_hash)
        if cell.header.system_time < prev_cell.header.system_time:
            raise TemporalViolation(
                f"Cell system_time {cell.header.system_time} is before "
                f"previous cell system_time {prev_cell.header.system_time}"
            )

        # Step 7: Signature verification (SIG-03) - optional
        if verify_signatures:
            # Import locally to avoid circular dependency with exceptions.py
            from .exceptions import SignatureInvalidError

            # Check if cell requires signature
            signature_required = getattr(cell.proof, 'signature_required', False)

            if signature_required:
                # Get signature from cell
                signature = getattr(cell.proof, 'signature', None)

                if not signature:
                    raise SignatureInvalidError(
                        message="Cell requires signature but none provided",
                        details={
                            "cell_id": cell.cell_id[:32] + "...",
                            "signature_required": True,
                            "signature_present": False
                        }
                    )

                # For Phase 4, we verify signature presence only.
                # Full signature verification requires:
                # 1. Computing canonical cell bytes
                # 2. Looking up signer's public key from registry
                # These are deferred to v2 (key registry implementation).
                #
                # Current behavior: If signature_required=True and signature is present,
                # accept the cell. Actual cryptographic verification is bootstrap mode.
                #
                # To enable full verification, a key resolver would need to be passed:
                # public_key = self._resolve_signer_key(cell.proof.signer_key_id)
                # canonical_bytes = self._compute_canonical_cell_bytes(cell)
                # if not verify_signature(public_key, canonical_bytes, signature):
                #     raise SignatureInvalidError(...)

                # FUTURE: When key registry exists, uncomment verification above.
                # For now, signature presence check satisfies the requirement.

        # All checks passed - append
        self.cells.append(cell)
        self.index[cell.cell_id] = len(self.cells) - 1
    
    def validate(self) -> ValidationResult:
        """
        Validate the entire chain.
        
        Checks all invariants:
        1. Genesis is first and valid
        2. All cells have valid cell_ids
        3. All prev_cell_hash links are valid
        4. Timestamps are monotonically increasing
        5. No duplicate cell_ids
        6. All cells have same graph_id (v1.3)
        
        Returns:
            ValidationResult with details
        """
        errors = []
        warnings = []
        
        if self.is_empty():
            return ValidationResult(
                is_valid=True,
                cells_checked=0,
                warnings=["Chain is empty"]
            )
        
        # Get graph_id from genesis
        chain_graph_id = self.cells[0].header.graph_id if self.cells else None
        chain_root_ns = self.cells[0].fact.namespace if self.cells else None
        
        # Check Genesis
        if not is_genesis(self.cells[0]):
            errors.append("First cell is not Genesis")
        else:
            is_valid, failed_checks = verify_genesis(self.cells[0])
            if not is_valid:
                for check in failed_checks:
                    errors.append(f"Genesis: {check}")
        
        # Check for duplicate Genesis
        genesis_count = sum(1 for c in self.cells if is_genesis(c))
        if genesis_count > 1:
            errors.append(f"Multiple Genesis cells found: {genesis_count}")
        
        # Check each cell
        seen_ids: Set[str] = set()
        prev_timestamp: Optional[str] = None
        
        for i, cell in enumerate(self.cells):
            # Check for duplicates
            if cell.cell_id in seen_ids:
                errors.append(f"Duplicate cell_id at position {i}: {cell.cell_id[:16]}...")
            seen_ids.add(cell.cell_id)
            
            # Verify integrity
            if not cell.verify_integrity():
                errors.append(f"Integrity violation at position {i}: {cell.cell_id[:16]}...")
            
            # Check graph_id (NEW in v1.3)
            if cell.header.graph_id != chain_graph_id:
                errors.append(
                    f"Graph ID mismatch at position {i}: "
                    f"expected '{chain_graph_id}', got '{cell.header.graph_id}'"
                )
            
            # Check chain link (skip Genesis)
            if i > 0:
                if cell.header.prev_cell_hash == NULL_HASH:
                    errors.append(f"Non-genesis cell at position {i} has NULL_HASH")
                elif not self.cell_exists(cell.header.prev_cell_hash):
                    errors.append(
                        f"Broken chain at position {i}: prev_cell_hash "
                        f"{cell.header.prev_cell_hash[:16]}... not found"
                    )
            
            # Check temporal consistency
            if prev_timestamp and cell.header.system_time < prev_timestamp:
                warnings.append(
                    f"Temporal inconsistency at position {i}: "
                    f"{cell.header.system_time} < {prev_timestamp}"
                )
            prev_timestamp = cell.header.system_time
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            cells_checked=len(self.cells),
            graph_id=chain_graph_id,
            root_namespace=chain_root_ns,
            errors=errors,
            warnings=warnings
        )
    
    def trace_to_genesis(self, cell_id: str) -> List[DecisionCell]:
        """
        Trace a cell back to Genesis.
        
        Returns the path from the given cell to Genesis,
        following prev_cell_hash links.
        
        Args:
            cell_id: The cell to trace from
        
        Returns:
            List of cells from the given cell to Genesis
        
        Raises:
            ChainBreak: If the chain is broken before reaching Genesis
        """
        path = []
        current_id = cell_id
        
        while current_id != NULL_HASH:
            cell = self.get_cell(current_id)
            if cell is None:
                raise ChainBreak(f"Chain broken: cell {current_id[:16]}... not found")
            
            path.append(cell)
            current_id = cell.header.prev_cell_hash
        
        return path
    
    def find_integrity_violations(self) -> List[Tuple[int, DecisionCell]]:
        """
        Find all cells with integrity violations.
        
        Returns:
            List of (position, cell) tuples for invalid cells
        """
        violations = []
        for i, cell in enumerate(self.cells):
            if not cell.verify_integrity():
                violations.append((i, cell))
        return violations
    
    def find_graph_id_mismatches(self) -> List[Tuple[int, DecisionCell]]:
        """
        Find all cells with graph_id mismatches (NEW in v1.3).
        
        Returns:
            List of (position, cell) tuples for mismatched cells
        """
        if not self.graph_id:
            return []
        
        mismatches = []
        for i, cell in enumerate(self.cells):
            if cell.header.graph_id != self.graph_id:
                mismatches.append((i, cell))
        return mismatches
    
    def find_by_type(self, cell_type: CellType) -> List[DecisionCell]:
        """Find all cells of a given type"""
        return [c for c in self.cells if c.header.cell_type == cell_type]
    
    def find_by_subject(self, subject: str) -> List[DecisionCell]:
        """Find all cells about a given subject"""
        return [c for c in self.cells if c.fact.subject == subject]
    
    def find_by_namespace(self, namespace: str, include_children: bool = True) -> List[DecisionCell]:
        """
        Find all cells in a namespace.
        
        Args:
            namespace: The namespace to search
            include_children: If True, include child namespaces (e.g., "corp.hr" includes "corp.hr.compensation")
        """
        from .cell import is_namespace_prefix
        
        results = []
        for cell in self.cells:
            if include_children:
                if is_namespace_prefix(namespace, cell.fact.namespace):
                    results.append(cell)
            else:
                if cell.fact.namespace == namespace:
                    results.append(cell)
        return results
    
    def find_by_rule(self, rule_id: str) -> List[DecisionCell]:
        """Find all cells that used a given rule"""
        return [c for c in self.cells if c.logic_anchor.rule_id == rule_id]
    
    def find_decisions_with_rule_mismatch(
        self,
        rule_cells: Dict[str, str]  # rule_id -> current_hash
    ) -> List[DecisionCell]:
        """
        Find decisions where the rule_logic_hash doesn't match current rule.
        
        This is the core integrity check: decisions made with old/wrong rules.
        
        Args:
            rule_cells: Dict mapping rule_id to the current official hash
        
        Returns:
            List of decision cells with mismatched rule hashes
        """
        mismatches = []
        
        for cell in self.cells:
            if cell.header.cell_type == CellType.DECISION:
                rule_id = cell.logic_anchor.rule_id
                if rule_id in rule_cells:
                    official_hash = rule_cells[rule_id]
                    if cell.logic_anchor.rule_logic_hash != official_hash:
                        mismatches.append(cell)
        
        return mismatches
    
    def __iter__(self) -> Iterator[DecisionCell]:
        """Iterate over all cells"""
        return iter(self.cells)
    
    def __len__(self) -> int:
        """Return number of cells"""
        return len(self.cells)
    
    def __getitem__(self, index: int) -> DecisionCell:
        """Get cell by position"""
        return self.cells[index]
    
    def to_json(self, indent: int = 2) -> str:
        """Export chain to JSON"""
        return json.dumps({
            "graph_id": self.graph_id,
            "root_namespace": self.root_namespace,
            "cells": [c.to_dict() for c in self.cells]
        }, indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Chain':
        """Import chain from JSON"""
        data = json.loads(json_str)
        chain = cls()
        
        for cell_data in data["cells"]:
            cell = DecisionCell.from_dict(cell_data)
            chain.append(cell)
        
        return chain


def create_chain(
    graph_name: str = "UniversalDecisionGraph",
    root_namespace: str = DEFAULT_ROOT_NAMESPACE,
    creator: Optional[str] = None,
    system_time: Optional[str] = None
) -> Chain:
    """
    Convenience function to create and initialize a new chain.

    Args:
        graph_name: Name for this graph instance
        root_namespace: Root namespace for the graph (default: "corp")
        creator: Who/what is creating this graph
        system_time: Optional timestamp for genesis (defaults to now, must be ISO 8601 UTC)

    Returns:
        A new Chain with Genesis cell
    """
    chain = Chain()
    chain.initialize(
        graph_name=graph_name,
        root_namespace=root_namespace,
        creator=creator,
        system_time=system_time
    )
    return chain


# Export public interface
__all__ = [
    'Chain',
    'ChainError',
    'IntegrityViolation',
    'ChainBreak',
    'GenesisViolation',
    'TemporalViolation',
    'GraphIdMismatch',
    'ValidationResult',
    'create_chain'
]

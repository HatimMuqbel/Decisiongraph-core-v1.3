"""
DecisionGraph Core: Scholar Module (v1.0)

The Scholar is the query/resolver layer that reads the vault.
It answers: "What do we know, and what follows from it?"

Features:
- Namespace visibility with bridge enforcement
- Bitemporal queries (valid_time + system_time)
- Deterministic conflict resolution
- Proof generation (which facts/bridges were used)

Core Principle: Every answer is traceable to sealed cells.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any
from enum import Enum

from .cell import (
    DecisionCell,
    CellType,
    SourceQuality,
    get_current_timestamp,
    is_namespace_prefix,
    get_parent_namespace
)
from .chain import Chain
from .namespace import (
    NamespaceRegistry,
    build_registry_from_chain,
    Permission
)


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class ResolutionReason(str, Enum):
    """Why a fact won conflict resolution"""
    QUALITY_WIN = "quality_win"         # Higher source_quality
    CONFIDENCE_WIN = "confidence_win"   # Higher confidence
    RECENCY_WIN = "recency_win"         # Later system_time
    HASH_TIEBREAK = "hash_tiebreak"     # Lexicographically smallest cell_id
    SINGLE_CANDIDATE = "single"         # Only one candidate, no conflict


class BridgeEffectivenessReason(str, Enum):
    """Why a bridge was or was not effective at query time"""
    AUTHORIZED = "authorized"                     # Bridge valid and active
    BRIDGE_NOT_YET_KNOWN = "bridge_not_yet_known" # Bridge system_time > query system_time
    BRIDGE_NOT_ACTIVE = "bridge_not_active"       # Bridge valid_from > query valid_time
    BRIDGE_EXPIRED = "bridge_expired"             # Bridge valid_to <= query valid_time
    BRIDGE_REVOKED = "bridge_revoked"             # Bridge explicitly revoked


# Source quality ranking (higher = better)
SOURCE_QUALITY_RANK = {
    SourceQuality.VERIFIED: 3,
    SourceQuality.SELF_REPORTED: 2,
    SourceQuality.INFERRED: 1,
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ResolutionEvent:
    """Record of how a conflict was resolved"""
    conflict_key: Tuple[str, str, str]  # (namespace, subject, predicate)
    winner_cell_id: str
    loser_cell_ids: List[str]
    reason: ResolutionReason


@dataclass
class BridgeEffectiveness:
    """Record of bridge evaluation at query time (for audit/proof)"""
    bridge_cell_id: str
    effective: bool
    reason: BridgeEffectivenessReason


@dataclass
class AuthorizationBasis:
    """Record of WHY access was granted"""
    allowed: bool
    reason: str  # e.g., "same_namespace", "parent_namespace", "child_namespace", "bridge", "bridge_via_parent", "no_access"
    bridges_used: List[str] = field(default_factory=list)
    bridge_effectiveness: List[BridgeEffectiveness] = field(default_factory=list)


@dataclass
class QueryResult:
    """Result of a Scholar query"""
    # The winning facts (effective truth)
    facts: List[DecisionCell]

    # All candidates considered (for proof/audit)
    candidates: List[DecisionCell]

    # Bridge cell_ids used to authorize cross-namespace access
    bridges_used: List[str]

    # How conflicts were resolved
    resolution_events: List[ResolutionEvent]

    # Echo of time filters used
    valid_time: str
    system_time: str

    # Query metadata
    namespace_scope: str
    requester_id: str

    # Authorization basis (WHY access was granted)
    authorization: AuthorizationBasis = field(default_factory=lambda: AuthorizationBasis(
        allowed=False, reason="not_checked", bridges_used=[]
    ))

    @property
    def count(self) -> int:
        return len(self.facts)

    def to_proof_bundle(self) -> Dict:
        """Generate canonical proof bundle for audit/verification.

        All lists are sorted and keys are alphabetically ordered for
        byte-identical output given the same query.

        v1.3 additions:
        - time_filters: explicit bitemporal coordinates
        - bridge_effectiveness: why each bridge was accepted/rejected
        """
        # Sort fact_cell_ids
        fact_cell_ids = sorted([f.cell_id for f in self.facts])

        # Sort candidate_cell_ids
        candidate_cell_ids = sorted([c.cell_id for c in self.candidates])

        # Sort bridges_used
        bridges_used = sorted(self.bridges_used)

        # Sort resolution_events by conflict_key tuple
        sorted_events = sorted(self.resolution_events, key=lambda e: e.conflict_key)
        resolution_events = [
            {
                "key": e.conflict_key,
                "losers": sorted(e.loser_cell_ids),
                "reason": e.reason.value,
                "winner": e.winner_cell_id
            }
            for e in sorted_events
        ]

        # Sort bridge_effectiveness by cell_id for deterministic output
        sorted_bridge_effectiveness = sorted(
            self.authorization.bridge_effectiveness,
            key=lambda be: be.bridge_cell_id
        )
        bridge_effectiveness = [
            {
                "bridge_cell_id": be.bridge_cell_id,
                "effective": be.effective,
                "reason": be.reason.value
            }
            for be in sorted_bridge_effectiveness
        ]

        # Build proof bundle with alphabetically ordered keys
        return {
            "authorization_basis": {
                "allowed": self.authorization.allowed,
                "bridge_effectiveness": bridge_effectiveness,
                "bridges_used": sorted(self.authorization.bridges_used),
                "reason": self.authorization.reason
            },
            "proof": {
                "bridges_used": bridges_used,
                "candidate_cell_ids": candidate_cell_ids,
                "candidates_considered": len(self.candidates),
                "resolution_events": resolution_events
            },
            "query": {
                "namespace_scope": self.namespace_scope,
                "requester_id": self.requester_id
            },
            "results": {
                "fact_cell_ids": fact_cell_ids,
                "fact_count": len(self.facts)
            },
            "scholar_version": "1.3",
            "time_filters": {
                "as_of_system_time": self.system_time,
                "at_valid_time": self.valid_time
            }
        }


@dataclass
class VisibilityResult:
    """Result of namespace visibility check"""
    allowed: bool
    reason: str
    bridges_used: List[str] = field(default_factory=list)
    bridge_effectiveness: List[BridgeEffectiveness] = field(default_factory=list)


# ============================================================================
# SCHOLAR INDEX
# ============================================================================

@dataclass
class ScholarIndex:
    """
    In-memory indexes for fast queries.
    
    Built from chain, enables fast lookups without scanning.
    """
    # cell_id -> DecisionCell
    cell_by_id: Dict[str, DecisionCell] = field(default_factory=dict)
    
    # namespace -> list of cell_ids (sorted by system_time)
    by_namespace: Dict[str, List[str]] = field(default_factory=dict)
    
    # (namespace, subject, predicate) -> list of cell_ids (sorted by system_time)
    by_key: Dict[Tuple[str, str, str], List[str]] = field(default_factory=dict)
    
    # (namespace, subject) -> list of cell_ids
    by_ns_subject: Dict[Tuple[str, str], List[str]] = field(default_factory=dict)
    
    def add_cell(self, cell: DecisionCell):
        """Add a cell to all indexes"""
        cell_id = cell.cell_id
        ns = cell.fact.namespace
        subj = cell.fact.subject
        pred = cell.fact.predicate
        
        # Primary index
        self.cell_by_id[cell_id] = cell
        
        # By namespace
        if ns not in self.by_namespace:
            self.by_namespace[ns] = []
        self.by_namespace[ns].append(cell_id)
        
        # By key (namespace, subject, predicate)
        key = (ns, subj, pred)
        if key not in self.by_key:
            self.by_key[key] = []
        self.by_key[key].append(cell_id)
        
        # By namespace + subject
        ns_subj = (ns, subj)
        if ns_subj not in self.by_ns_subject:
            self.by_ns_subject[ns_subj] = []
        self.by_ns_subject[ns_subj].append(cell_id)
    
    def get_cell(self, cell_id: str) -> Optional[DecisionCell]:
        return self.cell_by_id.get(cell_id)
    
    def get_by_key(self, namespace: str, subject: str, predicate: str) -> List[DecisionCell]:
        """Get cells by exact (namespace, subject, predicate)"""
        key = (namespace, subject, predicate)
        cell_ids = self.by_key.get(key, [])
        return [self.cell_by_id[cid] for cid in cell_ids if cid in self.cell_by_id]
    
    def get_by_namespace(self, namespace: str) -> List[DecisionCell]:
        """Get all cells in a namespace"""
        cell_ids = self.by_namespace.get(namespace, [])
        return [self.cell_by_id[cid] for cid in cell_ids if cid in self.cell_by_id]
    
    def get_by_subject(self, namespace: str, subject: str) -> List[DecisionCell]:
        """Get all cells for a subject in a namespace"""
        key = (namespace, subject)
        cell_ids = self.by_ns_subject.get(key, [])
        return [self.cell_by_id[cid] for cid in cell_ids if cid in self.cell_by_id]


def build_index_from_chain(chain: Chain) -> ScholarIndex:
    """Build Scholar index from chain"""
    index = ScholarIndex()
    
    for cell in chain.cells:
        # Skip system cells (genesis, namespace_def, access_rule, bridge_rule)
        # We only index "content" cells (fact, rule, decision, evidence, override)
        if cell.header.cell_type in (
            CellType.FACT,
            CellType.RULE,
            CellType.DECISION,
            CellType.EVIDENCE,
            CellType.OVERRIDE
        ):
            index.add_cell(cell)
    
    return index


# ============================================================================
# BRIDGE BITEMPORAL LOGIC
# ============================================================================

def is_bridge_effective(
    bridge_cell: DecisionCell,
    at_valid_time: str,
    as_of_system_time: str,
    is_revoked: bool = False
) -> Tuple[bool, BridgeEffectivenessReason]:
    """
    Check if a bridge is effective at the given bitemporal coordinates.

    Two clocks must be satisfied:
    - Clock A (knowledge): bridge.system_time <= as_of_system_time
    - Clock B (validity): bridge.valid_from <= at_valid_time < bridge.valid_to

    Args:
        bridge_cell: The bridge rule cell
        at_valid_time: The valid time for the query (when the truth applies)
        as_of_system_time: The system time for the query (what was known)
        is_revoked: Whether this bridge has been explicitly revoked

    Returns:
        (effective: bool, reason: BridgeEffectivenessReason)
    """
    if is_revoked:
        return (False, BridgeEffectivenessReason.BRIDGE_REVOKED)

    # Clock A: Was the bridge known at query time?
    # Bridge must have been recorded before the query's system_time
    if bridge_cell.header.system_time > as_of_system_time:
        return (False, BridgeEffectivenessReason.BRIDGE_NOT_YET_KNOWN)

    # Clock B: Was the bridge active at query's valid_time?
    # valid_from must be <= at_valid_time
    bridge_valid_from = bridge_cell.fact.valid_from
    if bridge_valid_from and bridge_valid_from > at_valid_time:
        return (False, BridgeEffectivenessReason.BRIDGE_NOT_ACTIVE)

    # valid_to must be > at_valid_time (or None for open-ended)
    bridge_valid_to = bridge_cell.fact.valid_to
    if bridge_valid_to is not None and bridge_valid_to <= at_valid_time:
        return (False, BridgeEffectivenessReason.BRIDGE_EXPIRED)

    return (True, BridgeEffectivenessReason.AUTHORIZED)


# ============================================================================
# SCHOLAR (THE RESOLVER)
# ============================================================================

class Scholar:
    """
    The Scholar reads the vault and answers queries.
    
    It does NOT create facts - it only reads and derives.
    Every answer is traceable to sealed cells.
    """
    
    def __init__(self, chain: Chain):
        self.chain = chain
        self.index = build_index_from_chain(chain)
        self.registry = build_registry_from_chain(chain.cells)
    
    def refresh(self):
        """Refresh indexes after chain changes"""
        self.index = build_index_from_chain(self.chain)
        self.registry = build_registry_from_chain(self.chain.cells)
    
    # ========================================================================
    # VISIBILITY / JURISDICTION
    # ========================================================================
    
    def check_visibility(
        self,
        requester_namespace: str,
        target_namespace: str,
        at_valid_time: str,
        as_of_system_time: str
    ) -> VisibilityResult:
        """
        Check if requester can access target namespace at given bitemporal coordinates.

        Rules (in order):
        1. Same namespace -> allowed
        2. Parent/child relationship -> allowed
        3. Explicit bridge exists AND is effective -> allowed
        4. Bridge via parent namespace AND is effective -> allowed
        5. Otherwise -> denied

        Bridge effectiveness requires both clocks to be satisfied:
        - Clock A (knowledge): bridge.system_time <= as_of_system_time
        - Clock B (validity): bridge.valid_from <= at_valid_time < bridge.valid_to

        Returns VisibilityResult with bridges_used and bridge_effectiveness for proof.
        """
        # Same namespace
        if requester_namespace == target_namespace:
            return VisibilityResult(True, "same_namespace")

        # Parent can see child
        if is_namespace_prefix(requester_namespace, target_namespace):
            return VisibilityResult(True, "parent_namespace")

        # Child can see parent
        if is_namespace_prefix(target_namespace, requester_namespace):
            return VisibilityResult(True, "child_namespace")

        # Check for bridge with bitemporal validation
        bridges_used = []
        bridge_effectiveness_list = []

        # Direct bridge
        bridge_key = (requester_namespace, target_namespace)
        if bridge_key in self.registry.bridges:
            bridge_cell = self.registry.bridges[bridge_key]
            is_revoked = bridge_cell.cell_id in self.registry.revoked_bridges

            effective, reason = is_bridge_effective(
                bridge_cell, at_valid_time, as_of_system_time, is_revoked
            )
            bridge_effectiveness_list.append(
                BridgeEffectiveness(bridge_cell.cell_id, effective, reason)
            )

            if effective:
                bridges_used.append(bridge_cell.cell_id)
                return VisibilityResult(
                    True, "bridge", bridges_used, bridge_effectiveness_list
                )

        # Bridge via parent
        parent = get_parent_namespace(requester_namespace)
        while parent:
            parent_bridge_key = (parent, target_namespace)
            if parent_bridge_key in self.registry.bridges:
                bridge_cell = self.registry.bridges[parent_bridge_key]
                is_revoked = bridge_cell.cell_id in self.registry.revoked_bridges

                effective, reason = is_bridge_effective(
                    bridge_cell, at_valid_time, as_of_system_time, is_revoked
                )
                bridge_effectiveness_list.append(
                    BridgeEffectiveness(bridge_cell.cell_id, effective, reason)
                )

                if effective:
                    bridges_used.append(bridge_cell.cell_id)
                    return VisibilityResult(
                        True, "bridge_via_parent", bridges_used, bridge_effectiveness_list
                    )
            parent = get_parent_namespace(parent)

        return VisibilityResult(False, "no_access", [], bridge_effectiveness_list)
    
    def visible_namespaces(
        self,
        requester_namespace: str,
        as_of_system_time: Optional[str] = None
    ) -> Set[str]:
        """
        Get all namespaces visible to requester.
        
        Returns deterministically sorted set.
        """
        visible = set()
        
        # Own namespace and all children
        for ns in self.registry.namespaces.keys():
            if ns == requester_namespace:
                visible.add(ns)
            elif is_namespace_prefix(requester_namespace, ns):
                visible.add(ns)  # Child
            elif is_namespace_prefix(ns, requester_namespace):
                visible.add(ns)  # Parent
        
        # Add root namespace
        if self.chain.root_namespace:
            visible.add(self.chain.root_namespace)
        
        # Via bridges
        for (source, target), bridge_cell in self.registry.bridges.items():
            if bridge_cell.cell_id in self.registry.revoked_bridges:
                continue
            
            # Direct bridge from requester
            if source == requester_namespace:
                visible.add(target)
            
            # Bridge from parent
            parent = get_parent_namespace(requester_namespace)
            while parent:
                if source == parent:
                    visible.add(target)
                parent = get_parent_namespace(parent)
        
        return visible
    
    # ========================================================================
    # BITEMPORAL FILTERING
    # ========================================================================
    
    def _is_valid_at_time(
        self,
        cell: DecisionCell,
        valid_time: str,
        system_time: str
    ) -> bool:
        """
        Check if fact is valid at given times.
        
        Valid time condition:
            valid_from <= valid_time < valid_to (or valid_to is None)
        
        System time condition:
            cell.header.system_time <= system_time
        """
        # System time check: fact must have been recorded by system_time
        if cell.header.system_time > system_time:
            return False
        
        # Valid time check
        valid_from = cell.fact.valid_from or cell.header.system_time
        valid_to = cell.fact.valid_to  # None means forever
        
        if valid_from > valid_time:
            return False
        
        if valid_to is not None and valid_time >= valid_to:
            return False
        
        return True
    
    # ========================================================================
    # CONFLICT RESOLUTION
    # ========================================================================
    
    def _resolve_conflicts(
        self,
        candidates: List[DecisionCell]
    ) -> Tuple[List[DecisionCell], List[ResolutionEvent]]:
        """
        Resolve conflicts among candidate facts.
        
        Conflict key: (namespace, subject, predicate)
        
        Resolution order:
        1. Higher source_quality (verified > self_reported > inferred)
        2. Higher confidence
        3. Later system_time (most recent knowledge)
        4. Lexicographically smallest cell_id (deterministic tiebreak)
        
        Returns (winners, resolution_events)
        """
        if not candidates:
            return [], []
        
        # Group by conflict key
        groups: Dict[Tuple[str, str, str], List[DecisionCell]] = {}
        for cell in candidates:
            key = (cell.fact.namespace, cell.fact.subject, cell.fact.predicate)
            if key not in groups:
                groups[key] = []
            groups[key].append(cell)
        
        winners = []
        events = []
        
        for key, group in groups.items():
            if len(group) == 1:
                # No conflict
                winners.append(group[0])
                events.append(ResolutionEvent(
                    conflict_key=key,
                    winner_cell_id=group[0].cell_id,
                    loser_cell_ids=[],
                    reason=ResolutionReason.SINGLE_CANDIDATE
                ))
            else:
                # Resolve conflict
                winner, losers, reason = self._pick_winner(group)
                winners.append(winner)
                events.append(ResolutionEvent(
                    conflict_key=key,
                    winner_cell_id=winner.cell_id,
                    loser_cell_ids=[c.cell_id for c in losers],
                    reason=reason
                ))
        
        return winners, events
    
    def _pick_winner(
        self,
        candidates: List[DecisionCell]
    ) -> Tuple[DecisionCell, List[DecisionCell], ResolutionReason]:
        """
        Pick winner from conflicting candidates.
        
        Returns (winner, losers, reason)
        """
        # Sort by resolution criteria
        def sort_key(cell: DecisionCell):
            return (
                -SOURCE_QUALITY_RANK.get(cell.fact.source_quality, 0),  # Higher is better (negative for desc)
                -cell.fact.confidence,  # Higher is better
                cell.header.system_time,  # Later is better (will reverse)
                cell.cell_id  # Tiebreak
            )
        
        sorted_candidates = sorted(candidates, key=sort_key)
        
        # Determine why winner won
        winner = sorted_candidates[0]
        
        # Check what differentiated winner from second place
        if len(sorted_candidates) > 1:
            second = sorted_candidates[1]
            
            winner_quality = SOURCE_QUALITY_RANK.get(winner.fact.source_quality, 0)
            second_quality = SOURCE_QUALITY_RANK.get(second.fact.source_quality, 0)
            
            if winner_quality > second_quality:
                reason = ResolutionReason.QUALITY_WIN
            elif winner.fact.confidence > second.fact.confidence:
                reason = ResolutionReason.CONFIDENCE_WIN
            elif winner.header.system_time > second.header.system_time:
                reason = ResolutionReason.RECENCY_WIN
            else:
                reason = ResolutionReason.HASH_TIEBREAK
        else:
            reason = ResolutionReason.SINGLE_CANDIDATE
        
        # Re-sort properly: we want highest quality, highest confidence, LATEST system_time
        def proper_sort_key(cell: DecisionCell):
            return (
                SOURCE_QUALITY_RANK.get(cell.fact.source_quality, 0),  # Higher is better
                cell.fact.confidence,  # Higher is better
                cell.header.system_time,  # Later is better
                cell.cell_id  # Tiebreak: smallest wins
            )
        
        sorted_candidates = sorted(candidates, key=proper_sort_key, reverse=True)
        # But for cell_id tiebreak, smaller should win, so we need custom logic
        
        # Actually, let's be explicit:
        sorted_candidates = sorted(candidates, key=lambda c: (
            -SOURCE_QUALITY_RANK.get(c.fact.source_quality, 0),
            -c.fact.confidence,
            c.header.system_time,  # We want LATER, so this should be reversed too
        ))
        
        # Re-sort with correct logic
        # Higher quality wins, higher confidence wins, later system_time wins, smaller cell_id wins
        best = None
        for cell in candidates:
            if best is None:
                best = cell
                continue
            
            # Compare
            cell_quality = SOURCE_QUALITY_RANK.get(cell.fact.source_quality, 0)
            best_quality = SOURCE_QUALITY_RANK.get(best.fact.source_quality, 0)
            
            if cell_quality > best_quality:
                best = cell
            elif cell_quality == best_quality:
                if cell.fact.confidence > best.fact.confidence:
                    best = cell
                elif cell.fact.confidence == best.fact.confidence:
                    if cell.header.system_time > best.header.system_time:
                        best = cell
                    elif cell.header.system_time == best.header.system_time:
                        if cell.cell_id < best.cell_id:
                            best = cell
        
        winner = best
        losers = [c for c in candidates if c.cell_id != winner.cell_id]
        
        # Determine reason
        if len(losers) > 0:
            # Compare winner to best loser
            best_loser = losers[0]
            winner_quality = SOURCE_QUALITY_RANK.get(winner.fact.source_quality, 0)
            loser_quality = SOURCE_QUALITY_RANK.get(best_loser.fact.source_quality, 0)
            
            if winner_quality > loser_quality:
                reason = ResolutionReason.QUALITY_WIN
            elif winner.fact.confidence > best_loser.fact.confidence:
                reason = ResolutionReason.CONFIDENCE_WIN
            elif winner.header.system_time > best_loser.header.system_time:
                reason = ResolutionReason.RECENCY_WIN
            else:
                reason = ResolutionReason.HASH_TIEBREAK
        
        return winner, losers, reason
    
    # ========================================================================
    # MAIN QUERY API
    # ========================================================================
    
    def query_facts(
        self,
        requester_namespace: str,
        namespace: str,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object_value: Optional[str] = None,
        at_valid_time: Optional[str] = None,
        as_of_system_time: Optional[str] = None,
        requester_id: str = "anonymous"
    ) -> QueryResult:
        """
        Query facts from the vault.
        
        Args:
            requester_namespace: Namespace of the requester (for bridge checking)
            namespace: Target namespace to query
            subject: Filter by subject (None = all)
            predicate: Filter by predicate (None = all)
            object_value: Filter by object value (None = all)
            at_valid_time: Point in valid time (default: now)
            as_of_system_time: Point in system time (default: now)
            requester_id: Identifier for audit trail
        
        Returns:
            QueryResult with facts, candidates, bridges_used, and resolution_events
        """
        # Default times to now
        now = get_current_timestamp()
        valid_time = at_valid_time or now
        system_time = as_of_system_time or now

        # Check visibility with bitemporal coordinates
        visibility = self.check_visibility(
            requester_namespace, namespace, valid_time, system_time
        )

        # Convert VisibilityResult to AuthorizationBasis (includes bridge_effectiveness)
        authorization = AuthorizationBasis(
            allowed=visibility.allowed,
            reason=visibility.reason,
            bridges_used=visibility.bridges_used.copy(),
            bridge_effectiveness=visibility.bridge_effectiveness.copy()
        )

        if not visibility.allowed:
            # Return empty result with reason
            return QueryResult(
                facts=[],
                candidates=[],
                bridges_used=[],
                resolution_events=[],
                valid_time=valid_time,
                system_time=system_time,
                namespace_scope=namespace,
                requester_id=requester_id,
                authorization=authorization
            )
        
        # Get candidates based on filters
        if subject and predicate:
            # Exact key lookup
            candidates = self.index.get_by_key(namespace, subject, predicate)
        elif subject:
            # All predicates for subject
            candidates = self.index.get_by_subject(namespace, subject)
        else:
            # All cells in namespace
            candidates = self.index.get_by_namespace(namespace)
        
        # Filter by predicate if specified (when subject is None)
        if predicate and not subject:
            candidates = [c for c in candidates if c.fact.predicate == predicate]
        
        # Filter by object if specified
        if object_value:
            candidates = [c for c in candidates if c.fact.object == object_value]
        
        # Apply bitemporal filter
        candidates = [
            c for c in candidates 
            if self._is_valid_at_time(c, valid_time, system_time)
        ]
        
        # Resolve conflicts
        winners, resolution_events = self._resolve_conflicts(candidates)

        # Helper to create sort key for a cell
        def cell_sort_key(cell: DecisionCell) -> Tuple:
            return (
                cell.fact.namespace,
                cell.fact.subject,
                cell.fact.predicate,
                cell.header.system_time,
                cell.cell_id
            )

        # Sort facts deterministically
        sorted_facts = sorted(winners, key=cell_sort_key)

        # Sort candidates deterministically
        sorted_candidates = sorted(candidates, key=cell_sort_key)

        # Sort bridges alphabetically
        sorted_bridges = sorted(visibility.bridges_used)

        # Sort resolution_events by conflict_key tuple
        sorted_resolution_events = sorted(resolution_events, key=lambda e: e.conflict_key)

        return QueryResult(
            facts=sorted_facts,
            candidates=sorted_candidates,
            bridges_used=sorted_bridges,
            resolution_events=sorted_resolution_events,
            valid_time=valid_time,
            system_time=system_time,
            namespace_scope=namespace,
            requester_id=requester_id,
            authorization=authorization
        )
    
    # ========================================================================
    # TRAVERSAL
    # ========================================================================
    
    def traverse(
        self,
        requester_namespace: str,
        start_subject: str,
        predicates: List[str],
        namespace: str,
        max_depth: int = 10,
        at_valid_time: Optional[str] = None,
        as_of_system_time: Optional[str] = None
    ) -> List[Tuple[str, List[DecisionCell]]]:
        """
        Traverse relationships from a starting subject.
        
        Args:
            requester_namespace: For bridge checking
            start_subject: Starting entity ID
            predicates: Relationship predicates to follow (e.g., ["reports_to", "owns"])
            namespace: Namespace to traverse in
            max_depth: Maximum traversal depth (cycle protection)
            at_valid_time: Point in valid time
            as_of_system_time: Point in system time
        
        Returns:
            List of (entity_id, path) tuples reached
        """
        now = get_current_timestamp()
        valid_time = at_valid_time or now
        system_time = as_of_system_time or now
        
        visited = set()
        results = []
        
        def _traverse(subject: str, path: List[DecisionCell], depth: int):
            if depth > max_depth:
                return
            if subject in visited:
                return
            
            visited.add(subject)
            results.append((subject, path.copy()))
            
            # Find outgoing relationships
            for pred in predicates:
                query_result = self.query_facts(
                    requester_namespace=requester_namespace,
                    namespace=namespace,
                    subject=subject,
                    predicate=pred,
                    at_valid_time=valid_time,
                    as_of_system_time=system_time
                )
                
                for fact in query_result.facts:
                    # The object is the next entity to visit
                    next_entity = fact.fact.object
                    _traverse(next_entity, path + [fact], depth + 1)
        
        _traverse(start_subject, [], 0)
        return results


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def create_scholar(chain: Chain) -> Scholar:
    """Create a Scholar instance for a chain"""
    return Scholar(chain)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Main class
    'Scholar',
    'create_scholar',

    # Results
    'QueryResult',
    'VisibilityResult',
    'AuthorizationBasis',
    'BridgeEffectiveness',
    'BridgeEffectivenessReason',
    'ResolutionEvent',
    'ResolutionReason',

    # Bridge evaluation
    'is_bridge_effective',

    # Index
    'ScholarIndex',
    'build_index_from_chain',
]

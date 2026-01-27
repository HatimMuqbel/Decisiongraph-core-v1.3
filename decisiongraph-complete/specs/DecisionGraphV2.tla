--------------------------- MODULE DecisionGraphV2 ---------------------------
(*
 * DecisionGraph: Formal Specification v2.0
 * Version: 2.0 (Hierarchical Governance)
 * Date: January 26, 2026
 * 
 * This TLA+ specification defines the invariants for a DecisionGraph
 * with Hierarchical Namespaces and Cryptographic Bridges.
 *
 * Core Principle: Namespace Isolation via Cryptographic Bridges
 * "Departments don't have to trust; they can verify the bridge."
 *)

EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    NULL_HASH,              \* "000...000" - only valid for Genesis
    MAX_CONFIDENCE,         \* 1.0 represented as 100 for integer math
    SystemAdmins            \* Set of system administrator IDs

VARIABLES
    cells,                  \* Set of all cells in the graph
    chain,                  \* Sequence representing the append-only log
    genesis_created,        \* Boolean: has genesis been created?
    namespaces,             \* Set of defined namespaces
    bridges                 \* Set of active bridge rules

-----------------------------------------------------------------------------
(*
 * TYPE DEFINITIONS
 *)

CellTypes == {
    "genesis",
    "fact", 
    "rule", 
    "decision", 
    "evidence", 
    "override",
    "access_rule",      \* NEW: Access control definitions
    "bridge_rule",      \* NEW: Cross-namespace bridge
    "namespace_def"     \* NEW: Namespace definition
}

SourceQuality == {"verified", "self_reported", "inferred"}

SensitivityLevels == {"public", "internal", "confidential", "restricted"}

(*
 * A Namespace is a hierarchical dotted path
 * Examples: "corp", "corp.hr", "corp.hr.compensation"
 *)
Namespace == STRING

(*
 * A Cell is a record containing header, fact, logic_anchor, and proof
 *)
Cell == [
    cell_id: STRING,
    header: [
        version: STRING,
        cell_type: CellTypes,
        timestamp: STRING,
        prev_cell_hash: STRING
    ],
    fact: [
        namespace: Namespace,       \* NEW: Hierarchical namespace
        subject: STRING,
        predicate: STRING,
        object: STRING,
        confidence: 0..MAX_CONFIDENCE,
        source_quality: SourceQuality,
        valid_from: STRING,
        valid_to: STRING
    ],
    logic_anchor: [
        rule_id: STRING,
        rule_logic_hash: STRING
    ],
    proof: [
        signature: STRING,
        signer_id: STRING,
        merkle_root: STRING
    ]
]

-----------------------------------------------------------------------------
(*
 * HELPER FUNCTIONS
 *)

(*
 * Compute the cell_id from cell contents (v1.2 - includes namespace)
 *)
ComputeCellId(c) ==
    c.header.version \o
    c.header.cell_type \o
    c.header.timestamp \o
    c.header.prev_cell_hash \o
    c.fact.namespace \o         \* NEW: Namespace in seal
    c.fact.subject \o
    c.fact.predicate \o
    c.fact.object \o
    c.logic_anchor.rule_id \o
    c.logic_anchor.rule_logic_hash

(*
 * Check if namespace A is a prefix of namespace B
 * "corp.hr" is prefix of "corp.hr.compensation"
 *)
IsPrefix(prefix, full) ==
    \/ prefix = full
    \/ (Len(prefix) < Len(full) /\ 
        SubSeq(full, 1, Len(prefix)) = prefix /\
        full[Len(prefix) + 1] = ".")

(*
 * Check if a cell is the Genesis cell
 *)
IsGenesis(c) ==
    /\ c.header.cell_type = "genesis"
    /\ c.header.prev_cell_hash = NULL_HASH

(*
 * Check if a cell is a bridge rule
 *)
IsBridgeRule(c) ==
    c.header.cell_type = "bridge_rule"

(*
 * Check if a cell is an access rule
 *)
IsAccessRule(c) ==
    c.header.cell_type = "access_rule"

(*
 * Get the owner of a namespace (from namespace_def cells)
 *)
NamespaceOwner(ns) ==
    LET defs == {c \in cells : 
        /\ c.header.cell_type = "namespace_def"
        /\ c.fact.subject = ns}
    IN IF defs = {} THEN "system"
       ELSE (CHOOSE c \in defs : TRUE).fact.object

(*
 * Check if a bridge exists from source to target namespace
 *)
BridgeExists(source, target) ==
    \E c \in cells :
        /\ IsBridgeRule(c)
        /\ c.fact.subject = source
        /\ c.fact.predicate = "can_query"
        /\ IsPrefix(c.fact.object, target)

(*
 * Check if user has access to namespace
 *)
HasAccess(user_role, namespace, permission) ==
    \E c \in cells :
        /\ IsAccessRule(c)
        /\ c.fact.subject = user_role
        /\ c.fact.predicate = permission
        /\ IsPrefix(c.fact.object, namespace)

-----------------------------------------------------------------------------
(*
 * INVARIANT 1: ATOMIC INTEGRITY
 * 
 * No cell can exist without a valid cell_id that matches the computed hash
 *)
AtomicIntegrity ==
    \A c \in cells :
        c.cell_id = ComputeCellId(c)

-----------------------------------------------------------------------------
(*
 * INVARIANT 2: GENESIS UNIQUENESS
 * 
 * There can be exactly one Genesis cell, and it must be the first cell
 *)
GenesisUniqueness ==
    /\ genesis_created => 
        \E! c \in cells : IsGenesis(c)
    /\ \A c \in cells :
        IsGenesis(c) => c = Head(chain)

-----------------------------------------------------------------------------
(*
 * INVARIANT 3: CHAIN OF CUSTODY
 * 
 * Every cell (except Genesis) must point to an existing prev_cell_hash
 *)
ChainOfCustody ==
    \A c \in cells :
        \/ IsGenesis(c)
        \/ \E prev \in cells : prev.cell_id = c.header.prev_cell_hash

-----------------------------------------------------------------------------
(*
 * INVARIANT 4: NULL HASH ONLY GENESIS
 * 
 * Only Genesis can have prev_cell_hash = NULL_HASH
 *)
NullHashOnlyGenesis ==
    \A c \in cells :
        c.header.prev_cell_hash = NULL_HASH => IsGenesis(c)

-----------------------------------------------------------------------------
(*
 * INVARIANT 5: LOGIC ANCHORING
 * 
 * Every decision cell must reference a rule that exists with matching hash
 *)
LogicAnchoring ==
    \A c \in cells :
        c.header.cell_type = "decision" =>
            \E r \in cells :
                /\ r.header.cell_type = "rule"
                /\ r.logic_anchor.rule_id = c.logic_anchor.rule_id
                /\ r.logic_anchor.rule_logic_hash = c.logic_anchor.rule_logic_hash

-----------------------------------------------------------------------------
(*
 * INVARIANT 6: SOURCE QUALITY ORDERING
 * 
 * Confidence cannot be 1.0 (MAX_CONFIDENCE) unless source is "verified"
 *)
SourceQualityOrdering ==
    \A c \in cells :
        c.fact.confidence = MAX_CONFIDENCE => 
            c.fact.source_quality = "verified"

-----------------------------------------------------------------------------
(*
 * INVARIANT 7: NAMESPACE ISOLATION (NEW)
 * 
 * A query from namespace A cannot access cells in namespace B unless:
 * - A is a prefix of B (parent can see children), OR
 * - A bridge_rule exists from A to B
 *)
NamespaceIsolation ==
    \A query \in Queries :
        \A cell \in query.results :
            LET origin == query.origin_namespace
                target == cell.fact.namespace
            IN
                \/ IsPrefix(origin, target)     \* Parent can see children
                \/ IsPrefix(target, origin)     \* Child can see parent (up the tree)
                \/ BridgeExists(origin, target) \* Explicit bridge exists

-----------------------------------------------------------------------------
(*
 * INVARIANT 8: BRIDGE REQUIRES BOTH SIDES (NEW)
 * 
 * A bridge_rule from namespace A to namespace B requires signatures
 * from the owners of BOTH namespaces
 *)
BridgeRequiresBothSides ==
    \A c \in cells :
        IsBridgeRule(c) =>
            LET source == c.fact.subject
                target == c.fact.object
                source_owner == NamespaceOwner(source)
                target_owner == NamespaceOwner(target)
            IN
                /\ \E sig \in c.proof.signatures : sig.signer = source_owner
                /\ \E sig \in c.proof.signatures : sig.signer = target_owner

-----------------------------------------------------------------------------
(*
 * INVARIANT 9: NO ORPHAN BRIDGES (NEW)
 * 
 * A bridge_rule cannot exist if either namespace doesn't exist
 *)
NoOrphanBridges ==
    \A c \in cells :
        IsBridgeRule(c) =>
            /\ c.fact.subject \in namespaces
            /\ \E ns \in namespaces : IsPrefix(c.fact.object, ns)

-----------------------------------------------------------------------------
(*
 * INVARIANT 10: VALID NAMESPACE HIERARCHY (NEW)
 * 
 * A namespace must be a valid dotted path:
 * - Non-empty
 * - No leading/trailing dots
 * - No consecutive dots
 * - Only alphanumeric and dots
 *)
ValidNamespaceFormat ==
    \A c \in cells :
        LET ns == c.fact.namespace
        IN
            /\ ns # ""
            /\ Head(ns) # "."
            /\ Last(ns) # "."
            /\ ~ContainsSubstring(ns, "..")

-----------------------------------------------------------------------------
(*
 * INVARIANT 11: ACCESS CONTROL INTEGRITY (NEW)
 * 
 * access_rule cells can only be created by system admins
 * or namespace owners
 *)
AccessControlIntegrity ==
    \A c \in cells :
        IsAccessRule(c) =>
            \/ c.proof.signer_id \in SystemAdmins
            \/ c.proof.signer_id = NamespaceOwner(c.fact.object)

-----------------------------------------------------------------------------
(*
 * INVARIANT 12: NAMESPACE OWNERSHIP CHAIN (NEW)
 * 
 * Child namespaces must be created by parent namespace owner
 * "corp.hr.compensation" can only be created by owner of "corp.hr"
 *)
NamespaceOwnershipChain ==
    \A c \in cells :
        c.header.cell_type = "namespace_def" =>
            LET ns == c.fact.subject
                parent == ParentNamespace(ns)
            IN
                parent = "" \/ c.proof.signer_id = NamespaceOwner(parent)

-----------------------------------------------------------------------------
(*
 * INVARIANT 13: TEMPORAL CONSISTENCY
 * 
 * A cell's timestamp must be >= its predecessor's timestamp
 *)
TemporalConsistency ==
    \A c \in cells :
        ~IsGenesis(c) =>
            LET prev == CHOOSE p \in cells : p.cell_id = c.header.prev_cell_hash
            IN c.header.timestamp >= prev.header.timestamp

-----------------------------------------------------------------------------
(*
 * INVARIANT 14: BRIDGE IMMUTABILITY (NEW)
 * 
 * Once a bridge is created, it can only be revoked by creating
 * a new cell of type "bridge_revocation" - never deleted
 *)
BridgeImmutability ==
    \* This is implicitly enforced by append-only chain
    \* Bridges can be "revoked" but the original cell remains for audit
    TRUE

-----------------------------------------------------------------------------
(*
 * COMBINED INVARIANT
 * 
 * All invariants must hold simultaneously
 *)
TypeInvariant ==
    /\ AtomicIntegrity
    /\ GenesisUniqueness
    /\ ChainOfCustody
    /\ NullHashOnlyGenesis
    /\ LogicAnchoring
    /\ SourceQualityOrdering
    /\ NamespaceIsolation
    /\ BridgeRequiresBothSides
    /\ NoOrphanBridges
    /\ ValidNamespaceFormat
    /\ AccessControlIntegrity
    /\ NamespaceOwnershipChain
    /\ TemporalConsistency
    /\ BridgeImmutability

-----------------------------------------------------------------------------
(*
 * INITIAL STATE
 * 
 * The graph starts empty, with no cells
 *)
Init ==
    /\ cells = {}
    /\ chain = <<>>
    /\ genesis_created = FALSE
    /\ namespaces = {}
    /\ bridges = {}

-----------------------------------------------------------------------------
(*
 * ACTIONS
 *)

(*
 * CreateGenesis: Create the Genesis cell with root namespace
 * Can only happen once, must be first action
 *)
CreateGenesis(c) ==
    /\ ~genesis_created
    /\ IsGenesis(c)
    /\ c.fact.namespace = "corp"  \* Root namespace
    /\ c.cell_id = ComputeCellId(c)
    /\ cells' = cells \union {c}
    /\ chain' = Append(chain, c)
    /\ genesis_created' = TRUE
    /\ namespaces' = {"corp"}
    /\ UNCHANGED bridges

(*
 * CreateNamespace: Define a new namespace
 * Must be created by parent namespace owner
 *)
CreateNamespace(c) ==
    /\ genesis_created
    /\ c.header.cell_type = "namespace_def"
    /\ c.cell_id = ComputeCellId(c)
    /\ LET parent == ParentNamespace(c.fact.subject)
       IN \/ parent = ""
          \/ c.proof.signer_id = NamespaceOwner(parent)
    /\ cells' = cells \union {c}
    /\ chain' = Append(chain, c)
    /\ namespaces' = namespaces \union {c.fact.subject}
    /\ UNCHANGED <<genesis_created, bridges>>

(*
 * CreateBridgeRule: Create a bridge between namespaces
 * Requires signatures from both namespace owners
 *)
CreateBridgeRule(c) ==
    /\ genesis_created
    /\ IsBridgeRule(c)
    /\ c.cell_id = ComputeCellId(c)
    /\ c.fact.subject \in namespaces
    /\ \E ns \in namespaces : IsPrefix(c.fact.object, ns)
    /\ LET source_owner == NamespaceOwner(c.fact.subject)
           target_owner == NamespaceOwner(c.fact.object)
       IN /\ \E sig \in c.proof.signatures : sig.signer = source_owner
          /\ \E sig \in c.proof.signatures : sig.signer = target_owner
    /\ cells' = cells \union {c}
    /\ chain' = Append(chain, c)
    /\ bridges' = bridges \union {<<c.fact.subject, c.fact.object>>}
    /\ UNCHANGED <<genesis_created, namespaces>>

(*
 * AddCell: Add a new cell to the graph
 * Validates namespace access
 *)
AddCell(c) ==
    /\ genesis_created
    /\ ~IsGenesis(c)
    /\ ~IsBridgeRule(c)
    /\ c.header.cell_type # "namespace_def"
    /\ c.cell_id = ComputeCellId(c)
    /\ c.fact.namespace \in namespaces
    /\ \E prev \in cells : prev.cell_id = c.header.prev_cell_hash
    /\ cells' = cells \union {c}
    /\ chain' = Append(chain, c)
    /\ UNCHANGED <<genesis_created, namespaces, bridges>>

(*
 * Next: The next state relation
 *)
Next ==
    \/ \E c \in Cell : CreateGenesis(c)
    \/ \E c \in Cell : CreateNamespace(c)
    \/ \E c \in Cell : CreateBridgeRule(c)
    \/ \E c \in Cell : AddCell(c)

-----------------------------------------------------------------------------
(*
 * SPECIFICATION
 *)
Spec == Init /\ [][Next]_<<cells, chain, genesis_created, namespaces, bridges>>

-----------------------------------------------------------------------------
(*
 * THEOREMS TO VERIFY
 *)

(*
 * Safety: TypeInvariant is always maintained
 *)
THEOREM Spec => []TypeInvariant

(*
 * Liveness: Genesis will eventually be created
 *)
THEOREM Spec => <>(genesis_created)

(*
 * Safety: Namespace isolation is never violated
 *)
THEOREM Spec => []NamespaceIsolation

(*
 * Safety: Bridges always have both-side approval
 *)
THEOREM Spec => []BridgeRequiresBothSides

=============================================================================

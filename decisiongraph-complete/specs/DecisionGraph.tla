--------------------------- MODULE DecisionGraph ---------------------------
(*
 * DecisionGraph: Formal Specification
 * Version: 1.0
 * Date: January 26, 2026
 * 
 * This TLA+ specification defines the invariants that must hold
 * for every state of a DecisionGraph instance.
 *)

EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    NULL_HASH,          \* "000...000" - only valid for Genesis
    MAX_CONFIDENCE      \* 1.0 represented as 100 for integer math

VARIABLES
    cells,              \* Set of all cells in the graph
    chain,              \* Sequence representing the append-only log
    genesis_created     \* Boolean: has genesis been created?

-----------------------------------------------------------------------------
(*
 * TYPE DEFINITIONS
 *)

CellTypes == {"genesis", "fact", "rule", "decision", "evidence", "override"}

SourceQuality == {"verified", "self_reported", "inferred"}

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
        subject: STRING,
        predicate: STRING,
        object: STRING,
        confidence: 0..MAX_CONFIDENCE,
        source_quality: SourceQuality
    ],
    logic_anchor: [
        rule_id: STRING,
        rule_logic_hash: STRING
    ]
]

-----------------------------------------------------------------------------
(*
 * HELPER FUNCTIONS
 *)

(*
 * Compute the cell_id from cell contents
 * In implementation, this is SHA256 hash
 * Here we model it as a deterministic function
 *)
ComputeCellId(c) ==
    \* Concatenate all fields that form the Logic Seal
    c.header.version \o
    c.header.cell_type \o
    c.header.timestamp \o
    c.header.prev_cell_hash \o
    c.fact.subject \o
    c.fact.predicate \o
    c.fact.object \o
    c.logic_anchor.rule_id \o
    c.logic_anchor.rule_logic_hash

(*
 * Check if a cell is the Genesis cell
 *)
IsGenesis(c) ==
    /\ c.header.cell_type = "genesis"
    /\ c.header.prev_cell_hash = NULL_HASH

(*
 * Find a cell by its ID
 *)
FindCell(id) ==
    CHOOSE c \in cells : c.cell_id = id

(*
 * Check if a cell exists
 *)
CellExists(id) ==
    \E c \in cells : c.cell_id = id

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
        \/ CellExists(c.header.prev_cell_hash)

-----------------------------------------------------------------------------
(*
 * INVARIANT 4: NO NULL HASH EXCEPT GENESIS
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
 * Every decision cell must reference a rule that exists
 * and the hash must match
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
 * INVARIANT 7: APPEND ONLY
 * 
 * The chain can only grow, never shrink or modify
 *)
AppendOnly ==
    \* This is enforced by the state machine - cells can only be added
    \* Once in chain, a cell cannot be removed or modified
    Len(chain) >= 0 /\
    \A i \in 1..Len(chain) :
        chain[i] \in cells

-----------------------------------------------------------------------------
(*
 * INVARIANT 8: TEMPORAL CONSISTENCY
 * 
 * A cell's timestamp must be >= its predecessor's timestamp
 *)
TemporalConsistency ==
    \A c \in cells :
        ~IsGenesis(c) =>
            LET prev == FindCell(c.header.prev_cell_hash)
            IN c.header.timestamp >= prev.header.timestamp

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
    /\ AppendOnly
    /\ TemporalConsistency

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

-----------------------------------------------------------------------------
(*
 * ACTIONS
 *)

(*
 * CreateGenesis: Create the Genesis cell
 * Can only happen once, must be first action
 *)
CreateGenesis(c) ==
    /\ ~genesis_created
    /\ IsGenesis(c)
    /\ c.cell_id = ComputeCellId(c)
    /\ cells' = cells \union {c}
    /\ chain' = Append(chain, c)
    /\ genesis_created' = TRUE

(*
 * AddCell: Add a new cell to the graph
 * Can only happen after Genesis exists
 *)
AddCell(c) ==
    /\ genesis_created
    /\ ~IsGenesis(c)
    /\ c.cell_id = ComputeCellId(c)
    /\ CellExists(c.header.prev_cell_hash)
    /\ c.header.timestamp >= FindCell(c.header.prev_cell_hash).header.timestamp
    /\ cells' = cells \union {c}
    /\ chain' = Append(chain, c)
    /\ UNCHANGED genesis_created

(*
 * Next: The next state relation
 *)
Next ==
    \/ \E c \in Cell : CreateGenesis(c)
    \/ \E c \in Cell : AddCell(c)

-----------------------------------------------------------------------------
(*
 * SPECIFICATION
 *)
Spec == Init /\ [][Next]_<<cells, chain, genesis_created>>

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
 * (In practice, this is guaranteed by the boot sequence)
 *)
THEOREM Spec => <>(genesis_created)

=============================================================================

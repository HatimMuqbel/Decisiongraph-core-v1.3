"""
DecisionGraph Core (v1.3 - Universal Base)

The Universal Operating System for Deterministic Reasoning.

Core Principle: Namespace Isolation via Cryptographic Bridges
"Departments don't have to trust; they can verify the bridge."

v1.3 CHANGES:
- graph_id binds all cells to their graph instance
- system_time vs valid_time (clear bitemporal semantics)
- Strict namespace validation with regex
- Canonicalized rule hashing (whitespace-insensitive)
"""

__version__ = "1.3.0"
__author__ = "DecisionGraph"

# Cell primitives
from .cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Evidence,
    Proof,
    CellType,
    SourceQuality,
    SensitivityLevel,
    NULL_HASH,
    NAMESPACE_PATTERN,
    ROOT_NAMESPACE_PATTERN,
    compute_rule_logic_hash,
    compute_content_id,
    get_current_timestamp,
    validate_namespace,
    validate_root_namespace,
    validate_timestamp,
    get_parent_namespace,
    is_namespace_prefix,
    generate_graph_id,
    canonicalize_rule_content
)

# Genesis
from .genesis import (
    create_genesis_cell,
    verify_genesis,
    verify_genesis_strict,
    is_genesis,
    validate_graph_id,
    get_genesis_rule,
    get_genesis_rule_hash,
    get_canonicalized_genesis_rule,
    GenesisError,
    GenesisValidationError,
    GENESIS_RULE,
    GENESIS_RULE_HASH,
    DEFAULT_ROOT_NAMESPACE,
    SCHEMA_VERSION,
    GRAPH_ID_PATTERN
)

# Chain
from .chain import (
    Chain,
    ChainError,
    IntegrityViolation,
    ChainBreak,
    GenesisViolation,
    TemporalViolation,
    GraphIdMismatch,
    ValidationResult,
    create_chain
)

# Namespace
from .namespace import (
    Permission,
    BridgeStatus,
    NamespaceMetadata,
    Signature,
    NamespaceRegistry,
    NamespaceError,
    AccessDeniedError,
    BridgeRequiredError,
    BridgeApprovalError,
    create_namespace_definition,
    create_access_rule,
    create_bridge_rule,
    create_bridge_revocation,
    build_registry_from_chain
)

# Scholar (Resolver)
from .scholar import (
    Scholar,
    create_scholar,
    QueryResult,
    VisibilityResult,
    AuthorizationBasis,
    BridgeEffectiveness,
    BridgeEffectivenessReason,
    ResolutionEvent,
    ResolutionReason,
    ScholarIndex,
    build_index_from_chain,
    is_bridge_effective
)

__all__ = [
    '__version__',
    # Cell
    'DecisionCell', 'Header', 'Fact', 'LogicAnchor', 'Evidence', 'Proof',
    'CellType', 'SourceQuality', 'SensitivityLevel', 'NULL_HASH',
    'NAMESPACE_PATTERN', 'ROOT_NAMESPACE_PATTERN',
    'compute_rule_logic_hash', 'compute_content_id', 'get_current_timestamp',
    'validate_namespace', 'validate_root_namespace', 'validate_timestamp',
    'get_parent_namespace', 'is_namespace_prefix',
    'generate_graph_id', 'canonicalize_rule_content',
    # Genesis
    'create_genesis_cell', 'verify_genesis', 'verify_genesis_strict', 'is_genesis',
    'validate_graph_id',
    'get_genesis_rule', 'get_genesis_rule_hash', 'get_canonicalized_genesis_rule',
    'GenesisError', 'GenesisValidationError',
    'GENESIS_RULE', 'GENESIS_RULE_HASH', 'DEFAULT_ROOT_NAMESPACE', 'SCHEMA_VERSION',
    'GRAPH_ID_PATTERN',
    # Chain
    'Chain', 'ChainError', 'IntegrityViolation', 'ChainBreak',
    'GenesisViolation', 'TemporalViolation', 'GraphIdMismatch',
    'ValidationResult', 'create_chain',
    # Namespace
    'Permission', 'BridgeStatus', 'NamespaceMetadata', 'Signature', 'NamespaceRegistry',
    'NamespaceError', 'AccessDeniedError', 'BridgeRequiredError', 'BridgeApprovalError',
    'create_namespace_definition', 'create_access_rule', 'create_bridge_rule',
    'create_bridge_revocation', 'build_registry_from_chain',
    # Scholar
    'Scholar', 'create_scholar', 'QueryResult', 'VisibilityResult',
    'AuthorizationBasis', 'BridgeEffectiveness', 'BridgeEffectivenessReason',
    'ResolutionEvent', 'ResolutionReason',
    'ScholarIndex', 'build_index_from_chain', 'is_bridge_effective'
]

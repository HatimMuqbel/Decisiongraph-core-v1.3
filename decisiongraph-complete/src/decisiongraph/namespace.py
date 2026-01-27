"""
DecisionGraph Core: Namespace Module (v1.3 - Universal Base)

This module implements namespace management including:
- Namespace definitions (creating new namespaces)
- Access rules (who can read/write what)
- Bridge rules (cross-namespace access)

Core Principle: Namespace Isolation via Cryptographic Bridges
"Departments don't have to trust; they can verify the bridge."

v1.3: Uses graph_id binding and system_time semantics
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum

from .cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    Evidence,
    CellType,
    SourceQuality,
    get_current_timestamp,
    compute_rule_logic_hash,
    validate_namespace,
    get_parent_namespace,
    is_namespace_prefix,
    generate_graph_id
)


class Permission(str, Enum):
    """Permission types for access control"""
    READ = "can_read"
    WRITE = "can_write"
    ADMIN = "can_admin"
    QUERY = "can_query"


class BridgeStatus(str, Enum):
    """Status of a bridge rule"""
    ACTIVE = "active"
    REVOKED = "revoked"
    PENDING = "pending_approval"


@dataclass
class NamespaceMetadata:
    """Metadata for a namespace definition"""
    owner: str
    sensitivity: str
    retention_days: Optional[int] = None
    requires_encryption: bool = False
    description: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "owner": self.owner,
            "sensitivity": self.sensitivity,
            "retention_days": self.retention_days,
            "requires_encryption": self.requires_encryption,
            "description": self.description
        }


@dataclass
class Signature:
    """A cryptographic signature for approval"""
    signer_id: str
    signature: str
    timestamp: str
    role: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "signer_id": self.signer_id,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "role": self.role
        }


class NamespaceError(Exception):
    """Base exception for namespace errors"""
    pass


class AccessDeniedError(NamespaceError):
    """Raised when access is denied"""
    pass


class BridgeRequiredError(NamespaceError):
    """Raised when a bridge is required for cross-namespace access"""
    pass


class BridgeApprovalError(NamespaceError):
    """Raised when bridge doesn't have required approvals"""
    pass


def create_namespace_definition(
    namespace: str,
    owner: str,
    graph_id: str,
    sensitivity: str = "internal",
    parent_signer: str = None,
    creator: str = None,
    description: str = None,
    prev_cell_hash: str = None,
    system_time: str = None
) -> DecisionCell:
    """Create a namespace definition cell."""
    if not validate_namespace(namespace):
        raise NamespaceError(f"Invalid namespace format: {namespace}")

    metadata = NamespaceMetadata(
        owner=owner,
        sensitivity=sensitivity,
        description=description
    )

    ts = system_time or get_current_timestamp()
    rule_content = f"NAMESPACE_CREATE: {namespace} BY {parent_signer or 'system'}"
    
    header = Header(
        version="1.3",
        graph_id=graph_id,
        cell_type=CellType.NAMESPACE_DEF,
        system_time=ts,
        prev_cell_hash=prev_cell_hash or ("0" * 64)
    )
    
    fact = Fact(
        namespace="system.namespaces",
        subject=namespace,
        predicate="has_metadata",
        object=str(metadata.to_dict()),
        confidence=1.0,
        source_quality=SourceQuality.VERIFIED,
        valid_from=ts
    )
    
    logic_anchor = LogicAnchor(
        rule_id="system:namespace_creation",
        rule_logic_hash=compute_rule_logic_hash(rule_content)
    )
    
    proof = Proof(
        signer_id=parent_signer or creator or "system"
    )
    
    return DecisionCell(
        header=header,
        fact=fact,
        logic_anchor=logic_anchor,
        evidence=[],
        proof=proof
    )


def create_access_rule(
    role: str,
    namespace: str,
    permission: Permission,
    granted_by: str,
    graph_id: str,
    prev_cell_hash: str,
    conditions: Optional[Dict] = None
) -> DecisionCell:
    """Create an access rule cell."""
    ts = get_current_timestamp()
    rule_content = f"ACCESS_GRANT: {role} {permission.value} {namespace}"
    
    header = Header(
        version="1.3",
        graph_id=graph_id,
        cell_type=CellType.ACCESS_RULE,
        system_time=ts,
        prev_cell_hash=prev_cell_hash
    )
    
    fact = Fact(
        namespace="system.access",
        subject=role,
        predicate=permission.value,
        object=namespace,
        confidence=1.0,
        source_quality=SourceQuality.VERIFIED,
        valid_from=ts
    )
    
    logic_anchor = LogicAnchor(
        rule_id="system:access_control",
        rule_logic_hash=compute_rule_logic_hash(rule_content)
    )
    
    evidence = []
    if conditions:
        evidence.append(Evidence(
            type="conditions",
            description=str(conditions)
        ))
    
    proof = Proof(signer_id=granted_by)
    
    return DecisionCell(
        header=header,
        fact=fact,
        logic_anchor=logic_anchor,
        evidence=evidence,
        proof=proof
    )


def create_bridge_rule(
    source_namespace: str,
    target_namespace: str,
    source_owner_signature: Signature,
    target_owner_signature: Signature,
    graph_id: str,
    prev_cell_hash: str,
    purpose: str = None,
    expiry: str = None,
    system_time: str = None,
    valid_from: str = None
) -> DecisionCell:
    """Create a bridge rule cell. Requires signatures from BOTH namespace owners."""
    if not source_owner_signature or not target_owner_signature:
        raise BridgeApprovalError(
            "Bridge rules require signatures from BOTH namespace owners"
        )

    ts = system_time or get_current_timestamp()
    vf = valid_from or ts
    rule_content = (
        f"BRIDGE: {source_namespace} -> {target_namespace} "
        f"APPROVED_BY: {source_owner_signature.signer_id}, "
        f"{target_owner_signature.signer_id}"
    )

    header = Header(
        version="1.3",
        graph_id=graph_id,
        cell_type=CellType.BRIDGE_RULE,
        system_time=ts,
        prev_cell_hash=prev_cell_hash
    )

    fact = Fact(
        namespace="system.bridges",
        subject=source_namespace,
        predicate="can_query",
        object=target_namespace,
        confidence=1.0,
        source_quality=SourceQuality.VERIFIED,
        valid_from=vf,
        valid_to=expiry
    )
    
    logic_anchor = LogicAnchor(
        rule_id="system:bridge_creation",
        rule_logic_hash=compute_rule_logic_hash(rule_content)
    )
    
    evidence = [
        Evidence(
            type="approval",
            description=f"Source owner approval: {source_owner_signature.signer_id}",
            payload_hash=source_owner_signature.signature
        ),
        Evidence(
            type="approval",
            description=f"Target owner approval: {target_owner_signature.signer_id}",
            payload_hash=target_owner_signature.signature
        )
    ]
    
    if purpose:
        evidence.append(Evidence(type="purpose", description=purpose))
    
    proof = Proof(
        signer_id=f"{source_owner_signature.signer_id},{target_owner_signature.signer_id}",
        signature=f"{source_owner_signature.signature}|{target_owner_signature.signature}"
    )
    
    return DecisionCell(
        header=header,
        fact=fact,
        logic_anchor=logic_anchor,
        evidence=evidence,
        proof=proof
    )


def create_bridge_revocation(
    bridge_cell_id: str,
    revoked_by: str,
    reason: str,
    graph_id: str,
    prev_cell_hash: str
) -> DecisionCell:
    """Create a bridge revocation cell."""
    ts = get_current_timestamp()
    rule_content = f"BRIDGE_REVOKE: {bridge_cell_id} BY {revoked_by}"
    
    header = Header(
        version="1.3",
        graph_id=graph_id,
        cell_type=CellType.OVERRIDE,
        system_time=ts,
        prev_cell_hash=prev_cell_hash
    )
    
    fact = Fact(
        namespace="system.bridges",
        subject=bridge_cell_id,
        predicate="status",
        object=BridgeStatus.REVOKED.value,
        confidence=1.0,
        source_quality=SourceQuality.VERIFIED,
        valid_from=ts
    )
    
    logic_anchor = LogicAnchor(
        rule_id="system:bridge_revocation",
        rule_logic_hash=compute_rule_logic_hash(rule_content)
    )
    
    evidence = [Evidence(type="reason", description=reason)]
    proof = Proof(signer_id=revoked_by)
    
    return DecisionCell(
        header=header,
        fact=fact,
        logic_anchor=logic_anchor,
        evidence=evidence,
        proof=proof
    )


@dataclass
class NamespaceRegistry:
    """In-memory registry of namespaces, access rules, and bridges."""
    
    namespaces: Dict[str, NamespaceMetadata] = field(default_factory=dict)
    access_rules: Dict[str, List[Tuple[str, Permission]]] = field(default_factory=dict)
    bridges: Dict[Tuple[str, str], DecisionCell] = field(default_factory=dict)
    revoked_bridges: Set[str] = field(default_factory=set)
    
    def register_namespace(self, namespace: str, metadata: NamespaceMetadata):
        self.namespaces[namespace] = metadata
    
    def grant_access(self, role: str, namespace: str, permission: Permission):
        if role not in self.access_rules:
            self.access_rules[role] = []
        self.access_rules[role].append((namespace, permission))
    
    def register_bridge(self, source: str, target: str, cell: DecisionCell):
        self.bridges[(source, target)] = cell
    
    def revoke_bridge(self, cell_id: str):
        self.revoked_bridges.add(cell_id)
    
    def has_access(self, role: str, namespace: str, permission: Permission) -> bool:
        if role not in self.access_rules:
            return False
        
        for granted_ns, granted_perm in self.access_rules[role]:
            if is_namespace_prefix(granted_ns, namespace):
                if granted_perm == Permission.ADMIN:
                    return True
                if granted_perm == permission:
                    return True
        return False
    
    def bridge_exists(self, source: str, target: str) -> bool:
        key = (source, target)
        if key not in self.bridges:
            return False
        
        bridge_cell = self.bridges[key]
        if bridge_cell.cell_id in self.revoked_bridges:
            return False
        return True
    
    def can_query_namespace(
        self,
        requester_namespace: str,
        target_namespace: str
    ) -> Tuple[bool, Optional[str]]:
        if requester_namespace == target_namespace:
            return True, "Same namespace"
        
        if is_namespace_prefix(requester_namespace, target_namespace):
            return True, "Parent namespace"
        
        if is_namespace_prefix(target_namespace, requester_namespace):
            return True, "Child namespace"
        
        if self.bridge_exists(requester_namespace, target_namespace):
            return True, "Bridge exists"
        
        parent = get_parent_namespace(requester_namespace)
        while parent:
            if self.bridge_exists(parent, target_namespace):
                return True, f"Bridge via parent: {parent}"
            parent = get_parent_namespace(parent)
        
        return False, "No bridge exists"
    
    def get_namespace_owner(self, namespace: str) -> Optional[str]:
        if namespace in self.namespaces:
            return self.namespaces[namespace].owner
        return None


def build_registry_from_chain(cells: List[DecisionCell]) -> NamespaceRegistry:
    """Build a namespace registry by scanning the chain."""
    registry = NamespaceRegistry()
    
    for cell in cells:
        if cell.header.cell_type == CellType.NAMESPACE_DEF:
            try:
                import ast
                metadata_dict = ast.literal_eval(cell.fact.object)
                metadata = NamespaceMetadata(**metadata_dict)
                registry.register_namespace(cell.fact.subject, metadata)
            except:
                pass
        
        elif cell.header.cell_type == CellType.ACCESS_RULE:
            try:
                permission = Permission(cell.fact.predicate)
                registry.grant_access(cell.fact.subject, cell.fact.object, permission)
            except:
                pass
        
        elif cell.header.cell_type == CellType.BRIDGE_RULE:
            registry.register_bridge(cell.fact.subject, cell.fact.object, cell)
        
        elif cell.header.cell_type == CellType.OVERRIDE:
            if cell.fact.namespace == "system.bridges":
                if cell.fact.predicate == "status" and cell.fact.object == "revoked":
                    registry.revoke_bridge(cell.fact.subject)
    
    return registry


__all__ = [
    'Permission',
    'BridgeStatus',
    'NamespaceMetadata',
    'Signature',
    'NamespaceRegistry',
    'NamespaceError',
    'AccessDeniedError',
    'BridgeRequiredError',
    'BridgeApprovalError',
    'create_namespace_definition',
    'create_access_rule',
    'create_bridge_rule',
    'create_bridge_revocation',
    'build_registry_from_chain'
]

"""
DecisionGraph Engine Module (v1.4)

Provides the validated entry point for querying DecisionGraph through process_rfa().
External developers call engine.process_rfa(rfa_dict) and receive either:
- ProofPacket on success (includes proof_bundle from Scholar)
- DecisionGraphError on failure (with actionable error code)

Requirements implemented:
- RFA-01: Single validated entry point for all queries
- RFA-02: Schema validation (required fields: namespace, requester_namespace, requester_id)
- RFA-03: Input canonicalization (sorted keys, stripped whitespace, removed None values)
"""

import json
import base64
from typing import Optional, Dict, Any, List
from uuid import uuid4

from .promotion import PromotionRequest, PromotionStatus
from .registry import WitnessRegistry
from .simulation import (
    SimulationContext,
    SimulationResult,
    DeltaReport,
    ContaminationAttestation,
    compute_delta_report,
    tag_proof_bundle_origin,
    create_contamination_attestation
)
from .shadow import (
    OverlayContext,
    create_shadow_fact,
    create_shadow_rule,
    create_shadow_policy_head,
    create_shadow_bridge
)
from .anchors import detect_counterfactual_anchors, AnchorResult, ExecutionBudget
from .backtest import BatchBacktestResult, _sort_results, _count_cells_in_simulation

from .chain import Chain
from .scholar import create_scholar
from .policyhead import create_policy_head, get_current_policy_head, verify_policy_hash
from .validators import (
    validate_subject_field,
    validate_predicate_field,
    validate_object_field
)
from .cell import validate_namespace, get_current_timestamp
from .exceptions import (
    DecisionGraphError,
    SchemaInvalidError,
    InputInvalidError,
    UnauthorizedError,
    SignatureInvalidError,
    IntegrityFailError,
    wrap_internal_exception
)
from .signing import sign_bytes, verify_signature

__all__ = [
    'Engine',
    'process_rfa',
    'verify_proof_packet',
    'run_backtest'
]


class Engine:
    """
    The Engine is the validated entry point for DecisionGraph queries.

    It provides a single method process_rfa() that:
    1. Canonicalizes input (RFA-03)
    2. Validates schema (RFA-02)
    3. Validates fields (VAL-01/02/03)
    4. Queries Scholar for facts
    5. Generates proof bundle
    6. Wraps in ProofPacket

    All errors are deterministic DecisionGraphError subclasses with
    actionable error codes (DG_SCHEMA_INVALID, DG_INPUT_INVALID, etc.)
    """

    def __init__(
        self,
        chain: Chain,
        signing_key: Optional[bytes] = None,
        public_key: Optional[bytes] = None,
        verify_cell_signatures: bool = False
    ):
        """
        Initialize Engine with a chain.

        Args:
            chain: The DecisionGraph chain to query
            signing_key: Optional Ed25519 signing key (32 bytes) for packet signatures
            public_key: Optional Ed25519 public key (32 bytes) for verification
            verify_cell_signatures: If True, verify cell signatures during queries
        """
        self.chain = chain
        self.scholar = create_scholar(chain)
        self.signing_key = signing_key
        self.public_key = public_key
        self.verify_cell_signatures = verify_cell_signatures

        # Promotion workflow state (v1.5)
        self._promotions: Dict[str, PromotionRequest] = {}
        self._expected_prev_policy_head: Dict[str, Optional[str]] = {}  # For race detection
        self._registry = WitnessRegistry(chain)

    def process_rfa(self, rfa_dict: dict) -> dict:
        """
        Process a Request-For-Access (RFA) and return a ProofPacket.

        This is the single validated entry point for DecisionGraph queries.

        7-step pipeline:
        1. Canonicalize RFA (sorted keys, stripped whitespace, removed None)
        2. Validate schema (required fields present and correct types)
        3. Validate fields (namespace, subject, predicate, object formats)
        4. Query Scholar with parameters from RFA
        5. Generate proof bundle from query result
        6. Wrap in ProofPacket with metadata
        7. Return ProofPacket (signature=None for now, signing in Plan 02)

        Args:
            rfa_dict: Request-For-Access dictionary with:
                - namespace (required): Target namespace to query
                - requester_namespace (required): Namespace of requester
                - requester_id (required): Identifier for audit trail
                - subject (optional): Filter by subject
                - predicate (optional): Filter by predicate
                - object (optional): Filter by object value
                - at_valid_time (optional): Point in valid time
                - as_of_system_time (optional): Point in system time

        Returns:
            ProofPacket dict with:
                - packet_version: "1.4"
                - packet_id: Unique UUID for this packet
                - generated_at: ISO-8601 timestamp
                - graph_id: Graph identifier from chain
                - proof_bundle: Canonical proof from Scholar
                - signature: None (signing handled in Plan 02)

        Raises:
            SchemaInvalidError: Missing required field or wrong type (DG_SCHEMA_INVALID)
            InputInvalidError: Invalid field format (DG_INPUT_INVALID)
            DecisionGraphError: Other errors (wrapped internal exceptions)

        Example:
            rfa = {
                "namespace": "corp.hr",
                "requester_namespace": "corp.audit",
                "requester_id": "auditor:alice",
                "subject": "user:bob",
                "predicate": "has_salary"
            }
            packet = engine.process_rfa(rfa)
            # Returns ProofPacket with proof_bundle containing facts and authorization
        """
        try:
            # Step 1: Canonicalize RFA
            canonical_rfa = self._canonicalize_rfa(rfa_dict)

            # Step 2: Validate schema
            self._validate_rfa_schema(canonical_rfa)

            # Step 3: Validate fields
            self._validate_rfa_fields(canonical_rfa)

            # Step 4: Query Scholar
            query_result = self.scholar.query_facts(
                requester_namespace=canonical_rfa['requester_namespace'],
                namespace=canonical_rfa['namespace'],
                subject=canonical_rfa.get('subject'),
                predicate=canonical_rfa.get('predicate'),
                object_value=canonical_rfa.get('object'),
                at_valid_time=canonical_rfa.get('at_valid_time'),
                as_of_system_time=canonical_rfa.get('as_of_system_time'),
                requester_id=canonical_rfa['requester_id']
            )

            # Step 5: Generate proof bundle
            proof_bundle = query_result.to_proof_bundle()

            # Step 6: Wrap in ProofPacket
            proof_packet = {
                "packet_version": "1.4",
                "packet_id": str(uuid4()),
                "generated_at": get_current_timestamp(),
                "graph_id": self.chain.graph_id,
                "proof_bundle": proof_bundle,
                "signature": None  # Will be populated in Step 7 if signing key provided
            }

            # Step 7: Sign if key provided (SIG-04)
            if self.signing_key:
                proof_packet = self._sign_proof_packet(proof_packet)

            return proof_packet

        except DecisionGraphError:
            # Re-raise DecisionGraphError subclasses as-is
            raise
        except (ValueError, TypeError, KeyError) as e:
            # Wrap standard Python exceptions as InputInvalidError
            raise wrap_internal_exception(
                e,
                details={"operation": "process_rfa"}
            ) from e
        except Exception as e:
            # Wrap unexpected exceptions as InternalError
            raise wrap_internal_exception(
                e,
                details={"operation": "process_rfa"}
            ) from e

    def _canonicalize_rfa(self, rfa_dict: dict) -> dict:
        """
        Canonicalize RFA input (RFA-03).

        Operations:
        1. Sort keys alphabetically
        2. Strip whitespace from string values
        3. Remove None values

        This ensures deterministic processing and prevents whitespace-based
        variations from causing different validation results.

        Args:
            rfa_dict: Input RFA dictionary

        Returns:
            Canonicalized RFA dictionary
        """
        # Use json.dumps with sort_keys to canonicalize structure
        canonical_json = json.dumps(rfa_dict, sort_keys=True)
        canonical_dict = json.loads(canonical_json)

        # Strip whitespace from string values and remove None values
        result = {}
        for key, value in canonical_dict.items():
            if value is None:
                # Remove None values
                continue
            elif isinstance(value, str):
                # Strip whitespace from strings
                result[key] = value.strip()
            else:
                # Keep other types as-is
                result[key] = value

        return result

    def _validate_rfa_schema(self, rfa: dict) -> None:
        """
        Validate RFA schema (RFA-02).

        Required fields:
        - namespace (string): Target namespace to query
        - requester_namespace (string): Namespace of requester
        - requester_id (string): Identifier for audit trail

        Args:
            rfa: Canonicalized RFA dictionary

        Raises:
            SchemaInvalidError: If required field missing or wrong type
        """
        required_fields = ['namespace', 'requester_namespace', 'requester_id']
        missing_fields = []

        # Check for missing fields
        for field in required_fields:
            if field not in rfa:
                missing_fields.append(field)

        if missing_fields:
            raise SchemaInvalidError(
                message=f"RFA schema validation failed: missing required fields: {', '.join(missing_fields)}",
                details={
                    "missing_fields": missing_fields,
                    "required_fields": required_fields,
                    "provided_fields": list(rfa.keys())
                }
            )

        # Check field types
        for field in required_fields:
            value = rfa.get(field)
            if not isinstance(value, str):
                raise SchemaInvalidError(
                    message=f"RFA schema validation failed: field '{field}' must be a string, got {type(value).__name__}",
                    details={
                        "field": field,
                        "expected_type": "string",
                        "actual_type": type(value).__name__,
                        "value": str(value)[:100] if value is not None else "None"
                    }
                )

    def _validate_rfa_fields(self, rfa: dict) -> None:
        """
        Validate RFA field formats (VAL-01/02/03).

        Validates:
        - namespace: Hierarchical format (corp, corp.hr, etc.)
        - subject: type:identifier format (if present)
        - predicate: snake_case format (if present)
        - object: Length and control char constraints (if present)

        Args:
            rfa: Canonicalized RFA dictionary

        Raises:
            InputInvalidError: If field format invalid
        """
        # Validate namespace (required field)
        namespace = rfa['namespace']
        if not validate_namespace(namespace):
            raise InputInvalidError(
                message=f"Invalid namespace: '{namespace}' does not match required format. "
                        f"Expected: lowercase letters/digits/underscores, segments separated by dots. "
                        f"Examples: 'corp', 'corp.hr', 'acme.sales'",
                details={
                    "field": "namespace",
                    "value": namespace,
                    "constraint": "lowercase hierarchical format with dots",
                    "pattern": "^[a-z][a-z0-9_]{0,63}(\\.[a-z][a-z0-9_]{0,63})*$"
                }
            )

        # Validate requester_namespace (required field)
        requester_namespace = rfa['requester_namespace']
        if not validate_namespace(requester_namespace):
            raise InputInvalidError(
                message=f"Invalid requester_namespace: '{requester_namespace}' does not match required format. "
                        f"Expected: lowercase letters/digits/underscores, segments separated by dots. "
                        f"Examples: 'corp', 'corp.hr', 'acme.sales'",
                details={
                    "field": "requester_namespace",
                    "value": requester_namespace,
                    "constraint": "lowercase hierarchical format with dots",
                    "pattern": "^[a-z][a-z0-9_]{0,63}(\\.[a-z][a-z0-9_]{0,63})*$"
                }
            )

        # Validate optional fields
        if 'subject' in rfa:
            validate_subject_field(rfa['subject'], field_name='subject')

        if 'predicate' in rfa:
            validate_predicate_field(rfa['predicate'], field_name='predicate')

        if 'object' in rfa:
            validate_object_field(rfa['object'], field_name='object')

    def _sign_proof_packet(self, proof_packet: dict) -> dict:
        """
        Sign the ProofPacket's proof_bundle with Ed25519.

        Signs the canonical JSON bytes of proof_bundle.
        Adds signature object with algorithm, public_key, signature, signed_at.

        Returns:
            ProofPacket with signature field populated
        """
        if not self.signing_key or not self.public_key:
            return proof_packet  # Return unsigned

        # Canonicalize proof_bundle to bytes
        proof_bundle = proof_packet["proof_bundle"]
        canonical_bytes = json.dumps(
            proof_bundle, sort_keys=True, separators=(',', ':')
        ).encode('utf-8')

        # Sign using Phase 3 signing utilities
        signature_bytes = sign_bytes(self.signing_key, canonical_bytes)

        # Add signature object (base64 encoded for JSON safety)
        proof_packet["signature"] = {
            "algorithm": "Ed25519",
            "public_key": base64.b64encode(self.public_key).decode('ascii'),
            "signature": base64.b64encode(signature_bytes).decode('ascii'),
            "signed_at": get_current_timestamp()
        }

        return proof_packet

    def submit_promotion(
        self,
        namespace: str,
        rule_ids: List[str],
        submitter_id: str
    ) -> str:
        """
        Submit a promotion request (PRO-01).

        Creates a PromotionRequest tracking the promotion of rule_ids
        for the given namespace. Returns promotion_id for subsequent
        signature collection.

        Args:
            namespace: Target namespace for promotion
            rule_ids: List of rule IDs to promote
            submitter_id: Identifier of who is submitting

        Returns:
            promotion_id: Unique identifier for this promotion

        Raises:
            InputInvalidError: If namespace invalid, no WitnessSet configured,
                               rule not found, or rule from wrong namespace (INT-03)

        Example:
            >>> promotion_id = engine.submit_promotion(
            ...     namespace="corp",
            ...     rule_ids=["rule:salary_v2", "rule:benefits_v1"],
            ...     submitter_id="alice"
            ... )
        """
        # Validate namespace format
        if not validate_namespace(namespace):
            raise InputInvalidError(
                message=f"Invalid namespace: '{namespace}'",
                details={"namespace": namespace}
            )

        # INT-03: Validate each rule_id belongs to namespace (fail fast)
        for rule_id in rule_ids:
            rule_cell = self.chain.get_cell(rule_id)
            if rule_cell is None:
                raise InputInvalidError(
                    message=f"Rule {rule_id} not found",
                    details={"rule_id": rule_id, "namespace": namespace}
                )
            if rule_cell.fact.namespace != namespace:
                raise InputInvalidError(
                    message=f"Rule {rule_id} is from namespace {rule_cell.fact.namespace}, expected {namespace}",
                    details={
                        "rule_id": rule_id,
                        "rule_namespace": rule_cell.fact.namespace,
                        "expected_namespace": namespace
                    }
                )

        # Get WitnessSet for threshold
        witness_set = self._registry.get_witness_set(namespace)
        if not witness_set:
            raise InputInvalidError(
                message=f"No WitnessSet configured for namespace: {namespace}",
                details={"namespace": namespace}
            )

        # Capture current policy head for race detection at finalize time
        current_policy_head = get_current_policy_head(self.chain, namespace)
        expected_prev_policy_head = current_policy_head.cell_id if current_policy_head else None

        # Create promotion request
        promotion = PromotionRequest.create(
            namespace=namespace,
            rule_ids=rule_ids,
            submitter_id=submitter_id,
            threshold=witness_set.threshold,
            created_at=get_current_timestamp()
        )

        # Store in active promotions
        self._promotions[promotion.promotion_id] = promotion
        # Store expected prev_policy_head for race detection
        self._expected_prev_policy_head[promotion.promotion_id] = expected_prev_policy_head

        return promotion.promotion_id

    def collect_witness_signature(
        self,
        promotion_id: str,
        witness_id: str,
        signature: bytes,
        public_key: bytes
    ) -> PromotionStatus:
        """
        Collect a witness signature for a promotion (PRO-02, PRO-05, PRO-06).

        Validates witness is in WitnessSet (PRO-05), verifies signature (PRO-06),
        stores signature, and updates status based on signature count.

        IMPORTANT: Authorization check BEFORE signature verification.
        Order matters: unauthorized witness should not trigger signature verification.

        Args:
            promotion_id: ID of promotion to add signature to
            witness_id: ID of the witness providing signature
            signature: 64-byte Ed25519 signature of canonical_payload
            public_key: 32-byte Ed25519 public key for verification

        Returns:
            Current PromotionStatus after signature collection

        Raises:
            InputInvalidError: If promotion_id not found
            UnauthorizedError: If witness not in WitnessSet (DG_UNAUTHORIZED)
            SignatureInvalidError: If signature verification fails (DG_SIGNATURE_INVALID)

        Example:
            >>> status = engine.collect_witness_signature(
            ...     promotion_id=promotion_id,
            ...     witness_id="alice",
            ...     signature=sig_bytes,
            ...     public_key=alice_pub_key
            ... )
            >>> print(status)  # PromotionStatus.COLLECTING or THRESHOLD_MET
        """
        # Get promotion
        promotion = self._promotions.get(promotion_id)
        if not promotion:
            raise InputInvalidError(
                message=f"Promotion not found: {promotion_id}",
                details={"promotion_id": promotion_id}
            )

        # PRO-05: Check witness authorization FIRST (before signature verification)
        witness_set = self._registry.get_witness_set(promotion.namespace)
        if witness_set is None:
            raise InputInvalidError(
                message=f"No WitnessSet for namespace: {promotion.namespace}",
                details={"namespace": promotion.namespace}
            )

        if witness_id not in witness_set.witnesses:
            raise UnauthorizedError(
                message=f"Witness '{witness_id}' not in WitnessSet for namespace '{promotion.namespace}'",
                details={
                    "witness_id": witness_id,
                    "namespace": promotion.namespace,
                    "allowed_witnesses": list(witness_set.witnesses)
                }
            )

        # PRO-06: Verify signature
        # CRITICAL: verify_signature returns False on invalid, does NOT raise exception
        is_valid = verify_signature(public_key, promotion.canonical_payload, signature)
        if not is_valid:
            raise SignatureInvalidError(
                message=f"Signature verification failed for witness '{witness_id}'",
                details={
                    "witness_id": witness_id,
                    "promotion_id": promotion_id
                }
            )

        # Store signature (dict prevents duplicates - same witness overwrites)
        promotion.signatures[witness_id] = signature

        # Update status based on signature count
        sig_count = len(promotion.signatures)
        if sig_count == 1 and promotion.status == PromotionStatus.PENDING:
            promotion.status = PromotionStatus.COLLECTING
        if sig_count >= promotion.required_threshold:
            promotion.status = PromotionStatus.THRESHOLD_MET

        return promotion.status

    def finalize_promotion(self, promotion_id: str) -> str:
        """
        Finalize promotion and create PolicyHead cell (PRO-04).

        Creates a PolicyHead cell for the promoted rules and appends
        it to the chain. This is atomic - either the PolicyHead is
        created and appended, or an error is raised.

        Requires promotion status to be THRESHOLD_MET. After finalization,
        status is updated to FINALIZED.

        Includes race detection: compares current policy head to expected
        prev_policy_head stored at submit time. If different, another
        promotion was finalized concurrently.

        Args:
            promotion_id: ID of the promotion to finalize

        Returns:
            cell_id of the created PolicyHead

        Raises:
            InputInvalidError: If promotion_id not found or concurrent promotion detected
            UnauthorizedError: If threshold not met (status != THRESHOLD_MET)
            IntegrityFailError: If policy_hash verification fails (INT-02)

        Example:
            >>> # After collecting enough signatures...
            >>> cell_id = engine.finalize_promotion(promotion_id)
            >>> # PolicyHead now on chain, rules are promoted
        """
        # Get promotion
        promotion = self._promotions.get(promotion_id)
        if not promotion:
            raise InputInvalidError(
                message=f"Promotion not found: {promotion_id}",
                details={"promotion_id": promotion_id}
            )

        # Check threshold is met (INT-04)
        if promotion.status != PromotionStatus.THRESHOLD_MET:
            raise UnauthorizedError(
                message=f"Cannot finalize: status is {promotion.status.value}, need THRESHOLD_MET",
                details={
                    "current_status": promotion.status.value,
                    "signatures_collected": len(promotion.signatures),
                    "threshold_required": promotion.required_threshold
                }
            )

        # Race condition detection: compare current policy head to expected
        current_policy_head = get_current_policy_head(self.chain, promotion.namespace)
        current_head_id = current_policy_head.cell_id if current_policy_head else None
        expected_prev = self._expected_prev_policy_head.get(promotion_id)

        # Race detection: flag if expected differs from current
        if expected_prev is not None and current_head_id != expected_prev:
            raise InputInvalidError(
                message=f"Concurrent promotion detected. Expected prev_policy_head {expected_prev}, but current is {current_head_id}",
                details={
                    "promotion_id": promotion_id,
                    "expected_prev_policy_head": expected_prev,
                    "current_policy_head": current_head_id
                }
            )
        # Also flag if expected was None but now there's a head (someone promoted first)
        if expected_prev is None and current_head_id is not None:
            raise InputInvalidError(
                message=f"Concurrent promotion detected. Expected no previous policy, but found {current_head_id}",
                details={
                    "promotion_id": promotion_id,
                    "expected_prev_policy_head": None,
                    "current_policy_head": current_head_id
                }
            )

        # Use current_head_id for linking (verified to match expected)
        prev_policy_head_id = current_head_id

        # Create PolicyHead cell with witness signatures for audit trail (INT-01)
        policy_head = create_policy_head(
            namespace=promotion.namespace,
            promoted_rule_ids=list(promotion.rule_ids),
            graph_id=self.chain.graph_id,
            prev_cell_hash=self.chain.head.cell_id,
            prev_policy_head=prev_policy_head_id,
            system_time=get_current_timestamp(),
            creator=promotion.submitter_id,
            bootstrap_mode=True,  # Signature enforcement is via WitnessSet, not cell-level
            witness_signatures=promotion.signatures,  # INT-01: Store for audit trail
            canonical_payload=promotion.canonical_payload  # INT-01: Store for verification
        )

        # INT-02: Verify policy_hash before chain append
        if not verify_policy_hash(policy_head):
            raise IntegrityFailError(
                message="PolicyHead policy_hash verification failed",
                details={
                    "promotion_id": promotion_id,
                    "cell_id": policy_head.cell_id
                }
            )

        # Append to chain (atomic)
        self.chain.append(policy_head)

        # Update promotion status
        promotion.status = PromotionStatus.FINALIZED

        # Clean up expected prev tracking
        if promotion_id in self._expected_prev_policy_head:
            del self._expected_prev_policy_head[promotion_id]

        return policy_head.cell_id

    def simulate_rfa(
        self,
        rfa_dict: dict,
        simulation_spec: dict,
        at_valid_time: str,
        as_of_system_time: str,
        max_anchor_attempts: int = 100,
        max_runtime_ms: int = 5000
    ) -> SimulationResult:
        """
        Simulate an RFA against shadow reality (SIM-01 through SIM-06, SHD-03, SHD-05, SHD-06, CTF-01 through CTF-04).

        Phase 8: Creates isolated simulation, returns base/shadow results.
        Phase 9 additions:
        - delta_report: Structured comparison of base vs shadow (SIM-04)
        - proof_bundle: Tagged bundles with contamination attestation (SIM-05, SHD-06)
        - Deterministic outputs (SIM-06)

        Phase 10 additions:
        - anchors: Counterfactual anchors when verdict_changed=True (CTF-01 through CTF-04)
        - Bounded anchor detection via max_anchor_attempts and max_runtime_ms (CTF-02)

        Creates an isolated "what-if" scenario by:
        1. Freezing base reality at specified bitemporal coordinates (SIM-02, SHD-05)
        2. Building OverlayContext from simulation_spec shadow cells
        3. Running shadow query with deterministic precedence (SIM-03)
        4. Computing delta report (SIM-04)
        5. Detecting counterfactual anchors if verdict changed (CTF-03, CTF-04)
        6. Tagging proof bundles with origin (SIM-05)
        7. Creating contamination attestation (SHD-06)
        8. Returning immutable SimulationResult with complete analysis

        Zero contamination guaranteed: context manager ensures shadow chain
        cleanup even on exception. Base chain is NEVER modified.

        Args:
            rfa_dict: Request-For-Access to simulate (same format as process_rfa)
            simulation_spec: Shadow cells to inject, dict with keys:
                - shadow_facts: List[dict] with {base_cell_id, modifications}
                - shadow_rules: List[dict] with {base_cell_id, modifications}
                - shadow_policy_heads: List[dict] with {base_cell_id, modifications}
                - shadow_bridges: List[dict] with {base_cell_id, modifications}
            at_valid_time: Freeze valid time coordinate (ISO 8601 UTC)
            as_of_system_time: Freeze system time coordinate (ISO 8601 UTC)
            max_anchor_attempts: Max simulation attempts for anchor detection (default 100, CTF-02)
            max_runtime_ms: Max runtime for anchor detection in milliseconds (default 5000, CTF-02)

        Returns:
            SimulationResult with base_result, shadow_result, delta_report,
            anchors (populated when verdict_changed=True), proof_bundle,
            and contamination attestation

        Raises:
            SchemaInvalidError: If RFA schema invalid
            InputInvalidError: If field format invalid or simulation_spec malformed

        Example:
            >>> result = engine.simulate_rfa(
            ...     rfa_dict={"namespace": "corp.hr", "requester_namespace": "corp.hr",
            ...               "requester_id": "analyst:bob", "subject": "employee:alice"},
            ...     simulation_spec={"shadow_facts": [
            ...         {"base_cell_id": "abc123...", "object": "90000"}  # What if salary was 90000?
            ...     ]},
            ...     at_valid_time="2025-01-15T00:00:00Z",
            ...     as_of_system_time="2025-01-15T00:00:00Z"
            ... )
            >>> print(result.delta_report.verdict_changed)  # True if fact count changed
            >>> print(result.anchors)  # Minimal shadow components causing verdict delta
            >>> print(result.proof_bundle["contamination_attestation"])  # Chain integrity proof
        """
        try:
            # Step 1: Capture chain head BEFORE simulation (SHD-06)
            chain_head_before = self.chain.head.cell_id

            # Step 2: Canonicalize RFA (reuse existing method)
            canonical_rfa = self._canonicalize_rfa(rfa_dict)

            # Step 3: Validate RFA schema and fields (reuse existing)
            self._validate_rfa_schema(canonical_rfa)
            self._validate_rfa_fields(canonical_rfa)

            # Step 4: Query base reality at frozen coordinates (SIM-02, SHD-05)
            base_query_result = self.scholar.query_facts(
                requester_namespace=canonical_rfa['requester_namespace'],
                namespace=canonical_rfa['namespace'],
                subject=canonical_rfa.get('subject'),
                predicate=canonical_rfa.get('predicate'),
                object_value=canonical_rfa.get('object'),
                at_valid_time=at_valid_time,
                as_of_system_time=as_of_system_time,
                requester_id=canonical_rfa['requester_id']
            )
            base_result = base_query_result.to_proof_bundle()

            # Step 5: Build OverlayContext from simulation_spec
            overlay_ctx = self._build_overlay_context(simulation_spec)

            # Step 6: Run shadow query in context manager (SIM-03, cleanup guaranteed)
            # NOTE: SimulationContext.__enter__ appends shadow cells from overlay_ctx
            # to shadow_chain BEFORE creating shadow_scholar, so Scholar sees them.
            with SimulationContext(
                self.chain, overlay_ctx, at_valid_time, as_of_system_time
            ) as sim_ctx:
                # Query shadow reality (same RFA, same frozen coordinates)
                shadow_query_result = sim_ctx.shadow_scholar.query_facts(
                    requester_namespace=canonical_rfa['requester_namespace'],
                    namespace=canonical_rfa['namespace'],
                    subject=canonical_rfa.get('subject'),
                    predicate=canonical_rfa.get('predicate'),
                    object_value=canonical_rfa.get('object'),
                    at_valid_time=at_valid_time,
                    as_of_system_time=as_of_system_time,
                    requester_id=canonical_rfa['requester_id']
                )
                shadow_result = shadow_query_result.to_proof_bundle()
            # Context manager __exit__ called here - shadow_chain discarded

            # Step 7: Capture chain head AFTER simulation (SHD-06)
            chain_head_after = self.chain.head.cell_id

            # Step 8: Generate simulation_id for this run
            simulation_id = str(uuid4())

            # Step 9: Compute delta report (SIM-04, SIM-06)
            delta_report = compute_delta_report(base_result, shadow_result)

            # Step 9.5: Detect counterfactual anchors if verdict changed (CTF-02, CTF-03, CTF-04)
            if delta_report.verdict_changed:
                anchor_result = detect_counterfactual_anchors(
                    engine=self,
                    rfa_dict=canonical_rfa,
                    base_result=base_result,
                    simulation_spec=simulation_spec,
                    at_valid_time=at_valid_time,
                    as_of_system_time=as_of_system_time,
                    max_anchor_attempts=max_anchor_attempts,
                    max_runtime_ms=max_runtime_ms
                )
                anchors_dict = anchor_result.to_dict()
            else:
                # No verdict change = no anchors to detect
                anchors_dict = {
                    'anchors': [],
                    'anchors_incomplete': False,
                    'attempts_used': 0,
                    'runtime_ms': 0.0,
                    'anchor_hash': ''
                }

            # Step 10: Tag proof bundles with origin (SIM-05)
            tagged_base = tag_proof_bundle_origin(base_result, "BASE")
            tagged_shadow = tag_proof_bundle_origin(shadow_result, "SHADOW")

            # Step 11: Create contamination attestation (SHD-06)
            attestation = create_contamination_attestation(
                chain_head_before, chain_head_after, simulation_id
            )

            # Step 12: Assemble proof_bundle (SIM-05, SHD-06)
            proof_bundle = {
                "base": tagged_base,
                "shadow": tagged_shadow,
                "contamination_attestation": {
                    "chain_head_before": attestation.chain_head_before,
                    "chain_head_after": attestation.chain_head_after,
                    "attestation_hash": attestation.attestation_hash,
                    "contamination_detected": attestation.contamination_detected
                }
            }

            # Step 13: Create immutable SimulationResult (SHD-03)
            return SimulationResult(
                simulation_id=simulation_id,
                rfa_dict=canonical_rfa,
                simulation_spec=simulation_spec,
                base_result=base_result,
                shadow_result=shadow_result,
                at_valid_time=at_valid_time,
                as_of_system_time=as_of_system_time,
                delta_report=delta_report,
                anchors=anchors_dict,  # Populated from Step 9.5 (CTF-03)
                proof_bundle=proof_bundle
            )

        except DecisionGraphError:
            raise
        except (ValueError, TypeError, KeyError) as e:
            raise wrap_internal_exception(
                e, details={"operation": "simulate_rfa"}
            ) from e
        except Exception as e:
            raise wrap_internal_exception(
                e, details={"operation": "simulate_rfa"}
            ) from e

    def _build_overlay_context(self, simulation_spec: dict) -> OverlayContext:
        """
        Build OverlayContext from simulation_spec.

        Processes shadow_facts, shadow_rules, shadow_policy_heads, shadow_bridges
        from simulation_spec and creates shadow cells using Phase 7 functions.

        Args:
            simulation_spec: Dict with shadow cell specifications

        Returns:
            OverlayContext populated with shadow cells
        """
        ctx = OverlayContext()

        # Process shadow facts
        for spec in simulation_spec.get('shadow_facts', []):
            base_cell_id = spec.get('base_cell_id')
            if base_cell_id:
                base_cell = self.chain.get_cell(base_cell_id)
                if base_cell:
                    shadow_cell = create_shadow_fact(
                        base_cell,
                        object=spec.get('object'),
                        confidence=spec.get('confidence'),
                        valid_from=spec.get('valid_from'),
                        valid_to=spec.get('valid_to')
                    )
                    ctx.add_shadow_fact(shadow_cell, base_cell_id)

        # Process shadow rules
        for spec in simulation_spec.get('shadow_rules', []):
            base_cell_id = spec.get('base_cell_id')
            if base_cell_id:
                base_cell = self.chain.get_cell(base_cell_id)
                if base_cell:
                    shadow_cell = create_shadow_rule(
                        base_cell,
                        rule_logic_hash=spec.get('rule_logic_hash')
                    )
                    ctx.add_shadow_rule(shadow_cell, base_cell_id)

        # Process shadow policy heads
        for spec in simulation_spec.get('shadow_policy_heads', []):
            base_cell_id = spec.get('base_cell_id')
            if base_cell_id:
                base_cell = self.chain.get_cell(base_cell_id)
                if base_cell:
                    shadow_cell = create_shadow_policy_head(
                        base_cell,
                        promoted_rule_ids=spec.get('promoted_rule_ids')
                    )
                    ctx.add_shadow_policy_head(shadow_cell, base_cell_id)

        # Process shadow bridges
        for spec in simulation_spec.get('shadow_bridges', []):
            base_cell_id = spec.get('base_cell_id')
            if base_cell_id:
                base_cell = self.chain.get_cell(base_cell_id)
                if base_cell:
                    shadow_cell = create_shadow_bridge(
                        base_cell,
                        object=spec.get('object')  # target namespace
                    )
                    ctx.add_shadow_bridge(shadow_cell, base_cell_id)

        return ctx

    def run_backtest(
        self,
        rfa_list: List[Dict[str, Any]],
        simulation_spec: Dict[str, Any],
        at_valid_time: str,
        as_of_system_time: str,
        max_cases: int = 1000,
        max_runtime_ms: int = 60000,
        max_cells_touched: int = 100000
    ) -> BatchBacktestResult:
        """
        Run simulations over multiple RFAs (BAT-01, BAT-02, BAT-03).

        Iterates over rfa_list, calling simulate_rfa() for each with the same
        simulation_spec and bitemporal coordinates. Results are collected,
        sorted deterministically, and returned with execution metrics.

        Bounded execution (BAT-02):
        - max_cases: Stop after N RFAs processed
        - max_runtime_ms: Stop after timeout exceeded
        - max_cells_touched: Stop after cumulative cell access limit

        When any limit is exceeded, returns partial results with
        backtest_incomplete=True. This prevents DoS via large batches.

        Args:
            rfa_list: List of RFA dicts to simulate (same format as process_rfa)
            simulation_spec: Shadow cells to inject (same for all RFAs)
            at_valid_time: Valid-time coordinate (ISO 8601 UTC)
            as_of_system_time: System-time coordinate (ISO 8601 UTC)
            max_cases: Max RFAs to process (default 1000, BAT-02)
            max_runtime_ms: Max runtime in ms (default 60000 = 60s, BAT-02)
            max_cells_touched: Max cumulative cells (default 100000, BAT-02)

        Returns:
            BatchBacktestResult with:
            - results: List[SimulationResult] sorted by (subject, valid_time, system_time)
            - backtest_incomplete: True if any limit exceeded
            - cases_processed: Number of RFAs successfully processed
            - runtime_ms: Actual runtime in milliseconds
            - cells_touched: Total cells accessed across all simulations

        Example:
            >>> result = engine.run_backtest(
            ...     rfa_list=[
            ...         {"namespace": "corp.hr", "requester_namespace": "corp.hr",
            ...          "requester_id": "analyst", "subject": "employee:alice"},
            ...         {"namespace": "corp.hr", "requester_namespace": "corp.hr",
            ...          "requester_id": "analyst", "subject": "employee:bob"},
            ...     ],
            ...     simulation_spec={"shadow_facts": [...]},
            ...     at_valid_time="2025-01-15T00:00:00Z",
            ...     as_of_system_time="2025-01-15T00:00:00Z"
            ... )
            >>> print(result.cases_processed)  # 2
            >>> print(result.backtest_incomplete)  # False
        """
        # Handle empty input gracefully (BAT-01 edge case)
        if not rfa_list:
            return BatchBacktestResult(
                results=[],
                backtest_incomplete=False,
                cases_processed=0,
                runtime_ms=0.0,
                cells_touched=0
            )

        # Create execution budget (reuse Phase 10 pattern for cases + time)
        budget = ExecutionBudget(max_attempts=max_cases, max_runtime_ms=max_runtime_ms)

        results: List[SimulationResult] = []
        cells_touched = 0

        for rfa_dict in rfa_list:
            # Check max_cases and max_runtime_ms limits (BAT-02)
            if budget.is_exceeded():
                return BatchBacktestResult(
                    results=_sort_results(results),  # BAT-03
                    backtest_incomplete=True,
                    cases_processed=len(results),
                    runtime_ms=budget.elapsed_ms(),
                    cells_touched=cells_touched
                )

            # Check max_cells_touched limit (BAT-02)
            if cells_touched >= max_cells_touched:
                return BatchBacktestResult(
                    results=_sort_results(results),
                    backtest_incomplete=True,
                    cases_processed=len(results),
                    runtime_ms=budget.elapsed_ms(),
                    cells_touched=cells_touched
                )

            # Run simulation for this RFA
            sim_result = self.simulate_rfa(
                rfa_dict=rfa_dict,
                simulation_spec=simulation_spec,
                at_valid_time=at_valid_time,
                as_of_system_time=as_of_system_time
            )

            results.append(sim_result)
            budget.increment()

            # Track cells touched for limit check
            cells_touched += _count_cells_in_simulation(sim_result)

        # All cases completed within budget
        return BatchBacktestResult(
            results=_sort_results(results),  # BAT-03: deterministic order
            backtest_incomplete=False,
            cases_processed=len(results),
            runtime_ms=budget.elapsed_ms(),
            cells_touched=cells_touched
        )


def process_rfa(
    chain: Chain,
    rfa_dict: dict,
    signing_key: Optional[bytes] = None,
    public_key: Optional[bytes] = None
) -> dict:
    """
    Convenience function to process an RFA without creating an Engine instance.

    Creates an Engine and calls process_rfa() on it.

    Args:
        chain: The DecisionGraph chain to query
        rfa_dict: Request-For-Access dictionary
        signing_key: Optional Ed25519 signing key for packet signatures
        public_key: Optional Ed25519 public key for verification

    Returns:
        ProofPacket dict

    Raises:
        SchemaInvalidError: Missing required field or wrong type
        InputInvalidError: Invalid field format
        DecisionGraphError: Other errors

    Example:
        from decisiongraph import create_chain, process_rfa

        chain = create_chain("my_graph")
        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.audit",
            "requester_id": "auditor:alice"
        }
        packet = process_rfa(chain, rfa)
    """
    engine = Engine(chain, signing_key, public_key)
    return engine.process_rfa(rfa_dict)


def verify_proof_packet(proof_packet: dict, engine_public_key: bytes) -> bool:
    """
    Verify a ProofPacket's signature.

    Reconstructs canonical bytes from proof_bundle and verifies
    the signature using the provided public key.

    Args:
        proof_packet: The packet returned by process_rfa()
        engine_public_key: Engine's Ed25519 public key (32 bytes)

    Returns:
        True if signature is valid, False if:
        - Packet is unsigned (signature is None)
        - Signature verification fails
        - public_key doesn't match

    Note: Does NOT raise exceptions for invalid signatures.
    Invalid signature is normal control flow (returns False).
    """
    # Check if packet is signed
    if not proof_packet.get("signature"):
        return False

    sig_info = proof_packet["signature"]

    # Decode signature from base64
    try:
        signature_bytes = base64.b64decode(sig_info["signature"])
    except Exception:
        return False

    # Reconstruct canonical bytes from proof_bundle
    proof_bundle = proof_packet["proof_bundle"]
    canonical_bytes = json.dumps(
        proof_bundle, sort_keys=True, separators=(',', ':')
    ).encode('utf-8')

    # Verify signature using Phase 3 utilities
    return verify_signature(engine_public_key, canonical_bytes, signature_bytes)

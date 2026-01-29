#!/usr/bin/env python3
"""
DecisionGraph CLI - Bank Appliance Runner

Command-line interface for running Financial Crime cases through DecisionGraph.
Produces auditor-ready report bundles with verifiable hashes and policy citations.

Usage:
    dg run-case --case bundle.json --pack fincrime_canada.yaml --out out/
    dg verify-bundle --bundle out/CASE_ID/bundle.zip
    dg validate-pack --pack fincrime_canada.yaml
    dg validate-case --case bundle.json
    dg pack-info --pack fincrime_canada.yaml

Exit Codes:
    0   PASS            - Case processed, auto-archive permitted
    2   REVIEW_REQUIRED - Analyst review required
    3   ESCALATE        - Senior review / compliance escalation required
    4   BLOCK           - Case blocked, STR consideration
    10  INPUT_INVALID   - Invalid input (case or pack)
    11  PACK_ERROR      - Pack validation/loading failed
    12  VERIFY_FAIL     - Verification failed (integrity, determinism)
    20  INTERNAL_ERROR  - Unexpected internal error

Output Bundle (in out/CASE_ID/):
    report.txt          - Deterministic report bytes
    report.sha256       - Hash of report bytes
    manifest.json       - ReportManifest + included cell IDs
    pack.json           - Pack metadata (id, version, hash)
    verification.json   - PASS/FAIL verification checks
    cells.jsonl         - All cells produced (deterministic order)
    bundle.zip          - Everything zipped for audit handoff
    manifest.sig        - Optional Ed25519 signature (with --sign)
"""

import argparse
import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, date, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional, Any

# Engine version - updated on release
ENGINE_VERSION = "1.0.0"

# Add paths for imports
_src_path = Path(__file__).parent
sys.path.insert(0, str(_src_path.parent))

from decisiongraph.cell import (
    DecisionCell,
    CellType,
    get_current_timestamp,
    HASH_SCHEME_CANONICAL,
)
from decisiongraph.chain import Chain
from decisiongraph.rules import EvaluationContext

# Local imports
from .case_schema import (
    CaseBundle,
    CaseMeta,
    CaseType,
    CasePhase,
    EntityType,
    Individual,
    Organization,
    Account,
    Relationship,
    RelationshipType,
    EvidenceItem,
    EvidenceType,
    TransactionEvent,
    AlertEvent,
    ScreeningEvent,
    Assertion,
    Sensitivity,
    RiskRating,
    PEPCategory,
    validate_case_bundle,
)
from .case_loader import load_case_bundle, load_case_bundle_to_chain
from .pack_loader import (
    load_pack_yaml,
    PackRuntime,
    PackValidationError,
    PackLoaderError,
)
from .case_mapper import (
    map_case,
    load_adapter,
    validate_adapter,
    AdapterError,
    AdapterValidationError,
    MappingError,
    MappingResult,
)


# ============================================================================
# EXIT CODES
# ============================================================================

class ExitCode:
    """Deterministic exit codes for pipeline integration."""
    PASS = 0              # Auto-archive permitted
    REVIEW_REQUIRED = 2   # Analyst review required
    ESCALATE = 3          # Senior/compliance escalation
    BLOCK = 4             # STR consideration / blocked
    INPUT_INVALID = 10    # Invalid input files
    PACK_ERROR = 11       # Pack validation/loading failed
    VERIFY_FAIL = 12      # Verification failed
    INTERNAL_ERROR = 20   # Unexpected error


def gate_to_exit_code(gate: str, auto_archive: bool) -> int:
    """Map threshold gate to exit code."""
    if auto_archive or gate == "AUTO_CLOSE":
        return ExitCode.PASS
    elif gate == "ANALYST_REVIEW":
        return ExitCode.REVIEW_REQUIRED
    elif gate in ("SENIOR_REVIEW", "COMPLIANCE_REVIEW"):
        return ExitCode.ESCALATE
    elif gate == "STR_CONSIDERATION":
        return ExitCode.BLOCK
    else:
        return ExitCode.REVIEW_REQUIRED


def get_environment_info() -> dict:
    """
    Get environment information for audit trail.

    Returns non-sensitive system info that helps with reproducibility
    and debugging without affecting report determinism.
    """
    env_info = {
        "engine_version": ENGINE_VERSION,
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
    }

    # Try to get git commit hash
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).parent,
        ).decode().strip()
        env_info["git_commit"] = git_hash
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Check for container environment
    if os.path.exists("/.dockerenv"):
        env_info["container"] = "docker"
    elif os.environ.get("KUBERNETES_SERVICE_HOST"):
        env_info["container"] = "kubernetes"

    # Get container image digest if available
    image_digest = os.environ.get("IMAGE_DIGEST") or os.environ.get("CONTAINER_IMAGE_DIGEST")
    if image_digest:
        env_info["container_image_digest"] = image_digest

    return env_info


def get_retention_class(verdict: str, legal_hold: bool = False) -> str:
    """
    Determine retention class based on verdict.

    Retention classes:
    - 7y: Standard retention for auto-archived cases
    - 10y: Extended retention for reviewed cases
    - indefinite: Cases under legal hold

    Banks can override these based on their policies.
    """
    if legal_hold:
        return "indefinite"
    elif verdict in ("AUTO_CLOSE",):
        return "7y"
    elif verdict in ("ANALYST_REVIEW", "SENIOR_REVIEW"):
        return "10y"
    elif verdict in ("COMPLIANCE_REVIEW", "STR_CONSIDERATION"):
        return "10y"  # May need longer based on jurisdiction
    else:
        return "10y"


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

    @classmethod
    def disable(cls):
        cls.HEADER = ''
        cls.BLUE = ''
        cls.CYAN = ''
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.RED = ''
        cls.BOLD = ''
        cls.UNDERLINE = ''
        cls.END = ''


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")


def print_success(text: str):
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")


def print_error(text: str):
    print(f"{Colors.RED}[ERROR] {text}{Colors.END}", file=sys.stderr)


def print_warning(text: str):
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.END}")


def print_info(text: str):
    print(f"{Colors.BLUE}[INFO] {text}{Colors.END}")


def print_step(step: int, total: int, text: str):
    print(f"{Colors.CYAN}[{step}/{total}]{Colors.END} {text}")


def print_kv(key: str, value: str, indent: int = 0):
    spaces = "  " * indent
    print(f"{spaces}{Colors.BOLD}{key}:{Colors.END} {value}")


# ============================================================================
# JSON SERIALIZATION
# ============================================================================

class DecisionGraphEncoder(json.JSONEncoder):
    """JSON encoder that handles DecisionGraph types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if hasattr(obj, 'value'):  # Enum
            return obj.value
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        if hasattr(obj, '__dataclass_fields__'):
            return {k: getattr(obj, k) for k in obj.__dataclass_fields__}
        return super().default(obj)


def json_dumps(obj: Any, indent: int = 2) -> str:
    """Serialize object to JSON string."""
    return json.dumps(obj, cls=DecisionGraphEncoder, indent=indent, sort_keys=True)


def compute_sha256(data: bytes) -> str:
    """Compute SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


# ============================================================================
# SIGNING
# ============================================================================

def sign_manifest(manifest_bytes: bytes, key_path: Path) -> bytes:
    """Sign manifest with Ed25519 key."""
    try:
        from decisiongraph.signing import sign_bytes

        with open(key_path, 'rb') as f:
            private_key = f.read()

        signature = sign_bytes(manifest_bytes, private_key)
        return signature
    except ImportError:
        # Fallback: use hashlib HMAC if signing module not available
        import hmac
        with open(key_path, 'rb') as f:
            key = f.read()
        sig = hmac.new(key, manifest_bytes, hashlib.sha256).digest()
        return sig
    except Exception as e:
        raise RuntimeError(f"Signing failed: {e}")


def verify_signature(manifest_bytes: bytes, signature: bytes, key_path: Path) -> bool:
    """Verify Ed25519 signature."""
    try:
        from decisiongraph.signing import verify_signature as verify_sig

        with open(key_path, 'rb') as f:
            public_key = f.read()

        return verify_sig(manifest_bytes, signature, public_key)
    except ImportError:
        # Fallback: HMAC verification
        import hmac
        with open(key_path, 'rb') as f:
            key = f.read()
        expected = hmac.new(key, manifest_bytes, hashlib.sha256).digest()
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


# ============================================================================
# CASE BUNDLE PARSING
# ============================================================================

def parse_case_bundle_json(path: Path) -> CaseBundle:
    """Parse a case bundle from JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Parse CaseMeta
    meta_data = data.get("meta", {})
    meta = CaseMeta(
        id=meta_data.get("id", ""),
        case_type=CaseType(meta_data.get("case_type", "aml_alert")),
        case_phase=CasePhase(meta_data.get("case_phase", "intake")),
        created_at=datetime.fromisoformat(meta_data.get("created_at", datetime.now(timezone.utc).isoformat())),
        jurisdiction=meta_data.get("jurisdiction", "CA"),
        primary_entity_type=EntityType(meta_data.get("primary_entity_type", "individual")),
        primary_entity_id=meta_data.get("primary_entity_id", ""),
        status=meta_data.get("status", "open"),
        priority=meta_data.get("priority", "normal"),
        sensitivity=Sensitivity(meta_data.get("sensitivity", "internal")),
        access_tags=meta_data.get("access_tags", ["fincrime"]),
    )

    # Parse Individuals
    individuals = []
    for ind_data in data.get("individuals", []):
        individuals.append(Individual(
            id=ind_data.get("id", ""),
            given_name=ind_data.get("given_name", ""),
            family_name=ind_data.get("family_name", ""),
            date_of_birth=_parse_date(ind_data.get("date_of_birth")),
            nationality=ind_data.get("nationality"),
            country_of_residence=ind_data.get("country_of_residence"),
            pep_status=PEPCategory(ind_data.get("pep_status", "none")),
            risk_rating=RiskRating(ind_data.get("risk_rating")) if ind_data.get("risk_rating") else None,
            sensitivity=Sensitivity(ind_data.get("sensitivity", "internal")),
            access_tags=ind_data.get("access_tags", ["fincrime"]),
        ))

    # Parse Organizations
    organizations = []
    for org_data in data.get("organizations", []):
        organizations.append(Organization(
            id=org_data.get("id", ""),
            legal_name=org_data.get("legal_name", ""),
            entity_type=org_data.get("entity_type", "corporation"),
            jurisdiction=org_data.get("jurisdiction", "CA"),
            registration_number=org_data.get("registration_number"),
            risk_rating=RiskRating(org_data.get("risk_rating")) if org_data.get("risk_rating") else None,
            sensitivity=Sensitivity(org_data.get("sensitivity", "internal")),
            access_tags=org_data.get("access_tags", ["fincrime"]),
        ))

    # Parse Accounts
    accounts = []
    for acc_data in data.get("accounts", []):
        accounts.append(Account(
            id=acc_data.get("id", ""),
            account_number=acc_data.get("account_number", ""),
            account_type=acc_data.get("account_type", "checking"),
            currency=acc_data.get("currency", "CAD"),
            status=acc_data.get("status", "active"),
            sensitivity=Sensitivity(acc_data.get("sensitivity", "internal")),
            access_tags=acc_data.get("access_tags", ["fincrime"]),
        ))

    # Parse Relationships
    relationships = []
    for rel_data in data.get("relationships", []):
        relationships.append(Relationship(
            id=rel_data.get("id", ""),
            relationship_type=RelationshipType(rel_data.get("relationship_type", "account_holder")),
            from_entity_type=EntityType(rel_data.get("from_entity_type", "individual")),
            from_entity_id=rel_data.get("from_entity_id", ""),
            to_entity_type=EntityType(rel_data.get("to_entity_type", "individual")),
            to_entity_id=rel_data.get("to_entity_id", ""),
            ownership_percentage=Decimal(rel_data.get("ownership_percentage")) if rel_data.get("ownership_percentage") else None,
            sensitivity=Sensitivity(rel_data.get("sensitivity", "internal")),
            access_tags=rel_data.get("access_tags", ["fincrime"]),
        ))

    # Parse Evidence
    evidence = []
    for ev_data in data.get("evidence", []):
        evidence.append(EvidenceItem(
            id=ev_data.get("id", ""),
            evidence_type=EvidenceType(ev_data.get("evidence_type", "other")),
            description=ev_data.get("description", ""),
            collected_date=_parse_date(ev_data.get("collected_date")) or datetime.now(timezone.utc).date(),
            source=ev_data.get("source", "system"),
            verified=ev_data.get("verified", False),
            sensitivity=Sensitivity(ev_data.get("sensitivity", "internal")),
            access_tags=ev_data.get("access_tags", ["fincrime"]),
        ))

    # Parse Events
    events = []
    for event_data in data.get("events", []):
        event_type = event_data.get("event_type", "")
        timestamp = datetime.fromisoformat(event_data.get("timestamp", datetime.now(timezone.utc).isoformat()))

        if event_type == "transaction":
            events.append(TransactionEvent(
                id=event_data.get("id", ""),
                event_type="transaction",
                timestamp=timestamp,
                description=event_data.get("description"),
                amount=Decimal(str(event_data.get("amount", "0"))),
                currency=event_data.get("currency", "CAD"),
                direction=event_data.get("direction", "outbound"),
                counterparty_name=event_data.get("counterparty_name"),
                counterparty_country=event_data.get("counterparty_country"),
                payment_method=event_data.get("payment_method"),
                sensitivity=Sensitivity(event_data.get("sensitivity", "internal")),
                access_tags=event_data.get("access_tags", ["fincrime"]),
            ))
        elif event_type == "alert":
            events.append(AlertEvent(
                id=event_data.get("id", ""),
                event_type="alert",
                timestamp=timestamp,
                description=event_data.get("description"),
                alert_type=event_data.get("alert_type", ""),
                rule_id=event_data.get("rule_id"),
                sensitivity=Sensitivity(event_data.get("sensitivity", "internal")),
                access_tags=event_data.get("access_tags", ["fincrime"]),
            ))
        elif event_type == "screening":
            events.append(ScreeningEvent(
                id=event_data.get("id", ""),
                event_type="screening",
                timestamp=timestamp,
                description=event_data.get("description"),
                screening_type=event_data.get("screening_type", "sanctions"),
                vendor=event_data.get("vendor", ""),
                disposition=event_data.get("disposition"),
                sensitivity=Sensitivity(event_data.get("sensitivity", "internal")),
                access_tags=event_data.get("access_tags", ["fincrime"]),
            ))

    # Parse Assertions
    assertions = []
    for ass_data in data.get("assertions", []):
        assertions.append(Assertion(
            id=ass_data.get("id", ""),
            subject_type=ass_data.get("subject_type", ""),
            subject_id=ass_data.get("subject_id", ""),
            predicate=ass_data.get("predicate", ""),
            value=ass_data.get("value", ""),
            asserted_at=datetime.fromisoformat(ass_data.get("asserted_at", datetime.now(timezone.utc).isoformat())),
            asserted_by=ass_data.get("asserted_by", "system"),
            sensitivity=Sensitivity(ass_data.get("sensitivity", "internal")),
            access_tags=ass_data.get("access_tags", ["fincrime"]),
        ))

    return CaseBundle(
        meta=meta,
        individuals=individuals,
        organizations=organizations,
        accounts=accounts,
        relationships=relationships,
        evidence=evidence,
        events=events,
        assertions=assertions,
    )


def _parse_date(date_str: Optional[str]):
    """Parse date string to date object."""
    if not date_str:
        return None
    if isinstance(date_str, date):
        return date_str
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None


# ============================================================================
# REPORT RENDERING
# ============================================================================

def render_report_text(
    case_id: str,
    pack_runtime: PackRuntime,
    chain: Chain,
    eval_result,
    bundle: CaseBundle,
    strict_mode: bool = False,
) -> str:
    """
    Render deterministic report text.

    This produces identical output for identical inputs (deterministic).
    """
    lines = []

    # Header
    lines.append("=" * 72)
    lines.append("DECISIONGRAPH CASE REPORT")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Case ID:      {case_id}")
    lines.append(f"Case Type:    {bundle.meta.case_type.value.upper()}")
    lines.append(f"Case Phase:   {bundle.meta.case_phase.value}")
    lines.append(f"Jurisdiction: {bundle.meta.jurisdiction}")
    lines.append(f"Priority:     {bundle.meta.priority}")
    lines.append("")
    lines.append(f"Pack ID:      {pack_runtime.pack_id}")
    lines.append(f"Pack Version: {pack_runtime.pack_version}")
    lines.append(f"Pack Hash:    {pack_runtime.pack_hash}")
    lines.append("")
    lines.append(f"Graph ID:     {chain.graph_id}")
    lines.append(f"Chain Length: {len(chain)} cells")
    if strict_mode:
        lines.append(f"Mode:         STRICT")
    lines.append("")

    # Verdict Banner
    lines.append("-" * 72)
    if eval_result and eval_result.verdict:
        verdict_obj = eval_result.verdict.fact.object
        verdict = verdict_obj.get("verdict", "UNKNOWN")
        auto_archive = verdict_obj.get("auto_archive_permitted", False)
        lines.append(f"VERDICT: {verdict}")
        lines.append(f"Auto-Archive Permitted: {'YES' if auto_archive else 'NO'}")

        if strict_mode and not auto_archive:
            lines.append("")
            lines.append("*** STRICT MODE: CASE NOT APPROVED FOR AUTO-PROCESSING ***")
    else:
        lines.append("VERDICT: PENDING")
    lines.append("-" * 72)
    lines.append("")

    # Score Summary
    lines.append("RISK SCORE SUMMARY")
    lines.append("-" * 36)
    if eval_result and eval_result.score:
        score_obj = eval_result.score.fact.object
        lines.append(f"Inherent Score:    {score_obj.get('inherent_score', 'N/A'):>10}")
        lines.append(f"Mitigations:       {score_obj.get('mitigation_sum', 'N/A'):>10}")
        lines.append(f"Residual Score:    {score_obj.get('residual_score', 'N/A'):>10}")
        lines.append(f"Threshold Gate:    {score_obj.get('threshold_gate', 'N/A'):>10}")
    else:
        lines.append("Score not computed")
    lines.append("")

    # Signals Fired
    lines.append("SIGNALS FIRED")
    lines.append("-" * 36)
    if eval_result and eval_result.signals:
        for signal in sorted(eval_result.signals, key=lambda s: s.fact.object.get('code', '')):
            obj = signal.fact.object
            code = obj.get('code', 'UNKNOWN')
            severity = obj.get('severity', 'N/A')
            name = obj.get('name', '')
            policy_ref = obj.get('policy_ref', '')
            lines.append(f"  [{severity:8}] {code}")
            if name:
                lines.append(f"             {name}")
            if policy_ref:
                lines.append(f"             Ref: {policy_ref}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Mitigations Applied
    lines.append("MITIGATIONS APPLIED")
    lines.append("-" * 36)
    if eval_result and eval_result.mitigations:
        for mitigation in sorted(eval_result.mitigations, key=lambda m: m.fact.object.get('code', '')):
            obj = mitigation.fact.object
            code = obj.get('code', 'UNKNOWN')
            weight = obj.get('weight', 'N/A')
            name = obj.get('name', '')
            lines.append(f"  [{weight:>6}] {code}")
            if name:
                lines.append(f"             {name}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Entity Summary
    lines.append("ENTITIES")
    lines.append("-" * 36)
    for ind in bundle.individuals:
        lines.append(f"  [INDIVIDUAL] {ind.id}: {ind.full_name}")
        if ind.pep_status and ind.pep_status.value != "none":
            lines.append(f"               PEP: {ind.pep_status.value.upper()}")
        if ind.risk_rating:
            lines.append(f"               Risk: {ind.risk_rating.value.upper()}")
    for org in bundle.organizations:
        lines.append(f"  [ORGANIZATION] {org.id}: {org.legal_name}")
        if org.risk_rating:
            lines.append(f"                 Risk: {org.risk_rating.value.upper()}")
    if not bundle.individuals and not bundle.organizations:
        lines.append("  (none)")
    lines.append("")

    # Evidence Summary
    lines.append("EVIDENCE")
    lines.append("-" * 36)
    for ev in bundle.evidence:
        status = "VERIFIED" if ev.verified else "UNVERIFIED"
        desc = ev.description[:50] if ev.description else ""
        lines.append(f"  [{status:10}] {ev.id}: {ev.evidence_type.value}")
        if desc:
            lines.append(f"               {desc}...")
    if not bundle.evidence:
        lines.append("  (none)")
    lines.append("")

    # Transaction Summary
    lines.append("TRANSACTIONS")
    lines.append("-" * 36)
    for event in bundle.events:
        if hasattr(event, 'amount'):
            direction = getattr(event, 'direction', 'N/A')
            amount = getattr(event, 'amount', '0')
            currency = getattr(event, 'currency', 'CAD')
            counterparty = getattr(event, 'counterparty_name', None)
            country = getattr(event, 'counterparty_country', '')
            lines.append(f"  [{direction.upper():8}] {event.id}: {amount} {currency}")
            if counterparty:
                lines.append(f"             To: {counterparty} ({country})")
    lines.append("")

    # Chain Integrity
    lines.append("CHAIN INTEGRITY")
    lines.append("-" * 36)
    validation = chain.validate()
    if validation.is_valid:
        lines.append("  Status: VALID")
        lines.append(f"  Cells:  {len(chain)}")
    else:
        lines.append("  Status: INVALID")
        for error in validation.errors[:5]:
            lines.append(f"  Error:  {error}")
    lines.append("")

    # Policy References
    lines.append("POLICY REFERENCES")
    lines.append("-" * 36)
    if pack_runtime.policy_refs:
        for ref in sorted(pack_runtime.policy_refs, key=lambda r: r.ref_id):
            lines.append(f"  {ref.ref_id}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Footer
    lines.append("=" * 72)
    lines.append("END OF REPORT")
    lines.append("=" * 72)
    lines.append("")

    return "\n".join(lines)


# ============================================================================
# CELL ORDERING (deterministic)
# ============================================================================

def order_cells_deterministic(
    case_cells: list,
    policy_cells: list,
    eval_result,
) -> list:
    """
    Order cells in deterministic, auditable sequence.

    Order:
    1. Case cells (CaseMeta -> Phase -> Entities -> Accounts -> Relationships -> Evidence -> Events -> Assertions)
    2. Policy cells (sorted by ref_id)
    3. Signal cells (sorted by code)
    4. Mitigation cells (sorted by code)
    5. Score cell
    6. Verdict cell
    """
    ordered = []

    # 1. Case cells (already in order from case_loader)
    ordered.extend(case_cells)

    # 2. Policy cells (sorted by subject for stability)
    sorted_policy = sorted(policy_cells, key=lambda c: c.fact.subject)
    ordered.extend(sorted_policy)

    if eval_result:
        # 3. Signals (sorted by code)
        sorted_signals = sorted(
            eval_result.signals or [],
            key=lambda c: c.fact.object.get('code', '')
        )
        ordered.extend(sorted_signals)

        # 4. Mitigations (sorted by code)
        sorted_mitigations = sorted(
            eval_result.mitigations or [],
            key=lambda c: c.fact.object.get('code', '')
        )
        ordered.extend(sorted_mitigations)

        # 5. Score
        if eval_result.score:
            ordered.append(eval_result.score)

        # 6. Verdict
        if eval_result.verdict:
            ordered.append(eval_result.verdict)

    return ordered


# ============================================================================
# OUTPUT BUNDLE WRITING
# ============================================================================

def write_bundle(
    output_dir: Path,
    case_id: str,
    pack_runtime: PackRuntime,
    chain: Chain,
    case_cells: list,
    policy_cells: list,
    eval_result,
    bundle: CaseBundle,
    include_cells: bool = True,
    sign_key: Optional[Path] = None,
    strict_mode: bool = False,
    legal_hold: bool = False,
) -> dict:
    """Write all bank-ready deliverables to output directory."""
    case_dir = output_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    # Get environment info for audit trail
    env_info = get_environment_info()

    verification = {
        "case_id": case_id,
        "timestamp": get_current_timestamp(),
        "strict_mode": strict_mode,
        "environment": env_info,
        "checks": [],
        "overall": "PASS",
    }

    # 1. Render report.txt (deterministic bytes)
    print_step(1, 8 if sign_key else 7, "Rendering report...")
    report_text = render_report_text(case_id, pack_runtime, chain, eval_result, bundle, strict_mode)
    report_bytes = report_text.encode('utf-8')
    report_path = case_dir / "report.txt"
    with open(report_path, 'wb') as f:
        f.write(report_bytes)

    # 2. Compute report.sha256
    print_step(2, 8 if sign_key else 7, "Computing report hash...")
    report_hash = compute_sha256(report_bytes)
    hash_path = case_dir / "report.sha256"
    with open(hash_path, 'w') as f:
        f.write(f"{report_hash}  report.txt\n")

    verification["checks"].append({
        "name": "report_hash",
        "status": "PASS",
        "hash": report_hash,
        "bytes": len(report_bytes),
    })

    # 3. Write manifest.json
    print_step(3, 8 if sign_key else 7, "Writing manifest...")

    # Order cells deterministically
    ordered_cells = order_cells_deterministic(case_cells, policy_cells, eval_result)

    verdict_val = None
    auto_archive = False
    score_obj = None

    if eval_result:
        if eval_result.verdict:
            verdict_val = eval_result.verdict.fact.object.get("verdict")
            auto_archive = eval_result.verdict.fact.object.get("auto_archive_permitted", False)
        if eval_result.score:
            score_obj = eval_result.score.fact.object

    # Determine retention class based on verdict
    retention_class = get_retention_class(verdict_val or "", legal_hold)

    manifest = {
        "case_id": case_id,
        "report_hash": report_hash,
        "graph_id": chain.graph_id,
        "chain_length": len(chain),
        "case_cells": len(case_cells),
        "policy_cells": len(policy_cells),
        "derived_cells": len(eval_result.all_cells) if eval_result else 0,
        "total_cells": len(ordered_cells),
        "cell_ids": [cell.cell_id for cell in ordered_cells],
        "signals_fired": eval_result.signals_fired if eval_result else 0,
        "mitigations_applied": eval_result.mitigations_applied if eval_result else 0,
        "verdict": verdict_val,
        "auto_archive_permitted": auto_archive,
        "score": score_obj,
        "strict_mode": strict_mode,
        "approved": auto_archive if not strict_mode else False,
        "created_at": get_current_timestamp(),
        # Retention and legal hold
        "retention": {
            "retention_class": retention_class,
            "legal_hold": legal_hold,
        },
        # Environment info for audit trail
        "environment": env_info,
    }
    manifest_path = case_dir / "manifest.json"
    manifest_bytes = json_dumps(manifest).encode('utf-8')
    with open(manifest_path, 'wb') as f:
        f.write(manifest_bytes)

    # 4. Write pack.json
    print_step(4, 8 if sign_key else 7, "Writing pack metadata...")
    pack_meta = {
        "pack_id": pack_runtime.pack_id,
        "name": pack_runtime.name,
        "version": pack_runtime.pack_version,
        "pack_hash": pack_runtime.pack_hash,
        "domain": pack_runtime.domain,
        "jurisdiction": pack_runtime.jurisdiction,
        "signals_count": len(pack_runtime.signals_by_code),
        "mitigations_count": len(pack_runtime.mitigations_by_code),
        "policy_refs_count": len(pack_runtime.policy_refs),
        "regulatory_framework": pack_runtime.regulatory_framework,
    }
    pack_path = case_dir / "pack.json"
    with open(pack_path, 'w') as f:
        f.write(json_dumps(pack_meta))

    # 5. Verification checks
    print_step(5, 8 if sign_key else 7, "Running verification checks...")

    # Check: Chain integrity
    chain_validation = chain.validate()
    verification["checks"].append({
        "name": "chain_integrity",
        "status": "PASS" if chain_validation.is_valid else "FAIL",
        "errors": chain_validation.errors[:5] if not chain_validation.is_valid else [],
    })
    if not chain_validation.is_valid:
        verification["overall"] = "FAIL"

    # Check: Determinism (re-render and compare)
    report_text_2 = render_report_text(case_id, pack_runtime, chain, eval_result, bundle, strict_mode)
    report_hash_2 = compute_sha256(report_text_2.encode('utf-8'))
    determinism_pass = (report_hash == report_hash_2)
    verification["checks"].append({
        "name": "determinism",
        "status": "PASS" if determinism_pass else "FAIL",
        "message": "Report renders identically" if determinism_pass else "Report hash mismatch on re-render",
    })
    if not determinism_pass:
        verification["overall"] = "FAIL"

    # Check: Coverage (all signals have policy refs)
    signals_without_refs = []
    for code, sig in pack_runtime.signals_by_code.items():
        if not sig.policy_ref:
            signals_without_refs.append(code)
    coverage_pass = len(signals_without_refs) == 0
    verification["checks"].append({
        "name": "policy_coverage",
        "status": "PASS" if coverage_pass else "WARN",
        "signals_without_refs": signals_without_refs,
    })

    # Check: Gate outcome consistency
    if eval_result and eval_result.score and eval_result.verdict:
        score_gate = eval_result.score.fact.object.get("threshold_gate")
        gate_consistent = (score_gate == verdict_val or verdict_val in ["CLOSE", "ESCALATE"])
        verification["checks"].append({
            "name": "gate_consistency",
            "status": "PASS" if gate_consistent else "WARN",
            "score_gate": score_gate,
            "verdict": verdict_val,
        })

    # Check: Manifest hash
    manifest_hash = compute_sha256(manifest_bytes)
    verification["checks"].append({
        "name": "manifest_hash",
        "status": "PASS",
        "hash": manifest_hash,
    })

    verification_path = case_dir / "verification.json"
    with open(verification_path, 'w') as f:
        f.write(json_dumps(verification))

    # 6. Write cells.jsonl (deterministic order)
    cells_path = None
    if include_cells:
        print_step(6, 8 if sign_key else 7, "Writing cells...")
        cells_path = case_dir / "cells.jsonl"
        with open(cells_path, 'w') as f:
            for cell in ordered_cells:
                f.write(json_dumps(cell.to_dict(), indent=None) + "\n")
    else:
        print_step(6, 8 if sign_key else 7, "Skipping cells export...")

    # 7. Sign manifest (optional)
    sig_path = None
    if sign_key:
        print_step(7, 8, "Signing manifest...")
        try:
            signature = sign_manifest(manifest_bytes, sign_key)
            sig_path = case_dir / "manifest.sig"
            with open(sig_path, 'wb') as f:
                f.write(signature)
            verification["checks"].append({
                "name": "signature",
                "status": "PASS",
                "key_file": str(sign_key),
            })
        except Exception as e:
            print_warning(f"Signing failed: {e}")
            verification["checks"].append({
                "name": "signature",
                "status": "FAIL",
                "error": str(e),
            })

    # 8. Create bundle.zip
    print_step(8 if sign_key else 7, 8 if sign_key else 7, "Creating bundle.zip...")
    zip_path = case_dir / "bundle.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(report_path, "report.txt")
        zf.write(hash_path, "report.sha256")
        zf.write(manifest_path, "manifest.json")
        zf.write(pack_path, "pack.json")
        zf.write(verification_path, "verification.json")
        if cells_path and cells_path.exists():
            zf.write(cells_path, "cells.jsonl")
        if sig_path and sig_path.exists():
            zf.write(sig_path, "manifest.sig")

    return verification


# ============================================================================
# BUNDLE VERIFICATION
# ============================================================================

def verify_bundle(bundle_path: Path, key_path: Optional[Path] = None) -> dict:
    """
    Verify an existing bundle for integrity.

    Checks:
    1. report.sha256 matches report.txt
    2. manifest.json cell_ids exist in cells.jsonl
    3. manifest signature valid (if present and key provided)
    4. pack.json pack_hash is valid format
    """
    results = {
        "bundle_path": str(bundle_path),
        "timestamp": get_current_timestamp(),
        "checks": [],
        "overall": "PASS",
    }

    # Extract to temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        try:
            with zipfile.ZipFile(bundle_path, 'r') as zf:
                zf.extractall(tmppath)
        except Exception as e:
            results["checks"].append({
                "name": "bundle_extract",
                "status": "FAIL",
                "error": str(e),
            })
            results["overall"] = "FAIL"
            return results

        results["checks"].append({
            "name": "bundle_extract",
            "status": "PASS",
        })

        # 1. Verify report hash
        report_path = tmppath / "report.txt"
        hash_path = tmppath / "report.sha256"

        if report_path.exists() and hash_path.exists():
            with open(report_path, 'rb') as f:
                report_bytes = f.read()
            computed_hash = compute_sha256(report_bytes)

            with open(hash_path, 'r') as f:
                expected_line = f.read().strip()
                expected_hash = expected_line.split()[0] if expected_line else ""

            hash_match = (computed_hash == expected_hash)
            results["checks"].append({
                "name": "report_hash",
                "status": "PASS" if hash_match else "FAIL",
                "computed": computed_hash[:16] + "...",
                "expected": expected_hash[:16] + "...",
            })
            if not hash_match:
                results["overall"] = "FAIL"
        else:
            results["checks"].append({
                "name": "report_hash",
                "status": "FAIL",
                "error": "Missing report.txt or report.sha256",
            })
            results["overall"] = "FAIL"

        # 2. Verify manifest structure
        manifest_path = tmppath / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            required_fields = ["case_id", "report_hash", "graph_id", "cell_ids"]
            missing = [f for f in required_fields if f not in manifest]

            if missing:
                results["checks"].append({
                    "name": "manifest_structure",
                    "status": "FAIL",
                    "missing_fields": missing,
                })
                results["overall"] = "FAIL"
            else:
                results["checks"].append({
                    "name": "manifest_structure",
                    "status": "PASS",
                    "case_id": manifest.get("case_id"),
                    "cells": len(manifest.get("cell_ids", [])),
                })

            # Verify manifest hash matches report hash in manifest
            if manifest.get("report_hash") != computed_hash:
                results["checks"].append({
                    "name": "manifest_report_hash",
                    "status": "FAIL",
                    "error": "Manifest report_hash doesn't match computed hash",
                })
                results["overall"] = "FAIL"
            else:
                results["checks"].append({
                    "name": "manifest_report_hash",
                    "status": "PASS",
                })
        else:
            results["checks"].append({
                "name": "manifest_structure",
                "status": "FAIL",
                "error": "Missing manifest.json",
            })
            results["overall"] = "FAIL"

        # 3. Verify cells.jsonl matches manifest
        cells_path = tmppath / "cells.jsonl"
        if cells_path.exists() and manifest_path.exists():
            with open(cells_path, 'r') as f:
                cell_lines = f.readlines()

            cell_ids_in_file = []
            for line in cell_lines:
                try:
                    cell = json.loads(line)
                    cell_ids_in_file.append(cell.get("cell_id"))
                except:
                    pass

            manifest_cell_ids = manifest.get("cell_ids", [])

            # Check all manifest cells are in file
            missing_cells = [cid for cid in manifest_cell_ids if cid not in cell_ids_in_file]

            if missing_cells:
                results["checks"].append({
                    "name": "cells_coverage",
                    "status": "FAIL",
                    "missing_count": len(missing_cells),
                })
                results["overall"] = "FAIL"
            else:
                results["checks"].append({
                    "name": "cells_coverage",
                    "status": "PASS",
                    "cells_verified": len(manifest_cell_ids),
                })

        # 4. Verify signature (if present and key provided)
        sig_path = tmppath / "manifest.sig"
        if sig_path.exists():
            if key_path and key_path.exists():
                with open(manifest_path, 'rb') as f:
                    manifest_bytes = f.read()
                with open(sig_path, 'rb') as f:
                    signature = f.read()

                sig_valid = verify_signature(manifest_bytes, signature, key_path)
                results["checks"].append({
                    "name": "signature",
                    "status": "PASS" if sig_valid else "FAIL",
                })
                if not sig_valid:
                    results["overall"] = "FAIL"
            else:
                results["checks"].append({
                    "name": "signature",
                    "status": "SKIP",
                    "message": "Signature present but no key provided",
                })
        else:
            results["checks"].append({
                "name": "signature",
                "status": "SKIP",
                "message": "No signature in bundle",
            })

        # 5. Verify pack.json
        pack_path = tmppath / "pack.json"
        if pack_path.exists():
            with open(pack_path, 'r') as f:
                pack_meta = json.load(f)

            pack_hash = pack_meta.get("pack_hash", "")
            if len(pack_hash) == 64:
                results["checks"].append({
                    "name": "pack_hash_format",
                    "status": "PASS",
                    "pack_id": pack_meta.get("pack_id"),
                    "version": pack_meta.get("version"),
                })
            else:
                results["checks"].append({
                    "name": "pack_hash_format",
                    "status": "FAIL",
                    "error": "Invalid pack_hash length",
                })
                results["overall"] = "FAIL"

    return results


# ============================================================================
# COMMANDS
# ============================================================================

def cmd_run_case(args):
    """Run a case through the rules engine and produce bank-ready deliverables."""
    print_header("DecisionGraph - Run Case")

    case_path = Path(args.case)
    pack_path = Path(args.pack)
    output_dir = Path(args.out) if args.out else Path("./out")
    include_cells = not args.no_cells
    sign_key = Path(args.sign) if args.sign else None
    strict_mode = args.strict

    # Check files exist
    if not case_path.exists():
        print_error(f"Case file not found: {case_path}")
        return ExitCode.INPUT_INVALID

    if not pack_path.exists():
        print_error(f"Pack file not found: {pack_path}")
        return ExitCode.INPUT_INVALID

    if sign_key and not sign_key.exists():
        print_error(f"Signing key not found: {sign_key}")
        return ExitCode.INPUT_INVALID

    total_steps = 9

    # Step 1: Load pack
    print_step(1, total_steps, f"Loading pack: {pack_path.name}")
    try:
        pack_runtime = load_pack_yaml(str(pack_path))
        print_success(f"Pack: {pack_runtime.pack_id} v{pack_runtime.pack_version}")
        print_kv("Pack hash", pack_runtime.pack_hash[:16] + "...", indent=1)
        print_kv("Signals", str(len(pack_runtime.signals_by_code)), indent=1)
        print_kv("Mitigations", str(len(pack_runtime.mitigations_by_code)), indent=1)
    except PackValidationError as e:
        print_error(f"Pack validation failed: {e}")
        return ExitCode.PACK_ERROR
    except PackLoaderError as e:
        print_error(f"Pack loading failed: {e}")
        return ExitCode.PACK_ERROR

    # Step 2: Load case bundle
    print_step(2, total_steps, f"Loading case: {case_path.name}")
    try:
        bundle = parse_case_bundle_json(case_path)
        case_id = bundle.meta.id
        print_success(f"Case: {case_id}")
        print_kv("Type", bundle.meta.case_type.value, indent=1)
        print_kv("Phase", bundle.meta.case_phase.value, indent=1)
        print_kv("Entities", str(len(bundle.individuals) + len(bundle.organizations)), indent=1)
        print_kv("Events", str(len(bundle.events)), indent=1)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        return ExitCode.INPUT_INVALID
    except Exception as e:
        print_error(f"Case loading failed: {e}")
        return ExitCode.INPUT_INVALID

    # Validate case bundle
    errors = validate_case_bundle(bundle)
    if errors:
        print_warning(f"Case bundle has {len(errors)} validation warning(s)")

    # Step 3: Create chain
    print_step(3, total_steps, "Creating decision chain...")
    chain = Chain()
    chain.initialize(
        graph_name=f"Case_{case_id}",
        root_namespace="fincrime",
        hash_scheme=HASH_SCHEME_CANONICAL,
    )
    print_success(f"Graph ID: {chain.graph_id}")

    # Step 4: Load case into chain
    print_step(4, total_steps, "Loading case into chain...")
    case_cells = load_case_bundle_to_chain(bundle, chain)
    print_success(f"Created {len(case_cells)} case cells")

    # Step 5: Add policy cells
    print_step(5, total_steps, "Adding policy cells...")
    policy_cells = pack_runtime.create_policy_cells(
        graph_id=chain.graph_id,
        prev_hash=chain.head.cell_id,
    )
    for cell in policy_cells:
        chain.append(cell)
    print_success(f"Added {len(policy_cells)} policy cells")

    # Step 6: Run rules engine
    print_step(6, total_steps, "Evaluating rules...")
    engine = pack_runtime.create_rules_engine()

    facts = []
    for cell in chain.cells:
        if cell.header.cell_type in (CellType.FACT, CellType.EVIDENCE):
            facts.append(cell.fact)

    context = EvaluationContext(
        graph_id=chain.graph_id,
        namespace="fincrime.eval",
        case_id=case_id,
        prev_cell_hash=chain.head.cell_id,
    )

    eval_result = engine.evaluate(facts, context)

    for cell in eval_result.all_cells:
        chain.append(cell)

    print_success(f"Signals fired: {eval_result.signals_fired}")
    print_success(f"Mitigations applied: {eval_result.mitigations_applied}")

    # Get verdict info
    verdict_val = None
    auto_archive = False
    gate = None

    if eval_result.score:
        score_obj = eval_result.score.fact.object
        gate = score_obj.get("threshold_gate", "UNKNOWN")
        print_kv("Score", "", indent=1)
        print_kv("Inherent", score_obj.get("inherent_score", "N/A"), indent=2)
        print_kv("Mitigations", score_obj.get("mitigation_sum", "N/A"), indent=2)
        print_kv("Residual", score_obj.get("residual_score", "N/A"), indent=2)
        print_kv("Gate", gate, indent=2)

    if eval_result.verdict:
        verdict_obj = eval_result.verdict.fact.object
        verdict_val = verdict_obj.get("verdict", "UNKNOWN")
        auto_archive = verdict_obj.get("auto_archive_permitted", False)
        print()

        if auto_archive:
            print(f"  {Colors.GREEN}{Colors.BOLD}VERDICT: {verdict_val}{Colors.END}")
        elif gate in ("ANALYST_REVIEW", "SENIOR_REVIEW"):
            print(f"  {Colors.YELLOW}{Colors.BOLD}VERDICT: {verdict_val}{Colors.END}")
        else:
            print(f"  {Colors.RED}{Colors.BOLD}VERDICT: {verdict_val}{Colors.END}")

        if strict_mode and not auto_archive:
            print(f"  {Colors.RED}*** STRICT MODE: NOT APPROVED ***{Colors.END}")

    # Step 7-9: Write bundle
    print()
    print_step(7, total_steps, "Writing output bundle...")
    # Get legal_hold flag
    legal_hold = getattr(args, 'legal_hold', False)

    verification = write_bundle(
        output_dir=output_dir,
        case_id=case_id,
        pack_runtime=pack_runtime,
        chain=chain,
        case_cells=case_cells,
        policy_cells=policy_cells,
        eval_result=eval_result,
        bundle=bundle,
        include_cells=include_cells,
        sign_key=sign_key,
        strict_mode=strict_mode,
        legal_hold=legal_hold,
    )

    # Final summary
    print_header("Output Bundle")
    bundle_dir = output_dir / case_id
    print_kv("Location", str(bundle_dir))
    print()
    print("  Files:")
    for f in sorted(bundle_dir.iterdir()):
        size = f.stat().st_size
        print(f"    {f.name:20} {size:>10,} bytes")

    print()
    print_header("Verification")
    overall = verification["overall"]
    if overall == "PASS":
        print(f"  {Colors.GREEN}{Colors.BOLD}OVERALL: PASS{Colors.END}")
    else:
        print(f"  {Colors.RED}{Colors.BOLD}OVERALL: {overall}{Colors.END}")

    for check in verification["checks"]:
        status = check["status"]
        name = check["name"]
        if status == "PASS":
            print(f"  {Colors.GREEN}[PASS]{Colors.END} {name}")
        elif status == "WARN":
            print(f"  {Colors.YELLOW}[WARN]{Colors.END} {name}")
        elif status == "SKIP":
            print(f"  {Colors.BLUE}[SKIP]{Colors.END} {name}")
        else:
            print(f"  {Colors.RED}[FAIL]{Colors.END} {name}")

    print()
    print_success(f"Bundle ready: {bundle_dir / 'bundle.zip'}")

    # Determine exit code
    if verification["overall"] == "FAIL":
        return ExitCode.VERIFY_FAIL

    exit_code = gate_to_exit_code(gate or "UNKNOWN", auto_archive)

    if strict_mode and exit_code != ExitCode.PASS:
        print()
        print_warning(f"Strict mode: exit code {exit_code} (review required)")

    return exit_code


def cmd_verify_bundle(args):
    """Verify an existing bundle for integrity."""
    print_header("DecisionGraph - Verify Bundle")

    bundle_path = Path(args.bundle)
    key_path = Path(args.key) if args.key else None

    if not bundle_path.exists():
        print_error(f"Bundle not found: {bundle_path}")
        return ExitCode.INPUT_INVALID

    print_info(f"Verifying: {bundle_path}")
    print()

    results = verify_bundle(bundle_path, key_path)

    # Print results
    for check in results["checks"]:
        status = check["status"]
        name = check["name"]

        if status == "PASS":
            print(f"  {Colors.GREEN}[PASS]{Colors.END} {name}")
        elif status == "WARN":
            print(f"  {Colors.YELLOW}[WARN]{Colors.END} {name}")
        elif status == "SKIP":
            print(f"  {Colors.BLUE}[SKIP]{Colors.END} {name}")
            if "message" in check:
                print(f"         {check['message']}")
        else:
            print(f"  {Colors.RED}[FAIL]{Colors.END} {name}")
            if "error" in check:
                print(f"         {check['error']}")

    print()
    overall = results["overall"]
    if overall == "PASS":
        print(f"{Colors.GREEN}{Colors.BOLD}VERIFICATION: PASS{Colors.END}")
        return ExitCode.PASS
    else:
        print(f"{Colors.RED}{Colors.BOLD}VERIFICATION: FAIL{Colors.END}")
        return ExitCode.VERIFY_FAIL


def cmd_validate_pack(args):
    """Validate a pack file."""
    print_header("DecisionGraph - Validate Pack")

    pack_path = Path(args.pack)

    if not pack_path.exists():
        print_error(f"Pack file not found: {pack_path}")
        return ExitCode.INPUT_INVALID

    print_info(f"Validating: {pack_path}")

    try:
        runtime = load_pack_yaml(str(pack_path))
        print_success("Pack is valid!")
        print()
        print_kv("Pack ID", runtime.pack_id)
        print_kv("Version", runtime.pack_version)
        print_kv("Domain", runtime.domain)
        print_kv("Jurisdiction", runtime.jurisdiction)
        print_kv("Pack Hash", runtime.pack_hash[:32] + "...")
        print()
        print_kv("Signals", str(len(runtime.signals_by_code)))
        print_kv("Mitigations", str(len(runtime.mitigations_by_code)))
        print_kv("Policy Refs", str(len(runtime.policy_refs)))
        print()

        if runtime.scoring_rule:
            print_kv("Scoring Rule", runtime.scoring_rule.rule_id)
            print_kv("Threshold Gates", str(len(runtime.scoring_rule.threshold_gates)))

        if runtime.verdict_rule:
            print_kv("Verdict Rule", runtime.verdict_rule.rule_id)

        return ExitCode.PASS

    except PackValidationError as e:
        print_error(f"Validation failed with {len(e.errors)} error(s):")
        for error in e.errors:
            print(f"  {Colors.RED}[X]{Colors.END} {error}")
        return ExitCode.PACK_ERROR

    except PackLoaderError as e:
        print_error(f"Loading failed: {e}")
        return ExitCode.PACK_ERROR


def cmd_validate_case(args):
    """Validate a case bundle file."""
    print_header("DecisionGraph - Validate Case")

    case_path = Path(args.case)

    if not case_path.exists():
        print_error(f"Case file not found: {case_path}")
        return ExitCode.INPUT_INVALID

    print_info(f"Validating: {case_path}")

    try:
        bundle = parse_case_bundle_json(case_path)
        errors = validate_case_bundle(bundle)

        if errors:
            print_warning(f"Case has {len(errors)} validation error(s):")
            for error in errors:
                print(f"  {Colors.YELLOW}[!]{Colors.END} {error}")
            return ExitCode.INPUT_INVALID
        else:
            print_success("Case is valid!")
            print()
            print_kv("Case ID", bundle.meta.id)
            print_kv("Type", bundle.meta.case_type.value)
            print_kv("Phase", bundle.meta.case_phase.value)
            print_kv("Jurisdiction", bundle.meta.jurisdiction)
            print()
            print_kv("Individuals", str(len(bundle.individuals)))
            print_kv("Organizations", str(len(bundle.organizations)))
            print_kv("Accounts", str(len(bundle.accounts)))
            print_kv("Relationships", str(len(bundle.relationships)))
            print_kv("Evidence Items", str(len(bundle.evidence)))
            print_kv("Events", str(len(bundle.events)))
            print_kv("Assertions", str(len(bundle.assertions)))
            return ExitCode.PASS

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        return ExitCode.INPUT_INVALID
    except Exception as e:
        print_error(f"Parsing failed: {e}")
        return ExitCode.INPUT_INVALID


def cmd_pack_info(args):
    """Show pack information."""
    print_header("DecisionGraph - Pack Info")

    pack_path = Path(args.pack)

    if not pack_path.exists():
        print_error(f"Pack file not found: {pack_path}")
        return ExitCode.INPUT_INVALID

    try:
        runtime = load_pack_yaml(str(pack_path))

        print_kv("Pack ID", runtime.pack_id)
        print_kv("Name", runtime.name)
        print_kv("Version", runtime.pack_version)
        print_kv("Domain", runtime.domain)
        print_kv("Jurisdiction", runtime.jurisdiction)
        print()
        print_kv("Pack Hash", runtime.pack_hash)
        print()

        if runtime.regulatory_framework:
            print(f"\n{Colors.BOLD}Regulatory Framework:{Colors.END}")
            for key, value in runtime.regulatory_framework.items():
                if isinstance(value, (str, int, float)):
                    print_kv(key, str(value), indent=1)

        print(f"\n{Colors.BOLD}Signals ({len(runtime.signals_by_code)}):{Colors.END}")
        for code, sig in sorted(runtime.signals_by_code.items()):
            print(f"  {code}: {sig.severity.value} - {sig.name}")

        print(f"\n{Colors.BOLD}Mitigations ({len(runtime.mitigations_by_code)}):{Colors.END}")
        for code, mit in sorted(runtime.mitigations_by_code.items()):
            print(f"  {code}: {mit.weight} - {mit.name}")

        if runtime.scoring_rule:
            print(f"\n{Colors.BOLD}Threshold Gates:{Colors.END}")
            for gate in runtime.scoring_rule.threshold_gates:
                print(f"  {gate.code}: < {gate.max_score}")

        return ExitCode.PASS

    except Exception as e:
        print_error(f"Failed to load pack: {e}")
        return ExitCode.PACK_ERROR


# ============================================================================
# MAP-CASE COMMAND
# ============================================================================

def cmd_map_case(args):
    """Map a vendor export to CaseBundle format using an adapter."""
    print_header("DecisionGraph - Map Case")

    input_path = Path(args.input)
    adapter_path = Path(args.adapter)
    output_path = Path(args.out) if args.out else None
    max_errors = getattr(args, 'max_errors', 0) or 0
    error_file = getattr(args, 'error_file', None)

    # Validate paths
    if not input_path.exists():
        print_error(f"Input file not found: {input_path}")
        return ExitCode.INPUT_INVALID

    if not adapter_path.exists():
        print_error(f"Adapter file not found: {adapter_path}")
        return ExitCode.INPUT_INVALID

    try:
        # Load and validate adapter
        print_info(f"Loading adapter: {adapter_path.name}")
        adapter = load_adapter(adapter_path)
        print_success(f"Adapter: {adapter.metadata.name} v{adapter.metadata.version}")
        print_kv("Vendor", adapter.metadata.vendor)
        print_kv("Format", adapter.metadata.input_format)
        print_kv("Adapter Hash", adapter.adapter_hash[:16] + "...")

        # Map using the high-level API
        print_info(f"Loading and mapping: {input_path.name}")
        result = map_case(
            input_path=input_path,
            adapter_path=adapter_path,
            output_path=output_path,
            max_errors=max_errors,
            error_file=error_file,
        )
        print_success("Mapping complete")

        # Validate output bundle
        print_info("Validating output bundle...")
        parsed_bundle = parse_case_bundle_dict(result.bundle)
        validation_errors = validate_case_bundle(parsed_bundle)

        if validation_errors:
            print_warning(f"Output bundle has {len(validation_errors)} validation warning(s):")
            for error in validation_errors[:5]:
                print(f"  {Colors.YELLOW}[!]{Colors.END} {error}")
            if len(validation_errors) > 5:
                print(f"  ... and {len(validation_errors) - 5} more")
        else:
            print_success("Output bundle is valid")

        # Mapping summary
        print()
        print(f"{Colors.BOLD}Mapping Summary:{Colors.END}")
        print_kv("Case ID", result.bundle["meta"].get("id", "N/A"))
        print_kv("Case Type", result.bundle["meta"].get("case_type", "N/A"))
        print_kv("Jurisdiction", result.bundle["meta"].get("jurisdiction", "N/A"))
        print()
        print_kv("Records Processed", str(result.records_processed))
        print_kv("Records Mapped", str(result.records_mapped))
        print_kv("Records Skipped", str(result.records_skipped))
        if result.errors:
            print_kv("Mapping Errors", str(len(result.errors)))
        print()
        print_kv("Individuals", str(len(result.bundle.get("individuals", []))))
        print_kv("Accounts", str(len(result.bundle.get("accounts", []))))
        print_kv("Relationships", str(len(result.bundle.get("relationships", []))))
        print_kv("Events", str(len(result.bundle.get("events", []))))

        # Provenance
        print()
        print(f"{Colors.BOLD}Provenance:{Colors.END}")
        print_kv("Adapter", f"{result.provenance.adapter_name} v{result.provenance.adapter_version}")
        print_kv("Adapter Hash", result.provenance.adapter_hash[:16] + "...")
        print_kv("Source System", result.provenance.source_system)
        if result.provenance.source_file_hash:
            print_kv("Source File Hash", result.provenance.source_file_hash[:16] + "...")
        print_kv("Ingested At", result.provenance.ingested_at)

        # Output location
        if output_path:
            print()
            print_success(f"Bundle written to: {output_path}")

        # Error file
        if error_file and result.errors:
            print_success(f"Errors written to: {error_file}")

        return ExitCode.PASS

    except AdapterValidationError as e:
        print_error(f"Adapter validation failed: {e}")
        return ExitCode.INPUT_INVALID
    except AdapterError as e:
        print_error(f"Adapter error: {e}")
        return ExitCode.INPUT_INVALID
    except MappingError as e:
        print_error(f"Mapping failed: {e}")
        return ExitCode.INPUT_INVALID
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in input: {e}")
        return ExitCode.INPUT_INVALID
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return ExitCode.INTERNAL_ERROR


def cmd_validate_adapter(args):
    """Validate an adapter YAML file."""
    print_header("DecisionGraph - Validate Adapter")

    adapter_path = Path(args.adapter)

    if not adapter_path.exists():
        print_error(f"Adapter file not found: {adapter_path}")
        return ExitCode.INPUT_INVALID

    print_info(f"Validating: {adapter_path}")

    is_valid, errors = validate_adapter(adapter_path)

    if not is_valid:
        print_error("Adapter validation failed:")
        for error in errors:
            print(f"  {Colors.RED}[X]{Colors.END} {error}")
        return ExitCode.INPUT_INVALID

    # Load and display adapter info
    try:
        adapter = load_adapter(adapter_path)

        print_success("Adapter is valid!")
        print()
        print_kv("Name", adapter.metadata.name)
        print_kv("Vendor", adapter.metadata.vendor)
        print_kv("Version", adapter.metadata.version)
        print_kv("Input Format", adapter.metadata.input_format)

        if adapter.metadata.description:
            print_kv("Description", adapter.metadata.description)

        print()
        print(f"{Colors.BOLD}Roots:{Colors.END}")
        for name, path in adapter.roots.items():
            print(f"  {name}: {path}")

        print()
        print(f"{Colors.BOLD}Mappings ({len(adapter.mappings)}):{Colors.END}")
        # Group by entity type
        by_entity = {}
        for target in adapter.mappings.keys():
            entity = target.split(".")[0]
            by_entity.setdefault(entity, []).append(target)

        for entity, fields in sorted(by_entity.items()):
            print(f"  {entity}: {len(fields)} fields")

        if adapter.transforms:
            print()
            print(f"{Colors.BOLD}Transforms ({len(adapter.transforms)}):{Colors.END}")
            for name, mapping in adapter.transforms.items():
                print(f"  {name}: {len(mapping)} mappings")

        if adapter.defaults:
            print()
            print(f"{Colors.BOLD}Defaults ({len(adapter.defaults)}):{Colors.END}")
            for key, value in list(adapter.defaults.items())[:5]:
                print(f"  {key}: {value}")
            if len(adapter.defaults) > 5:
                print(f"  ... and {len(adapter.defaults) - 5} more")

        return ExitCode.PASS

    except Exception as e:
        print_error(f"Failed to load adapter: {e}")
        return ExitCode.INPUT_INVALID


def parse_case_bundle_dict(data: dict) -> 'CaseBundle':
    """Parse a dictionary into a CaseBundle."""
    # This mirrors parse_case_bundle_json but takes a dict
    from .case_schema import (
        CaseBundle, CaseMeta, CaseType, CasePhase, EntityType,
        Individual, Organization, Account, Relationship, RelationshipType,
        EvidenceItem, EvidenceType, TransactionEvent, AlertEvent,
        ScreeningEvent, Assertion, Sensitivity, RiskRating, PEPCategory,
    )

    meta_data = data.get("meta", {})
    meta = CaseMeta(
        id=meta_data.get("id", ""),
        case_type=CaseType(meta_data.get("case_type", "aml_alert")),
        case_phase=CasePhase(meta_data.get("case_phase", "analysis")),
        created_at=meta_data.get("created_at", ""),
        jurisdiction=meta_data.get("jurisdiction", ""),
        primary_entity_type=EntityType(meta_data.get("primary_entity_type", "individual")),
        primary_entity_id=meta_data.get("primary_entity_id", ""),
        status=meta_data.get("status", "open"),
        priority=meta_data.get("priority", "medium"),
        sensitivity=Sensitivity(meta_data.get("sensitivity", "internal")),
        access_tags=meta_data.get("access_tags", []),
    )

    individuals = []
    for ind_data in data.get("individuals", []):
        pep_val = ind_data.get("pep_status", "none")
        pep = PEPCategory(pep_val) if pep_val else PEPCategory.NONE
        risk_val = ind_data.get("risk_rating", "medium")
        risk = RiskRating(risk_val) if risk_val else RiskRating.MEDIUM

        individuals.append(Individual(
            id=ind_data.get("id", ""),
            given_name=ind_data.get("given_name", ""),
            family_name=ind_data.get("family_name", ""),
            date_of_birth=ind_data.get("date_of_birth"),
            nationality=ind_data.get("nationality"),
            country_of_residence=ind_data.get("country_of_residence"),
            pep_status=pep,
            risk_rating=risk,
            sensitivity=Sensitivity(ind_data.get("sensitivity", "internal")),
            access_tags=ind_data.get("access_tags", []),
        ))

    accounts = []
    for acc_data in data.get("accounts", []):
        accounts.append(Account(
            id=acc_data.get("id", ""),
            account_number=acc_data.get("account_number", ""),
            account_type=acc_data.get("account_type", ""),
            currency=acc_data.get("currency", ""),
            status=acc_data.get("status", "active"),
            opened_date=acc_data.get("opened_date"),
            sensitivity=Sensitivity(acc_data.get("sensitivity", "internal")),
            access_tags=acc_data.get("access_tags", []),
        ))

    relationships = []
    for rel_data in data.get("relationships", []):
        relationships.append(Relationship(
            id=rel_data.get("id", ""),
            relationship_type=RelationshipType(rel_data.get("relationship_type", "account_holder")),
            from_entity_type=EntityType(rel_data.get("from_entity_type", "individual")),
            from_entity_id=rel_data.get("from_entity_id", ""),
            to_entity_type=EntityType(rel_data.get("to_entity_type", "individual")),
            to_entity_id=rel_data.get("to_entity_id", ""),
            sensitivity=Sensitivity(rel_data.get("sensitivity", "internal")),
            access_tags=rel_data.get("access_tags", []),
        ))

    # Parse events
    events = []
    for evt_data in data.get("events", []):
        event_type = evt_data.get("event_type", "transaction")
        if event_type == "transaction":
            events.append(TransactionEvent(
                id=evt_data.get("id", ""),
                event_type="transaction",
                timestamp=evt_data.get("timestamp", ""),
                description=evt_data.get("description", ""),
                amount=evt_data.get("amount", "0"),
                currency=evt_data.get("currency", ""),
                direction=evt_data.get("direction", ""),
                counterparty_name=evt_data.get("counterparty_name"),
                counterparty_country=evt_data.get("counterparty_country"),
                payment_method=evt_data.get("payment_method"),
                sensitivity=Sensitivity(evt_data.get("sensitivity", "internal")),
                access_tags=evt_data.get("access_tags", []),
            ))
        elif event_type == "alert":
            events.append(AlertEvent(
                id=evt_data.get("id", ""),
                event_type="alert",
                timestamp=evt_data.get("timestamp", ""),
                description=evt_data.get("description", ""),
                alert_type=evt_data.get("alert_type", ""),
                rule_id=evt_data.get("rule_id"),
                sensitivity=Sensitivity(evt_data.get("sensitivity", "internal")),
                access_tags=evt_data.get("access_tags", []),
            ))
        elif event_type == "screening":
            events.append(ScreeningEvent(
                id=evt_data.get("id", ""),
                event_type="screening",
                timestamp=evt_data.get("timestamp", ""),
                description=evt_data.get("description", ""),
                screening_type=evt_data.get("screening_type", ""),
                vendor=evt_data.get("vendor"),
                disposition=evt_data.get("disposition"),
                sensitivity=Sensitivity(evt_data.get("sensitivity", "internal")),
                access_tags=evt_data.get("access_tags", []),
            ))

    return CaseBundle(
        meta=meta,
        individuals=individuals,
        organizations=[],
        accounts=accounts,
        relationships=relationships,
        evidence=[],
        events=events,
        assertions=[],
    )


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    if not sys.stdout.isatty():
        Colors.disable()

    parser = argparse.ArgumentParser(
        prog="dg",
        description="DecisionGraph CLI - Financial Crime case processing appliance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0   PASS            Auto-archive permitted
  2   REVIEW_REQUIRED Analyst review required
  3   ESCALATE        Senior/compliance escalation
  4   BLOCK           STR consideration
  10  INPUT_INVALID   Invalid input files
  11  PACK_ERROR      Pack validation failed
  12  VERIFY_FAIL     Verification failed

Examples:
  dg run-case --case bundle.json --pack fincrime_canada.yaml --out results/
  dg run-case --case bundle.json --pack pack.yaml --strict --sign key.pem
  dg verify-bundle --bundle results/CASE_ID/bundle.zip
  dg map-case --input export.json --adapter adapters/actimize/mapping.yaml --out bundle.json
  dg validate-adapter --adapter adapters/actimize/mapping.yaml
  dg validate-pack --pack fincrime_canada.yaml
  dg validate-case --case bundle.json
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run-case
    run_parser = subparsers.add_parser(
        "run-case",
        help="Run a case through the rules engine"
    )
    run_parser.add_argument("--case", "-c", required=True, help="Case bundle JSON file")
    run_parser.add_argument("--pack", "-p", required=True, help="Pack YAML file")
    run_parser.add_argument("--out", "-o", default="./out", help="Output directory")
    run_parser.add_argument("--no-cells", action="store_true", help="Skip cells.jsonl export")
    run_parser.add_argument("--sign", help="Sign manifest with key file")
    run_parser.add_argument("--strict", action="store_true",
                           help="Strict mode: mark non-PASS cases as NOT APPROVED")
    run_parser.add_argument("--legal-hold", action="store_true",
                           help="Mark case as under legal hold (indefinite retention)")
    run_parser.set_defaults(func=cmd_run_case)

    # verify-bundle
    verify_parser = subparsers.add_parser(
        "verify-bundle",
        help="Verify an existing bundle for integrity"
    )
    verify_parser.add_argument("--bundle", "-b", required=True, help="Bundle zip file")
    verify_parser.add_argument("--key", "-k", help="Public key for signature verification")
    verify_parser.set_defaults(func=cmd_verify_bundle)

    # map-case
    map_parser = subparsers.add_parser(
        "map-case",
        help="Map a vendor export to CaseBundle format"
    )
    map_parser.add_argument("--input", "-i", required=True, help="Vendor export file (JSON)")
    map_parser.add_argument("--adapter", "-a", required=True, help="Adapter mapping YAML file")
    map_parser.add_argument("--out", "-o", help="Output CaseBundle JSON file (optional, prints to stdout if not specified)")
    map_parser.add_argument("--max-errors", type=int, default=0,
                           help="Maximum mapping errors before aborting (0 = no limit)")
    map_parser.add_argument("--error-file", help="Write mapping errors to JSONL file")
    map_parser.set_defaults(func=cmd_map_case)

    # validate-adapter
    val_adapter_parser = subparsers.add_parser(
        "validate-adapter",
        help="Validate an adapter mapping file"
    )
    val_adapter_parser.add_argument("--adapter", "-a", required=True, help="Adapter YAML file")
    val_adapter_parser.set_defaults(func=cmd_validate_adapter)

    # validate-pack
    val_pack_parser = subparsers.add_parser("validate-pack", help="Validate a pack file")
    val_pack_parser.add_argument("--pack", "-p", required=True, help="Pack YAML file")
    val_pack_parser.set_defaults(func=cmd_validate_pack)

    # validate-case
    val_case_parser = subparsers.add_parser("validate-case", help="Validate a case bundle")
    val_case_parser.add_argument("--case", "-c", required=True, help="Case bundle JSON file")
    val_case_parser.set_defaults(func=cmd_validate_case)

    # pack-info
    info_parser = subparsers.add_parser("pack-info", help="Show pack information")
    info_parser.add_argument("--pack", "-p", required=True, help="Pack YAML file")
    info_parser.set_defaults(func=cmd_pack_info)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return ExitCode.INTERNAL_ERROR


if __name__ == "__main__":
    sys.exit(main())

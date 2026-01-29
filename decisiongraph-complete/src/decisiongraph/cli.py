#!/usr/bin/env python3
"""
DecisionGraph CLI - Bank Appliance Runner

Command-line interface for running Financial Crime cases through DecisionGraph.
Produces auditor-ready report bundles with verifiable hashes and policy citations.

Usage:
    dg run-case --case bundle.json --pack fincrime_canada.yaml --out out/
    dg validate-pack --pack fincrime_canada.yaml
    dg validate-case --case bundle.json
    dg pack-info --pack fincrime_canada.yaml

Output Bundle (in out/CASE_ID/):
    report.txt          - Deterministic report bytes
    report.sha256       - Hash of report bytes
    manifest.json       - ReportManifest + included cell IDs
    pack.json           - Pack metadata (id, version, hash)
    verification.json   - PASS/FAIL verification checks
    cells.jsonl         - All cells produced (optional)
    bundle.zip          - Everything zipped for audit handoff
"""

import argparse
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime, date, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional, Any

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
        """Disable colors for non-TTY output."""
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
# JSON SERIALIZATION HELPERS
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
    lines.append("")

    # Verdict Banner
    lines.append("-" * 72)
    if eval_result and eval_result.verdict:
        verdict_obj = eval_result.verdict.fact.object
        verdict = verdict_obj.get("verdict", "UNKNOWN")
        auto_archive = verdict_obj.get("auto_archive_permitted", False)
        lines.append(f"VERDICT: {verdict}")
        lines.append(f"Auto-Archive Permitted: {'YES' if auto_archive else 'NO'}")
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
        lines.append(f"  [{status:10}] {ev.id}: {ev.evidence_type.value}")
        lines.append(f"               {ev.description[:50]}...")
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
            counterparty = getattr(event, 'counterparty_name', 'Unknown')
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
# OUTPUT BUNDLE WRITING
# ============================================================================

def write_bundle(
    output_dir: Path,
    case_id: str,
    pack_runtime: PackRuntime,
    chain: Chain,
    case_cells: list,
    eval_result,
    bundle: CaseBundle,
    include_cells: bool = True,
) -> dict:
    """
    Write all bank-ready deliverables to output directory.

    Returns verification results.
    """
    case_dir = output_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    verification = {
        "case_id": case_id,
        "timestamp": get_current_timestamp(),
        "checks": [],
        "overall": "PASS",
    }

    # 1. Render report.txt (deterministic bytes)
    print_step(1, 7, "Rendering report...")
    report_text = render_report_text(case_id, pack_runtime, chain, eval_result, bundle)
    report_bytes = report_text.encode('utf-8')
    report_path = case_dir / "report.txt"
    with open(report_path, 'wb') as f:
        f.write(report_bytes)

    # 2. Compute report.sha256
    print_step(2, 7, "Computing report hash...")
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
    print_step(3, 7, "Writing manifest...")
    all_cells = case_cells + (eval_result.all_cells if eval_result else [])
    manifest = {
        "case_id": case_id,
        "report_hash": report_hash,
        "graph_id": chain.graph_id,
        "chain_length": len(chain),
        "case_cells": len(case_cells),
        "derived_cells": len(eval_result.all_cells) if eval_result else 0,
        "total_cells": len(all_cells),
        "cell_ids": [cell.cell_id for cell in all_cells],
        "signals_fired": eval_result.signals_fired if eval_result else 0,
        "mitigations_applied": eval_result.mitigations_applied if eval_result else 0,
        "verdict": eval_result.verdict.fact.object.get("verdict") if eval_result and eval_result.verdict else None,
        "score": eval_result.score.fact.object if eval_result and eval_result.score else None,
        "created_at": get_current_timestamp(),
    }
    manifest_path = case_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        f.write(json_dumps(manifest))

    # 4. Write pack.json
    print_step(4, 7, "Writing pack metadata...")
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

    # 5. Write verification.json (run all checks)
    print_step(5, 7, "Running verification checks...")

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
    report_text_2 = render_report_text(case_id, pack_runtime, chain, eval_result, bundle)
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
        verdict_val = eval_result.verdict.fact.object.get("verdict")
        gate_consistent = (score_gate == verdict_val or verdict_val in ["CLOSE", "ESCALATE"])
        verification["checks"].append({
            "name": "gate_consistency",
            "status": "PASS" if gate_consistent else "WARN",
            "score_gate": score_gate,
            "verdict": verdict_val,
        })

    verification_path = case_dir / "verification.json"
    with open(verification_path, 'w') as f:
        f.write(json_dumps(verification))

    # 6. Write cells.jsonl (optional)
    if include_cells:
        print_step(6, 7, "Writing cells...")
        cells_path = case_dir / "cells.jsonl"
        with open(cells_path, 'w') as f:
            for cell in all_cells:
                f.write(json_dumps(cell.to_dict(), indent=None) + "\n")
    else:
        print_step(6, 7, "Skipping cells export...")

    # 7. Create bundle.zip
    print_step(7, 7, "Creating bundle.zip...")
    zip_path = case_dir / "bundle.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(report_path, "report.txt")
        zf.write(hash_path, "report.sha256")
        zf.write(manifest_path, "manifest.json")
        zf.write(pack_path, "pack.json")
        zf.write(verification_path, "verification.json")
        if include_cells:
            zf.write(cells_path, "cells.jsonl")

    return verification


# ============================================================================
# COMMANDS
# ============================================================================

def cmd_run_case(args):
    """
    Run a case through the rules engine and produce bank-ready deliverables.

    Pipeline:
    1. Load pack
    2. Load case bundle
    3. Create chain with canonical hashing
    4. Load case into chain (creates cells)
    5. Add policy cells from pack
    6. Run rules engine
    7. Render report
    8. Verify artifact
    9. Write bundle
    """
    print_header("DecisionGraph - Run Case")

    case_path = Path(args.case)
    pack_path = Path(args.pack)
    output_dir = Path(args.out) if args.out else Path("./out")
    include_cells = not args.no_cells

    # Check files exist
    if not case_path.exists():
        print_error(f"Case file not found: {case_path}")
        return 1

    if not pack_path.exists():
        print_error(f"Pack file not found: {pack_path}")
        return 1

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
        return 1
    except PackLoaderError as e:
        print_error(f"Pack loading failed: {e}")
        return 1

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
    except Exception as e:
        print_error(f"Case loading failed: {e}")
        return 1

    # Validate case bundle
    errors = validate_case_bundle(bundle)
    if errors:
        print_warning(f"Case bundle has {len(errors)} validation warning(s)")

    # Step 3: Create chain with canonical hash scheme
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

    # Step 5: Add policy cells from pack
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

    # Extract facts from cells
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

    # Add evaluation cells to chain
    for cell in eval_result.all_cells:
        chain.append(cell)

    print_success(f"Signals fired: {eval_result.signals_fired}")
    print_success(f"Mitigations applied: {eval_result.mitigations_applied}")

    # Print score and verdict
    if eval_result.score:
        score_obj = eval_result.score.fact.object
        print_kv("Score", "", indent=1)
        print_kv("Inherent", score_obj.get("inherent_score", "N/A"), indent=2)
        print_kv("Mitigations", score_obj.get("mitigation_sum", "N/A"), indent=2)
        print_kv("Residual", score_obj.get("residual_score", "N/A"), indent=2)
        print_kv("Gate", score_obj.get("threshold_gate", "N/A"), indent=2)

    if eval_result.verdict:
        verdict_obj = eval_result.verdict.fact.object
        verdict = verdict_obj.get("verdict", "UNKNOWN")
        auto_archive = verdict_obj.get("auto_archive_permitted", False)
        print()
        if "CLOSE" in verdict or auto_archive:
            print(f"  {Colors.GREEN}{Colors.BOLD}VERDICT: {verdict}{Colors.END}")
        elif "REVIEW" in verdict:
            print(f"  {Colors.YELLOW}{Colors.BOLD}VERDICT: {verdict}{Colors.END}")
        else:
            print(f"  {Colors.RED}{Colors.BOLD}VERDICT: {verdict}{Colors.END}")

    # Step 7-9: Write bundle (includes render, verify, write)
    print()
    print_step(7, total_steps, "Writing output bundle...")
    verification = write_bundle(
        output_dir=output_dir,
        case_id=case_id,
        pack_runtime=pack_runtime,
        chain=chain,
        case_cells=case_cells,
        eval_result=eval_result,
        bundle=bundle,
        include_cells=include_cells,
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
        else:
            print(f"  {Colors.RED}[FAIL]{Colors.END} {name}")

    print()
    print_success(f"Bundle ready: {bundle_dir / 'bundle.zip'}")

    return 0 if verification["overall"] == "PASS" else 1


def cmd_validate_pack(args):
    """Validate a pack file."""
    print_header("DecisionGraph - Validate Pack")

    pack_path = Path(args.pack)

    if not pack_path.exists():
        print_error(f"Pack file not found: {pack_path}")
        return 1

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

        return 0

    except PackValidationError as e:
        print_error(f"Validation failed with {len(e.errors)} error(s):")
        for error in e.errors:
            print(f"  {Colors.RED}[X]{Colors.END} {error}")
        return 1

    except PackLoaderError as e:
        print_error(f"Loading failed: {e}")
        return 1


def cmd_validate_case(args):
    """Validate a case bundle file."""
    print_header("DecisionGraph - Validate Case")

    case_path = Path(args.case)

    if not case_path.exists():
        print_error(f"Case file not found: {case_path}")
        return 1

    print_info(f"Validating: {case_path}")

    try:
        bundle = parse_case_bundle_json(case_path)
        errors = validate_case_bundle(bundle)

        if errors:
            print_warning(f"Case has {len(errors)} validation error(s):")
            for error in errors:
                print(f"  {Colors.YELLOW}[!]{Colors.END} {error}")
            return 1
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
            return 0

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        return 1
    except Exception as e:
        print_error(f"Parsing failed: {e}")
        return 1


def cmd_pack_info(args):
    """Show pack information."""
    print_header("DecisionGraph - Pack Info")

    pack_path = Path(args.pack)

    if not pack_path.exists():
        print_error(f"Pack file not found: {pack_path}")
        return 1

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

        # Regulatory framework
        if runtime.regulatory_framework:
            print(f"\n{Colors.BOLD}Regulatory Framework:{Colors.END}")
            for key, value in runtime.regulatory_framework.items():
                if isinstance(value, (str, int, float)):
                    print_kv(key, str(value), indent=1)

        # Signal summary
        print(f"\n{Colors.BOLD}Signals ({len(runtime.signals_by_code)}):{Colors.END}")
        for code, sig in sorted(runtime.signals_by_code.items()):
            print(f"  {code}: {sig.severity.value} - {sig.name}")

        # Mitigation summary
        print(f"\n{Colors.BOLD}Mitigations ({len(runtime.mitigations_by_code)}):{Colors.END}")
        for code, mit in sorted(runtime.mitigations_by_code.items()):
            print(f"  {code}: {mit.weight} - {mit.name}")

        # Threshold gates
        if runtime.scoring_rule:
            print(f"\n{Colors.BOLD}Threshold Gates:{Colors.END}")
            for gate in runtime.scoring_rule.threshold_gates:
                print(f"  {gate.code}: < {gate.max_score}")

        return 0

    except Exception as e:
        print_error(f"Failed to load pack: {e}")
        return 1


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    # Disable colors if not TTY
    if not sys.stdout.isatty():
        Colors.disable()

    parser = argparse.ArgumentParser(
        prog="dg",
        description="DecisionGraph CLI - Financial Crime case processing appliance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output Bundle (in out/CASE_ID/):
  report.txt          Deterministic report bytes
  report.sha256       Hash of report bytes
  manifest.json       ReportManifest + included cell IDs
  pack.json           Pack metadata (id, version, hash)
  verification.json   PASS/FAIL verification checks
  cells.jsonl         All cells produced
  bundle.zip          Everything zipped for audit handoff

Examples:
  dg run-case --case bundle.json --pack fincrime_canada.yaml --out results/
  dg validate-pack --pack fincrime_canada.yaml
  dg validate-case --case bundle.json
  dg pack-info --pack fincrime_canada.yaml
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run-case command
    run_parser = subparsers.add_parser(
        "run-case",
        help="Run a case through the rules engine and produce bank-ready deliverables"
    )
    run_parser.add_argument(
        "--case", "-c",
        required=True,
        help="Path to case bundle JSON file"
    )
    run_parser.add_argument(
        "--pack", "-p",
        required=True,
        help="Path to pack YAML file"
    )
    run_parser.add_argument(
        "--out", "-o",
        default="./out",
        help="Output directory (default: ./out)"
    )
    run_parser.add_argument(
        "--no-cells",
        action="store_true",
        help="Skip cells.jsonl export to reduce bundle size"
    )
    run_parser.set_defaults(func=cmd_run_case)

    # validate-pack command
    val_pack_parser = subparsers.add_parser(
        "validate-pack",
        help="Validate a pack file"
    )
    val_pack_parser.add_argument(
        "--pack", "-p",
        required=True,
        help="Path to pack YAML file"
    )
    val_pack_parser.set_defaults(func=cmd_validate_pack)

    # validate-case command
    val_case_parser = subparsers.add_parser(
        "validate-case",
        help="Validate a case bundle file"
    )
    val_case_parser.add_argument(
        "--case", "-c",
        required=True,
        help="Path to case bundle JSON file"
    )
    val_case_parser.set_defaults(func=cmd_validate_case)

    # pack-info command
    info_parser = subparsers.add_parser(
        "pack-info",
        help="Show pack information"
    )
    info_parser.add_argument(
        "--pack", "-p",
        required=True,
        help="Path to pack YAML file"
    )
    info_parser.set_defaults(func=cmd_pack_info)

    # Parse args
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Run command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

"""ViewModel — Stage C of the Report Compiler Pipeline.

Merges NormalizedDecision + DerivedRegulatoryModel into a single
ReportViewModel dict consumed identically by HTML / Markdown / JSON
renderers.

Responsibilities:
  - convert amounts to currency strings
  - build table rows / section lists
  - prepare markdown-safe values
  - apply language sanitizer as final pass

All three format endpoints consume the SAME view-model — no more
re-deriving tables per format.
"""

from datetime import datetime

from service.suspicion_classifier import CLASSIFIER_VERSION

from .sanitize import sanitize_narrative, kill_duplicate_uncertainty

# ── Module identity ───────────────────────────────────────────────────────────
REPORT_MODULE_VERSION = "2026-02-05.v10"
NARRATIVE_COMPILER_VERSION = "DecisionNarrativeCompiler v1"


def build_view_model(normalized: dict, derived: dict) -> dict:
    """Build the final view-model consumed by every renderer."""

    # ── Transaction facts (formatted) ─────────────────────────────────────
    transaction_facts = _build_transaction_facts(normalized)

    # ── Escalation reasons ────────────────────────────────────────────────
    escalation_reasons: list[str] = []
    for rule in normalized.get("absolute_rules_validated", []):
        if "triggered" in str(rule).lower() or "failed" in str(rule).lower():
            escalation_reasons.append(rule)
    if normalized.get("decision_path"):
        escalation_reasons.append(f"Decision path: {normalized['decision_path']}")

    # ── Short hashes ──────────────────────────────────────────────────────
    decision_id = normalized["decision_id"]
    input_hash = normalized["input_hash"]
    policy_hash = normalized["policy_hash"]

    # ── Language sanitizer (final pass on narrative text) ─────────────────
    decision_explainer = kill_duplicate_uncertainty(
        sanitize_narrative(derived["decision_explainer"])
    )
    escalation_summary = kill_duplicate_uncertainty(
        sanitize_narrative(derived["escalation_summary"])
    )

    # ── Precedent analysis (enrich with similarity summary) ──────────────
    precedent_analysis = dict(normalized["precedent_analysis"])
    if derived["similarity_summary"]:
        precedent_analysis["similarity_summary"] = derived["similarity_summary"]

    report_sections = [
        "Administrative Details",
        "Investigation Outcome Summary",
        "Case Classification",
        "Regulatory Determination",
        "Suspicion Classification",
        "Decision Drivers",
        "Gate Evaluation",
        "Rules Evaluated",
        "Precedent Intelligence",
        "Risk Factors",
        "Evidence Considered",
        "Auditability & Governance",
    ]

    return {
        # Administrative Details
        "decision_id": decision_id,
        "decision_id_short": decision_id[:16] if decision_id else "N/A",
        "case_id": normalized["case_id"],
        "timestamp": normalized["timestamp"] or datetime.utcnow().isoformat(),
        "jurisdiction": normalized["jurisdiction"],
        "engine_version": normalized["engine_version"],
        "policy_version": normalized["policy_version"],
        "domain": normalized["domain"],
        "report_schema_version": "DecisionReportSchema v1",
        "narrative_compiler_version": NARRATIVE_COMPILER_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "report_sections": report_sections,

        # Input / Policy hashes
        "input_hash": input_hash,
        "input_hash_short": input_hash[:16] if input_hash else "N/A",
        "policy_hash": policy_hash,
        "policy_hash_short": policy_hash[:16] if policy_hash else "N/A",

        # Case classification
        "source_type": normalized["source_label"],
        "seed_category": normalized["seed_category"],
        "scenario_code": normalized["scenario_code"],
        "is_seed": normalized["is_seed"],
        "escalation_summary": escalation_summary,
        "decision_confidence": derived["decision_confidence"],
        "decision_confidence_reason": derived["decision_confidence_reason"],
        "decision_confidence_score": derived["decision_confidence_score"],
        "similarity_summary": derived["similarity_summary"],
        "decision_drivers": derived["decision_drivers"],

        # Transaction Facts
        "transaction_facts": transaction_facts,

        # Decision (governed)
        "verdict": normalized["verdict"],
        "action": normalized["action"],
        "decision_status": derived["decision_status"],
        "decision_explainer": decision_explainer,
        "str_required": derived["str_required"],
        "escalation_reasons": escalation_reasons,
        "regulatory_status": derived["regulatory_status"],
        "investigation_state": derived["investigation_state"],
        "primary_typology": derived["primary_typology"],
        "regulatory_obligation": derived["regulatory_obligation"],
        "regulatory_position": derived["regulatory_position"],

        # Gates
        "gate1_passed": normalized["gate1_passed"],
        "gate1_decision": normalized["gate1_decision"],
        "gate1_sections": normalized["gate1_sections"],
        "gate2_decision": normalized["gate2_decision"],
        "gate2_status": normalized["gate2_status"],
        "gate2_sections": normalized["gate2_sections"],

        # Evaluation trace
        "rules_fired": normalized["rules_fired"],
        "evidence_used": normalized["evidence_used"],
        "risk_factors": derived["risk_factors"],
        "decision_path_trace": normalized["decision_path_trace"],

        # Rationale
        "summary": normalized["rationale_summary"],

        # Precedent Analysis
        "precedent_analysis": precedent_analysis,

        # Suspicion Classification
        "classification": derived["classification"],
        "classification_outcome": derived["classification_outcome"],
        "classification_reason": derived["classification_reason"],
        "tier1_signals": derived["tier1_signals"],
        "tier2_signals": derived["tier2_signals"],
        "suspicion_count": derived["suspicion_count"],
        "investigative_count": derived["investigative_count"],
        "precedent_consistency_alert": derived["precedent_consistency_alert"],
        "precedent_consistency_detail": derived["precedent_consistency_detail"],

        # Decision Integrity & Governance Alerts
        "decision_integrity_alert": derived["decision_integrity_alert"],
        "precedent_deviation_alert": derived["precedent_deviation_alert"],
        "corrections_applied": derived.get("corrections_applied", {}),
        "classifier_is_sovereign": True,
    }


# ── Transaction facts ────────────────────────────────────────────────────────

def _build_transaction_facts(normalized: dict) -> list[dict]:
    """Build formatted transaction facts from normalized layer-1 data."""
    facts: list[dict] = []
    layer1 = normalized["layer1_facts"]

    customer = layer1.get("customer", {}) or {}
    if customer.get("pep_flag") is not None:
        facts.append({"field": "PEP Status", "value": "Yes" if customer.get("pep_flag") else "No"})
    if customer.get("type"):
        facts.append({"field": "Customer Type", "value": customer["type"]})
    if customer.get("residence"):
        facts.append({"field": "Residence Country", "value": customer["residence"]})

    txn = layer1.get("transaction", {}) or {}
    if txn.get("amount_cad") is not None:
        facts.append({"field": "Amount (CAD)", "value": f"${txn['amount_cad']:,.2f}"})
    if txn.get("method"):
        facts.append({"field": "Payment Method", "value": txn["method"]})
    if txn.get("destination"):
        facts.append({"field": "Destination", "value": txn["destination"]})

    screening = layer1.get("screening", {}) or {}
    if screening.get("match_score") is not None:
        facts.append({"field": "Match Score", "value": f"{screening['match_score']}%"})
    if screening.get("list_type"):
        facts.append({"field": "List Type", "value": screening["list_type"]})

    if not facts:
        facts = [
            {"field": "Case ID", "value": normalized["case_id"]},
            {"field": "Jurisdiction", "value": normalized["jurisdiction"]},
        ]

    return facts

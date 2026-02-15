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
        "Decision Path",
        "Canonical Outcome",
        "Case Classification",
        "Regulatory Determination",
        "Suspicion Classification",
        "Decision Drivers",
        "Gate Evaluation",
        "Rules Evaluated",
        "Precedent Intelligence",
        "Defensibility Check",
        "Risk Factors",
        "Evidence Considered",
        "Recommended Actions",
        "Timeline",
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
        # FIX-022: display_verdict reflects corrections; engine_verdict for audit
        "verdict": derived.get("display_verdict") or normalized["verdict"],
        "engine_verdict": normalized["verdict"],
        "action": normalized["action"],
        "decision_status": derived["decision_status"],
        "decision_explainer": decision_explainer,
        "str_required": derived["str_required"],
        "escalation_reasons": escalation_reasons,
        "regulatory_status": derived["regulatory_status"],
        "investigation_state": derived["investigation_state"],
        "primary_typology": derived["primary_typology"],
        "typology_stage": derived.get("typology_stage", "NONE"),
        "regulatory_obligation": derived["regulatory_obligation"],
        "regulatory_position": derived["regulatory_position"],

        # Engine vs Governed dispositions (audit + deviation clarity)
        "engine_disposition": derived.get("engine_disposition", ""),
        "governed_disposition": derived.get("governed_disposition", ""),

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
        # FIX-022: governed_rationale replaces canned engine rationale after corrections
        "summary": derived.get("governed_rationale") or normalized["rationale_summary"],
        "engine_rationale": normalized["rationale_summary"],

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
        "override_justification": derived.get("override_justification"),
        "precedent_deviation_alert": derived["precedent_deviation_alert"],
        "corrections_applied": derived.get("corrections_applied", {}),
        "classifier_is_sovereign": True,

        # FIX-001: Canonical outcome
        "canonical_outcome": derived.get("canonical_outcome", {}),

        # FIX-005: Distinct precedent metrics
        "precedent_alignment_pct": derived.get("precedent_alignment_pct", 0),
        "precedent_match_rate": derived.get("precedent_match_rate", 0),
        "scored_precedent_count": derived.get("scored_precedent_count", 0),
        "total_comparable_pool": derived.get("total_comparable_pool", 0),

        # FIX-019: Precedent pool threshold warning
        "precedent_pool_warning": derived.get("precedent_pool_warning"),

        # FIX-006: Defensibility check
        "defensibility_check": derived.get("defensibility_check", {}),

        # FIX-018: Enhanced precedent analysis
        "enhanced_precedent": derived.get("enhanced_precedent", {}),

        # FIX-007: EDD recommendations
        "edd_recommendations": derived.get("edd_recommendations", []),

        # FIX-009: SLA timeline
        "sla_timeline": derived.get("sla_timeline", {}),

        # FIX-015: Analyst actions (outcome-aware)
        "analyst_actions": derived.get("analyst_actions", []),

        # FIX-028 through FIX-035: Narrative coherence
        "gate_override_explanations": derived.get("gate_override_explanations", []),
        "disposition_reconciliation": derived.get("disposition_reconciliation", {}),
        "precedent_divergence": derived.get("precedent_divergence"),
        "unmapped_indicator_checks": derived.get("unmapped_indicator_checks", []),
        "policy_regime_exception": derived.get("policy_regime_exception"),
        "risk_heatmap_context": derived.get("risk_heatmap_context"),
        "required_actions": derived.get("required_actions", []),
        "related_activity": derived.get("related_activity", {}),

        # Decision Conflict Alert
        "decision_conflict_alert": derived.get("decision_conflict_alert"),

        # Decision Path Narrative Trace
        "decision_path_narrative": derived.get("decision_path_narrative", {}),

        # Mandatory hard stop (sanctions, etc.)
        "is_mandatory_hard_stop": derived.get("is_mandatory_hard_stop", False),
        "hard_stop_reason": derived.get("hard_stop_reason", ""),

        # GAP-E: Senior Summary
        "senior_summary": derived.get("senior_summary", {}),

        # GAP-B: STR Decision Authority
        "str_decision_frame": derived.get("str_decision_frame", {}),

        # GAP-C: Case Facts Sections (structured)
        "case_facts_sections": _build_case_facts_sections(normalized),
    }


# ── Transaction facts ────────────────────────────────────────────────────────

def _build_transaction_facts(normalized: dict) -> list[dict]:
    """Build formatted transaction facts from normalized layer-1 data.

    Expanded for GAP-C: pulls additional fields from layer1_facts and
    evidence_used while keeping backward-compatible flat list format.
    """
    facts: list[dict] = []
    layer1 = normalized["layer1_facts"]
    evidence_used = normalized.get("evidence_used", []) or []
    ev_map = {str(ev.get("field", "")): ev.get("value") for ev in evidence_used}

    customer = layer1.get("customer", {}) or {}
    if customer.get("pep_flag") is not None:
        facts.append({"field": "PEP Status", "value": "Yes" if customer.get("pep_flag") else "No"})
    if customer.get("type"):
        facts.append({"field": "Customer Type", "value": customer["type"]})
    if customer.get("residence"):
        facts.append({"field": "Residence Country", "value": customer["residence"]})
    if customer.get("tenure_years") is not None:
        facts.append({"field": "Customer Tenure", "value": f"{customer['tenure_years']} years"})
    if customer.get("risk_rating"):
        facts.append({"field": "Customer Risk Rating", "value": customer["risk_rating"]})

    txn = layer1.get("transaction", {}) or {}
    if txn.get("amount_cad") is not None:
        facts.append({"field": "Amount (CAD)", "value": f"${txn['amount_cad']:,.2f}"})
    if txn.get("method"):
        facts.append({"field": "Payment Method", "value": txn["method"]})
    if txn.get("channel"):
        facts.append({"field": "Channel", "value": txn["channel"]})
    if txn.get("destination"):
        facts.append({"field": "Destination", "value": txn["destination"]})
    if txn.get("cross_border") is not None:
        facts.append({"field": "Cross-Border", "value": "Yes" if txn["cross_border"] else "No"})
    if txn.get("currency"):
        facts.append({"field": "Currency", "value": txn["currency"]})
    if txn.get("purpose"):
        facts.append({"field": "Transaction Purpose", "value": txn["purpose"]})
    # Evidence-sourced transaction fields
    for ev_key, label in [
        ("txn.amount_band", "Amount Band"),
        ("txn.count", "Transaction Count"),
    ]:
        if ev_key in ev_map and ev_map[ev_key] is not None:
            facts.append({"field": label, "value": str(ev_map[ev_key])})

    screening = layer1.get("screening", {}) or {}
    if screening.get("sanctions_match") is not None:
        facts.append({"field": "Sanctions Match", "value": "Yes" if screening["sanctions_match"] else "No"})
    if screening.get("pep_match") is not None:
        facts.append({"field": "PEP Match", "value": "Yes" if screening["pep_match"] else "No"})
    if screening.get("adverse_media") is not None:
        facts.append({"field": "Adverse Media", "value": "Yes" if screening["adverse_media"] else "No"})
    if screening.get("match_score") is not None:
        facts.append({"field": "Match Score", "value": f"{screening['match_score']}%"})
    if screening.get("list_type"):
        facts.append({"field": "List Type", "value": screening["list_type"]})
    if screening.get("mltf_linked") is not None:
        facts.append({"field": "ML/TF Linked", "value": "Yes" if screening["mltf_linked"] else "No"})

    if not facts:
        facts = [
            {"field": "Case ID", "value": normalized["case_id"]},
            {"field": "Jurisdiction", "value": normalized["jurisdiction"]},
        ]

    return facts


def _build_case_facts_sections(normalized: dict) -> dict:
    """Build structured case facts in three sections for GAP-C rendering.

    Returns {transaction: [...], customer: [...], screening: [...]}.
    """
    layer1 = normalized["layer1_facts"]
    evidence_used = normalized.get("evidence_used", []) or []
    ev_map = {str(ev.get("field", "")): ev.get("value") for ev in evidence_used}

    # ── Transaction context ──────────────────────────────────────────
    txn_facts: list[dict] = []
    txn = layer1.get("transaction", {}) or {}
    _txn_fields = [
        ("channel", "Channel"),
        ("method", "Payment Method"),
        ("amount_cad", "Amount (CAD)"),
        ("currency", "Currency"),
        ("destination", "Destination"),
        ("purpose", "Transaction Purpose"),
    ]
    for key, label in _txn_fields:
        val = txn.get(key)
        if val is not None:
            if key == "amount_cad":
                txn_facts.append({"field": label, "value": f"${val:,.2f}"})
            else:
                txn_facts.append({"field": label, "value": str(val)})
    if txn.get("cross_border") is not None:
        txn_facts.append({"field": "Cross-Border", "value": "Yes" if txn["cross_border"] else "No"})
    for ev_key, label in [
        ("txn.amount_band", "Amount Band"),
        ("txn.count", "Transaction Count"),
    ]:
        if ev_key in ev_map and ev_map[ev_key] is not None:
            txn_facts.append({"field": label, "value": str(ev_map[ev_key])})

    # ── Customer context ─────────────────────────────────────────────
    cust_facts: list[dict] = []
    customer = layer1.get("customer", {}) or {}
    _cust_fields = [
        ("type", "Customer Type"),
        ("residence", "Residence Country"),
        ("risk_rating", "Risk Rating"),
    ]
    for key, label in _cust_fields:
        val = customer.get(key)
        if val is not None:
            cust_facts.append({"field": label, "value": str(val)})
    if customer.get("pep_flag") is not None:
        cust_facts.append({"field": "PEP Status", "value": "Yes" if customer["pep_flag"] else "No"})
    if customer.get("tenure_years") is not None:
        cust_facts.append({"field": "Tenure (Years)", "value": str(customer["tenure_years"])})
    for ev_key, label in [
        ("customer.source_verified", "Source of Funds Verified"),
        ("customer.ownership_clear", "Ownership Structure Clear"),
    ]:
        if ev_key in ev_map and ev_map[ev_key] is not None:
            val = ev_map[ev_key]
            if isinstance(val, bool):
                val = "Yes" if val else "No"
            cust_facts.append({"field": label, "value": str(val)})

    # ── Screening context ────────────────────────────────────────────
    screen_facts: list[dict] = []
    screening = layer1.get("screening", {}) or {}
    _screen_fields = [
        ("sanctions_match", "Sanctions Match"),
        ("adverse_media", "Adverse Media"),
        ("pep_match", "PEP Match"),
        ("mltf_linked", "ML/TF Linked"),
    ]
    for key, label in _screen_fields:
        val = screening.get(key)
        if val is not None:
            screen_facts.append({"field": label, "value": "Yes" if val else "No"})
    if screening.get("match_score") is not None:
        screen_facts.append({"field": "Match Score", "value": f"{screening['match_score']}%"})
    if screening.get("list_type"):
        screen_facts.append({"field": "List Type", "value": screening["list_type"]})

    return {
        "transaction": txn_facts,
        "customer": cust_facts,
        "screening": screen_facts,
    }

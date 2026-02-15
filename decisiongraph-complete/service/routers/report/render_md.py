"""Markdown renderer — Stage D (Markdown) of the Report Compiler Pipeline.

Accepts a ReportViewModel (the same dict used by HTML/JSON) and returns
the complete Markdown report string.  No business logic lives here —
only presentation.
"""

from datetime import datetime

from .view_model import NARRATIVE_COMPILER_VERSION
from service.suspicion_classifier import CLASSIFIER_VERSION


# ── Markdown helpers ─────────────────────────────────────────────────────────

def _md_escape(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return text.replace("\r", " ").replace("\n", " ").replace("|", "\\|").replace("`", "\\`")


# ── Precedent section ────────────────────────────────────────────────────────

def _build_precedent_markdown(precedent_analysis: dict) -> str:
    if not precedent_analysis:
        return ""
    if not precedent_analysis.get("available"):
        message = (
            precedent_analysis.get("message")
            or precedent_analysis.get("error")
            or "Precedent analysis unavailable."
        )
        return f"""> {message}\n\n"""

    def _label(value: object) -> str:
        return str(value).upper() if value is not None else "N/A"

    match_distribution = (
        precedent_analysis.get("match_outcome_distribution")
        or precedent_analysis.get("outcome_distribution", {})
        or {}
    )
    overlap_distribution = (
        precedent_analysis.get("raw_outcome_distribution")
        or precedent_analysis.get("overlap_outcome_distribution", {})
        or {}
    )

    match_rows = ""
    for outcome, count in sorted(match_distribution.items(), key=lambda i: str(i[0])):
        match_rows += f"| {_label(outcome)} | {count} |\n"

    overlap_rows = ""
    for outcome, count in sorted(overlap_distribution.items(), key=lambda i: str(i[0])):
        overlap_rows += f"| {_label(outcome)} | {count} |\n"

    appeal = precedent_analysis.get("appeal_statistics", {})

    # Caution precedents
    caution = precedent_analysis.get("caution_precedents", [])
    caution_section = ""
    if caution:
        caution_section = "\n### Caution Precedents (Overturned Cases)\n\n"
        caution_section += f"**{len(caution)}** similar cases were later overturned on appeal:\n\n"
        for prec in caution[:5]:
            caution_section += f"- **{prec.get('case_ref', 'N/A')}** — {_label(prec.get('outcome'))}"
            if prec.get("appeal_result"):
                caution_section += f" (Appeal: {prec['appeal_result']})"
            caution_section += "\n"
        if len(caution) > 5:
            caution_section += f"- ... and {len(caution) - 5} more\n"

    confidence_pct = int((precedent_analysis.get("precedent_confidence", 0) or 0) * 100)

    # FIX-008: Upheld rate — N/A when no appeals
    total_appealed = int(appeal.get("total_appealed", 0) or 0)
    upheld_count = int(appeal.get("upheld", 0) or 0)
    overturned_count = int(appeal.get("overturned", 0) or 0)
    if total_appealed > 0:
        upheld_rate_display = f"{int(upheld_count / total_appealed * 100)}%"
    else:
        upheld_rate_display = "N/A — No appeals filed"
    sample_size = int(precedent_analysis.get("sample_size", 0) or 0)
    neutral = int(precedent_analysis.get("neutral_precedents", 0) or 0)
    min_similarity_pct = int(precedent_analysis.get("min_similarity_pct", 50) or 50)
    raw_overlap_count = int(
        (
            precedent_analysis.get("raw_overlap_count")
            or precedent_analysis.get("overlap_count")
            or precedent_analysis.get("raw_count")
            or 0
        ) or 0
    )

    sample_cases = precedent_analysis.get("sample_cases", []) or []
    exact_match_count = int(precedent_analysis.get("exact_match_count", 0) or 0)
    match_count = int(precedent_analysis.get("match_count", 0) or 0)

    matches_md = ""
    if sample_cases:
        threshold_pct = int(round((precedent_analysis.get("threshold_used") or 0.5) * 100))
        matches_md = f"\n### Precedent Evidence (Top Matches)\n\n"
        matches_md += f"*Similarity threshold: \u2265{threshold_pct}%. Matches below threshold are nearest neighbors shown for analyst context only.*\n\n"
        for match in sample_cases:
            outcome_label = match.get("outcome_label") or _label(match.get("outcome"))
            sim_pct = int(match.get('similarity_pct', 0) or 0)
            similarity = f"{sim_pct}%"
            if match.get("exact_match"):
                similarity += " EXACT"
            if sim_pct < threshold_pct:
                similarity += " *(below threshold)*"
            reason_codes = " · ".join(match.get("reason_codes", []) or [])
            components = match.get("similarity_components", {}) or {}
            classification = match.get("classification", "neutral")

            matches_md += f"**{match.get('precedent_id', 'N/A')}** — {similarity} similarity\n"
            matches_md += f"> {outcome_label} · {match.get('decision_level', 'N/A')}"
            if match.get("appealed"):
                matches_md += f" · Appealed ({match.get('appeal_outcome', 'pending')})"
            matches_md += f" · _{classification}_\n\n"

            driver_items = [
                ("Rules", components.get("rules_overlap", 0)),
                ("Gates", components.get("gate_match", 0)),
                ("Typology", components.get("typology_overlap", 0)),
                ("Amount", components.get("amount_bucket", 0)),
                ("Corridor", components.get("corridor_match", 0)),
                ("Channel", components.get("channel_method", 0)),
                ("PEP", components.get("pep_match", 0)),
                ("Customer", components.get("customer_profile", 0)),
                ("Geo Risk", components.get("geo_risk", 0)),
            ]
            active_drivers = [(name, pct) for name, pct in driver_items if pct and pct > 0]
            if active_drivers:
                driver_str = " · ".join(f"{name} {pct}%" for name, pct in active_drivers)
                matches_md += f"Similarity features: {driver_str}\n"
            matches_md += f"`{reason_codes}`\n\n---\n\n"

    note_md = ""
    if raw_overlap_count > 0 and match_count == 0 and not sample_cases:
        note_md = (
            "\n> Raw overlaps were found based on limited features, "
            "but no precedents met the similarity threshold. "
            "Provide transaction shape and customer profile facts (amount bucket, channel, corridor, customer type, "
            "relationship length, PEP) to enable scoring.\n"
            "> Raw overlaps reflect cases sharing one or more structural indicators but not meeting the "
            "similarity threshold required for scored comparison.\n"
        )
    elif raw_overlap_count > 0:
        note_md = (
            "\n> Raw overlaps reflect cases sharing one or more structural indicators but not meeting the "
            "similarity threshold required for scored comparison.\n"
        )

    candidates_scored = int(precedent_analysis.get("candidates_scored", sample_size) or 0)
    threshold_mode = precedent_analysis.get("threshold_mode", "prod")
    threshold_pct = int(round((precedent_analysis.get("threshold_used") or 0) * 100))
    show_overlap = bool(overlap_distribution) and overlap_distribution != match_distribution

    overlap_section = ""
    if show_overlap:
        overlap_section = f"""
### Raw Overlap Outcome Distribution

| Outcome | Count |
|---------|-------|
{overlap_rows or "| No data | - |"}
"""

    # FIX-002: Scored vs total pool
    supporting = int(precedent_analysis.get("supporting_precedents", 0) or 0)
    contrary = int(precedent_analysis.get("contrary_precedents", 0) or 0)
    scored_count = supporting + contrary + neutral
    threshold_pct_global = int(round((precedent_analysis.get("threshold_used") or 0.5) * 100))

    # GAP-D: Use backend-sourced disclaimer with sensible fallback
    _disclaimer = (
        precedent_analysis.get("_precedent_disclaimer")
        or "Precedent analysis is non-authoritative; used only for consistency "
           "review and peer comparison; never overrides gates, rules, or "
           "statutory reporting determinations."
    )
    return f"""*{_disclaimer}*
*Absence of precedent matches does not imply the recommendation is incorrect.*

### Tier 1 — Scored Matches (≥{threshold_pct_global}% Similarity)

*Used for confidence scoring and deviation analysis.*

| Metric | Value |
|--------|-------|
| Scored Matches (Above Threshold) | {scored_count} |
| Supporting Precedents | {supporting} |
| Contrary Precedents | {contrary} |
| Neutral Precedents | {neutral} |
| Precedent Confidence | {confidence_pct}% |
| Exact Matches | {exact_match_count} |

{_md_escape(precedent_analysis.get("similarity_summary", ""))}

#### Scored Match Outcome Distribution

| Outcome | Count |
|---------|-------|
{match_rows or "| No data | - |"}

### Tier 2 — Broader Comparable Pool

*Contextual — not used in confidence scoring or deviation analysis.*

| Metric | Value |
|--------|-------|
| Total Comparable Pool | {match_count} |
| Raw Overlaps Found | {raw_overlap_count} |
| Candidates Scored | {candidates_scored} (≥{threshold_pct_global or min_similarity_pct}% similarity required; mode: {threshold_mode}) |

{overlap_section}

{note_md}

### Appeal Statistics

| Metric | Value |
|--------|-------|
| Total Appealed | {total_appealed} |
| Upheld | {upheld_count} |
| Overturned | {overturned_count} |
| Upheld Rate | {upheld_rate_display} |
{caution_section}
{matches_md}
"""


# ── Main render function ─────────────────────────────────────────────────────

def render_markdown(ctx: dict) -> str:
    """Render the complete Markdown report from a ReportViewModel."""

    # ── Build table rows ─────────────────────────────────────────────────
    # ── GAP-E: Senior Summary Box ─────────────────────────────────
    senior = ctx.get("senior_summary", {})
    senior_summary_md = ""
    if senior:
        senior_summary_md = (
            "## Senior Officer Summary\n\n"
            "| | |\n|---|---|\n"
            f"| **Alert Trigger** | {_md_escape(senior.get('alert_trigger', 'N/A'))} |\n"
            f"| **Suspicious Elements** | {_md_escape(senior.get('suspicious_elements', 'None'))} |\n"
            f"| **Not Yet Established** | {_md_escape(senior.get('not_established', 'N/A'))} |\n"
            f"| **Current Decision** | {_md_escape(senior.get('current_decision', 'N/A'))} |\n"
            f"| **STR Pending** | {_md_escape(senior.get('str_pending', 'N/A'))} |\n"
            f"| **Next Deadline** | {_md_escape(senior.get('next_evidence_deadline', 'N/A'))} |\n\n"
            "---\n\n"
        )

    # ── GAP-C: Case Facts (structured sections if available) ─────
    case_sections = ctx.get("case_facts_sections", {})

    facts_rows = ""
    for fact in ctx.get("transaction_facts", []):
        facts_rows += f"| {_md_escape(fact['field'])} | `{_md_escape(fact['value'])}` |\n"

    case_facts_structured_md = ""
    if case_sections and any(case_sections.get(k) for k in ("transaction", "customer", "screening")):
        case_facts_structured_md = "### Case Facts\n\n"
        for section_key, section_title in [("transaction", "Transaction Context"), ("customer", "Customer Context"), ("screening", "Screening Context")]:
            items = case_sections.get(section_key, [])
            if items:
                case_facts_structured_md += f"**{section_title}**\n\n| Field | Value |\n|-------|-------|\n"
                for item in items:
                    case_facts_structured_md += f"| {_md_escape(item.get('field', ''))} | `{_md_escape(item.get('value', ''))}` |\n"
                case_facts_structured_md += "\n"

    gate1_passed = ctx.get("gate1_passed", False)
    gate1_rows = ""
    for section in ctx.get("gate1_sections", []):
        status = "PASS" if section.get("passed") else "FAIL"
        reason = _md_escape(section.get("reason", ""))
        if not section.get("passed") and gate1_passed:
            reason += " *(Sub-check failed but overall gate PERMITTED — hard stop or classifier sovereignty overrides this check.)*"
        gate1_rows += f"| {_md_escape(section.get('name', 'N/A'))} | {status} | {reason} |\n"

    gate2_rows = ""
    for section in ctx.get("gate2_sections", []):
        status = "PASS" if section.get("passed") else "REVIEW"
        gate2_rows += f"| {_md_escape(section.get('name', 'N/A'))} | {status} | {_md_escape(section.get('reason', ''))} |\n"


    # Decision header (governed — not engine)
    governed = ctx.get("governed_disposition", "EDD_REQUIRED")
    engine = ctx.get("engine_disposition", governed)
    if governed == "NO_REPORT":
        decision_header = "### **NO_REPORT** — Alert Cleared"
    elif governed == "STR_REQUIRED":
        decision_header = "### **FILE_STR** — Suspicious Transaction Report Required"
    elif governed == "ESCALATE":
        decision_header = "### **ESCALATE** — Compliance Review Required"
    else:
        decision_header = "### **EDD_REQUIRED** — Enhanced Due Diligence Required"
    if engine != governed:
        decision_header += f"\n\n*Engine originally suggested: {engine.replace('_', ' ')}. Classifier sovereignty applied — governed outcome is authoritative.*"
    # Disposition ladder display values
    governed_display = governed.replace("_", " ")
    action_val = ctx.get("action", "")
    engine_display = engine.replace("_", " ")
    if action_val and action_val.lower() != "n/a":
        engine_display += f" \u2014 {action_val}"
    disposition_note = ""
    if engine != governed:
        disposition_note = (
            "\n> Engine output differs from governed disposition. "
            "Governance correction applied \u2014 governed outcome is authoritative. "
            "This correction ensures escalation is consistent with suspicion threshold requirements.\n"
        )
    safe_path = _md_escape(ctx["decision_path_trace"] or "N/A")

    # ── Decision Path Narrative Trace ────────────────────────────────────
    decision_path_narrative = ctx.get("decision_path_narrative", {})
    decision_path_md = ""
    if decision_path_narrative and decision_path_narrative.get("steps"):
        decision_path_md = "## Decision Path\n\n"
        for step in decision_path_narrative["steps"]:
            decision_path_md += f"**{step['symbol']} {step['title']}**\n\n"
            for line in step.get("detail_lines", []):
                decision_path_md += f"   {_md_escape(line)}\n\n"
            decision_path_md += f"   \u2192 {_md_escape(step['arrow_line'])}\n\n"
        decision_path_md += "---\n\n"

    # ── FIX-001: Canonical outcome block ────────────────────────────────
    canonical = ctx.get("canonical_outcome", {})
    reporting_display = canonical.get("reporting", "UNKNOWN")
    if canonical.get("reporting_note"):
        reporting_display += f" ({canonical['reporting_note']})"
    canonical_outcome_md = (
        f"| Disposition | **{canonical.get('disposition', 'UNKNOWN')}** |\n"
        f"| Disposition Basis | **{canonical.get('disposition_basis', 'UNKNOWN')}** |\n"
        f"| Reporting | **{reporting_display}** |\n"
    )

    # ── FIX-005: Distinct confidence metrics ──────────────────────────────
    decision_confidence_block = ""
    if ctx.get("decision_confidence"):
        prec_alignment = ctx.get("precedent_alignment_pct", 0)
        match_rate = ctx.get("precedent_match_rate", 0)
        scored_ct = ctx.get("scored_precedent_count", 0)
        total_pool = ctx.get("total_comparable_pool", 0)
        conf_score = ctx.get("decision_confidence_score", 0)

        # FIX-017: Institutional threshold indicator
        if conf_score >= 70:
            threshold_indicator = "Above Threshold"
        elif conf_score >= 40:
            threshold_indicator = "Within Band"
        else:
            threshold_indicator = "Below Threshold — Manual Review Required"

        decision_confidence_block = (
            f"### Confidence Metrics\n\n"
            f"| Metric | Value | Definition |\n"
            f"|--------|-------|------------|\n"
            f"| Decision Confidence | {ctx['decision_confidence']} ({conf_score}%) | "
            f"Composite score reflecting evidence completeness and rule alignment |\n"
            f"| Institutional Threshold | {threshold_indicator} | "
            f"Bands: ≥70% High, 40–70% Moderate, <40% Low (manual review) |\n"
            f"| Precedent Alignment | {prec_alignment}% | "
            f"supporting_decisive / count(decisive_precedents) within same basis |\n"
            f"| Precedent Match Rate | {match_rate}% ({scored_ct} / {total_pool}) | "
            f"Percentage of comparable pool meeting similarity threshold |\n\n"
            f"{ctx['decision_confidence_reason']}"
        )
        if conf_score < 40:
            decision_confidence_block += (
                f"\n\n> **LOW CONFIDENCE FLAG:** Decision confidence ({conf_score}%) is below "
                f"the institutional threshold of 40%. This decision requires senior analyst "
                f"or compliance officer review before final disposition.\n"
            )

    # ── FIX-003: Evidence with scope qualifiers ───────────────────────────
    # Pull display names from the banking field registry (single source of truth)
    from decisiongraph.banking_field_registry import get_canonical_to_display_map
    _EVIDENCE_SCOPE_LABELS: dict[str, str] = get_canonical_to_display_map()
    # Add non-registry fields from decision_pack evaluation trace
    _EVIDENCE_SCOPE_LABELS.update({
        "facts.sanctions_result": "Sanctions screening determination",
        "facts.adverse_media_mltf": "Adverse media ML/TF relevance indicator",
        "suspicion.has_intent": "Suspicion element: intent indicators present",
        "suspicion.has_deception": "Suspicion element: deception indicators present",
        "suspicion.has_sustained_pattern": "Suspicion element: sustained transaction pattern",
        "obligations.count": "Count of regulatory obligations triggered",
        "mitigations.count": "Count of mitigating factors identified",
        "typology.maturity": "Typology assessment maturity level",
        # Legacy field aliases (website names) for backward compat
        "risk.high_risk_jurisdiction": "Customer domicile jurisdiction risk",
        "risk.pep": "Politically Exposed Person status",
        "risk.high_risk_industry": "High-risk industry indicator",
        "risk.cash_intensive_business": "Cash-intensive business indicator",
        "screen.sanctions_match": "Sanctions screening match",
        "screen.pep_match": "PEP screening match",
        "screen.adverse_media": "Adverse media indicator",
        "screen.prior_sars_filed": "Prior Suspicious Activity Reports filed",
        "screen.previous_account_closures": "Previous account closures on record",
        "flag.structuring_suspected": "Structuring indicators present",
        "flag.layering_indicators": "Layering indicators present",
        "flag.third_party_payment": "Third-party payment indicator",
        "flag.shell_company_indicators": "Shell company indicators present",
        "risk.risk_score": "Overall risk score",
    })

    evidence_rows = ""
    for ev in ctx.get("evidence_used", []):
        value = ev.get("value", "N/A")
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        field_raw = ev.get("field", "N/A")
        # FIX-003: Use scope-qualified label if available
        field_display = _EVIDENCE_SCOPE_LABELS.get(field_raw, field_raw)
        evidence_rows += f"| `{_md_escape(field_raw)}` | {_md_escape(field_display)} | {_md_escape(value)} |\n"

    # ── FIX-012: Rule-evidence linking ────────────────────────────────────
    # Build map of triggered rules → evidence fields
    ev_fields = {str(ev.get("field", "")): ev.get("value") for ev in ctx.get("evidence_used", [])}
    _RULE_EVIDENCE_MAP: dict[str, list[str]] = {
        "AML_ESC_HR_COUNTRY": ["txn.destination_country_risk", "txn.cross_border"],
        "AML_ESC_PEP_SCREEN": ["customer.pep", "screening.pep_match"],
        "AML_ESC_PEP": ["customer.pep", "screening.pep_match"],
        "AML_ESC_STRUCT": ["flag.structuring", "txn.amount_band"],
        "AML_BLOCK_SANCTIONS": ["screening.sanctions_match"],
        "AML_INV_STRUCT": ["flag.structuring", "txn.amount_band"],
        "AML_STR_LAYER": ["flag.rapid_movement", "txn.type"],
        "AML_ESC_ADVERSE_MEDIA": ["screening.adverse_media"],
        "AML_ESC_SHELL": ["flag.shell_company"],
        "AML_ESC_LAYERING": ["flag.layering"],
        "AML_ESC_3P": ["flag.third_party"],
        "AML_ESC_CASH_INTENSIVE": ["customer.cash_intensive"],
        "AML_ESC_CRYPTO": ["txn.type"],
        "AML_LCTR": ["txn.amount_band", "txn.type"],
    }

    rules_rows = ""
    for rule in ctx.get("rules_fired", []):
        code = rule.get("code", "N/A")
        result = rule.get("result", "N/A")
        reason = rule.get("reason", "")
        triggered_by = ""

        # FIX-012: For triggered rules, show which evidence fields activated them
        if str(result).upper() in {"WARN", "FAIL", "TRIGGERED", "ACTIVATED", "FAILED"}:
            code_upper = str(code).upper()
            mapped_fields = _RULE_EVIDENCE_MAP.get(code_upper, [])
            active = []
            for f in mapped_fields:
                if f in ev_fields:
                    active.append(f"{f} = {ev_fields[f]}")
            if not active:
                # Try to find matching evidence by rule code prefix
                for f, v in ev_fields.items():
                    if code_upper.lower().replace("aml_", "").replace("esc_", "").replace("inv_", "") in f.lower():
                        active.append(f"{f} = {v}")
            if active:
                triggered_by = " · Triggered by: " + ", ".join(active[:3])

        rules_rows += f"| `{_md_escape(code)}` | {_md_escape(result)} | {_md_escape(reason)}{triggered_by} |\n"

    # ── FIX-006: Defensibility check section ──────────────────────────────
    defensibility = ctx.get("defensibility_check", {})
    defensibility_md = ""
    if defensibility:
        status = defensibility.get("status", "UNKNOWN")
        status_icon = "✅" if status == "PASS" else "⏳" if status == "DEFERRED" else "🚨"
        defensibility_md = (
            f"### Defensibility Check\n\n"
            f"| | |\n|---|---|\n"
            f"| Status | {status_icon} **{status}** — {_md_escape(defensibility.get('message', ''))} |\n"
        )
        if defensibility.get("action"):
            defensibility_md += f"| Action | {_md_escape(defensibility['action'])} |\n"
        if defensibility.get("note"):
            defensibility_md += f"| Note | {_md_escape(defensibility['note'])} |\n"
        defensibility_md += "\n"

    # ── FIX-007: EDD recommendations ──────────────────────────────────────
    edd_recommendations = ctx.get("edd_recommendations", [])
    edd_md = ""
    if edd_recommendations:
        edd_md = "## Recommended Actions\n\n"
        for i, rec in enumerate(edd_recommendations, 1):
            edd_md += f"{i}. **{_md_escape(rec.get('action', ''))}**\n"
            if rec.get("reference"):
                edd_md += f"   *Ref: {_md_escape(rec['reference'])}*\n"
            edd_md += "\n"

    # ── FIX-015: Analyst Actions (outcome-aware) ─────────────────────────
    analyst_actions = ctx.get("analyst_actions", [])
    analyst_actions_md = ""
    if analyst_actions:
        governed = ctx.get("governed_disposition", "")
        analyst_actions_md = f"## Analyst Actions\n\n"
        analyst_actions_md += f"*Actions available for governed disposition: **{governed}***\n\n"
        for act in analyst_actions:
            marker = "**[PRIMARY]** " if act.get("primary") else ""
            analyst_actions_md += f"- {marker}{_md_escape(act.get('label', ''))}\n"
        analyst_actions_md += "\n"

    # ── FIX-028: Gate Override Analysis ───────────────────────────────────
    gate_overrides = ctx.get("gate_override_explanations", [])
    gate_override_md = ""
    if gate_overrides:
        has_conflict = any(g.get("conflict") for g in gate_overrides)
        if has_conflict:
            gate_override_md = "### Gate Override Analysis\n\n"
            for g in gate_overrides:
                if not g.get("conflict"):
                    continue
                gate_override_md += f"**{_md_escape(g.get('gate', ''))}**\n\n"
                gate_override_md += "| | |\n|---|---|\n"
                gate_override_md += f"| Gate Result | `{_md_escape(g.get('gate_result', ''))}` |\n"
                gate_override_md += f"| Final Disposition | **{_md_escape(g.get('final_disposition', ''))}** |\n"
                gate_override_md += f"| Override Mechanism | {_md_escape(g.get('override_mechanism', ''))} |\n"
                gate_override_md += f"| Authority | {_md_escape(g.get('authority', ''))} |\n\n"
                if g.get("override_basis"):
                    gate_override_md += "**Override Basis:**\n\n"
                    for basis in g["override_basis"]:
                        gate_override_md += f"- {_md_escape(basis)}\n"
                    gate_override_md += "\n"
        else:
            # Check for UPHELD gates
            upheld = [g for g in gate_overrides if g.get("upheld")]
            if upheld:
                gate_override_md = "### Gate Override Analysis\n\n"
                for g in upheld:
                    gate_override_md += f"**{_md_escape(g.get('gate', ''))}** — UPHELD\n\n"
                    gate_override_md += f"> {_md_escape(g.get('upheld_detail', ''))}\n\n"
                    if g.get("upheld_basis"):
                        gate_override_md += "**Gate Basis:**\n\n"
                        for b in g["upheld_basis"]:
                            gate_override_md += f"- {_md_escape(b)}\n"
                        gate_override_md += "\n"
            else:
                gate_override_md = "### Gate Override Analysis\n\n> All gates consistent with final disposition.\n\n"

    # ── FIX-029: Disposition Reconciliation ────────────────────────────────
    reconciliation = ctx.get("disposition_reconciliation", {})
    reconciliation_md = ""
    if reconciliation:
        if reconciliation.get("consistent"):
            reconciliation_md = "## Disposition Reconciliation\n\n> All disposition layers consistent. No override applied.\n\n"
        else:
            reconciliation_md = "## Disposition Reconciliation\n\n"
            reconciliation_md += f"*{_md_escape(reconciliation.get('summary', ''))}*\n\n"
            for diff in reconciliation.get("differences", []):
                reconciliation_md += (
                    f"**{_md_escape(diff.get('component_a', ''))}** determined "
                    f"`{_md_escape(diff.get('value_a', ''))}` — "
                    f"**{_md_escape(diff.get('component_b', ''))}** "
                    f"{'overrode to' if diff.get('value_a') != diff.get('value_b') else 'agrees:'} "
                    f"`{_md_escape(diff.get('value_b', ''))}`\n\n"
                    f"> {_md_escape(diff.get('reason', ''))}\n\n"
                    f"> Authority: {_md_escape(diff.get('authority', ''))}\n\n"
                )

    # ── Decision Conflict Alert ────────────────────────────────────────────
    conflict = ctx.get("decision_conflict_alert")
    conflict_alert_md = ""
    if conflict:
        conflict_alert_md = (
            "### ⚠ DECISION CONFLICT\n\n"
            f"| | |\n|---|---|\n"
            f"| Classifier | **{conflict['classifier']}** |\n"
            f"| Engine | **{conflict['engine']}** |\n"
            f"| Governed | **{conflict['governed']}** |\n\n"
            f"> **Resolution:** {conflict['resolution']}\n\n"
        )

    # ── FIX-030: Precedent Divergence Narrative ────────────────────────────
    divergence = ctx.get("precedent_divergence")
    divergence_md = ""
    if divergence:
        pool = divergence.get("pool_breakdown", {})
        pool_line = ", ".join(f"{k}: {v}" for k, v in sorted(pool.items())) if pool else "N/A"
        if divergence.get("divergent"):
            divergence_md = "### Institutional Divergence Explanation\n\n"
            divergence_md += (
                f"Historical pattern: {divergence.get('alignment_pct', 0)}% of "
                f"{divergence.get('alignment_total', 0)} comparable cases aligned with "
                f"current disposition.\n\n"
                f"Dominant historical outcome: **{_md_escape(divergence.get('dominant_historical', 'N/A'))}** "
                f"({divergence.get('dominant_count', 0)} cases)\n\n"
                f"Comparable pool outcomes: {pool_line}\n\n"
                "**Current disposition diverges. Basis:**\n\n"
            )
            for reason in divergence.get("divergence_reasons", []):
                divergence_md += f"- {_md_escape(reason)}\n"
            divergence_md += "\n"
        else:
            divergence_md = (
                f"### Precedent Pool Outcomes\n\n"
                f"Comparable pool outcomes: {pool_line}\n\n"
                f"Alignment: {divergence.get('alignment_pct', 0)}% "
                f"({divergence.get('alignment_count', 0)}/{divergence.get('alignment_total', 0)})\n\n"
            )

    # ── FIX-031: Unmapped Indicator Independence ───────────────────────────
    unmapped_checks = ctx.get("unmapped_indicator_checks", [])
    unmapped_md = ""
    if unmapped_checks:
        unmapped_md = "### Unmapped Indicator Independence Check\n\n"
        for check in unmapped_checks:
            if check.get("independent"):
                unmapped_md += (
                    f"**{_md_escape(check.get('indicator_code', ''))}**: "
                    f"Determination Independence: CONFIRMED. {_md_escape(check.get('basis', ''))}\n\n"
                )
            else:
                unmapped_md += (
                    f"**{_md_escape(check.get('indicator_code', ''))}**: "
                    f"DEFENSIBILITY WARNING: Disposition DEPENDS on unmapped indicator. "
                    f"{_md_escape(check.get('basis', ''))}. "
                    "Manual classification required before filing.\n\n"
                )

    # ── FIX-032: Policy Regime Exception ───────────────────────────────────
    regime_exception = ctx.get("policy_regime_exception")
    regime_exception_md = ""
    if regime_exception:
        if regime_exception.get("exception"):
            regime_exception_md = "### Policy Pattern Exception\n\n"
            regime_exception_md += f"> {_md_escape(regime_exception.get('summary', ''))}\n\n"
            regime_exception_md += "**Exception basis:**\n\n"
            for basis in regime_exception.get("exception_basis", []):
                regime_exception_md += f"- {_md_escape(basis)}\n"
            regime_exception_md += "\n"
        else:
            regime_exception_md = (
                "### Policy Regime Consistency\n\n"
                "> Disposition consistent with post-shift institutional pattern.\n\n"
            )

    # ── FIX-033: Risk Heatmap Context ──────────────────────────────────────
    heatmap_ctx = ctx.get("risk_heatmap_context")
    heatmap_note_md = ""
    if heatmap_ctx and heatmap_ctx.get("elevated"):
        heatmap_note_md = f"\n> {_md_escape(heatmap_ctx.get('note', ''))}\n\n"

    # ── FIX-034: Required Actions ──────────────────────────────────────────
    req_actions = ctx.get("required_actions", [])
    required_actions_md = ""
    if req_actions:
        required_actions_md = "## Required Actions\n\n"
        for i, act in enumerate(req_actions, 1):
            priority = act.get("priority", "")
            marker = f"**[{priority}]** " if priority else ""
            required_actions_md += f"{i}. {marker}{_md_escape(act.get('action', ''))}\n"
        required_actions_md += "\n"

    # ── FIX-035: Related Activity ──────────────────────────────────────────
    related = ctx.get("related_activity", {})
    related_activity_md = ""
    if related:
        screening = related.get("screening", {})
        related_activity_md = "## Related Activity\n\n"
        related_activity_md += "| Field | Value |\n|-------|-------|\n"
        related_activity_md += f"| Prior STRs Filed | {related.get('prior_sars_filed', 0)} |\n"
        related_activity_md += f"| Prior Account Closures | {'Yes' if related.get('prior_account_closures') else 'No'} |\n"
        related_activity_md += f"| PEP Status | {'Yes' if related.get('pep_status') else 'No'} |\n"
        related_activity_md += f"| Sanctions Match | {'Yes' if screening.get('sanctions_match') else 'No'} |\n"
        related_activity_md += f"| PEP Screening | {'Yes' if screening.get('pep_match') else 'No'} |\n"
        related_activity_md += f"| Adverse Media | {'Yes' if screening.get('adverse_media') else 'No'} |\n\n"
        for flag in related.get("flags", []):
            related_activity_md += f"> {_md_escape(flag)}\n\n"
        related_activity_md += f"Connected accounts: {_md_escape(related.get('connected_accounts', 'N/A'))}\n\n"

    # ── GAP-B: STR Decision Authority ────────────────────────────────────
    str_frame = ctx.get("str_decision_frame", {})
    str_authority_md = ""
    if str_frame and str_frame.get("decision_owner"):
        owner = str_frame["decision_owner"]
        str_authority_md = (
            "## STR Decision Authority\n\n"
            "| | |\n|---|---|\n"
            f"| **Decision Owner** | {_md_escape(owner.get('role', 'N/A'))} |\n"
            f"| **Basis** | {_md_escape(owner.get('basis', ''))} |\n"
            f"| **Decision Deadline** | {_md_escape(str_frame.get('decision_deadline', 'N/A'))} |\n"
            f"| **Authority** | {_md_escape(str_frame.get('authority_basis', ''))} |\n\n"
        )
        options = str_frame.get("decision_options", [])
        if options:
            str_authority_md += "### Decision Options\n\n| Option | Conditions |\n|--------|------------|\n"
            for opt in options:
                str_authority_md += f"| {_md_escape(opt.get('option', ''))} | {_md_escape(opt.get('conditions', ''))} |\n"
            str_authority_md += "\n"
        evidence = str_frame.get("minimum_evidence", [])
        if evidence:
            str_authority_md += "### Minimum Evidence Required\n\n"
            for i, item in enumerate(evidence, 1):
                str_authority_md += f"{i}. {_md_escape(item)}\n"
            str_authority_md += "\n"

    # ── FIX-009: SLA timeline ─────────────────────────────────────────────
    sla = ctx.get("sla_timeline", {})
    timeline_md = ""
    if sla:
        timeline_md = (
            f"## Timeline\n\n"
            f"| Field | Value |\n"
            f"|-------|-------|\n"
            f"| Case Created | `{sla.get('case_created', 'N/A')}` |\n"
            f"| EDD Deadline | `{sla.get('edd_deadline', 'N/A')}` |\n"
            f"| Final Disposition Due | {sla.get('final_disposition_due', 'N/A')} |\n"
            f"| STR Filing Window | {sla.get('str_filing_window', 'N/A')} |\n\n"
        )

    decision_drivers_md = "\n".join(
        [f"- {_md_escape(driver)}" for driver in ctx.get("decision_drivers", [])]
    ) or "- Decision drivers derived from rule evaluation were not available in this record."

    risk_factors_md = "\n".join(
        [
            f"| {_md_escape(item.get('field', 'N/A'))} | {_md_escape(item.get('value', 'N/A'))} |"
            for item in ctx.get("risk_factors", [])
        ]
    ) or "| No risk factors recorded | - |"

    governance_note = ""
    if ctx["str_required"]:
        governance_note = (
            "### Governance Note\n\n"
            "A Suspicious Transaction Report (STR) is required under PCMLTFA/FINTRAC guidelines.\n"
            "File within applicable statutory timeframe per regulatory guidance "
            f"(policy version: {ctx.get('policy_version', 'N/A')}).\n"
        )

    seed_notice = "> Synthetic training case (seeded)." if ctx.get("is_seed") else ""
    str_required_label = "Yes" if ctx.get("str_required") else "No"
    gate1_label = "ALLOWED" if ctx.get("gate1_passed") else "BLOCKED"
    gate1_rows_output = gate1_rows or "| No sections evaluated | - | - |"
    gate2_rows_output = gate2_rows or "| No sections evaluated | - | - |"
    rules_rows_output = rules_rows or "| No rules evaluated | - | - |"
    evidence_rows_output = evidence_rows or "| No evidence recorded | - | - |"

    # GAP-D: Pass backend-sourced disclaimer through to precedent builder
    _prec_analysis = ctx.get("precedent_analysis", {})
    _ep_disclaimer = ctx.get("enhanced_precedent", {}).get("precedent_disclaimer", "")
    if _ep_disclaimer:
        _prec_analysis = dict(_prec_analysis)
        _prec_analysis["_precedent_disclaimer"] = _ep_disclaimer
    precedent_markdown = _build_precedent_markdown(_prec_analysis)

    # FIX-018 + FIX-027: Enhanced precedent analysis sections
    enhanced_prec = ctx.get("enhanced_precedent", {})
    enhanced_precedent_md = ""

    if enhanced_prec:
        # FIX-027: Pattern Summary (institutional knowledge headline)
        ps = enhanced_prec.get("pattern_summary", "")
        if ps:
            enhanced_precedent_md += (
                f"\n### Institutional Pattern Summary\n\n"
                f"> {_md_escape(ps)}\n\n"
            )

        # FIX-027: Institutional Posture Statement
        ip = enhanced_prec.get("institutional_posture", "")
        if ip:
            enhanced_precedent_md += (
                f"### Institutional Posture\n\n"
                f"> *{_md_escape(ip)}*\n\n"
            )

        # Post-shift STR gap statement
        gap_stmt = enhanced_prec.get("post_shift_gap_statement", "")
        if gap_stmt:
            enhanced_precedent_md += (
                f"> \u26a0 *{_md_escape(gap_stmt)}*\n\n"
            )

        # Suspicion posture (Part 5)
        susp_posture = enhanced_prec.get("suspicion_posture", [])
        if susp_posture:
            for line in susp_posture:
                enhanced_precedent_md += f"> {_md_escape(line)}\n"
            enhanced_precedent_md += "\n"

        # Two-axis alignment split (Part 6)
        ta_narrative = enhanced_prec.get("two_axis_alignment_narrative", "")
        if ta_narrative:
            enhanced_precedent_md += "### Governed Disposition Alignment (Two-Axis)\n\n"
            for line in ta_narrative.split("\n"):
                if line.strip():
                    enhanced_precedent_md += f"> {_md_escape(line)}\n"
                else:
                    enhanced_precedent_md += ">\n"
            enhanced_precedent_md += "\n"

        # FIX-027: Case Thumbnails (readable precedent summaries)
        ct = enhanced_prec.get("case_thumbnails", [])
        case_reporting = ctx.get("canonical_outcome", {}).get("reporting", "UNKNOWN")
        _REPORTING_LABELS_MD = {
            "FILE_STR": "STR", "NO_REPORT": "NO STR", "FILE_LCTR": "LCTR",
            "FILE_TPR": "TPR", "PENDING_COMPLIANCE_REVIEW": "PENDING",
            "PENDING_EDD": "PENDING EDD",
        }
        if ct:
            enhanced_precedent_md += "### Precedent Case Summaries\n\n"
            _nt_count = sum(1 for t in ct if t.get("non_transferable"))
            _t_count = len(ct) - _nt_count
            if _nt_count > 0:
                _warning = " ⚠ Effective precedent support is minimal." if _t_count < 3 else ""
                enhanced_precedent_md += (
                    f"Comparable: {len(ct)} | Transferable: {_t_count} | "
                    f"Non-Transferable: {_nt_count}{_warning}\n\n"
                )
            for thumb in ct:
                pid = _md_escape(thumb.get("precedent_id", "N/A"))
                sim = thumb.get("similarity_pct", 0)
                desc = _md_escape(thumb.get("description", ""))
                km = ", ".join(thumb.get("key_matches", [])) or "None"
                kd = ", ".join(thumb.get("key_differences", [])) or "None"

                # Two-axis classification (preferred) or fallback to single-axis
                ta = thumb.get("two_axis", {}) or {}
                composite_desc = thumb.get("composite_description", "")
                op_align = ta.get("op_alignment", "")
                susp_align = ta.get("suspicion_alignment", "")

                if op_align and susp_align:
                    # Two-axis display
                    prec_reporting = thumb.get("reporting", "UNKNOWN")
                    prec_label = _REPORTING_LABELS_MD.get(prec_reporting, prec_reporting.replace("_", " "))
                    disp_label = thumb.get("disposition", "UNKNOWN")
                    enhanced_precedent_md += (
                        f"**{pid}**  {disp_label} — {prec_label}  {sim}%\n"
                    )
                    enhanced_precedent_md += (
                        f">   Operational: **{op_align}**"
                    )
                    if op_align == "ALIGNED":
                        enhanced_precedent_md += " (same action)"
                    elif op_align == "PARTIAL":
                        enhanced_precedent_md += " (adjacent tier)"
                    elif op_align == "CONTRARY":
                        enhanced_precedent_md += " (opposite action)"
                    enhanced_precedent_md += "\n"
                    enhanced_precedent_md += (
                        f">   Regulatory:  **{susp_align}**"
                    )
                    if susp_align == "ALIGNED":
                        enhanced_precedent_md += " (same suspicion posture)"
                    elif susp_align == "CONTRARY":
                        enhanced_precedent_md += " (different suspicion)"
                    elif susp_align == "UNDETERMINED":
                        enhanced_precedent_md += " (reporting pending)"
                    enhanced_precedent_md += "\n"
                    if composite_desc:
                        enhanced_precedent_md += f">   \u25b8 {composite_desc}\n"
                    enhanced_precedent_md += f"> {desc}\n"
                    # Reporting rationale (expandable context)
                    rationale = thumb.get("reporting_rationale", "")
                    if rationale:
                        enhanced_precedent_md += f">   *Rationale: {_md_escape(rationale)}*\n"
                else:
                    # Fallback: single-axis display
                    cls = thumb.get("classification", "neutral")
                    prec_reporting = thumb.get("reporting", "UNKNOWN")
                    reporting_diverges = (
                        case_reporting != "UNKNOWN"
                        and prec_reporting != "UNKNOWN"
                        and prec_reporting != case_reporting
                    )
                    if reporting_diverges:
                        prec_label = _REPORTING_LABELS_MD.get(prec_reporting, prec_reporting.replace("_", " "))
                        enhanced_precedent_md += (
                            f"**{pid}** — {sim}% similarity · _Disposition: {cls}_ · \u26a0 _Reporting: DIVERGENT ({prec_label})_\n"
                            f"> {desc}\n"
                        )
                    else:
                        enhanced_precedent_md += (
                            f"**{pid}** — {sim}% similarity · _{cls}_\n"
                            f"> {desc}\n"
                        )
                    # Reporting rationale (expandable context)
                    rationale = thumb.get("reporting_rationale", "")
                    if rationale:
                        enhanced_precedent_md += f"> *Rationale: {_md_escape(rationale)}*\n"
                if thumb.get("key_matches"):
                    enhanced_precedent_md += f"> Matching: {km}\n"
                if thumb.get("key_differences"):
                    enhanced_precedent_md += f"> Differs: {kd}\n"
                enhanced_precedent_md += "\n"

            # Pool-level composite finding
            _pool_finding = enhanced_prec.get("pool_composite_finding", "")
            if _pool_finding:
                enhanced_precedent_md += f"> **Pool-level finding:** {_pool_finding}\n\n"

        # a) Outcome Distribution Summary
        od = enhanced_prec.get("outcome_distribution", {})
        if od:
            enhanced_precedent_md += (
                f"\n### Outcome Distribution Summary\n\n"
                f"| Category | Count |\n|----------|-------|\n"
                f"| Supporting (same outcome) | {od.get('supporting', 0)} |\n"
                f"| Contrary (different outcome) | {od.get('contrary', 0)} |\n"
                f"| Neutral | {od.get('neutral', 0)} |\n"
                f"| **Total Decisive** | **{od.get('total', 0)}** |\n"
                f"| Typical Outcome for Cluster | {_md_escape(od.get('typical_outcome', 'N/A'))} |\n\n"
            )

        # b) Feature Comparison Matrix
        fcm = enhanced_prec.get("feature_comparison_matrix", [])
        if fcm:
            enhanced_precedent_md += "### Feature Comparison Matrix\n\n"
            enhanced_precedent_md += "*Top precedents compared by similarity feature. Differentiating features highlight where the dissimilarity lives.*\n\n"
            for entry in fcm:
                pid = _md_escape(entry.get("precedent_id", "N/A"))
                sim = entry.get("similarity_pct", 0)
                outcome = _md_escape(entry.get("outcome", "N/A"))
                cls = entry.get("classification", "neutral")
                matching = ", ".join(entry.get("matching_features", [])) or "None"
                differing = ", ".join(entry.get("differing_features", [])) or "None"
                enhanced_precedent_md += (
                    f"**{pid}** — {sim}% similarity · {outcome} · _{cls}_\n"
                    f"- Matching: {matching}\n"
                    f"- Differentiating: {differing}\n\n"
                )

        # c) Divergence Justification
        dj = enhanced_prec.get("divergence_justification")
        if dj:
            enhanced_precedent_md += "### Divergence Justification\n\n"
            enhanced_precedent_md += f"> **{_md_escape(dj.get('statement', ''))}**\n\n"
            contrary_details = dj.get("contrary_details", [])
            if contrary_details:
                enhanced_precedent_md += "| Contrary Precedent | Outcome | Similarity | Distinguishing Factors |\n"
                enhanced_precedent_md += "|-------------------|---------|------------|------------------------|\n"
                for cd in contrary_details:
                    diffs = "; ".join(cd.get("distinguishing_factors", []))
                    enhanced_precedent_md += (
                        f"| {_md_escape(cd.get('precedent_id', 'N/A'))} "
                        f"| {_md_escape(cd.get('outcome', 'N/A'))} "
                        f"| {cd.get('similarity_pct', 0)}% "
                        f"| {_md_escape(diffs)} |\n"
                    )
            enhanced_precedent_md += "\n"

        # d) Temporal Context
        tc = enhanced_prec.get("temporal_context", [])
        if tc:
            contrary_timestamps = [t for t in tc if t.get("classification") == "contrary" and t.get("timestamp")]
            if contrary_timestamps:
                enhanced_precedent_md += "### Temporal Context\n\n"
                enhanced_precedent_md += "*Contrary precedent decision dates — older cases may reflect superseded regulatory guidance.*\n\n"
                for t in contrary_timestamps[:5]:
                    enhanced_precedent_md += f"- **{_md_escape(t.get('precedent_id', 'N/A'))}**: {_md_escape(t.get('timestamp', 'N/A'))}\n"
                enhanced_precedent_md += "\n"

        # e) Precedent Override Statement
        override_stmt = enhanced_prec.get("override_statement")
        if override_stmt:
            enhanced_precedent_md += (
                "### Precedent Override Statement\n\n"
                "*This statement must be reviewed and approved by a compliance officer when the "
                "current decision diverges from precedent majority.*\n\n"
                f"> {_md_escape(override_stmt)}\n\n"
                "| | |\n|---|---|\n"
                "| Reviewer | _________________________ |\n"
                "| Date | _________________________ |\n"
                "| Signature | _________________________ |\n\n"
            )

    # Classification sections
    tier1_md = ""
    tier1_signals = ctx.get("tier1_signals", [])
    if tier1_signals:
        tier1_md = "### Tier 1 — Suspicion Indicators (RGS Contributors)\n\n| Code | Source | Detail |\n|------|--------|--------|\n"
        for sig in tier1_signals:
            tier1_md += f"| `{_md_escape(sig.get('code', ''))}` | {_md_escape(sig.get('source', ''))} | {_md_escape(sig.get('detail', ''))} |\n"

    tier2_md = ""
    tier2_signals = ctx.get("tier2_signals", [])
    if tier2_signals:
        tier2_md = "### Tier 2 — Investigative Signals (EDD Triggers)\n\n| Code | Source | Detail |\n|------|--------|--------|\n"
        for sig in tier2_signals:
            tier2_md += f"| `{_md_escape(sig.get('code', ''))}` | {_md_escape(sig.get('source', ''))} | {_md_escape(sig.get('detail', ''))} |\n"

    consistency_alert_md = ""
    if ctx.get("precedent_consistency_alert"):
        consistency_alert_md = f"> ⚠️ **PRECEDENT CONSISTENCY ALERT:** {_md_escape(ctx.get('precedent_consistency_detail', ''))}\n"

    # FIX-004: Integrity alert — reframe classifier override narrative
    integrity_alert_md = ""
    dia = ctx.get("decision_integrity_alert")
    if dia:
        severity_icon = "🚨" if dia.get("severity") == "CRITICAL" else "⚠️"
        if dia.get("type") == "CLASSIFIER_OVERRIDE":
            # FIX-004: Reframe as false-escalation prevention, not suppression
            override_label = " **[GOVERNANCE CORRECTION]**"
            original = dia.get("original_verdict", "STR")
            classifier_outcome = dia.get("classifier_outcome", "N/A")
            integrity_alert_md = (
                f"\n> {severity_icon} **DECISION INTEGRITY ALERT**{override_label}\n>\n"
                f"> Rule engine triggered {original} based on risk indicators. "
                f"Suspicion Classifier determined that Tier 1 suspicion indicators are below "
                f"the threshold required for escalation under the governance framework. "
                f"Disposition corrected to {classifier_outcome} — enhanced review is warranted "
                f"but escalation is not permitted under institutional policy without suspicion indicators. "
                f"This correction ensures escalation is consistent with suspicion threshold requirements "
                f"(PCMLTFA s. 7).\n"
            )
            if dia.get("original_verdict"):
                integrity_alert_md += (
                    f">\n> Original engine output: `{dia['original_verdict']}` → "
                    f"Governed outcome: `{dia.get('classifier_outcome', 'N/A')}`\n"
                )
        else:
            override_label = ""
            integrity_alert_md = (
                f"\n> {severity_icon} **DECISION INTEGRITY ALERT**{override_label}\n>\n"
                f"> {_md_escape(dia.get('message', ''))}\n"
            )
            if dia.get("original_verdict"):
                integrity_alert_md += (
                    f">\n> Original verdict: `{dia['original_verdict']}` → "
                    f"Classifier outcome: `{dia.get('classifier_outcome', 'N/A')}`\n"
                )
        integrity_alert_md += "\n"

    # FIX-013: Override Justification Block — PROMINENT position
    override_justification_md = ""
    oj = ctx.get("override_justification")
    if oj:
        oj_severity = oj.get("severity", "INFO")
        oj_icon = "🚨" if oj_severity == "CRITICAL" else "⚠️"
        override_justification_md = (
            f"\n## {oj_icon} Override Justification\n\n"
            f"**Override Type:** {_md_escape(oj.get('override_type', ''))}\n\n"
            f"| | |\n|---|---|\n"
            f"| Gate Overridden | **{_md_escape(oj.get('overridden_gate', ''))}** |\n"
            f"| Gate Decision | `{_md_escape(oj.get('gate_decision', ''))}` |\n"
            f"| Classifier Decision | `{_md_escape(oj.get('classifier_decision', ''))}` |\n"
            f"| Regulatory Basis | {_md_escape(oj.get('regulatory_basis', ''))} |\n\n"
        )
        # Gate deficiencies
        deficiencies = oj.get("gate_deficiencies", [])
        if deficiencies:
            override_justification_md += "### Gate Deficiency Detail\n\n"
            for deficiency in deficiencies:
                override_justification_md += (
                    f"- **{_md_escape(deficiency.get('section', ''))}**: "
                    f"{_md_escape(deficiency.get('reason', ''))}\n"
                )
            override_justification_md += "\n"

        # Justifying signals
        signals = oj.get("justifying_signals", [])
        if signals:
            override_justification_md += "### Justifying Tier 1 Signals\n\n"
            override_justification_md += "| Code | Source | Detail |\n|------|--------|--------|\n"
            for sig in signals:
                override_justification_md += (
                    f"| `{_md_escape(sig.get('code', ''))}` | "
                    f"{_md_escape(sig.get('source', ''))} | "
                    f"{_md_escape(sig.get('detail', ''))} |\n"
                )
            override_justification_md += "\n"

        # Justification narrative
        override_justification_md += (
            f"### Justification\n\n"
            f"> {_md_escape(oj.get('justification', ''))}\n\n"
            f"---\n\n"
        )

    # FIX-011: Deviation alert — v2 dual deviation model (Consistency + Defensibility)
    deviation_alert_md = ""
    pda = ctx.get("precedent_deviation_alert")
    if pda:
        severity = pda.get("severity", "INFO")
        severity_icon = "🚨" if severity == "CRITICAL" else "⚠️" if severity == "WARNING" else "ℹ️"

        # Disposition deviation → Consistency Check
        dd = pda.get("disposition_deviation")
        if dd:
            deviation_alert_md += (
                f"\n### Consistency Check (Disposition Deviation)\n\n"
                f"> {severity_icon} **CONSISTENCY WARNING**\n>\n"
                f"> Current Disposition: **{dd.get('case_disposition', 'N/A')}**\n>\n"
                f"> Scored Precedent Majority: **{dd.get('majority_disposition', 'N/A')}** "
                f"({dd.get('majority_pct', 0)}% of {dd.get('comparable_count', 0)} comparable)\n>\n"
                f"> Deviation Detected: **YES**\n>\n"
                f"> {_md_escape(dd.get('message', ''))}\n\n"
            )
        elif pda.get("supporting") is not None:
            # Fallback v1-style
            evaluated_disp = pda.get("evaluated_disposition", "N/A")
            deviation_alert_md += (
                f"\n### Consistency Check (Disposition Deviation)\n\n"
                f"> {severity_icon} **{_md_escape(pda.get('type', 'DEVIATION'))}**\n>\n"
                f"> {_md_escape(pda.get('message', ''))}\n>\n"
                f"> Supporting: {pda.get('supporting', 0)} · Contrary: {pda.get('contrary', 0)}"
                f" · Evaluated: {evaluated_disp}\n\n"
            )

        # Reporting deviation → Defensibility Alert
        rd = pda.get("reporting_deviation")
        if rd:
            deviation_alert_md += (
                f"\n### Defensibility Alert (Reporting Deviation)\n\n"
                f"> 🚨 **DEFENSIBILITY ALERT**\n>\n"
                f"> Reporting: {rd.get('case_reporting', 'N/A')} contradicts "
                f"{rd.get('more_severe_pct', 0)}% historical "
                f"{rd.get('dominant_precedent_reporting', 'N/A')} filing rate\n\n"
            )

        if pda.get("engine_note"):
            deviation_alert_md += f"> *{_md_escape(pda['engine_note'])}*\n"
        deviation_alert_md += "\n"
    else:
        # No deviation — explicitly state
        deviation_alert_md = (
            "\n### Consistency Check (Disposition Deviation)\n\n"
            "> No disposition deviation detected. Current governed outcome is "
            "consistent with scored precedent patterns.\n\n"
        )

    # ── Template ─────────────────────────────────────────────────────────
    md_template = """# AML/KYC Decision Report

**Deterministic Regulatory Decision Engine (Zero LLM)**

{senior_summary_md}---

## Administrative Details

| Field | Value |
|-------|-------|
| Decision ID | `{decision_id_short}...` |
| Case ID | `{case_id}` |
| Timestamp | `{timestamp}` |
| Jurisdiction | {jurisdiction} |
| Engine Version | `{engine_version}` |
| Policy Version | `{policy_version}` |
| Report Schema | `{report_schema_version}` |

---

## Investigation Outcome Summary

### Disposition Ladder

| | |
|---|---|
| **Final Disposition (Classifier Sovereign)** | **{governed_disposition_display}** |
| Engine Output (Rules Layer) | {engine_disposition_display} |
{disposition_note}
| Field | Value |
|-------|-------|
| Investigation State | {investigation_state} |
| Primary Typology | {primary_typology} |
| Regulatory Obligation | {regulatory_obligation} |
| Regulatory Position | {regulatory_position} |
| STR Required | {str_required_label} |

{decision_explainer}

{case_facts_md}

---

{decision_path_md}
## Canonical Outcome

*Authoritative three-field outcome record per v2 specification. All other sections must be consistent with these values.*

| Field | Value |
|-------|-------|
{canonical_outcome_md}

---

{integrity_alert_md}

{override_justification_md}

{required_actions_md}

{str_authority_md}

---

## Case Classification

| Field | Value |
|-------|-------|
| Source | {source_type} |
{seed_fields_md}
{seed_notice}

---

## Regulatory Determination

{decision_header}

{decision_explainer}

**STR Required:** {str_required_label}

### Regulatory Escalation Summary

{escalation_summary}

{decision_confidence_block}

{reconciliation_md}

{conflict_alert_md}

---

## Suspicion Classification

| Field | Value |
|-------|-------|
| Classifier Outcome | **{classification_outcome}** |
| Suspicion Indicators (Tier 1) | {suspicion_count} |
| Investigative Signals (Tier 2) | {investigative_count} |
| Classifier Version | `{classifier_version}` |

{classification_reason}

{tier1_md}

{tier2_md}

{consistency_alert_md}

---

## Decision Drivers

{decision_drivers_md}

---

## Gate Evaluation

### Gate 1: Zero-False-Escalation

**Decision:** {gate1_label}

| Section | Status | Reason |
|---------|--------|--------|
{gate1_rows_output}


### Gate 2: STR Threshold

**STR Required:** {str_required_label}

| Section | Status | Reason |
|---------|--------|--------|
{gate2_rows_output}

{gate_override_md}

---

## Rules Evaluated

| Rule Code | Result | Reason |
|-----------|--------|--------|
{rules_rows_output}

---

## Precedent Intelligence

{precedent_markdown}

{enhanced_precedent_md}

{divergence_md}

{regime_exception_md}

{deviation_alert_md}

{defensibility_md}

{unmapped_md}

---

## Risk Factors

| Field | Value |
|-------|-------|
{risk_factors_md}
{heatmap_note_md}

---

## Evidence Considered

*Evidence fields reflect the normalized investigation record used for rule evaluation (booleans and buckets). Raw customer identifiers are not included in this report.*

| Field | Scope | Value |
|-------|-------|-------|
{evidence_rows_output}

---

{edd_md}

{analyst_actions_md}

{timeline_md}

{related_activity_md}

## Auditability & Governance

### Decision Provenance

| Field | Value |
|-------|-------|
| Decision Hash | `{decision_id}` |
| Input Hash | `{input_hash}` |
| Policy Hash | `{policy_hash}` |
| Decision Path | `{safe_path}` |
| Engine Verdict (Raw) | `{engine_verdict}` |
| Governed Verdict | **{verdict}** |
| Engine Disposition | `{engine_disposition}` |
| Governed Disposition | **{governed_disposition}** |

This decision is cryptographically bound to the exact input and policy evaluated.

### Determinism & Auditability Statement

This decision was produced by a deterministic rule engine.
Re-evaluation using identical inputs and the same policy version will produce identical results.

The decision may be independently verified using the `/verify` endpoint. Complete decision lineage, rule sequencing, and evidentiary artifacts are preserved within the immutable audit record and available for supervisory review.

{governance_note}

---

*DecisionGraph — Deterministic - Reproducible - Auditable*

*Generated {timestamp}*
"""

    # Build case facts display: use structured sections if available, else flat table
    if case_facts_structured_md:
        case_facts_md = case_facts_structured_md
    else:
        case_facts_md = (
            "### Case Facts\n\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            + (facts_rows or "| No data available | - |\n")
        )

    # Only show seed fields for synthetic cases
    if ctx.get("is_seed"):
        seed_fields_md = (
            f"| Seed Category | {_md_escape(ctx.get('seed_category'))} |\n"
            f"| Scenario Code | `{_md_escape(ctx.get('scenario_code'))}` |"
        )
    else:
        seed_fields_md = ""

    return md_template.format(
        seed_fields_md=seed_fields_md,
        senior_summary_md=senior_summary_md,
        case_facts_md=case_facts_md,
        str_authority_md=str_authority_md,
        action=ctx.get("action"),
        engine_verdict=ctx.get("engine_verdict", ctx.get("action", "N/A")),
        canonical_outcome_md=canonical_outcome_md,
        case_id=ctx.get("case_id"),
        classification_outcome=ctx.get("classification_outcome", ""),
        classification_reason=ctx.get("classification_reason", ""),
        classifier_version=CLASSIFIER_VERSION,
        consistency_alert_md=consistency_alert_md,
        decision_explainer=ctx.get("decision_explainer"),
        decision_header=decision_header,
        decision_id=ctx.get("decision_id"),
        decision_id_short=ctx.get("decision_id_short"),
        decision_confidence_block=decision_confidence_block,
        decision_drivers_md=decision_drivers_md,
        decision_path_md=decision_path_md,
        defensibility_md=defensibility_md,
        deviation_alert_md=deviation_alert_md,
        edd_md=edd_md,
        analyst_actions_md=analyst_actions_md,
        engine_version=ctx.get("engine_version"),
        evidence_rows_output=evidence_rows_output,
        facts_rows=facts_rows,
        gate1_label=gate1_label,
        gate1_rows_output=gate1_rows_output,
        gate2_rows_output=gate2_rows_output,
        governance_note=governance_note,
        input_hash=ctx.get("input_hash"),
        integrity_alert_md=integrity_alert_md,
        override_justification_md=override_justification_md,
        investigative_count=ctx.get("investigative_count", 0),
        investigation_state=ctx.get("investigation_state", ""),
        jurisdiction=ctx.get("jurisdiction"),
        policy_hash=ctx.get("policy_hash"),
        policy_version=ctx.get("policy_version"),
        precedent_markdown=precedent_markdown,
        enhanced_precedent_md=enhanced_precedent_md,
        primary_typology=_md_escape(ctx.get("primary_typology", "")),
        regulatory_obligation=ctx.get("regulatory_obligation", "\u2014"),
        regulatory_position=ctx.get("regulatory_position", ""),
        report_schema_version=ctx.get("report_schema_version"),
        risk_factors_md=risk_factors_md,
        rules_rows_output=rules_rows_output,
        safe_path=safe_path,
        scenario_code=_md_escape(ctx.get("scenario_code")),
        seed_category=ctx.get("seed_category"),
        seed_notice=seed_notice,
        source_type=ctx.get("source_type"),
        str_required_label=str_required_label,
        suspicion_count=ctx.get("suspicion_count", 0),
        tier1_md=tier1_md,
        tier2_md=tier2_md,
        timeline_md=timeline_md,
        timestamp=ctx.get("timestamp"),
        verdict=ctx.get("verdict"),
        escalation_summary=ctx.get("escalation_summary"),
        engine_disposition=ctx.get("engine_disposition", "N/A"),
        governed_disposition=ctx.get("governed_disposition", "N/A"),
        governed_disposition_display=governed_display,
        engine_disposition_display=engine_display,
        disposition_note=disposition_note,
        gate_override_md=gate_override_md,
        reconciliation_md=reconciliation_md,
        conflict_alert_md=conflict_alert_md,
        divergence_md=divergence_md,
        unmapped_md=unmapped_md,
        regime_exception_md=regime_exception_md,
        heatmap_note_md=heatmap_note_md,
        required_actions_md=required_actions_md,
        related_activity_md=related_activity_md,
    )

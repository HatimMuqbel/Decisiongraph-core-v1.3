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

    return f"""*Precedent analysis is advisory and does not override the deterministic engine verdict.*
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
    facts_rows = ""
    for fact in ctx.get("transaction_facts", []):
        facts_rows += f"| {_md_escape(fact['field'])} | `{_md_escape(fact['value'])}` |\n"

    gate1_rows = ""
    for section in ctx.get("gate1_sections", []):
        status = "PASS" if section.get("passed") else "FAIL"
        gate1_rows += f"| {_md_escape(section.get('name', 'N/A'))} | {status} | {_md_escape(section.get('reason', ''))} |\n"

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
            "This correction prevents false escalation and preserves STR threshold integrity.\n"
        )
    safe_path = _md_escape(ctx["decision_path_trace"] or "N/A")

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
        decision_confidence_block = (
            f"### Confidence Metrics\n\n"
            f"| Metric | Value | Definition |\n"
            f"|--------|-------|------------|\n"
            f"| Decision Confidence | {ctx['decision_confidence']} ({ctx.get('decision_confidence_score', 0)}%) | "
            f"Composite score reflecting evidence completeness and rule alignment |\n"
            f"| Precedent Alignment | {prec_alignment}% | "
            f"supporting_decisive / count(decisive_precedents) within same basis |\n"
            f"| Precedent Match Rate | {match_rate}% ({scored_ct} / {total_pool}) | "
            f"Percentage of comparable pool meeting similarity threshold |\n\n"
            f"{ctx['decision_confidence_reason']}"
        )

    # ── FIX-003: Evidence with scope qualifiers ───────────────────────────
    _EVIDENCE_SCOPE_LABELS: dict[str, str] = {
        "risk.high_risk_jurisdiction": "Customer domicile jurisdiction risk",
        "txn.destination_country": "Transaction destination jurisdiction",
        "txn.cross_border": "Transaction cross-border indicator",
        "flag.cross_border": "Cross-border flag (transaction-level)",
        "customer.type": "Customer entity type",
        "customer.pep_flag": "Customer PEP status",
        "flag.pep": "PEP flag (customer-level)",
        "txn.amount_band": "Transaction amount band",
        "txn.method": "Payment method",
        "flag.structuring_suspected": "Structuring indicator (transaction pattern)",
        "flag.sanctions_proximity": "Sanctions screening proximity",
        "flag.adverse_media": "Adverse media indicator",
        "flag.rapid_movement": "Rapid fund movement indicator",
        "flag.shell_entity": "Shell entity indicator",
        "risk.risk_score": "Overall risk score",
    }

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
        "AML_ESC_HR_COUNTRY": ["txn.destination_country", "txn.cross_border"],
        "AML_ESC_PEP_SCREEN": ["flag.pep", "customer.pep_flag"],
        "AML_ESC_PEP": ["flag.pep", "customer.pep_flag"],
        "AML_ESC_STRUCT": ["flag.structuring_suspected", "txn.amount_band"],
        "AML_BLOCK_SANCTIONS": ["flag.sanctions_proximity"],
        "AML_INV_STRUCT": ["flag.structuring_suspected", "txn.amount_band"],
        "AML_STR_LAYER": ["flag.rapid_movement", "txn.method"],
        "AML_ESC_ADVERSE_MEDIA": ["flag.adverse_media"],
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

    precedent_markdown = _build_precedent_markdown(ctx.get("precedent_analysis", {}))

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
                f"but escalation is not justified without suspicion indicators. "
                f"This correction prevents false escalation and preserves STR threshold integrity "
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

---

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

### Case Facts

| Field | Value |
|-------|-------|
{facts_rows}

---

## Canonical Outcome

*Authoritative three-field outcome record per v2 specification. All other sections must be consistent with these values.*

| Field | Value |
|-------|-------|
{canonical_outcome_md}

---

{integrity_alert_md}

---

## Case Classification

| Field | Value |
|-------|-------|
| Source | {source_type} |
| Seed Category | {seed_category} |
| Scenario Code | `{scenario_code}` |

{seed_notice}

---

## Regulatory Determination

{decision_header}

{decision_explainer}

**STR Required:** {str_required_label}

### Regulatory Escalation Summary

{escalation_summary}

{decision_confidence_block}

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


---

## Rules Evaluated

| Rule Code | Result | Reason |
|-----------|--------|--------|
{rules_rows_output}

---

## Precedent Intelligence

{precedent_markdown}

{deviation_alert_md}

{defensibility_md}

---

## Risk Factors

| Field | Value |
|-------|-------|
{risk_factors_md}

---

## Evidence Considered

*Evidence fields reflect the normalized investigation record used for rule evaluation (booleans and buckets). Raw customer identifiers are not included in this report.*

| Field | Scope | Value |
|-------|-------|-------|
{evidence_rows_output}

---

{edd_md}

{timeline_md}

## Auditability & Governance

### Decision Provenance

| Field | Value |
|-------|-------|
| Decision Hash | `{decision_id}` |
| Input Hash | `{input_hash}` |
| Policy Hash | `{policy_hash}` |
| Decision Path | `{safe_path}` |
| Engine Trigger (Rules) | `{action}` |
| Engine Disposition | `{engine_disposition}` |
| Governed Disposition | `{governed_disposition}` |

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

    return md_template.format(
        action=ctx.get("action"),
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
        defensibility_md=defensibility_md,
        deviation_alert_md=deviation_alert_md,
        edd_md=edd_md,
        engine_version=ctx.get("engine_version"),
        evidence_rows_output=evidence_rows_output,
        facts_rows=facts_rows,
        gate1_label=gate1_label,
        gate1_rows_output=gate1_rows_output,
        gate2_rows_output=gate2_rows_output,
        governance_note=governance_note,
        input_hash=ctx.get("input_hash"),
        integrity_alert_md=integrity_alert_md,
        investigative_count=ctx.get("investigative_count", 0),
        investigation_state=ctx.get("investigation_state", ""),
        jurisdiction=ctx.get("jurisdiction"),
        policy_hash=ctx.get("policy_hash"),
        policy_version=ctx.get("policy_version"),
        precedent_markdown=precedent_markdown,
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
    )

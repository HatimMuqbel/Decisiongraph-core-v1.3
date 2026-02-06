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
    upheld_rate_pct = int((appeal.get("upheld_rate", 0) or 0) * 100)
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
        matches_md = "\n### Precedent Evidence (Top Matches)\n\n"
        for match in sample_cases:
            outcome_label = match.get("outcome_label") or _label(match.get("outcome"))
            similarity = f"{int(match.get('similarity_pct', 0) or 0)}%"
            if match.get("exact_match"):
                similarity += " EXACT"
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
                matches_md += f"Drivers: {driver_str}\n"
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

    return f"""*Precedent analysis is advisory and does not override the deterministic engine verdict.*
*Absence of precedent matches does not imply the recommendation is incorrect.*

| Metric | Value |
|--------|-------|
| Comparable Matches (Scored) | {match_count} |
| Raw Overlaps Found | {raw_overlap_count} |
| Candidates Scored | {candidates_scored} (≥{threshold_pct or min_similarity_pct}% similarity required; mode: {threshold_mode}) |
| Precedent Confidence | {confidence_pct}% |
| Exact Matches | {exact_match_count} |
| Supporting Precedents | {precedent_analysis.get('supporting_precedents', 0)} |
| Contrary Precedents | {precedent_analysis.get('contrary_precedents', 0)} |
| Neutral Precedents | {neutral} |

*Neutral indicates precedents where the outcome is a review/escalation state rather than a final pay/deny decision.*

{_md_escape(precedent_analysis.get("similarity_summary", ""))}

### Scored Match Outcome Distribution

| Outcome | Count |
|---------|-------|
{match_rows or "| No data | - |"}

{overlap_section}

{note_md}

### Appeal Statistics

| Metric | Value |
|--------|-------|
| Total Appealed | {appeal.get('total_appealed', 0)} |
| Upheld | {appeal.get('upheld', 0)} |
| Overturned | {appeal.get('overturned', 0)} |
| Upheld Rate | {upheld_rate_pct}% |
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

    rules_rows = ""
    for rule in ctx.get("rules_fired", []):
        rules_rows += f"| `{_md_escape(rule.get('code', 'N/A'))}` | {_md_escape(rule.get('result', 'N/A'))} | {_md_escape(rule.get('reason', ''))} |\n"

    evidence_rows = ""
    for ev in ctx.get("evidence_used", []):
        value = ev.get("value", "N/A")
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        evidence_rows += f"| `{_md_escape(ev.get('field', 'N/A'))}` | {_md_escape(value)} |\n"

    # Decision header
    if ctx["decision_status"] == "pass":
        decision_header = "### **PASS** — Transaction Allowed"
    elif ctx["decision_status"] == "escalate":
        decision_header = f"### **ESCALATE** — {ctx['action']}"
    else:
        decision_header = "### **REVIEW REQUIRED**"

    safe_path = _md_escape(ctx["decision_path_trace"] or "N/A")

    decision_confidence_block = ""
    if ctx.get("decision_confidence"):
        decision_confidence_block = (
            f"Decision Confidence: {ctx['decision_confidence']}\n\n"
            f"{ctx['decision_confidence_reason']}"
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
    evidence_rows_output = evidence_rows or "| No evidence recorded | - |"

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

    # Integrity alert
    integrity_alert_md = ""
    dia = ctx.get("decision_integrity_alert")
    if dia:
        severity_icon = "🚨" if dia.get("severity") == "CRITICAL" else "⚠️"
        override_label = " **[OVERRIDE APPLIED]**" if dia.get("type") == "CLASSIFIER_OVERRIDE" else ""
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

    # Deviation alert
    deviation_alert_md = ""
    pda = ctx.get("precedent_deviation_alert")
    if pda:
        severity_icon = "⚠️" if pda.get("severity") == "WARNING" else "ℹ️"
        deviation_alert_md = (
            f"\n> {severity_icon} **PRECEDENT DEVIATION SIGNAL**\n>\n"
            f"> {_md_escape(pda.get('message', ''))}\n"
            f">\n> Supporting: {pda.get('supporting', 0)} · Contrary: {pda.get('contrary', 0)}\n\n"
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

{integrity_alert_md}
{deviation_alert_md}
---

## Investigation Outcome Summary

| Field | Value |
|-------|-------|
| Regulatory Status | **{regulatory_status}** |
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


## Precedent Intelligence

{precedent_markdown}

## Risk Factors

| Field | Value |
|-------|-------|
{risk_factors_md}

---

## Evidence Considered

*Evidence fields reflect the normalized investigation record used for rule evaluation (booleans and buckets). Raw customer identifiers are not included in this report.*

| Field | Value |
|-------|-------|
{evidence_rows_output}

---

## Auditability & Governance

### Decision Provenance

| Field | Value |
|-------|-------|
| Decision Hash | `{decision_id}` |
| Input Hash | `{input_hash}` |
| Policy Hash | `{policy_hash}` |
| Decision Path | `{safe_path}` |
| Primary Trigger | `{action}` |

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
        case_id=ctx.get("case_id"),
        classification_outcome=ctx.get("classification_outcome", ""),
        classification_reason=ctx.get("classification_reason", ""),
        classifier_version=CLASSIFIER_VERSION,
        consistency_alert_md=consistency_alert_md,
        decision_explainer=ctx.get("decision_explainer"),
        decision_header=decision_header,
        decision_id=ctx.get("decision_id"),
        decision_id_short=ctx.get("decision_id_short"),
        decision_status_upper=ctx.get("decision_status", "").upper(),
        decision_confidence_block=decision_confidence_block,
        decision_drivers_md=decision_drivers_md,
        deviation_alert_md=deviation_alert_md,
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
        regulatory_status=ctx.get("regulatory_status", ""),
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
        timestamp=ctx.get("timestamp"),
        verdict=ctx.get("verdict"),
        escalation_summary=ctx.get("escalation_summary"),
    )

"""Report Bridge — Wire standalone scripts through the v2 report pipeline.

Standalone scripts (run_pep_pain_case.py, run_structuring_case.py, etc.) call
the escalation/STR gates directly and have their own local render_report()
functions.  The REPORT_V2_FIX_SPEC fixes (FIX-001 through FIX-012) live in the
four-stage API pipeline:

    normalize → derive → view_model → render_markdown

This bridge converts gate results into a decision_pack and passes it through
that pipeline so that standalone scripts produce the same v2-format report
served by the API.
"""

import sys
from pathlib import Path

# Ensure both src/ and project root are importable
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_project_root / "src") not in sys.path:
    sys.path.insert(0, str(_project_root / "src"))

from decisiongraph.decision_pack import build_decision_pack
from service.routers.report.normalize import normalize_decision
from service.routers.report.derive import derive_regulatory_model
from service.routers.report.view_model import build_view_model
from service.routers.report.render_md import render_markdown


def render_v2_report(
    *,
    case_id: str,
    inputs: dict,
    esc_result,
    str_result,
    final_decision: dict,
    jurisdiction: str = "CA",
    fintrac_indicators: list | None = None,
    precedent_analysis: dict | None = None,
    customer_data: dict | None = None,
    transaction_data: dict | None = None,
) -> str:
    """Build a decision_pack from gate results and render a v2 markdown report.

    Parameters
    ----------
    case_id : str
        Human-readable case identifier.
    inputs : dict
        The dict returned by build_case_inputs() in the standalone script.
        Must contain: facts, obligations, indicators, typology_maturity,
        mitigations, suspicion_evidence.
    esc_result : EscalationGateResult
        Return value of run_escalation_gate().
    str_result : STRGateResult
        Return value of run_str_gate().
    final_decision : dict
        Return value of dual_gate_decision().
    jurisdiction : str
        ISO jurisdiction code (default: CA).
    fintrac_indicators : list, optional
        FINTRAC indicator codes matched.
    precedent_analysis : dict, optional
        If available, precedent query results.
    customer_data : dict, optional
        Customer-level data (pep_flag, type, residence) for enriched evidence.
    transaction_data : dict, optional
        Transaction-level data (amount_cad, method, destination) for enriched
        evidence.

    Returns
    -------
    str
        Rendered Markdown report with all v2 fixes applied.
    """
    fintrac_indicators = fintrac_indicators or []
    customer_data = customer_data or {}
    transaction_data = transaction_data or {}

    # ── 1. Build canonical decision_pack ──────────────────────────────────
    input_data = {
        "facts": inputs.get("facts", {}),
        "obligations": inputs.get("obligations", []),
        "indicators": inputs.get("indicators", []),
        "typology_maturity": inputs.get("typology_maturity", ""),
        "mitigations": inputs.get("mitigations", []),
        "suspicion_evidence": inputs.get("suspicion_evidence", {}),
        "instrument_type": inputs.get("instrument_type", ""),
    }

    decision_pack = build_decision_pack(
        case_id=case_id,
        input_data=input_data,
        facts=inputs["facts"],
        obligations=inputs.get("obligations", []),
        indicators=inputs.get("indicators", []),
        typology_maturity=inputs.get("typology_maturity", "FORMING"),
        mitigations=inputs.get("mitigations", []),
        suspicion_evidence=inputs.get("suspicion_evidence", {}),
        esc_result=esc_result,
        str_result=str_result,
        final_decision=final_decision,
        jurisdiction=jurisdiction,
        fintrac_indicators=fintrac_indicators,
    )

    # ── 2. Enrich evidence with customer/transaction data ─────────────────
    evidence = decision_pack.get("evaluation_trace", {}).get("evidence_used", [])

    if customer_data.get("pep_flag") is not None:
        evidence.append({"field": "customer.pep_flag", "value": customer_data["pep_flag"]})
    if customer_data.get("type"):
        evidence.append({"field": "customer.type", "value": customer_data["type"]})
    if customer_data.get("residence"):
        evidence.append({"field": "risk.high_risk_jurisdiction", "value": False})

    if transaction_data.get("amount_cad") is not None:
        amt = transaction_data["amount_cad"]
        if amt >= 100_000:
            band = "100K+"
        elif amt >= 50_000:
            band = "50K-100K"
        elif amt >= 10_000:
            band = "10K-50K"
        else:
            band = "<10K"
        evidence.append({"field": "txn.amount_band", "value": band})
    if transaction_data.get("method"):
        evidence.append({"field": "txn.method", "value": transaction_data["method"]})
    if transaction_data.get("destination"):
        evidence.append({"field": "txn.destination_country", "value": transaction_data["destination"]})
    if transaction_data.get("cross_border") is not None:
        evidence.append({"field": "txn.cross_border", "value": transaction_data["cross_border"]})

    # ── 3. Enrich with customer/transaction data for view_model facts ─────
    layer1 = decision_pack.setdefault("layers", {}).setdefault("layer1_facts", {})
    facts_dict = layer1.setdefault("facts", {})
    if customer_data:
        facts_dict["customer"] = {
            "pep_flag": customer_data.get("pep_flag"),
            "type": customer_data.get("type"),
            "residence": customer_data.get("residence"),
        }
    if transaction_data:
        facts_dict["transaction"] = {
            "amount_cad": transaction_data.get("amount_cad"),
            "method": transaction_data.get("method"),
            "destination": transaction_data.get("destination"),
        }

    # ── 4. Attach precedent analysis (if available) ───────────────────────
    if precedent_analysis:
        decision_pack["precedent_analysis"] = precedent_analysis

    # ── 5. Run the 4-stage report pipeline ────────────────────────────────
    normalized = normalize_decision(decision_pack)
    derived = derive_regulatory_model(normalized)
    ctx = build_view_model(normalized, derived)
    markdown = render_markdown(ctx)

    return markdown

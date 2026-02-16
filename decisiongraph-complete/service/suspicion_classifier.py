"""SuspicionClassifier v1 — Deterministic Suspicion Framework.

FINTRAC-aligned, regulator-safe, production-grade.

Classifies all signals into three tiers:
  Tier 1 — Suspicion Indicators (RGS Contributors) → STR-capable
  Tier 2 — Investigative Signals (EDD Triggers) → EDD only
  Tier 3 — Normal Activity → No report

Master Decision Tree:
  IF suspicion_count >= 1 AND no verified mitigation → STR REQUIRED
  IF suspicion_count == 0 AND investigative_count >= 1 → EDD REQUIRED
  IF suspicion_count == 0 AND investigative_count == 0 → NO REPORT

This module is regulatory infrastructure. Version it. Govern it.
Never casually tweak thresholds. Treat it like policy — because it is.
"""

CLASSIFIER_VERSION = "SuspicionClassifier v1"

from dataclasses import dataclass, field

# ── Tier 1: Strong Suspicion Indicators (RGS Contributors) ──────────────────
# ANY ONE of these is sufficient for STR. These are not risk indicators —
# they are suspicion indicators under Reasonable Grounds to Suspect (RGS).

TIER1_SUSPICION_CODES: dict[str, str] = {
    # Evidence flags (from evaluation trace)
    "flag.structuring_suspected": "STRUCTURING_PATTERN",
    "flag.layering": "LAYERING",
    "flag.rapid_movement": "EVASION_BEHAVIOR",
    "flag.funnel_account": "FUNNEL",
    "flag.third_party_unexplained": "THIRD_PARTY_UNEXPLAINED",
    "flag.false_source": "FALSE_SOURCE",
    "flag.sanctions_proximity": "SANCTIONS_SIGNAL",
    "flag.adverse_media": "ADVERSE_MEDIA_CONFIRMED",
    "flag.shell_entity": "SHELL_ENTITY",
    "flag.evasion": "EVASION_BEHAVIOR",
    "flag.sar_pattern": "SAR_PATTERN",
    # Registry-keyed evidence (from Evidence Gap Tracker fields)
    "screening.sanctions_match": "SANCTIONS_SIGNAL",
    # screening.adverse_media (boolean) is now a derived convenience field.
    # Classification uses screening.adverse_media_level (value-based routing below).
    "flag.structuring": "STRUCTURING_PATTERN",
    "flag.shell_company": "SHELL_ENTITY",
    "flag.third_party": "THIRD_PARTY_UNEXPLAINED",
    "flag.unusual_for_profile": "EVASION_BEHAVIOR",
    # Typology codes (from layer4)
    "structuring": "STRUCTURING_PATTERN",
    "layering": "LAYERING",
    "funnel_account": "FUNNEL",
    "third_party": "THIRD_PARTY_UNEXPLAINED",
    "shell_entity": "SHELL_ENTITY",
    "smurfing": "STRUCTURING_PATTERN",
    "terrorist_financing": "TERRORIST_FINANCING",
    "trade_based": "TRADE_BASED_LAUNDERING",
    "virtual_asset": "VIRTUAL_ASSET_LAUNDERING",
    # Rule family codes
    "aml_inv_struct": "STRUCTURING_PATTERN",
    "aml_str_layer": "LAYERING",
    "aml_tpr_associated": "THIRD_PARTY_UNEXPLAINED",
    "aml_round_trip": "ROUND_TRIP",
    "aml_trade": "TRADE_BASED_LAUNDERING",
    "aml_shell": "SHELL_ENTITY",
    "aml_crypto": "VIRTUAL_ASSET_LAUNDERING",
    "sanctions_block": "SANCTIONS_SIGNAL",
}

# Suspicion element names (from layer6) that map to Tier 1
TIER1_SUSPICION_ELEMENTS: dict[str, str] = {
    "structuring": "STRUCTURING_PATTERN",
    "layering": "LAYERING",
    "rapid_movement": "EVASION_BEHAVIOR",
    "funnel": "FUNNEL",
    "shell": "SHELL_ENTITY",
    "evasion": "EVASION_BEHAVIOR",
    "false_source": "FALSE_SOURCE",
    "sanctions": "SANCTIONS_SIGNAL",
    "adverse_media": "ADVERSE_MEDIA_CONFIRMED",
    "terrorist": "TERRORIST_FINANCING",
    "trade_based": "TRADE_BASED_LAUNDERING",
    "sustained_pattern": "SUSTAINED_SUSPICIOUS_PATTERN",
}

# ── Tier 2: Investigative Signals (EDD Triggers) ────────────────────────────
# These do NOT justify STR alone. They require further investigation.

TIER2_INVESTIGATIVE_CODES: dict[str, str] = {
    "flag.cross_border": "CROSS_BORDER",
    "flag.pep": "PEP_EXPOSURE",
    "flag.crypto": "CRYPTO",
    "flag.high_value": "HIGH_VALUE",
    "flag.new_account": "NEW_ACCOUNT",
    "flag.cash_intensive": "CASH_INTENSIVE",
    "flag.dormant_reactivated": "DORMANT_REACTIVATED",
    "txn.cross_border": "CROSS_BORDER",
    "txn.amount_band": "HIGH_VALUE",
    "customer.type": "ENTITY_TYPE",
}

# High-risk geography keywords (Tier 2 — not Tier 1 without behavior)
_HIGH_RISK_GEO_KEYWORDS = frozenset({
    "iran", "north korea", "dprk", "syria", "myanmar", "yemen",
    "afghanistan", "libya", "somalia", "south sudan",
})


# ── Classification Result ────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """Immutable output of the SuspicionClassifier."""
    # Outcome
    outcome: str  # "STR_REQUIRED" | "EDD_REQUIRED" | "NO_REPORT"
    outcome_reason: str

    # Signal breakdown
    tier1_signals: list[dict] = field(default_factory=list)
    tier2_signals: list[dict] = field(default_factory=list)
    suspicion_count: int = 0
    investigative_count: int = 0

    # Mitigation
    mitigation_applied: bool = False
    mitigation_reason: str = ""

    # Governance
    precedent_consistency_alert: bool = False
    precedent_consistency_detail: str = ""

    # Metadata
    classifier_version: str = CLASSIFIER_VERSION

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "outcome_reason": self.outcome_reason,
            "tier1_signals": self.tier1_signals,
            "tier2_signals": self.tier2_signals,
            "suspicion_count": self.suspicion_count,
            "investigative_count": self.investigative_count,
            "mitigation_applied": self.mitigation_applied,
            "mitigation_reason": self.mitigation_reason,
            "precedent_consistency_alert": self.precedent_consistency_alert,
            "precedent_consistency_detail": self.precedent_consistency_detail,
            "classifier_version": self.classifier_version,
        }


# ── The Classifier ───────────────────────────────────────────────────────────

def classify(
    evidence_used: list[dict],
    rules_fired: list[dict],
    layer4_typologies: dict,
    layer6_suspicion: dict,
    layer1_facts: dict,
    precedent_analysis: dict | None = None,
    mitigations: list[dict] | None = None,
) -> ClassificationResult:
    """Classify all signals into Tier 1/2/3 and apply the master decision tree.

    This is the regulatory brain. It produces a defensible suspicion framework.
    Suspicion is qualitative by law — ANY single Tier 1 signal = STR.

    Args:
        evidence_used: Evaluation trace evidence fields
        rules_fired: Rules fired by the engine
        layer4_typologies: Typology layer output
        layer6_suspicion: Suspicion element layer output
        layer1_facts: Raw case facts (transaction, customer, screening)
        precedent_analysis: Precedent engine output (for consistency check)
        mitigations: Verified mitigations (e.g., confirmed legitimate source)

    Returns:
        ClassificationResult with deterministic outcome and full audit trail
    """
    tier1: list[dict] = []
    tier2: list[dict] = []
    seen_t1: set[str] = set()
    seen_t2: set[str] = set()

    # ── Scan evidence flags ──────────────────────────────────────────────
    for ev in (evidence_used or []):
        field_name = str(ev.get("field", "")).lower()
        value = ev.get("value")
        is_true = value is True or str(value).lower() in {"true", "yes", "1"}

        if field_name in TIER1_SUSPICION_CODES and is_true:
            code = TIER1_SUSPICION_CODES[field_name]
            if code not in seen_t1:
                tier1.append({
                    "code": code,
                    "source": "evidence",
                    "field": field_name,
                    "detail": f"Evidence flag {field_name} = {value}",
                })
                seen_t1.add(code)
        elif field_name in TIER2_INVESTIGATIVE_CODES and is_true:
            code = TIER2_INVESTIGATIVE_CODES[field_name]
            if code not in seen_t2:
                tier2.append({
                    "code": code,
                    "source": "evidence",
                    "field": field_name,
                    "detail": f"Evidence flag {field_name} = {value}",
                })
                seen_t2.add(code)
        # ── Adverse media level: value-based tier routing ──────────────
        elif field_name == "screening.adverse_media_level" and value:
            level = str(value).lower()
            if level == "confirmed_mltf":
                code = "ADVERSE_MEDIA_MLTF"
                if code not in seen_t1:
                    tier1.append({
                        "code": code,
                        "source": "evidence",
                        "field": field_name,
                        "detail": f"Adverse media: confirmed, linked to ML/TF",
                    })
                    seen_t1.add(code)
            elif level == "confirmed":
                code = "ADVERSE_MEDIA_CONFIRMED"
                if code not in seen_t1:
                    tier1.append({
                        "code": code,
                        "source": "evidence",
                        "field": field_name,
                        "detail": f"Adverse media: confirmed (charges/regulatory action)",
                    })
                    seen_t1.add(code)
            elif level == "unconfirmed":
                code = "ADVERSE_MEDIA_UNCONFIRMED"
                if code not in seen_t2:
                    tier2.append({
                        "code": code,
                        "source": "evidence",
                        "field": field_name,
                        "detail": f"Adverse media: unconfirmed (requires EDD investigation)",
                    })
                    seen_t2.add(code)
            # level == "none" → no signal
        # Tier 2: amount band — only high bands (100K+) are investigative signals.
        # Lower amounts are normal commercial activity and should not trigger EDD.
        elif field_name == "txn.amount_band" and value:
            _HIGH_BANDS = {"100k_500k", "500k_1m", "over_1m"}
            if str(value) in _HIGH_BANDS and "HIGH_VALUE" not in seen_t2:
                tier2.append({
                    "code": "HIGH_VALUE",
                    "source": "evidence",
                    "field": field_name,
                    "detail": f"Amount band: {value}",
                })
                seen_t2.add("HIGH_VALUE")

    # ── Scan typologies (layer4) ─────────────────────────────────────────
    typologies = layer4_typologies.get("typologies", []) or []
    for typ in typologies:
        name = typ.get("name") if isinstance(typ, dict) else str(typ)
        if not name:
            continue
        normalized = name.lower().replace(" ", "_").replace("-", "_")
        # Strip workflow prefixes
        for prefix in ("investigate_", "escalate_", "review_"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        if normalized in TIER1_SUSPICION_CODES:
            code = TIER1_SUSPICION_CODES[normalized]
            if code not in seen_t1:
                tier1.append({
                    "code": code,
                    "source": "typology",
                    "field": name,
                    "detail": f"Typology tag: {name}",
                })
                seen_t1.add(code)
        else:
            # Check partial matches
            for key, t1_code in TIER1_SUSPICION_CODES.items():
                if key in normalized and t1_code not in seen_t1:
                    tier1.append({
                        "code": t1_code,
                        "source": "typology",
                        "field": name,
                        "detail": f"Typology tag: {name} (matched {key})",
                    })
                    seen_t1.add(t1_code)
                    break

    # ── Scan suspicion elements (layer6) ─────────────────────────────────
    elements = layer6_suspicion.get("elements", {}) or {}
    for element, active in elements.items():
        if not active:
            continue
        normalized = element.lower().replace(" ", "_").replace("-", "_")
        matched = False
        for key, code in TIER1_SUSPICION_ELEMENTS.items():
            if key in normalized:
                # Matched to a known Tier 1 code — even if already seen
                # (duplicate from evidence), it is NOT unclassified.
                if code not in seen_t1:
                    tier1.append({
                        "code": code,
                        "source": "suspicion_element",
                        "field": element,
                        "detail": f"Suspicion element: {element}",
                    })
                    seen_t1.add(code)
                matched = True
                break
        if not matched:
            # FIX-014: Unclassified elements are NOT silently promoted to Tier 1.
            # Instead, flag as UNCLASSIFIED_GAP in Tier 2 with a governance flag
            # requiring manual review.  Silent Tier 1 promotion creates false
            # STR triggers and is a defensibility risk.
            generic_code = f"UNCLASSIFIED_{normalized.upper()}"
            if generic_code not in seen_t2:
                tier2.append({
                    "code": generic_code,
                    "source": "suspicion_element",
                    "field": element,
                    "detail": (
                        f"Suspicion element '{element}' could not be mapped to a "
                        f"known Tier 1 indicator code. Classified as Tier 2 "
                        f"(investigative) pending manual review. If this element "
                        f"represents genuine suspicion, a compliance officer must "
                        f"explicitly reclassify it."
                    ),
                    "classification_gap": True,
                    "requires_manual_review": True,
                })
                seen_t2.add(generic_code)

    # ── Scan triggered rules ─────────────────────────────────────────────
    for rule in (rules_fired or []):
        result = str(rule.get("result", "")).upper()
        if result not in {"TRIGGERED", "ACTIVATED", "FAIL", "FAILED"}:
            continue
        code = str(rule.get("code", "")).lower().replace("-", "_")
        if code in TIER1_SUSPICION_CODES:
            t1_code = TIER1_SUSPICION_CODES[code]
            if t1_code not in seen_t1:
                tier1.append({
                    "code": t1_code,
                    "source": "rule",
                    "field": code,
                    "detail": f"Triggered rule: {rule.get('code', '')} — {rule.get('reason', '')}",
                })
                seen_t1.add(t1_code)
        else:
            # Check partial match
            for key, t1_code in TIER1_SUSPICION_CODES.items():
                if key in code and t1_code not in seen_t1:
                    tier1.append({
                        "code": t1_code,
                        "source": "rule",
                        "field": code,
                        "detail": f"Triggered rule: {rule.get('code', '')} — {rule.get('reason', '')}",
                    })
                    seen_t1.add(t1_code)
                    break

    # ── Scan layer1 facts for Tier 2 context ─────────────────────────────
    txn = (layer1_facts or {}).get("transaction", {}) or {}
    customer = (layer1_facts or {}).get("customer", {}) or {}

    if txn.get("cross_border") and "CROSS_BORDER" not in seen_t2:
        tier2.append({
            "code": "CROSS_BORDER",
            "source": "facts",
            "field": "txn.cross_border",
            "detail": "Cross-border transaction",
        })
        seen_t2.add("CROSS_BORDER")

    destination = str(txn.get("destination", "")).lower()
    if destination and any(geo in destination for geo in _HIGH_RISK_GEO_KEYWORDS):
        if "HIGH_RISK_COUNTRY" not in seen_t2:
            tier2.append({
                "code": "HIGH_RISK_COUNTRY",
                "source": "facts",
                "field": "txn.destination",
                "detail": f"Destination: {txn.get('destination', '')}",
            })
            seen_t2.add("HIGH_RISK_COUNTRY")

    if customer.get("pep_flag") and "PEP_EXPOSURE" not in seen_t2:
        # PEP alone is Tier 2. PEP + anomaly would need a Tier 1 element.
        tier2.append({
            "code": "PEP_EXPOSURE",
            "source": "facts",
            "field": "customer.pep_flag",
            "detail": "Customer is a Politically Exposed Person",
        })
        seen_t2.add("PEP_EXPOSURE")

    method = str(txn.get("method", "")).lower()
    if method in {"crypto", "cryptocurrency", "virtual_asset"} and "CRYPTO" not in seen_t2:
        tier2.append({
            "code": "CRYPTO",
            "source": "facts",
            "field": "txn.method",
            "detail": f"Crypto / virtual asset channel: {txn.get('method', '')}",
        })
        seen_t2.add("CRYPTO")

    # ── PEP + Suspicion = Tier 1 upgrade ─────────────────────────────────
    # If PEP flag AND any other suspicion element → PEP becomes Tier 1
    if customer.get("pep_flag") and tier1:
        pep_t1_code = "PEP_ANOMALY"
        if pep_t1_code not in seen_t1:
            tier1.append({
                "code": pep_t1_code,
                "source": "composite",
                "field": "customer.pep_flag + suspicion",
                "detail": "PEP status combined with suspicion indicators",
            })
            seen_t1.add(pep_t1_code)

    # ── Combinatorial flag escalation ─────────────────────────────────────
    # Count active red flags across evidence to detect multi-flag patterns
    # that individually might not trigger but collectively indicate risk.
    _RED_FLAG_FIELDS = {
        "flag.structuring", "flag.layering", "flag.rapid_movement",
        "flag.shell_company", "flag.third_party", "flag.unusual_for_profile",
    }
    _active_flags: set[str] = set()
    for ev in (evidence_used or []):
        fn = str(ev.get("field", "")).lower()
        val = ev.get("value")
        _is_true = val is True or str(val).lower() in {"true", "yes", "1"}
        if fn in _RED_FLAG_FIELDS and _is_true:
            _active_flags.add(fn)

    _has_prior_issues = any(
        str(ev.get("field", "")).lower() == "prior.sars_filed"
        and ev.get("value") not in (0, "0", None, False)
        for ev in (evidence_used or [])
    ) or any(
        str(ev.get("field", "")).lower() == "prior.account_closures"
        and ev.get("value") in (True, "true", "True", "yes", "1")
        for ev in (evidence_used or [])
    )

    # COMBO_HIGH_RISK: 3+ flags + prior issues → Tier 1 (STR-capable)
    # NOTE: prior.sars_filed is a count with no temporal dimension — a single
    # resolved SAR from years ago looks the same as a recent SAR-for-cause.
    # Future refinement: add temporal weighting to prior issue assessment.
    if len(_active_flags) >= 3 and _has_prior_issues:
        _combo_code = "COMBO_HIGH_RISK_MULTI_FLAG"
        if _combo_code not in seen_t1:
            tier1.append({
                "code": _combo_code,
                "source": "composite",
                "field": ", ".join(sorted(_active_flags)),
                "detail": (
                    f"{len(_active_flags)} red flags active "
                    f"({', '.join(sorted(_active_flags))}) with prior issues. "
                    f"Combinatorial risk exceeds individual flag assessment."
                ),
            })
            seen_t1.add(_combo_code)

    # COMBO_MODERATE: 2+ flags + unusual_for_profile → Tier 2 (EDD only)
    elif len(_active_flags) >= 2 and "flag.unusual_for_profile" in _active_flags:
        _combo_code = "COMBO_MODERATE_MULTI_FLAG"
        if _combo_code not in seen_t2:
            tier2.append({
                "code": _combo_code,
                "source": "composite",
                "field": ", ".join(sorted(_active_flags)),
                "detail": (
                    f"{len(_active_flags)} red flags active with unusual profile. "
                    f"Combinatorial pattern warrants enhanced investigation."
                ),
            })
            seen_t2.add(_combo_code)

    # ── Trade finance composite indicators ──────────────────────────────
    # Scan evidence for trade-based ML indicators per FINTRAC TBML typology.
    _trade_goods_desc = None
    _trade_pricing_ok = None
    for ev in (evidence_used or []):
        fn = str(ev.get("field", "")).lower()
        val = ev.get("value")
        if fn == "trade.goods_description":
            _trade_goods_desc = str(val).lower() if val else None
        elif fn == "trade.pricing_consistent":
            _trade_pricing_ok = val is True or str(val).lower() in {"true", "yes", "1"}

    _goods_suspicious = _trade_goods_desc in ("vague", "missing")
    _pricing_suspicious = _trade_pricing_ok is False  # explicit False, not None

    # TRADE_BASED_LAUNDERING: both indicators → Tier 1 (STR-capable)
    if _goods_suspicious and _pricing_suspicious:
        _tbml_code = "TRADE_BASED_LAUNDERING"
        if _tbml_code not in seen_t1:
            tier1.append({
                "code": _tbml_code,
                "source": "composite",
                "field": "trade.goods_description, trade.pricing_consistent",
                "detail": (
                    f"Trade-based ML indicators: goods description is "
                    f"'{_trade_goods_desc}' and pricing is inconsistent. "
                    f"FINTRAC TBML typology — both indicators present."
                ),
            })
            seen_t1.add(_tbml_code)

    # TRADE_FINANCE_SUSPICIOUS: one indicator → Tier 2 (EDD only)
    elif _goods_suspicious or _pricing_suspicious:
        _tf_code = "TRADE_FINANCE_SUSPICIOUS"
        if _tf_code not in seen_t2:
            detail_parts = []
            if _goods_suspicious:
                detail_parts.append(f"goods description is '{_trade_goods_desc}'")
            if _pricing_suspicious:
                detail_parts.append("pricing is inconsistent")
            tier2.append({
                "code": _tf_code,
                "source": "composite",
                "field": "trade.goods_description, trade.pricing_consistent",
                "detail": (
                    f"Trade finance indicator: {' and '.join(detail_parts)}. "
                    f"Single indicator warrants enhanced investigation."
                ),
            })
            seen_t2.add(_tf_code)

    # ── MITIGATION CHECK (Safety Valve) ──────────────────────────────────
    # Verified legitimate explanation can downgrade Tier 1 to Tier 2
    mitigation_applied = False
    mitigation_reason = ""
    if tier1 and mitigations:
        for mitigation in mitigations:
            if mitigation.get("verified") and mitigation.get("evidence_type") in {
                "source_of_funds_confirmed",
                "legitimate_business_purpose",
                "regulatory_exemption",
                "compliance_officer_override",
            }:
                mitigation_applied = True
                mitigation_reason = (
                    f"Verified mitigation: {mitigation.get('evidence_type', '')} — "
                    f"{mitigation.get('detail', 'documented')}"
                )
                # Move all Tier 1 to Tier 2 (downgrade)
                for signal in tier1:
                    signal["downgraded"] = True
                    signal["mitigation"] = mitigation_reason
                    tier2.append(signal)
                tier1 = []
                seen_t1.clear()
                break

    suspicion_count = len(tier1)
    investigative_count = len(tier2)

    # ── MASTER DECISION TREE ─────────────────────────────────────────────

    # RULE 1: STR Override
    if suspicion_count >= 1:
        outcome = "STR_REQUIRED"
        outcome_reason = (
            f"{suspicion_count} suspicion indicator(s) detected. "
            "Reasonable Grounds to Suspect (RGS) threshold met. "
            "STR filing required under PCMLTFA/FINTRAC guidance."
        )
    # RULE 2: EDD Band
    elif investigative_count >= 1:
        outcome = "EDD_REQUIRED"
        outcome_reason = (
            f"{investigative_count} investigative signal(s) detected. "
            "Suspicion threshold not met. "
            "Enhanced Due Diligence required to determine regulatory outcome."
        )
    # RULE 3: Normal Band
    else:
        outcome = "NO_REPORT"
        outcome_reason = (
            "No suspicion or investigative signals detected. "
            "Transaction does not meet reporting or escalation thresholds."
        )

    # ── OVER-ESCALATION GUARDRAIL (Precedent Consistency Check) ──────────
    precedent_alert = False
    precedent_detail = ""
    if precedent_analysis and precedent_analysis.get("available"):
        supporting = int(precedent_analysis.get("supporting_precedents", 0) or 0)
        contrary = int(precedent_analysis.get("contrary_precedents", 0) or 0)

        if outcome == "STR_REQUIRED" and contrary > supporting and (supporting + contrary) > 0:
            precedent_alert = True
            precedent_detail = (
                f"Classifier recommends STR REQUIRED, but precedent majority "
                f"({contrary} contrary vs {supporting} supporting) diverges. "
                "Compliance officer review required."
            )
        elif outcome == "NO_REPORT" and supporting > 0 and contrary > supporting:
            precedent_alert = True
            precedent_detail = (
                f"Classifier recommends NO REPORT, but {contrary} of "
                f"{supporting + contrary} comparable precedents resulted in "
                "a different outcome. Consider additional review for consistency."
            )

    return ClassificationResult(
        outcome=outcome,
        outcome_reason=outcome_reason,
        tier1_signals=tier1,
        tier2_signals=tier2,
        suspicion_count=suspicion_count,
        investigative_count=investigative_count,
        mitigation_applied=mitigation_applied,
        mitigation_reason=mitigation_reason,
        precedent_consistency_alert=precedent_alert,
        precedent_consistency_detail=precedent_detail,
    )

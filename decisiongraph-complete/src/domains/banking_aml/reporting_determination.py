"""
Deterministic EDD Reporting Status Derivation (v3)

Given a set of case facts from a completed EDD review, deterministically
derives whether the case should result in STR filing or no report.

This is the SINGLE SOURCE OF TRUTH for post-EDD reporting determination.
Same facts → same outcome, every time.

Design:
- Uses canonical seed field names (customer.*, txn.*, flag.*, screening.*, prior.*)
- Splits moderate indicators into SUBSTANTIVE vs ADMINISTRATIVE tiers
- Requires direct rebuttal for clearing strong-clearable indicators
- Every determination is self-documenting via rationale string

Field Name Reference (canonical seed names):
  screening.adverse_media_level  : "none"|"unconfirmed"|"confirmed"|"confirmed_mltf"
  screening.adverse_media        : bool (derived from level)
  flag.shell_company             : bool
  flag.layering                  : bool
  flag.structuring               : bool
  flag.unusual_for_profile       : bool
  flag.rapid_movement            : bool
  flag.third_party               : bool
  txn.source_of_funds_clear      : bool
  txn.pattern_matches_profile    : bool
  txn.stated_purpose             : "personal"|"business"|"investment"|"gift"|"unclear"
  customer.high_risk_jurisdiction: bool
  customer.high_risk_industry    : bool
  customer.pep                   : bool
  customer.relationship_length   : "new"|"recent"|"established"
  prior.sars_filed               : int (0-4)
  prior.account_closures         : bool
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Indicator tier classification
# ---------------------------------------------------------------------------

SUBSTANTIVE_MODERATES: frozenset[str] = frozenset({
    "Unclear source of funds",
    "Activity unusual for profile",
    "Rapid movement of funds",
    "Unexplained third-party involvement",
    "Suspected threshold avoidance",
})

ADMINISTRATIVE_MODERATES: frozenset[str] = frozenset({
    "Missing/vague stated purpose",
    "Generic adverse media (uncorroborated)",
    "Prior STR history (no current behavioral flags)",
})

# ---------------------------------------------------------------------------
# Clearing relevance mapping — which clearings directly rebut which risks
# ---------------------------------------------------------------------------

CLEARING_RELEVANCE: dict[str, list[str]] = {
    "Adverse media corroborated by unusual behavior": [
        "No behavioral flags triggered",
        "Pattern matches historical profile",
    ],
    "Prior STR history corroborated by current behavior": [
        "No behavioral flags triggered",
        "Pattern matches historical profile",
        "Established customer history",
    ],
}


# ---------------------------------------------------------------------------
# Core determination function
# ---------------------------------------------------------------------------

def derive_reporting_status_and_rationale(
    facts: dict[str, Any],
) -> tuple[str, str]:
    """Derive post-EDD reporting status and rationale from case facts.

    Args:
        facts: Dict of canonical seed field names → values.

    Returns:
        Tuple of (reporting_status, reporting_rationale).
        reporting_status is one of: "FILE_STR", "NO_REPORT", "UNDETERMINED".
        reporting_rationale is a human-readable explanation.
    """
    strong_terminal: list[str] = []
    strong_clearable: list[str] = []
    moderate_indicators: list[str] = []
    clearing_indicators: list[str] = []

    # --- Behavioral risk assessment ---
    is_unusual = bool(facts.get("flag.unusual_for_profile"))
    has_behavioral_risk = (
        is_unusual
        or bool(facts.get("flag.rapid_movement"))
        or bool(facts.get("flag.third_party"))
        or bool(facts.get("flag.structuring"))
    )

    # =================================================================
    # 1. TERMINAL STRONG (un-clearable) — immediate STR
    # =================================================================

    # Confirmed ML/TF adverse media
    if facts.get("screening.adverse_media_level") == "confirmed_mltf":
        strong_terminal.append("Confirmed ML/TF adverse media")

    # Shell company obfuscation
    if facts.get("flag.shell_company"):
        strong_terminal.append("Shell company obfuscation")

    # Combined layering + structuring
    if facts.get("flag.layering") and facts.get("flag.structuring"):
        strong_terminal.append("Combined layering and structuring")

    # Prior closure with ongoing unusual activity
    if facts.get("prior.account_closures") and is_unusual:
        strong_terminal.append("Prior closure with ongoing unusual activity")

    # =================================================================
    # 2. CLEARABLE STRONG & MODERATES
    # =================================================================

    # Adverse media (non-MLTF) — strong if corroborated, moderate if not
    has_adverse_media = facts.get("screening.adverse_media") or (
        facts.get("screening.adverse_media_level", "none") not in ("none", None, False, "")
    )
    is_confirmed_mltf = facts.get("screening.adverse_media_level") == "confirmed_mltf"

    if has_adverse_media and not is_confirmed_mltf:
        if has_behavioral_risk:
            strong_clearable.append(
                "Adverse media corroborated by unusual behavior"
            )
        else:
            moderate_indicators.append(
                "Generic adverse media (uncorroborated)"
            )

    # Prior STR history — strong if corroborated, moderate if not
    prior_sars = facts.get("prior.sars_filed", 0)
    if isinstance(prior_sars, bool):
        prior_sars = 1 if prior_sars else 0
    if prior_sars > 0:
        if has_behavioral_risk:
            strong_clearable.append(
                "Prior STR history corroborated by current behavior"
            )
        else:
            moderate_indicators.append(
                "Prior STR history (no current behavioral flags)"
            )

    # --- SUBSTANTIVE MODERATES ---
    if not facts.get("txn.source_of_funds_clear", True):
        moderate_indicators.append("Unclear source of funds")

    if is_unusual:
        moderate_indicators.append("Activity unusual for profile")

    if facts.get("flag.rapid_movement"):
        moderate_indicators.append("Rapid movement of funds")

    if facts.get("flag.third_party"):
        moderate_indicators.append("Unexplained third-party involvement")

    if facts.get("flag.structuring") and not facts.get("flag.layering"):
        moderate_indicators.append("Suspected threshold avoidance")

    # --- ADMINISTRATIVE MODERATES ---
    stated_purpose = facts.get("txn.stated_purpose", "")
    purpose_is_unclear = stated_purpose in ("unclear", "missing", "", None)
    if purpose_is_unclear:
        moderate_indicators.append("Missing/vague stated purpose")

    # =================================================================
    # 3. CONTEXT BOOST (additive, capped at 2)
    # =================================================================
    context_boost = 0
    if facts.get("customer.high_risk_jurisdiction") or facts.get("customer.high_risk_industry"):
        context_boost += 1
    if facts.get("customer.pep"):
        context_boost += 1
    context_boost = min(context_boost, 2)

    # =================================================================
    # 4. CLEARING INDICATORS (ranked by rebuttal strength)
    # =================================================================
    if facts.get("txn.source_of_funds_clear"):
        clearing_indicators.append("Source of funds verified")

    if facts.get("txn.pattern_matches_profile"):
        clearing_indicators.append("Pattern matches historical profile")

    if not purpose_is_unclear and stated_purpose:
        clearing_indicators.append("Clear business rationale provided")

    has_flags = any(
        v for k, v in facts.items()
        if k.startswith("flag.") and v is True
    )
    if not has_flags:
        clearing_indicators.append("No behavioral flags triggered")

    rel = facts.get("customer.relationship_length", "")
    if rel == "established":
        clearing_indicators.append("Established customer history")

    # =================================================================
    # 5. DETERMINATION
    # =================================================================
    base_moderates = len(moderate_indicators)
    clearing_count = len(clearing_indicators)

    # --- A. Terminal Strong → immediate STR ---
    if len(strong_terminal) > 0:
        reasons = " and ".join(strong_terminal[:2])
        return (
            "FILE_STR",
            f"Reasonable grounds established via critical risk: {reasons}. "
            f"EDD confirmed suspicion.",
        )

    # --- B. Clearable Strong → STR unless directly rebutted ---
    if len(strong_clearable) > 0:
        if base_moderates == 0 and clearing_count >= 3:
            relevant = CLEARING_RELEVANCE.get(strong_clearable[0], [])
            has_rebuttal = any(c in relevant for c in clearing_indicators)
            if has_rebuttal:
                rebuttal = next(
                    c for c in clearing_indicators if c in relevant
                )
                # Pick two other clearings for the rationale
                others = [c for c in clearing_indicators if c != rebuttal]
                other_1 = others[0] if len(others) > 0 else "additional evidence"
                other_2 = others[1] if len(others) > 1 else "supporting factors"
                return (
                    "NO_REPORT",
                    f"Isolated risk ({strong_clearable[0]}) directly rebutted "
                    f"by {rebuttal}. {other_1} and {other_2} further support "
                    f"clearance. EDD cleared.",
                )
        # Default: STR for un-rebutted strong clearable
        return (
            "FILE_STR",
            f"Reasonable grounds established via: {strong_clearable[0]}. "
            f"Clearing indicators present but do not directly address the "
            f"identified risk. EDD confirmed.",
        )

    # --- C. Moderates + Context ---
    if base_moderates >= 2:
        reasons = ", ".join(moderate_indicators[:2])
        if context_boost > 0:
            return (
                "FILE_STR",
                f"Elevated risk factors ({reasons}) combined with "
                f"high-risk profile met suspicion threshold.",
            )
        return (
            "FILE_STR",
            f"Elevated risk factors ({reasons}) met suspicion threshold "
            f"during EDD.",
        )

    if base_moderates == 1 and context_boost == 2:
        if moderate_indicators[0] in SUBSTANTIVE_MODERATES:
            return (
                "FILE_STR",
                f"Elevated risk factors ({moderate_indicators[0]}) combined "
                f"with high-risk profile met suspicion threshold.",
            )
        else:
            # Administrative gap + context alone ≠ suspicion
            if clearing_count > 0:
                return (
                    "NO_REPORT",
                    f"Administrative gap ({moderate_indicators[0]}) noted but "
                    f"insufficient for suspicion finding despite elevated risk "
                    f"profile. {clearing_indicators[0]}. EDD found no "
                    f"substantive grounds.",
                )
            return (
                "NO_REPORT",
                f"Administrative gap ({moderate_indicators[0]}) noted but "
                f"insufficient for suspicion finding despite elevated risk "
                f"profile. EDD found no substantive grounds.",
            )

    # --- D. Cleared / Below Threshold ---
    if clearing_count > 0:
        if base_moderates == 1:
            return (
                "NO_REPORT",
                f"Minor risk factor ({moderate_indicators[0]}) mitigated by "
                f"{clearing_indicators[0]}. EDD found insufficient grounds "
                f"for STR.",
            )
        return (
            "NO_REPORT",
            f"Activity aligned with expectations ({clearing_indicators[0]}). "
            f"EDD found insufficient grounds for STR.",
        )

    # --- E. No indicators at all ---
    return (
        "NO_REPORT",
        "Review found no actionable suspicion indicators. "
        "Activity within risk appetite.",
    )


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "derive_reporting_status_and_rationale",
    "SUBSTANTIVE_MODERATES",
    "ADMINISTRATIVE_MODERATES",
    "CLEARING_RELEVANCE",
]

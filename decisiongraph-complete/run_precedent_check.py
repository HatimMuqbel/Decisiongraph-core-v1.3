#!/usr/bin/env python3
"""
Precedent History Check Report Demo

Demonstrates the heat map and consistency checking functionality
using mock precedent data for both insurance and banking scenarios.
"""

import sys
sys.path.insert(0, '.')

from src.decisiongraph.precedent_check_report import (
    HeatMapEntry,
    PrecedentHeatMap,
    ConsistencyCheck,
    PrecedentMatch,
    PrecedentHistoryReport,
)
from src.decisiongraph.cell import get_current_timestamp
from uuid import uuid4


def create_demo_heat_map(domain: str) -> PrecedentHeatMap:
    """Create a realistic demo heat map for the specified domain."""

    if domain == "insurance":
        # Insurance claim heat map entries
        entries = [
            HeatMapEntry(
                code="4.2.1",
                code_label="Commercial Use Exclusion",
                total_count=85,
                pay_count=5,
                deny_count=75,
                partial_count=3,
                escalate_count=2,
                appeal_count=14,
                overturn_count=2,
            ),
            HeatMapEntry(
                code="4.3.3",
                code_label="Impaired Operation",
                total_count=72,
                pay_count=1,
                deny_count=70,
                partial_count=0,
                escalate_count=1,
                appeal_count=11,
                overturn_count=1,
            ),
            HeatMapEntry(
                code="5.1.0",
                code_label="Failure to Cooperate",
                total_count=45,
                pay_count=12,
                deny_count=28,
                partial_count=3,
                escalate_count=2,
                appeal_count=8,
                overturn_count=3,
            ),
            HeatMapEntry(
                code="2.1.4",
                code_label="Named Perils - Collision",
                total_count=180,
                pay_count=155,
                deny_count=10,
                partial_count=10,
                escalate_count=5,
                appeal_count=6,
                overturn_count=1,
            ),
            HeatMapEntry(
                code="3.2.1",
                code_label="Property Damage - Theft",
                total_count=95,
                pay_count=70,
                deny_count=15,
                partial_count=8,
                escalate_count=2,
                appeal_count=4,
                overturn_count=2,
            ),
        ]
    else:  # banking/AML
        entries = [
            HeatMapEntry(
                code="RC-TXN-STRUCT",
                code_label="Structuring Indicators",
                total_count=120,
                pay_count=5,
                deny_count=0,
                partial_count=0,
                escalate_count=115,
                appeal_count=18,
                overturn_count=2,
            ),
            HeatMapEntry(
                code="RC-KYC-ID-MISMATCH",
                code_label="ID Document Mismatch",
                total_count=65,
                pay_count=8,
                deny_count=52,
                partial_count=0,
                escalate_count=5,
                appeal_count=12,
                overturn_count=3,
            ),
            HeatMapEntry(
                code="RC-SCR-FALSE-POS",
                code_label="False Positive - Cleared",
                total_count=320,
                pay_count=295,
                deny_count=5,
                partial_count=0,
                escalate_count=20,
                appeal_count=8,
                overturn_count=0,
            ),
            HeatMapEntry(
                code="RC-RPT-STR-REQ",
                code_label="STR Required",
                total_count=45,
                pay_count=0,
                deny_count=0,
                partial_count=0,
                escalate_count=45,
                appeal_count=5,
                overturn_count=1,
            ),
            HeatMapEntry(
                code="RC-MON-DORMANT",
                code_label="Dormant Account Reactivation",
                total_count=78,
                pay_count=45,
                deny_count=8,
                partial_count=0,
                escalate_count=25,
                appeal_count=6,
                overturn_count=2,
            ),
        ]

    return PrecedentHeatMap(
        entries=entries,
        generated_at=get_current_timestamp(),
        namespace_prefix=f"{domain}.precedents",
        total_precedents_analyzed=sum(e.total_count for e in entries),
    )


def create_demo_matches(codes: list, outcome: str) -> tuple:
    """Create demo precedent matches."""
    tier0 = []
    tier05 = []
    tier1 = []

    # Simulate some matches
    for i, code in enumerate(codes[:2]):
        # Tier 0.5 matches (same codes, same outcome)
        tier05.append(PrecedentMatch(
            precedent_id=str(uuid4()),
            match_tier=0.5,
            overlap_score=len(codes),
            outcome_code=outcome,
            decision_level="adjuster",
            decided_at="2025-11-15T10:30:00Z",
            appealed=False,
            appeal_outcome=None,
            anchor_facts_summary={
                "primary_code": code,
                "amount_band": "medium",
            },
        ))

    # Tier 1 matches (overlapping codes, different outcomes)
    for i in range(3):
        alt_outcome = "deny" if outcome == "pay" else "pay"
        tier1.append(PrecedentMatch(
            precedent_id=str(uuid4()),
            match_tier=1.0,
            overlap_score=1,
            outcome_code=alt_outcome if i % 2 == 0 else outcome,
            decision_level="manager" if i == 0 else "adjuster",
            decided_at=f"2025-{10+i}-01T09:00:00Z",
            appealed=i == 0,
            appeal_outcome="upheld" if i == 0 else None,
            anchor_facts_summary={
                "primary_code": codes[0] if codes else "unknown",
            },
        ))

    return tier0, tier05, tier1


def create_demo_report(
    domain: str,
    codes: list,
    proposed_outcome: str,
    code_labels: dict,
) -> PrecedentHistoryReport:
    """Create a demo precedent history report."""

    heat_map = create_demo_heat_map(domain)
    tier0, tier05, tier1 = create_demo_matches(codes, proposed_outcome)

    # Simulate consistency check
    all_matches = tier0 + tier05 + tier1
    supporting = sum(1 for m in all_matches if m.outcome_code == proposed_outcome)
    contrary = len(all_matches) - supporting

    # Determine consistency
    consistency_score = supporting / max(len(all_matches), 1)
    is_consistent = consistency_score >= 0.4

    warning_level = None
    warning_message = None
    requires_escalation = False

    if consistency_score < 0.3:
        warning_level = "critical"
        warning_message = f"Proposed '{proposed_outcome}' conflicts with {(1-consistency_score):.0%} of precedents"
        requires_escalation = True
    elif consistency_score < 0.6:
        warning_level = "caution"
        warning_message = f"Mixed precedent history ({consistency_score:.0%} support)"
    else:
        warning_level = "advisory"
        warning_message = "Decision aligns with precedent pattern"

    consistency_check = ConsistencyCheck(
        proposed_outcome=proposed_outcome,
        is_consistent=is_consistent,
        consistency_score=consistency_score,
        warning_level=warning_level,
        warning_message=warning_message,
        supporting_precedents=supporting,
        contrary_precedents=contrary,
        similar_cases_overturned=1 if contrary > 0 else 0,
        requires_escalation=requires_escalation,
        recommended_action="Proceed with confidence" if is_consistent else "Escalate for review",
    )

    warnings = []
    if not is_consistent:
        warnings.append("Decision may deviate from established precedent")

    # Check heat map for hot codes
    for code in codes:
        entry = heat_map.get_entry_by_code(code)
        if entry and entry.deny_rate > 0.7:
            warnings.append(f"Code {code} has {entry.deny_rate:.0%} historical deny rate")

    recommendations = [consistency_check.recommended_action]
    if tier0:
        recommendations.append(f"Review binding precedent {tier0[0].precedent_id[:8]}...")

    return PrecedentHistoryReport(
        report_id=str(uuid4()),
        generated_at=get_current_timestamp(),
        namespace_prefix=f"{domain}.precedents",
        fingerprint_hash=None,
        exclusion_codes_searched=codes,
        proposed_outcome=proposed_outcome,
        tier0_matches=tier0,
        tier05_matches=tier05,
        tier1_matches=tier1,
        heat_map=heat_map,
        consistency_check=consistency_check,
        total_precedents_found=len(tier0) + len(tier05) + len(tier1),
        has_binding_precedent=len(tier0) > 0,
        binding_precedent_id=tier0[0].precedent_id if tier0 else None,
        warnings=warnings,
        recommendations=recommendations,
    )


def main():
    print("=" * 70)
    print("PRECEDENT HISTORY CHECK REPORT DEMO")
    print("=" * 70)
    print()
    print("This demo shows the Heat Map and Consistency Check features")
    print("that enable decision-makers to validate against precedent history.")
    print()

    # Demo 1: Insurance - Commercial Use Denial
    print("-" * 70)
    print("SCENARIO 1: INSURANCE - Commercial Use Exclusion (Deny)")
    print("-" * 70)
    report = create_demo_report(
        domain="insurance",
        codes=["4.2.1", "5.1.0"],
        proposed_outcome="deny",
        code_labels={
            "4.2.1": "Commercial Use Exclusion",
            "5.1.0": "Failure to Cooperate",
        },
    )
    print(report.format_summary())
    print()

    # Demo 2: Insurance - Potentially inconsistent pay
    print("-" * 70)
    print("SCENARIO 2: INSURANCE - Commercial Use (Propose Pay - Inconsistent)")
    print("-" * 70)
    report = create_demo_report(
        domain="insurance",
        codes=["4.2.1"],
        proposed_outcome="pay",  # Against pattern
        code_labels={
            "4.2.1": "Commercial Use Exclusion",
        },
    )
    print(report.format_summary())
    print()

    # Demo 3: Banking - Structuring escalation
    print("-" * 70)
    print("SCENARIO 3: BANKING - Structuring Indicators (Escalate)")
    print("-" * 70)
    report = create_demo_report(
        domain="banking",
        codes=["RC-TXN-STRUCT", "RC-RPT-STR-REQ"],
        proposed_outcome="escalate",
        code_labels={
            "RC-TXN-STRUCT": "Structuring Indicators",
            "RC-RPT-STR-REQ": "STR Required",
        },
    )
    print(report.format_summary())
    print()

    # Demo 4: Banking - False positive cleared
    print("-" * 70)
    print("SCENARIO 4: BANKING - Screening False Positive (Pay/Clear)")
    print("-" * 70)
    report = create_demo_report(
        domain="banking",
        codes=["RC-SCR-FALSE-POS"],
        proposed_outcome="pay",
        code_labels={
            "RC-SCR-FALSE-POS": "False Positive - Cleared",
        },
    )
    print(report.format_summary())

    # Summary
    print()
    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print()
    print("The Precedent History Check Report provides:")
    print("  1. TIERED MATCHING:")
    print("     - Tier 0: Exact fingerprint match (binding precedent)")
    print("     - Tier 0.5: Same codes + same outcome")
    print("     - Tier 1: Overlapping codes (any outcome)")
    print()
    print("  2. HEAT MAP:")
    print("     - Shows outcome distribution by exclusion/reason code")
    print("     - Identifies 'hot' codes with high deny rates")
    print("     - Highlights codes with high appeal/overturn rates")
    print()
    print("  3. CONSISTENCY CHECK:")
    print("     - Validates proposed decision against precedent")
    print("     - Calculates consistency score (0-100%)")
    print("     - Issues warnings for potential inconsistencies")
    print("     - Recommends escalation when needed")
    print()
    print("This feature supports both Insurance (ClaimPilot) and Banking (AML)")
    print("domains, enabling consistent decision-making across all cases.")
    print()


if __name__ == "__main__":
    main()

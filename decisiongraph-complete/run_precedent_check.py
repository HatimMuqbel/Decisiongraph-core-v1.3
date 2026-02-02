#!/usr/bin/env python3
"""
Precedent History Check Report - Using REAL Seeds

This report uses ACTUAL seed data:
- Banking (AML): 2,000 seeds from generate_all_banking_seeds()
- Insurance (ClaimPilot): 2,150 seeds from generate_all_insurance_seeds()

NO MOCK DATA - Everything comes from real seed generators.
"""

import sys
sys.path.insert(0, '.')
sys.path.insert(0, '/workspaces/Decisiongraph-core-v1.3/claimpilot')

from collections import defaultdict
from src.decisiongraph import generate_all_banking_seeds
from src.decisiongraph.precedent_check_report import (
    HeatMapEntry,
    PrecedentHeatMap,
    ConsistencyCheck,
    PrecedentMatch,
    PrecedentHistoryReport,
)
from src.decisiongraph.cell import get_current_timestamp
from uuid import uuid4


def build_heat_map_from_seeds(seeds, namespace_prefix):
    """Build heat map from REAL seed data."""
    by_code = defaultdict(lambda: {
        'total': 0, 'pay': 0, 'deny': 0, 'partial': 0,
        'escalate': 0, 'appealed': 0, 'overturned': 0
    })

    for seed in seeds:
        # Use unique codes from both exclusion_codes and reason_codes (deduplicated)
        all_codes = set(seed.exclusion_codes) | set(seed.reason_codes)
        for code in all_codes:
            stats = by_code[code]
            stats['total'] += 1
            if seed.outcome_code == 'pay':
                stats['pay'] += 1
            elif seed.outcome_code == 'deny':
                stats['deny'] += 1
            elif seed.outcome_code == 'partial':
                stats['partial'] += 1
            elif seed.outcome_code == 'escalate':
                stats['escalate'] += 1
            if seed.appealed:
                stats['appealed'] += 1
                if seed.appeal_outcome == 'overturned':
                    stats['overturned'] += 1

    entries = []
    for code, stats in by_code.items():
        if stats['total'] >= 5:  # Only codes with 5+ cases
            entries.append(HeatMapEntry(
                code=code,
                code_label=code,
                total_count=stats['total'],
                pay_count=stats['pay'],
                deny_count=stats['deny'],
                partial_count=stats['partial'],
                escalate_count=stats['escalate'],
                appeal_count=stats['appealed'],
                overturn_count=stats['overturned'],
            ))

    entries.sort(key=lambda e: e.total_count, reverse=True)

    return PrecedentHeatMap(
        entries=entries,
        generated_at=get_current_timestamp(),
        namespace_prefix=namespace_prefix,
        total_precedents_analyzed=len(seeds),
    )


def find_matching_seeds(seeds, codes, outcome=None):
    """Find seeds matching given codes."""
    matches = []
    codes_set = set(codes)
    for seed in seeds:
        seed_codes = set(seed.exclusion_codes) | set(seed.reason_codes)
        overlap = seed_codes & codes_set
        if overlap:
            if outcome is None or seed.outcome_code == outcome:
                matches.append((seed, len(overlap)))
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def build_report(seeds, namespace, codes, proposed_outcome):
    """Build precedent check report from REAL seeds."""
    heat_map = build_heat_map_from_seeds(seeds, namespace)

    # Find matches
    tier05_matches = []
    tier1_matches = []

    exact = find_matching_seeds(seeds, codes, outcome=proposed_outcome)
    for seed, overlap in exact[:10]:
        tier05_matches.append(PrecedentMatch(
            precedent_id=seed.precedent_id,
            match_tier=0.5,
            overlap_score=overlap,
            outcome_code=seed.outcome_code,
            decision_level=seed.decision_level,
            decided_at=seed.decided_at,
            appealed=seed.appealed,
            appeal_outcome=seed.appeal_outcome,
            anchor_facts_summary={},
        ))

    all_matches = find_matching_seeds(seeds, codes, outcome=None)
    for seed, overlap in all_matches[:15]:
        if seed.precedent_id not in [m.precedent_id for m in tier05_matches]:
            tier1_matches.append(PrecedentMatch(
                precedent_id=seed.precedent_id,
                match_tier=1.0,
                overlap_score=overlap,
                outcome_code=seed.outcome_code,
                decision_level=seed.decision_level,
                decided_at=seed.decided_at,
                appealed=seed.appealed,
                appeal_outcome=seed.appeal_outcome,
                anchor_facts_summary={},
            ))

    all_found = tier05_matches + tier1_matches
    supporting = sum(1 for m in all_found if m.outcome_code == proposed_outcome)
    contrary = len(all_found) - supporting
    consistency_score = supporting / max(len(all_found), 1)

    if consistency_score < 0.3:
        warning_level, is_consistent = "critical", False
        warning_message = f"Proposed '{proposed_outcome}' conflicts with {(1-consistency_score):.0%} of precedents"
    elif consistency_score < 0.6:
        warning_level, is_consistent = "caution", True
        warning_message = f"Mixed precedent history ({consistency_score:.0%} support)"
    else:
        warning_level, is_consistent = "advisory", True
        warning_message = "Decision aligns with precedent pattern"

    consistency_check = ConsistencyCheck(
        proposed_outcome=proposed_outcome,
        is_consistent=is_consistent,
        consistency_score=consistency_score,
        warning_level=warning_level,
        warning_message=warning_message,
        supporting_precedents=supporting,
        contrary_precedents=contrary,
        similar_cases_overturned=sum(1 for m in all_found if m.appealed and m.appeal_outcome == 'overturned'),
        requires_escalation=not is_consistent,
        recommended_action="Proceed" if is_consistent else "Escalate",
    )

    warnings = []
    for code in codes:
        entry = heat_map.get_entry_by_code(code)
        if entry and entry.deny_rate > 0.7:
            warnings.append(f"Code {code} has {entry.deny_rate:.0%} deny rate")
        if entry and entry.escalate_rate > 0.7:
            warnings.append(f"Code {code} has {entry.escalate_rate:.0%} escalation rate")

    return PrecedentHistoryReport(
        report_id=str(uuid4()),
        generated_at=get_current_timestamp(),
        namespace_prefix=namespace,
        fingerprint_hash=None,
        exclusion_codes_searched=codes,
        proposed_outcome=proposed_outcome,
        tier0_matches=[],
        tier05_matches=tier05_matches,
        tier1_matches=tier1_matches,
        heat_map=heat_map,
        consistency_check=consistency_check,
        total_precedents_found=len(all_found),
        has_binding_precedent=False,
        binding_precedent_id=None,
        warnings=warnings,
        recommendations=[consistency_check.recommended_action],
    )


def main():
    print("=" * 70)
    print("PRECEDENT HISTORY CHECK REPORT")
    print("Using REAL Seed Data (NOT Mock)")
    print("=" * 70)
    print()

    # Load REAL seeds
    print("Loading seeds...")
    banking_seeds = generate_all_banking_seeds()
    print(f"  Banking (AML):     {len(banking_seeds):,} seeds")

    from claimpilot.precedent.cli import generate_all_insurance_seeds
    insurance_seeds = generate_all_insurance_seeds()
    print(f"  Insurance:         {len(insurance_seeds):,} seeds")
    print(f"  TOTAL:             {len(banking_seeds) + len(insurance_seeds):,} seeds")
    print()

    # ========================================
    # INSURANCE SCENARIOS
    # ========================================
    print("=" * 70)
    print("INSURANCE (ClaimPilot) - Using 2,150 REAL Seeds")
    print("=" * 70)
    print()

    # Insurance Scenario 1: Commercial Use Denial
    print("-" * 70)
    print("INSURANCE SCENARIO 1: Commercial Use Exclusion (Deny)")
    print("-" * 70)
    report = build_report(
        seeds=insurance_seeds,
        namespace="insurance.auto",
        codes=["4.2.1", "RC-4.2.1"],
        proposed_outcome="deny",
    )
    print(report.format_summary())
    print()

    # Insurance Scenario 2: Flood Exclusion
    print("-" * 70)
    print("INSURANCE SCENARIO 2: Flood Exclusion (Deny)")
    print("-" * 70)
    report = build_report(
        seeds=insurance_seeds,
        namespace="insurance.property",
        codes=["RC-FLOOD", "RC-FLOOD-SURFACE"],
        proposed_outcome="deny",
    )
    print(report.format_summary())
    print()

    # Insurance Scenario 3: Clean Approval
    print("-" * 70)
    print("INSURANCE SCENARIO 3: Clean Claim (Pay)")
    print("-" * 70)
    report = build_report(
        seeds=insurance_seeds,
        namespace="insurance.auto",
        codes=["RC-COV-CONFIRMED"],
        proposed_outcome="pay",
    )
    print(report.format_summary())
    print()

    # ========================================
    # BANKING SCENARIOS
    # ========================================
    print("=" * 70)
    print("BANKING (AML) - Using 2,000 REAL Seeds")
    print("=" * 70)
    print()

    # Banking Scenario 1: Structuring
    print("-" * 70)
    print("BANKING SCENARIO 1: Structuring (Escalate)")
    print("-" * 70)
    report = build_report(
        seeds=banking_seeds,
        namespace="banking.aml",
        codes=["RC-TXN-STRUCT", "RC-TXN-STRUCT-MULTI"],
        proposed_outcome="escalate",
    )
    print(report.format_summary())
    print()

    # Banking Scenario 2: Sanctions Hit
    print("-" * 70)
    print("BANKING SCENARIO 2: Sanctions Match (Deny)")
    print("-" * 70)
    report = build_report(
        seeds=banking_seeds,
        namespace="banking.aml",
        codes=["RC-SCR-SANCTION", "RC-SCR-OFAC"],
        proposed_outcome="deny",
    )
    print(report.format_summary())
    print()

    # Banking Scenario 3: False Positive
    print("-" * 70)
    print("BANKING SCENARIO 3: Screening False Positive (Pay)")
    print("-" * 70)
    report = build_report(
        seeds=banking_seeds,
        namespace="banking.aml",
        codes=["RC-SCR-FP", "RC-SCR-FP-NAME"],
        proposed_outcome="pay",
    )
    print(report.format_summary())

    # ========================================
    # SUMMARY
    # ========================================
    print()
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print()
    print("All reports use REAL seed data:")
    print(f"  - Banking seeds:   {len(banking_seeds):,} (from generate_all_banking_seeds)")
    print(f"  - Insurance seeds: {len(insurance_seeds):,} (from generate_all_insurance_seeds)")
    print()
    print("NO MOCK DATA USED")
    print("=" * 70)


if __name__ == "__main__":
    main()

"""
ClaimPilot Precedent System: CLI Module

Command-line interface for seed generation and verification.

Usage:
    python -m claimpilot.precedent.cli generate --all
    python -m claimpilot.precedent.cli verify
    python -m claimpilot.precedent.cli stats
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from .seed_generator import SeedGenerator, SeedConfig, CleanApprovalConfig
from .seeds import load_seed_config, load_all_seed_configs, list_seed_configs


def generate_all_seeds(salt: str = "claimpilot-seed-salt-2024") -> dict[str, Any]:
    """
    Generate all seed precedents and return statistics.

    Args:
        salt: Salt for deterministic generation

    Returns:
        Dict with generation statistics
    """
    generator = SeedGenerator(salt=salt)
    all_configs = load_all_seed_configs()

    results: dict[str, Any] = {
        "policy_packs": {},
        "totals": {
            "generated": 0,
            "denials": 0,
            "pays": 0,
            "appealed": 0,
            "overturned": 0,
            "boundary_cases": 0,
        },
    }

    for config_name, config in all_configs.items():
        # Extract config values
        schema_id = config.get("schema_id", "")
        jurisdiction = config.get("jurisdiction", "CA-ON")
        policy_pack_id = config.get("policy_pack_id", "")
        policy_version = config.get("policy_version", "1.0")

        # Infer policy type from schema_id
        # Formats: "claimpilot:oap1:auto:v1" (4 parts) or "claimpilot:cgl:v1" (3 parts)
        parts = schema_id.split(":")
        if len(parts) == 4:
            # Format: claimpilot:product:type:version (e.g., claimpilot:oap1:auto:v1)
            policy_type = parts[2]
        elif len(parts) == 3:
            # Format: claimpilot:type:version (e.g., claimpilot:cgl:v1)
            policy_type = parts[1]
        else:
            policy_type = "unknown"

        # Build SeedConfig list
        seed_configs = []
        for exclusion in config.get("exclusions", []):
            seed_configs.append(SeedConfig(
                exclusion_code=exclusion["code"],
                count=exclusion.get("count", 10),
                deny_rate=exclusion.get("deny_rate", 0.9),
                appeal_rate=exclusion.get("appeal_rate", 0.15),
                upheld_rate=exclusion.get("upheld_rate", 0.8),
                base_facts=exclusion.get("base_facts", {}),
                variable_facts=exclusion.get("variable_facts", {}),
                name=exclusion.get("name", ""),
            ))

        # Build clean approvals config
        clean_approvals = None
        if "clean_approvals" in config:
            ca = config["clean_approvals"]
            clean_approvals = CleanApprovalConfig(
                count=ca.get("count", 0),
                appeal_rate=ca.get("appeal_rate", 0.03),
                base_facts=ca.get("base_facts", {}),
                variable_facts=ca.get("variable_facts", {}),
            )

        # Generate precedents
        precedents = generator.generate_precedents(
            policy_type=policy_type,
            jurisdiction=jurisdiction,
            configs=seed_configs,
            policy_pack_id=policy_pack_id,
            policy_version=policy_version,
            clean_approvals=clean_approvals,
        )

        # Compute statistics
        denials = sum(1 for p in precedents if p.outcome_code == "deny")
        pays = sum(1 for p in precedents if p.outcome_code == "pay")
        appealed = sum(1 for p in precedents if p.appealed)
        overturned = sum(1 for p in precedents if p.appeal_outcome == "overturned")
        boundary = sum(1 for p in precedents if p.outcome_notable == "boundary_case")

        pack_stats = {
            "count": len(precedents),
            "denials": denials,
            "pays": pays,
            "appealed": appealed,
            "overturned": overturned,
            "boundary_cases": boundary,
            "policy_type": policy_type,
            "jurisdiction": jurisdiction,
        }

        results["policy_packs"][config_name] = pack_stats

        # Update totals
        results["totals"]["generated"] += len(precedents)
        results["totals"]["denials"] += denials
        results["totals"]["pays"] += pays
        results["totals"]["appealed"] += appealed
        results["totals"]["overturned"] += overturned
        results["totals"]["boundary_cases"] += boundary

    return results


def print_stats(results: dict[str, Any]) -> None:
    """Print generation statistics."""
    print("=" * 70)
    print("SEED PRECEDENT GENERATION REPORT")
    print("=" * 70)
    print()

    # Per-pack stats
    print("BY POLICY PACK")
    print("-" * 70)
    print(f"{'Pack':<15} {'Count':>8} {'Deny':>8} {'Pay':>8} {'Appeal':>8} {'Overturn':>8}")
    print("-" * 70)

    for pack_name in sorted(results["policy_packs"].keys()):
        stats = results["policy_packs"][pack_name]
        print(
            f"{pack_name:<15} "
            f"{stats['count']:>8} "
            f"{stats['denials']:>8} "
            f"{stats['pays']:>8} "
            f"{stats['appealed']:>8} "
            f"{stats['overturned']:>8}"
        )

    print("-" * 70)

    # Totals
    t = results["totals"]
    print(
        f"{'TOTAL':<15} "
        f"{t['generated']:>8} "
        f"{t['denials']:>8} "
        f"{t['pays']:>8} "
        f"{t['appealed']:>8} "
        f"{t['overturned']:>8}"
    )
    print()

    # Percentages
    total = t["generated"]
    if total > 0:
        print("DISTRIBUTION ANALYSIS")
        print("-" * 70)
        print(f"  Denial rate:     {t['denials']/total*100:5.1f}%")
        print(f"  Pay rate:        {t['pays']/total*100:5.1f}%")
        print(f"  Appeal rate:     {t['appealed']/total*100:5.1f}%")
        if t["appealed"] > 0:
            print(f"  Overturn rate:   {t['overturned']/t['appealed']*100:5.1f}% (of appeals)")
        print(f"  Boundary cases:  {t['boundary_cases']}")
        print()

    # Verification
    print("VERIFICATION")
    print("-" * 70)
    expected_total = 2150
    if total >= expected_total:
        print(f"  [PASS] Total precedents: {total} (expected >= {expected_total})")
    else:
        print(f"  [FAIL] Total precedents: {total} (expected >= {expected_total})")

    expected_appealed = 0.10  # At least 10%
    if total > 0 and t["appealed"] / total >= expected_appealed:
        print(f"  [PASS] Appeal rate: {t['appealed']/total*100:.1f}% (expected >= 10%)")
    else:
        print(f"  [FAIL] Appeal rate: {t['appealed']/total*100:.1f}% (expected >= 10%)")

    expected_overturn = 0.05  # At most 5%
    if total > 0 and t["overturned"] / total <= expected_overturn:
        print(f"  [PASS] Overturn rate: {t['overturned']/total*100:.1f}% (expected <= 5%)")
    else:
        print(f"  [FAIL] Overturn rate: {t['overturned']/total*100:.1f}% (expected <= 5%)")

    print()
    print("=" * 70)


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate seeds command."""
    print("Generating seed precedents...")
    print()

    results = generate_all_seeds(salt=args.salt)
    print_stats(results)

    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Show stats from config files."""
    all_configs = load_all_seed_configs()

    print("SEED CONFIGURATION SUMMARY")
    print("=" * 60)
    print()
    print(f"{'Config':<20} {'Exclusions':>12} {'Clean':>10} {'Total':>10}")
    print("-" * 60)

    grand_total = 0
    for name in sorted(all_configs.keys()):
        config = all_configs[name]
        exclusion_count = sum(e.get("count", 0) for e in config.get("exclusions", []))
        clean_count = config.get("clean_approvals", {}).get("count", 0)
        total = exclusion_count + clean_count
        grand_total += total
        print(f"{name:<20} {exclusion_count:>12} {clean_count:>10} {total:>10}")

    print("-" * 60)
    print(f"{'TOTAL':<20} {'':<12} {'':<10} {grand_total:>10}")
    print()

    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify seed generation."""
    print("Running seed verification...")
    print()

    results = generate_all_seeds(salt=args.salt)

    total = results["totals"]["generated"]
    errors = []

    # Check total count
    if total < 2150:
        errors.append(f"Total count {total} below expected 2150")

    # Check each pack has precedents
    for pack_name, stats in results["policy_packs"].items():
        if stats["count"] == 0:
            errors.append(f"Pack {pack_name} has 0 precedents")

    # Check appeal rate
    if total > 0:
        appeal_rate = results["totals"]["appealed"] / total
        if appeal_rate < 0.08:
            errors.append(f"Appeal rate {appeal_rate*100:.1f}% below expected 8%")

    # Print results
    if errors:
        print("VERIFICATION FAILED")
        print("-" * 40)
        for error in errors:
            print(f"  - {error}")
        return 1
    else:
        print("VERIFICATION PASSED")
        print("-" * 40)
        print(f"  Total precedents: {total}")
        print(f"  Appeal rate: {results['totals']['appealed']/total*100:.1f}%")
        print(f"  All policy packs have precedents")
        return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ClaimPilot Seed Precedent CLI",
        prog="python -m claimpilot.precedent.cli",
    )
    parser.add_argument(
        "--salt",
        default="claimpilot-seed-salt-2024",
        help="Salt for deterministic generation",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate all seed precedents")
    gen_parser.set_defaults(func=cmd_generate)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show seed configuration stats")
    stats_parser.set_defaults(func=cmd_stats)

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify seed generation")
    verify_parser.set_defaults(func=cmd_verify)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

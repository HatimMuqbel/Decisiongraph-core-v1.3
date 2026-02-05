#!/usr/bin/env python
"""Audit precedent distribution for seeded AML precedents."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from typing import Iterable, Tuple

from decisiongraph.aml_seed_generator import generate_all_banking_seeds


def _sorted_items(counter: Counter, limit: int | None) -> Iterable[Tuple[str, int]]:
    items = sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))
    if limit is not None:
        return items[:limit]
    return items


def _print_counter(title: str, counter: Counter, limit: int | None = None) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not counter:
        print("(no data)")
        return
    for key, count in _sorted_items(counter, limit):
        print(f"{key}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit precedent distribution")
    parser.add_argument("--top-scenarios", type=int, default=20, help="Max scenarios to list")
    parser.add_argument("--top-reasons", type=int, default=8, help="Top reason codes per scenario")
    args = parser.parse_args()

    seeds = generate_all_banking_seeds()

    by_source = Counter((s.source_type or "unknown") for s in seeds)
    by_category = Counter((s.seed_category or "unknown") for s in seeds)
    by_scenario = Counter((s.scenario_code or "unknown") for s in seeds)

    _print_counter("Counts by source_type", by_source)
    _print_counter("Counts by seed_category", by_category)
    _print_counter("Counts by scenario_code", by_scenario, limit=args.top_scenarios)

    reason_by_scenario: dict[str, Counter] = defaultdict(Counter)
    for seed in seeds:
        scenario = seed.scenario_code or "unknown"
        for code in seed.reason_codes or []:
            reason_by_scenario[scenario][code] += 1

    print("\nTop reason codes per scenario")
    print("-" * 30)
    for scenario, _count in _sorted_items(by_scenario, args.top_scenarios):
        reasons = reason_by_scenario.get(scenario, Counter())
        top_reasons = ", ".join(
            f"{code} ({count})" for code, count in _sorted_items(reasons, args.top_reasons)
        )
        print(f"{scenario}: {top_reasons or '(no reason codes)'}")


if __name__ == "__main__":
    main()

"""
Policy Simulation Engine — Phase C1
====================================
Simulate-before-enact: run proposed policy changes against the full
precedent pool and measure the impact *before* any change is live.

Key capabilities:
  1. Simulate a DraftShift against all matching seeds
  2. Compute cross-decision CASCADE impact on precedent pools
  3. Detect unintended consequences
  4. Compare multiple competing proposals side-by-side
  5. Generate enactment-ready shift definitions
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Kernel-internal imports
from kernel.policy.regime_partitioner import extract_case_signals, DISP_SEVERITY
from kernel.precedent.governed_confidence import compute_governed_confidence

# Banking-domain imports (will move to domains/banking_aml/ in Phase 2)
from decisiongraph.policy_shift_shadows import (
    POLICY_SHIFTS,
    compute_shadow_outcome,
)
from decisiongraph.banking_domain import create_banking_domain_registry


# ---------------------------------------------------------------------------
# Data Models (C1.1)
# ---------------------------------------------------------------------------

@dataclass
class DraftShift:
    """A proposed policy change, not yet enacted."""
    id: str
    name: str
    description: str
    parameter: str
    old_value: Any
    new_value: Any
    trigger_signals: list[str]
    affected_typologies: list[str]
    citation: str | None = None


@dataclass
class SimulationResult:
    """Result of simulating one case under the draft shift."""
    case_id: str
    original_disposition: str
    simulated_disposition: str
    original_reporting: str
    simulated_reporting: str
    disposition_changed: bool
    reporting_changed: bool
    escalation_direction: str  # "UP" / "DOWN" / "UNCHANGED"


@dataclass
class CascadeImpact:
    """How the policy change ripples through the precedent pool."""
    typology: str

    # Pool changes
    pool_before: dict[str, int]
    pool_after: dict[str, int]
    pool_size: int

    # Confidence shift
    confidence_before: str
    confidence_after: str
    confidence_direction: str  # "IMPROVED" / "DEGRADED" / "UNCHANGED"

    # Posture shift
    posture_before: str
    posture_after: str
    posture_reversal: bool

    # Pool adequacy for new regime
    post_shift_pool_size: int
    pool_adequacy: str  # "LOW" / "MODERATE" / "HIGH" / "VERY_HIGH"


@dataclass
class SimulationReport:
    """Aggregate impact of a draft policy shift."""
    draft: DraftShift
    timestamp: str

    # Population stats
    total_cases_evaluated: int
    affected_cases: int
    unaffected_cases: int

    # Disposition changes
    disposition_changes: dict[str, int]
    escalation_count: int
    de_escalation_count: int

    # Reporting changes
    reporting_changes: dict[str, int]
    new_str_filings: int
    new_lctr_filings: int

    # Risk distribution
    risk_before: dict[str, int]
    risk_after: dict[str, int]

    # Magnitude
    magnitude: str  # FUNDAMENTAL / SIGNIFICANT / MODERATE / MINOR

    # Workload impact
    additional_edd_cases: int
    additional_str_filings: int
    estimated_analyst_hours_month: float
    estimated_filing_cost_month: float

    # Cross-decision cascade impact
    cascade_impacts: list[CascadeImpact] = field(default_factory=list)

    # Unintended consequences
    warnings: list[str] = field(default_factory=list)

    # Per-case detail
    case_results: list[SimulationResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_V1_TO_DISPOSITION = {"pay": "ALLOW", "escalate": "EDD", "deny": "BLOCK"}


def _seed_disposition(seed: dict) -> str:
    """Extract canonical disposition from a seed dict."""
    outcome = seed.get("outcome", {})
    if outcome:
        return outcome.get("disposition", "UNKNOWN")
    # Fall back to outcome_code
    oc = seed.get("outcome_code", "")
    return _V1_TO_DISPOSITION.get(oc, oc)


def _seed_reporting(seed: dict) -> str:
    """Extract reporting obligation from a seed dict."""
    outcome = seed.get("outcome", {})
    if outcome:
        return outcome.get("reporting", "UNKNOWN")
    return seed.get("reporting_obligation", "UNKNOWN")


def _seed_facts_dict(seed: dict) -> dict:
    """Build flat {field_id: value} from a seed's anchor_facts."""
    return {
        af["field_id"]: af["value"]
        for af in seed.get("anchor_facts", [])
    }


def _posture_str(counts: dict[str, int]) -> str:
    """Human-readable posture string: '90% ALLOW, 10% EDD'."""
    total = sum(counts.values())
    if total == 0:
        return "EMPTY"
    parts = []
    for disp in ("ALLOW", "EDD", "BLOCK"):
        n = counts.get(disp, 0)
        if n > 0:
            pct = round(n / total * 100)
            parts.append(f"{pct}% {disp}")
    return ", ".join(parts) if parts else "UNKNOWN"


def _dominant_disposition(counts: dict[str, int]) -> str:
    """Return the disposition with the highest count."""
    if not counts:
        return "UNKNOWN"
    return max(counts, key=lambda k: counts[k])


def _pool_adequacy_label(size: int) -> str:
    """Categorize pool adequacy."""
    if size < 5:
        return "LOW"
    if size < 15:
        return "MODERATE"
    if size < 50:
        return "HIGH"
    return "VERY_HIGH"


def _classify_magnitude(
    affected: int, total: int,
    escalation_count: int, de_escalation_count: int,
    posture_reversals: int,
) -> str:
    """Classify the overall magnitude of the shift."""
    if total == 0:
        return "MINOR"
    pct = affected / total * 100
    if posture_reversals > 0 or pct > 30:
        return "FUNDAMENTAL"
    if escalation_count > 20 or pct > 15:
        return "SIGNIFICANT"
    if affected > 5 or pct > 5:
        return "MODERATE"
    return "MINOR"


# ---------------------------------------------------------------------------
# Simulation Engine (C1.2)
# ---------------------------------------------------------------------------

class PolicySimulator:
    """Simulate proposed policy changes against the precedent pool."""

    def __init__(self, seeds: list[dict], current_shifts: list[dict] | None = None):
        self.seeds = seeds
        self.current_shifts = current_shifts or POLICY_SHIFTS

    def simulate(self, draft: DraftShift) -> SimulationReport:
        """Run every relevant seed through the draft policy change."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Filter seeds matching draft.trigger_signals
        matching_seeds = []
        for seed in self.seeds:
            facts = _seed_facts_dict(seed)
            signals = extract_case_signals(facts)
            if any(sig in signals for sig in draft.trigger_signals):
                matching_seeds.append(seed)

        # 2. For each: compute original vs simulated disposition
        case_results: list[SimulationResult] = []
        disposition_changes: Counter[str] = Counter()
        reporting_changes: Counter[str] = Counter()
        risk_before: Counter[str] = Counter()
        risk_after: Counter[str] = Counter()
        escalation_count = 0
        de_escalation_count = 0

        for seed in matching_seeds:
            orig_disp = _seed_disposition(seed)
            orig_report = _seed_reporting(seed)
            risk_before[orig_disp] += 1

            # Simulate: apply the draft's effect
            sim_disp, sim_report = self._simulate_single(seed, draft)
            risk_after[sim_disp] += 1

            disp_changed = orig_disp != sim_disp
            report_changed = orig_report != sim_report

            # Determine escalation direction
            sev_before = DISP_SEVERITY.get(orig_disp, 0)
            sev_after = DISP_SEVERITY.get(sim_disp, 0)
            if sev_after > sev_before:
                direction = "UP"
                escalation_count += 1
            elif sev_after < sev_before:
                direction = "DOWN"
                de_escalation_count += 1
            else:
                direction = "UNCHANGED"

            if disp_changed:
                key = f"{orig_disp}\u2192{sim_disp}"
                disposition_changes[key] += 1

            if report_changed:
                key = f"{orig_report}\u2192{sim_report}"
                reporting_changes[key] += 1

            case_results.append(SimulationResult(
                case_id=seed.get("precedent_id", "unknown"),
                original_disposition=orig_disp,
                simulated_disposition=sim_disp,
                original_reporting=orig_report,
                simulated_reporting=sim_report,
                disposition_changed=disp_changed,
                reporting_changed=report_changed,
                escalation_direction=direction,
            ))

        # Count unaffected seeds too
        for seed in self.seeds:
            if seed not in matching_seeds:
                disp = _seed_disposition(seed)
                risk_before[disp] += 1
                risk_after[disp] += 1

        affected = sum(1 for r in case_results if r.disposition_changed or r.reporting_changed)
        unaffected = len(case_results) - affected

        # New STR/LCTR filings
        new_str = sum(
            1 for r in case_results
            if r.reporting_changed and "FILE_STR" in r.simulated_reporting
            and "FILE_STR" not in r.original_reporting
        )
        new_lctr = sum(
            1 for r in case_results
            if r.reporting_changed and "FILE_LCTR" in r.simulated_reporting
            and "FILE_LCTR" not in r.original_reporting
        )

        # Additional EDD cases
        additional_edd = sum(
            1 for r in case_results
            if r.disposition_changed and r.simulated_disposition == "EDD"
            and r.original_disposition != "EDD"
        )

        # 4. Compute CASCADE IMPACT
        cascade_impacts = self._compute_cascade(draft, case_results, matching_seeds)

        # 5. Detect unintended consequences
        warnings = self._detect_warnings(
            draft, case_results, matching_seeds, cascade_impacts, new_str,
        )

        # 6. Magnitude
        posture_reversals = sum(1 for c in cascade_impacts if c.posture_reversal)
        magnitude = _classify_magnitude(
            affected, len(self.seeds),
            escalation_count, de_escalation_count,
            posture_reversals,
        )

        # Workload impact
        estimated_analyst_hours = additional_edd * 2.5 + new_str * 1.5
        estimated_filing_cost = new_str * 150.0

        return SimulationReport(
            draft=draft,
            timestamp=timestamp,
            total_cases_evaluated=len(matching_seeds),
            affected_cases=affected,
            unaffected_cases=unaffected,
            disposition_changes=dict(disposition_changes),
            escalation_count=escalation_count,
            de_escalation_count=de_escalation_count,
            reporting_changes=dict(reporting_changes),
            new_str_filings=new_str,
            new_lctr_filings=new_lctr,
            risk_before=dict(risk_before),
            risk_after=dict(risk_after),
            magnitude=magnitude,
            additional_edd_cases=additional_edd,
            additional_str_filings=new_str,
            estimated_analyst_hours_month=estimated_analyst_hours,
            estimated_filing_cost_month=estimated_filing_cost,
            cascade_impacts=cascade_impacts,
            warnings=warnings,
            case_results=case_results,
        )

    def _simulate_single(
        self, seed: dict, draft: DraftShift,
    ) -> tuple[str, str]:
        """Compute simulated disposition + reporting for one seed.

        Reuses shadow outcome logic from policy_shift_shadows where the
        draft maps to an existing shift.  For novel drafts, applies rule-
        based simulation logic.
        """
        facts = _seed_facts_dict(seed)

        # Try to reuse existing shift shadow logic if the draft maps to one
        for shift in self.current_shifts:
            if shift["id"] == draft.parameter or shift["id"] == draft.id.replace("draft_", ""):
                shadow = compute_shadow_outcome(facts, shift["id"])
                if shadow is not None:
                    return (
                        shadow.get("disposition", _seed_disposition(seed)),
                        shadow.get("reporting", _seed_reporting(seed)),
                    )

        # Rule-based simulation for novel drafts
        orig_disp = _seed_disposition(seed)
        orig_report = _seed_reporting(seed)

        # Default escalation logic based on draft signals
        signals = extract_case_signals(facts)
        if any(sig in signals for sig in draft.trigger_signals):
            # Case 1: New mandatory requirement (didn't exist before)
            if draft.old_value is None and draft.new_value is not None:
                if orig_disp == "ALLOW":
                    return "EDD", "FILE_STR"
                if orig_report not in ("FILE_STR",):
                    return orig_disp, "FILE_STR"
                return orig_disp, orig_report

            # Case 2: Threshold lowered → stricter policy
            if draft.new_value is not None and draft.old_value is not None:
                try:
                    if float(draft.new_value) < float(draft.old_value):
                        if orig_disp == "ALLOW":
                            return "EDD", "PENDING_EDD"
                        if orig_disp == "EDD" and orig_report != "FILE_STR":
                            return "EDD", "FILE_STR"
                except (TypeError, ValueError):
                    pass

            # Case 3: Zero-tolerance — escalate everything
            if draft.new_value == 0 or draft.new_value is True:
                if orig_disp == "ALLOW":
                    return "EDD", "PENDING_EDD"

        return orig_disp, orig_report

    def _compute_cascade(
        self,
        draft: DraftShift,
        case_results: list[SimulationResult],
        matching_seeds: list[dict],
    ) -> list[CascadeImpact]:
        """Compute how the policy change ripples through the precedent pool."""
        # Group seeds by typology
        typology_seeds: dict[str, list[dict]] = {}
        for seed in matching_seeds:
            typology = seed.get("driver_typology", "") or seed.get("scenario_code", "general")
            typology_seeds.setdefault(typology, []).append(seed)

        # Build result-lookup by precedent_id
        result_lookup = {r.case_id: r for r in case_results}

        banking_domain = create_banking_domain_registry()
        cascades: list[CascadeImpact] = []

        for typology, seeds in typology_seeds.items():
            # Pool disposition counts BEFORE
            pool_before: Counter[str] = Counter()
            for s in seeds:
                pool_before[_seed_disposition(s)] += 1

            # Pool disposition counts AFTER (apply simulated changes)
            pool_after: Counter[str] = Counter()
            for s in seeds:
                pid = s.get("precedent_id", "")
                result = result_lookup.get(pid)
                if result and (result.disposition_changed or result.reporting_changed):
                    pool_after[result.simulated_disposition] += 1
                else:
                    pool_after[_seed_disposition(s)] += 1

            pool_size = sum(pool_before.values())

            # Compute governed confidence BEFORE and AFTER
            conf_before = self._pool_confidence(
                banking_domain, pool_before, pool_size,
            )
            conf_after = self._pool_confidence(
                banking_domain, pool_after, pool_size,
            )

            if conf_after > conf_before:
                conf_dir = "IMPROVED"
            elif conf_after < conf_before:
                conf_dir = "DEGRADED"
            else:
                conf_dir = "UNCHANGED"

            # Posture analysis
            posture_before = _posture_str(dict(pool_before))
            posture_after = _posture_str(dict(pool_after))
            dominant_before = _dominant_disposition(dict(pool_before))
            dominant_after = _dominant_disposition(dict(pool_after))
            posture_reversal = dominant_before != dominant_after

            cascades.append(CascadeImpact(
                typology=typology,
                pool_before=dict(pool_before),
                pool_after=dict(pool_after),
                pool_size=pool_size,
                confidence_before=conf_before,
                confidence_after=conf_after,
                confidence_direction=conf_dir,
                posture_before=posture_before,
                posture_after=posture_after,
                posture_reversal=posture_reversal,
                post_shift_pool_size=sum(pool_after.values()),
                pool_adequacy=_pool_adequacy_label(sum(pool_after.values())),
            ))

        return cascades

    def _pool_confidence(
        self, domain: Any, disposition_counts: Counter, pool_size: int,
    ) -> str:
        """Compute governed confidence level string for a pool."""
        if pool_size == 0:
            return "NONE"

        # Simulate: ALLOW is the "proposed" outcome for confidence calc
        decisive_total = disposition_counts.get("ALLOW", 0) + disposition_counts.get("BLOCK", 0)
        decisive_supporting = max(
            disposition_counts.get("ALLOW", 0),
            disposition_counts.get("BLOCK", 0),
        )
        avg_similarity = 0.75  # Typical pool average for cascade estimation

        # Build minimal case_facts for evidence completeness
        minimal_facts = {
            "txn.type": "wire_domestic",
            "txn.amount_band": "10k_25k",
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
            "screening.pep_match": False,
            "screening.adverse_media": False,
            "txn.cross_border": False,
            "customer.relationship_length": "established",
            "txn.stated_purpose": "bill_payment",
            "txn.destination_country_risk": "low",
        }

        result = compute_governed_confidence(
            domain=domain,
            pool_size=pool_size,
            avg_similarity=avg_similarity,
            decisive_supporting=decisive_supporting,
            decisive_total=decisive_total,
            case_facts=minimal_facts,
        )
        return result.level.value

    def compare(self, drafts: list[DraftShift]) -> list[SimulationReport]:
        """Run multiple competing proposals side-by-side."""
        return [self.simulate(d) for d in drafts]

    # ── Unintended Consequence Detection (C1.3) ──────────────────────

    def _detect_warnings(
        self,
        draft: DraftShift,
        case_results: list[SimulationResult],
        matching_seeds: list[dict],
        cascade_impacts: list[CascadeImpact],
        new_str_count: int,
    ) -> list[str]:
        """Check for unintended consequences."""
        warnings: list[str] = []

        # 1. Legitimate business blocked
        blocked_low_risk = 0
        for seed, result in zip(matching_seeds, case_results):
            if result.simulated_disposition == "BLOCK":
                facts = _seed_facts_dict(seed)
                cust_type = facts.get("customer.type", "")
                amount = facts.get("txn.amount_band", "")
                # Low-risk indicators
                if cust_type in ("individual",) and amount in ("under_3k", "3k_10k"):
                    blocked_low_risk += 1
                if facts.get("txn.pattern_matches_profile") and facts.get("txn.source_of_funds_clear"):
                    blocked_low_risk += 1
        if blocked_low_risk > 0:
            warnings.append(
                f"{blocked_low_risk} low-risk cases would be blocked. "
                "Review for false positives."
            )

        # 2. Disproportionate segment impact
        if matching_seeds:
            segment_counts: Counter[str] = Counter()
            _segment_fields = (
                "customer.type", "txn.type", "driver_typology",
                "customer.pep", "screening.pep_match",
                "screening.sanctions_match", "txn.cross_border",
            )
            for seed in matching_seeds:
                facts = _seed_facts_dict(seed)
                for key in _segment_fields:
                    val = facts.get(key) or seed.get(key, "")
                    if val and val is not False:
                        segment_counts[f"{key}={val}"] += 1
            total_affected = len(matching_seeds)
            for segment, count in segment_counts.most_common(3):
                if count / total_affected > 0.80:
                    warnings.append(
                        f"Impact concentrated on [{segment}] "
                        f"({count}/{total_affected} cases)."
                    )

        # 3. STR volume spike
        if new_str_count > 20:
            warnings.append(
                f"STR filing volume would increase by {new_str_count}. "
                "Assess FINTRAC capacity."
            )
        elif new_str_count > 0:
            warnings.append(
                f"STR filing volume would increase by {new_str_count}."
            )

        # 4. Empty post-shift pool
        for ci in cascade_impacts:
            if ci.post_shift_pool_size < 5:
                warnings.append(
                    f"Minimal institutional precedent under proposed policy "
                    f"for typology [{ci.typology}] "
                    f"(only {ci.post_shift_pool_size} cases)."
                )

        # 5. De-escalation risk
        de_escalated = [
            r for r in case_results if r.escalation_direction == "DOWN"
        ]
        if de_escalated:
            warnings.append(
                f"{len(de_escalated)} cases de-escalated. "
                "Review for under-reporting risk."
            )

        # 6. Cascade confidence degradation
        for ci in cascade_impacts:
            if ci.confidence_direction == "DEGRADED":
                warnings.append(
                    f"Governed confidence for [{ci.typology}] would degrade "
                    f"from {ci.confidence_before} to {ci.confidence_after}. "
                    "Institutional guidance becomes less reliable."
                )

        # 7. Posture reversal
        for ci in cascade_impacts:
            if ci.posture_reversal:
                warnings.append(
                    f"Institutional posture for [{ci.typology}] would reverse "
                    f"from majority {_dominant_disposition(ci.pool_before)} to "
                    f"majority {_dominant_disposition(ci.pool_after)}. "
                    "This is a FUNDAMENTAL change in institutional practice."
                )

        return warnings

    # ── Enactment Flow (C1.6) ────────────────────────────────────────

    def enact(self, draft: DraftShift, simulation: SimulationReport) -> dict:
        """Return the shift definition that WOULD be added.

        Does NOT modify live data — returns a dict ready for review/approval.
        """
        cascade_summary = {}
        for ci in simulation.cascade_impacts:
            cascade_summary[ci.typology] = {
                "confidence": f"{ci.confidence_before}\u2192{ci.confidence_after}",
                "posture_reversal": ci.posture_reversal,
            }

        return {
            "shift_id": draft.id.replace("draft_", ""),
            "name": draft.name,
            "effective_date": datetime.now(timezone.utc).isoformat(),
            "parameter": draft.parameter,
            "new_value": draft.new_value,
            "trigger_signals": draft.trigger_signals,
            "citation": draft.citation,
            "simulation_id": simulation.timestamp,
            "cases_affected": simulation.affected_cases,
            "cascade_summary": cascade_summary,
            "magnitude": simulation.magnitude,
            "warnings_count": len(simulation.warnings),
            "status": "READY_TO_ENACT",
        }


# ---------------------------------------------------------------------------
# Pre-Built Demo Drafts (C1.4)
# ---------------------------------------------------------------------------

DEMO_DRAFTS: list[DraftShift] = [
    DraftShift(
        id="draft_crypto_str_mandatory",
        name="Mandatory STR for All Crypto >$10K",
        description=(
            "All crypto transactions above $10K require automatic STR "
            "filing regardless of other risk factors"
        ),
        parameter="crypto_str_threshold",
        old_value=None,
        new_value=10000,
        trigger_signals=["VIRTUAL_ASSET_TRANSACTION", "VIRTUAL_ASSET_LAUNDERING"],
        affected_typologies=["virtual_asset_laundering"],
        citation="Proposed FINTRAC Guideline 5 amendment",
    ),
    DraftShift(
        id="draft_cross_border_edd",
        name="EDD for All Cross-Border >$50K",
        description=(
            "All cross-border transactions above $50K require "
            "enhanced due diligence"
        ),
        parameter="cross_border_edd_threshold",
        old_value=100000,
        new_value=50000,
        trigger_signals=["CROSS_BORDER", "HIGH_VALUE"],
        affected_typologies=[
            "cross_border_structuring",
            "correspondent_banking_layering",
        ],
        citation="OSFI B-10 guideline update",
    ),
    DraftShift(
        id="draft_pep_zero_tolerance",
        name="Zero Tolerance PEP Policy",
        description=(
            "Any PEP involvement regardless of amount triggers "
            "mandatory senior management review and EDD"
        ),
        parameter="pep_escalation_threshold",
        old_value=25000,
        new_value=0,
        trigger_signals=["PEP_MATCH", "PEP_FOREIGN_DOMESTIC"],
        affected_typologies=["pep_foreign_domestic", "pep_associated_person"],
        citation="PCMLTFA s.9.3 enhanced interpretation",
    ),
]


# Lookup by ID
DEMO_DRAFTS_BY_ID: dict[str, DraftShift] = {d.id: d for d in DEMO_DRAFTS}


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "DraftShift",
    "SimulationResult",
    "CascadeImpact",
    "SimulationReport",
    "PolicySimulator",
    "DEMO_DRAFTS",
    "DEMO_DRAFTS_BY_ID",
]

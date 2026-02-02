"""
DecisionGraph Banking/AML Precedent System: Seed Generator Module

This module generates realistic seed precedents for the AML/Banking
domain based on YAML configuration files.

Key components:
- SeedConfig: Configuration for generating seeds for one scenario
- SeedGenerator: Generates realistic seed precedents from configuration
- SeedLoader: Loads seed precedents into a DecisionGraph chain

Design Principles:
- Deterministic: Same seed + same config = same precedents
- Configurable: YAML-driven scenario definitions
- Realistic: Follows real-world distribution of outcomes and appeals

Generated Precedent Counts (per BANKING_SEED_SPEC.md):
- Transaction Monitoring: 700 precedents
- KYC Onboarding: 450 precedents
- Reporting: 200 precedents
- Sanctions/Screening: 350 precedents
- Ongoing Monitoring: 300 precedents
- Total: 2,000 precedents

Example:
    >>> generator = SeedGenerator(fingerprint_registry, reason_registry, salt="seed-salt")
    >>> precedents = generator.generate_from_config(config)
    >>> loader = SeedLoader(chain, salt="seed-salt")
    >>> count = loader.load_precedents(precedents)
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .aml_fingerprint import AMLFingerprintSchemaRegistry
from .aml_reason_codes import AMLReasonCodeRegistry
from .judgment import JudgmentPayload, AnchorFact, compute_case_id_hash


# =============================================================================
# Exceptions
# =============================================================================

class SeedGeneratorError(Exception):
    """Base exception for seed generator errors."""
    pass


class SeedConfigError(SeedGeneratorError):
    """Raised when seed configuration is invalid."""
    pass


class SeedLoadError(SeedGeneratorError):
    """Raised when seed loading fails."""
    pass


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class SeedScenario:
    """
    Configuration for generating seeds for one scenario type.

    Attributes:
        code: Unique scenario code (e.g., "TXN-STRUCT-10K")
        name: Human-readable name
        reason_codes: List of reason codes for this scenario
        count: Number of precedents to generate
        outcome: Primary outcome (approve, deny, escalate, investigate, etc.)
        base_facts: Facts that are constant for this scenario
        variable_facts: Facts that vary (dict of field -> list of possible values)
        deny_rate: Rate of denials (0.0-1.0)
        appeal_rate: Rate of appeals (0.0-1.0)
        upheld_rate: Rate of upheld appeals (0.0-1.0)
    """
    code: str
    name: str
    reason_codes: list[str]
    count: int
    outcome: str
    base_facts: dict[str, Any] = field(default_factory=dict)
    variable_facts: dict[str, list[Any]] = field(default_factory=dict)
    deny_rate: float = 0.0
    appeal_rate: float = 0.10
    upheld_rate: float = 0.85

    def __post_init__(self) -> None:
        """Validate scenario on construction."""
        if not self.code:
            raise SeedConfigError("code cannot be empty")
        if not self.name:
            raise SeedConfigError("name cannot be empty")
        if self.count < 1:
            raise SeedConfigError("count must be at least 1")
        if not 0.0 <= self.deny_rate <= 1.0:
            raise SeedConfigError("deny_rate must be between 0.0 and 1.0")
        if not 0.0 <= self.appeal_rate <= 1.0:
            raise SeedConfigError("appeal_rate must be between 0.0 and 1.0")
        if not 0.0 <= self.upheld_rate <= 1.0:
            raise SeedConfigError("upheld_rate must be between 0.0 and 1.0")


@dataclass
class SeedConfig:
    """
    Configuration for generating seeds for one category.

    Attributes:
        category: Decision category (txn, kyc, report, screening, monitoring)
        schema_id: Fingerprint schema ID
        registry_id: Reason code registry ID
        jurisdiction: Jurisdiction code
        scenarios: List of scenarios to generate
        decision_level_weights: Weights for decision level distribution
    """
    category: str
    schema_id: str
    registry_id: str
    jurisdiction: str
    scenarios: list[SeedScenario] = field(default_factory=list)
    decision_level_weights: dict[str, float] = field(default_factory=lambda: {
        "analyst": 0.45,
        "senior_analyst": 0.25,
        "manager": 0.15,
        "compliance_officer": 0.10,
        "mlro": 0.03,
        "regulator": 0.02,
    })

    def __post_init__(self) -> None:
        """Validate config on construction."""
        if not self.category:
            raise SeedConfigError("category cannot be empty")
        if not self.schema_id:
            raise SeedConfigError("schema_id cannot be empty")


# =============================================================================
# Seed Generator
# =============================================================================

class SeedGenerator:
    """
    Generates realistic seed precedents from configuration.

    The generator creates JudgmentPayload objects that can be loaded
    into a DecisionGraph chain for precedent matching.

    Usage:
        >>> generator = SeedGenerator(fp_registry, rc_registry, salt="seed-salt")
        >>> precedents = generator.generate_from_config(config)
    """

    def __init__(
        self,
        fingerprint_registry: AMLFingerprintSchemaRegistry,
        reason_registry: AMLReasonCodeRegistry,
        salt: str,
        random_seed: int = 42,
    ) -> None:
        """
        Initialize the seed generator.

        Args:
            fingerprint_registry: Registry of fingerprint schemas
            reason_registry: Registry of reason codes
            salt: Salt for fingerprint hashing
            random_seed: Seed for random number generation (for reproducibility)
        """
        self.fingerprint_registry = fingerprint_registry
        self.reason_registry = reason_registry
        self.salt = salt
        self.rng = random.Random(random_seed)

    def generate_from_config(self, config: SeedConfig) -> list[JudgmentPayload]:
        """
        Generate precedents from a configuration.

        Args:
            config: SeedConfig defining scenarios to generate

        Returns:
            List of JudgmentPayload objects
        """
        precedents = []

        for scenario in config.scenarios:
            scenario_precedents = self._generate_scenario(config, scenario)
            precedents.extend(scenario_precedents)

        return precedents

    def _generate_scenario(
        self,
        config: SeedConfig,
        scenario: SeedScenario,
    ) -> list[JudgmentPayload]:
        """Generate precedents for a single scenario."""
        precedents = []

        for i in range(scenario.count):
            precedent = self._generate_single_precedent(config, scenario, i)
            precedents.append(precedent)

        return precedents

    def _generate_single_precedent(
        self,
        config: SeedConfig,
        scenario: SeedScenario,
        index: int,
    ) -> JudgmentPayload:
        """Generate a single precedent."""
        import uuid

        # Generate facts by combining base and variable facts
        facts = dict(scenario.base_facts)
        for field_id, possible_values in scenario.variable_facts.items():
            facts[field_id] = self.rng.choice(possible_values)

        # Determine outcome - map to valid JudgmentPayload outcomes
        is_denial = self.rng.random() < scenario.deny_rate
        if is_denial:
            outcome = "deny"
        else:
            # Map scenario outcomes to valid JudgmentPayload outcomes
            outcome_map = {
                "approve": "pay",
                "investigate": "escalate",
                "escalate": "escalate",
                "block": "deny",
                "hold": "escalate",
                "clear": "pay",
                "exit": "deny",
                "report_lctr": "pay",
                "report_str": "escalate",
                "report_tpr": "escalate",
                "no_report": "pay",
            }
            outcome = outcome_map.get(scenario.outcome, "escalate")

        # Determine appeal status
        is_appealed = self.rng.random() < scenario.appeal_rate
        appeal_outcome = None
        if is_appealed:
            is_upheld = self.rng.random() < scenario.upheld_rate
            if is_upheld:
                appeal_outcome = "upheld"
            else:
                # 80% overturned, 20% settled
                if self.rng.random() < 0.8:
                    appeal_outcome = "overturned"
                else:
                    appeal_outcome = "settled"

        # Determine decision level
        decision_level = self._select_decision_level(config.decision_level_weights)

        # Generate dates
        decided_at = self._generate_decided_at()
        appeal_decided_at = None
        if is_appealed and appeal_outcome:
            # Appeals typically decided 30-180 days after initial decision
            appeal_days = self.rng.randint(30, 180)
            # Parse without the Z suffix and add back
            decided_dt = datetime.strptime(decided_at, "%Y-%m-%dT%H:%M:%SZ")
            appeal_dt = decided_dt + timedelta(days=appeal_days)
            appeal_decided_at = appeal_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Compute fingerprint
        schema = self.fingerprint_registry.get_schema_by_id(config.schema_id)
        fingerprint_hash = self.fingerprint_registry.compute_fingerprint(
            schema, facts, self.salt
        )

        # Generate IDs
        case_id = f"SEED-{config.category.upper()}-{scenario.code}-{index:05d}"
        # Use deterministic UUID based on case_id for reproducibility
        precedent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, case_id))
        case_id_hash = compute_case_id_hash(case_id, self.salt)

        # Create anchor facts
        anchor_facts = [
            AnchorFact(field_id=k, value=str(v), label=self._field_to_label(k))
            for k, v in facts.items()
        ]

        # Determine if this is a notable case (boundary case)
        is_notable = appeal_outcome == "overturned"
        outcome_notable = "boundary_case" if is_notable else None

        # Determine certainty based on appeal status
        if is_appealed and appeal_outcome == "overturned":
            certainty = "low"
        elif is_appealed:
            certainty = "medium"
        else:
            certainty = "high"

        # Map internal decision levels to valid JudgmentPayload levels
        # Valid levels: adjuster, manager, tribunal, court
        level_map = {
            "analyst": "adjuster",
            "senior_analyst": "adjuster",
            "manager": "manager",
            "compliance_officer": "manager",
            "mlro": "manager",
            "regulator": "tribunal",
        }
        mapped_level = level_map.get(decision_level, "adjuster")

        # Determine decided_by_role based on original decision level
        role_map = {
            "analyst": "AML Analyst",
            "senior_analyst": "Senior AML Analyst",
            "manager": "AML Manager",
            "compliance_officer": "Compliance Officer",
            "mlro": "MLRO",
            "regulator": "Regulator",
        }
        decided_by_role = role_map.get(decision_level, "Analyst")

        # Generate deterministic policy_pack_hash (64-char hex)
        pack_hash_input = f"{config.category}:{config.registry_id}:v1"
        policy_pack_hash = hashlib.sha256(pack_hash_input.encode()).hexdigest()

        # Create the judgment payload
        return JudgmentPayload(
            # Identity
            precedent_id=precedent_id,
            case_id_hash=case_id_hash,
            jurisdiction_code=config.jurisdiction,
            # Fingerprint
            fingerprint_hash=fingerprint_hash,
            fingerprint_schema_id=config.schema_id,
            # Decision codes
            exclusion_codes=scenario.reason_codes,
            reason_codes=scenario.reason_codes,
            reason_code_registry_id=config.registry_id,
            outcome_code=outcome,
            certainty=certainty,
            # Anchor facts
            anchor_facts=anchor_facts,
            # Policy context
            policy_pack_hash=policy_pack_hash,
            policy_pack_id=f"CA-FINTRAC-{config.category.upper()}",
            policy_version="2025.1",
            # Authority
            decision_level=mapped_level,
            decided_at=decided_at,
            decided_by_role=decided_by_role,
            # Appeals
            appealed=is_appealed,
            appeal_outcome=appeal_outcome,
            appeal_decided_at=appeal_decided_at,
            appeal_level="manager" if is_appealed else None,
            # Metadata
            source_type="seeded",
            outcome_notable=outcome_notable,
        )

    def _select_decision_level(self, weights: dict[str, float]) -> str:
        """Select a decision level based on weights."""
        levels = list(weights.keys())
        probs = list(weights.values())
        return self.rng.choices(levels, weights=probs, k=1)[0]

    def _generate_decided_at(self) -> str:
        """Generate a random decision date in the past 2 years."""
        days_ago = self.rng.randint(1, 730)  # 1 day to 2 years
        dt = datetime.utcnow() - timedelta(days=days_ago)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _field_to_label(self, field_id: str) -> str:
        """Convert a field_id to a human-readable label."""
        # Common field label mappings
        label_map = {
            "txn.type": "Transaction Type",
            "txn.amount_band": "Amount Band",
            "txn.cross_border": "Cross-Border",
            "txn.destination_country_risk": "Destination Risk",
            "txn.originator_country_risk": "Originator Risk",
            "txn.round_amount": "Round Amount",
            "txn.just_below_threshold": "Just Below Threshold",
            "txn.multiple_same_day": "Multiple Same Day",
            "txn.rapid_movement": "Rapid Movement",
            "txn.pattern_matches_profile": "Pattern Matches Profile",
            "txn.third_party_involved": "Third Party",
            "txn.cash_involved": "Cash Involved",
            "txn.cash_amount_band": "Cash Amount",
            "customer.type": "Customer Type",
            "customer.risk_level": "Risk Level",
            "customer.pep": "PEP Status",
            "customer.pep_type": "PEP Type",
            "customer.high_risk_industry": "High-Risk Industry",
            "customer.relationship_length": "Relationship Length",
            "customer.industry_type": "Industry Type",
            "crypto.exchange_regulated": "Exchange Regulated",
            "crypto.wallet_type": "Wallet Type",
            "crypto.mixer_indicators": "Mixer Indicators",
            "screening.sanctions_match": "Sanctions Match",
            "screening.adverse_media": "Adverse Media",
            "screening.adverse_media_severity": "Adverse Severity",
            "kyc.id_verified": "ID Verified",
            "kyc.address_verified": "Address Verified",
            "kyc.beneficial_owners_identified": "BO Identified",
            "shell.nominee_directors": "Nominee Directors",
            "shell.registered_agent_only": "Registered Agent Only",
            "shell.no_physical_presence": "No Physical Presence",
            "edd.complete": "EDD Complete",
            "edd.senior_approval": "Senior Approval",
            "suspicious.structuring": "Structuring",
            "suspicious.unusual_pattern": "Unusual Pattern",
            "suspicious.third_party": "Third Party",
            "suspicious.layering": "Layering",
            "suspicious.indicator_count": "Indicator Count",
            "suspicious.unusual_explained": "Unusual Explained",
            "terrorist.property_indicators": "Terrorist Property",
            "terrorist.listed_entity": "Listed Entity",
            "terrorist.associated_entity": "Associated Entity",
            "match.name_match_type": "Match Type",
            "match.list_source": "List Source",
            "match.score_band": "Match Score",
            "match.secondary_identifiers": "Secondary IDs",
            "match.type": "Match Type",
            "ownership.direct_pct_band": "Direct Ownership",
            "ownership.aggregated_over_50": "Aggregated >50%",
            "ownership.chain_depth": "Chain Depth",
            "delisted.status": "Delisted",
            "delisted.date_band": "Delisted Date",
            "secondary.exposure": "Secondary Exposure",
            "secondary.jurisdiction": "Secondary Jurisdiction",
            "activity.volume_change_band": "Volume Change",
            "activity.value_change_band": "Value Change",
            "activity.new_pattern": "New Pattern",
            "review.type": "Review Type",
            "review.risk_change": "Risk Change",
            "review.kyc_refresh_needed": "KYC Refresh Needed",
            "profile.address_change": "Address Change",
            "profile.bo_change": "BO Change",
            "profile.industry_change": "Industry Change",
            "dormant.months_inactive": "Months Inactive",
            "dormant.reactivation_pattern": "Reactivation Pattern",
            "exit.decision": "Exit Decision",
            "exit.reason": "Exit Reason",
            "exit.sar_related": "SAR-Related",
        }

        if field_id in label_map:
            return label_map[field_id]

        # Fall back to title-casing the field name
        parts = field_id.split(".")
        return " ".join(p.replace("_", " ").title() for p in parts)


# =============================================================================
# Pre-built Seed Configurations
# =============================================================================

def create_txn_monitoring_seed_config() -> SeedConfig:
    """
    Create seed configuration for Transaction Monitoring.

    Generates 700 precedents across 8 scenario categories.
    """
    return SeedConfig(
        category="txn",
        schema_id="decisiongraph:aml:txn:v1",
        registry_id="decisiongraph:aml:txn:v1",
        jurisdiction="CA",
        scenarios=[
            # Normal Approvals - 200
            SeedScenario(
                code="TXN-NORMAL",
                name="Normal Transaction",
                reason_codes=["RC-TXN-NORMAL", "RC-TXN-PROFILE-MATCH"],
                count=200,
                outcome="approve",
                base_facts={
                    "txn.pattern_matches_profile": True,
                    "screening.sanctions_match": False,
                    "screening.adverse_media": False,
                },
                variable_facts={
                    "txn.type": ["wire_domestic", "wire_international", "ach", "check"],
                    "txn.amount_band": ["under_3k", "3k_10k", "10k_25k"],
                    "customer.type": ["individual", "corporation"],
                    "customer.risk_level": ["low", "medium"],
                },
                appeal_rate=0.04,
                upheld_rate=0.95,
            ),
            # Structuring - 120
            SeedScenario(
                code="TXN-STRUCT",
                name="Structuring Indicators",
                reason_codes=["RC-TXN-STRUCT", "RC-TXN-STRUCT-MULTI"],
                count=120,
                outcome="investigate",
                deny_rate=0.15,
                base_facts={
                    "suspicious.structuring": True,
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "txn.just_below_threshold": [True, False],
                    "txn.multiple_same_day": [True, False],
                    "txn.round_amount": [True, False],
                    "txn.amount_band": ["3k_10k", "10k_25k"],
                },
                appeal_rate=0.20,
                upheld_rate=0.85,
            ),
            # High-Risk Jurisdiction - 100
            SeedScenario(
                code="TXN-FATF",
                name="High-Risk Jurisdiction",
                reason_codes=["RC-TXN-FATF-GREY", "RC-TXN-FATF-BLACK"],
                count=100,
                outcome="escalate",
                deny_rate=0.10,
                base_facts={
                    "txn.cross_border": True,
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "txn.destination_country_risk": ["high", "prohibited"],
                    "txn.amount_band": ["10k_25k", "25k_100k", "100k_500k"],
                    "customer.pep": [True, False],
                },
                appeal_rate=0.18,
                upheld_rate=0.88,
            ),
            # PEP Transactions - 80
            SeedScenario(
                code="TXN-PEP",
                name="PEP Transaction",
                reason_codes=["RC-TXN-PEP", "RC-TXN-PEP-EDD"],
                count=80,
                outcome="escalate",
                deny_rate=0.05,
                base_facts={
                    "customer.pep": True,
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "customer.pep_type": ["domestic", "foreign", "rca"],
                    "txn.amount_band": ["25k_100k", "100k_500k", "over_1m"],
                },
                appeal_rate=0.20,
                upheld_rate=0.87,
            ),
            # Crypto - 70
            SeedScenario(
                code="TXN-CRYPTO",
                name="Crypto Transaction",
                reason_codes=["RC-TXN-CRYPTO-UNREG", "RC-TXN-CRYPTO-UNHOSTED"],
                count=70,
                outcome="investigate",
                deny_rate=0.10,
                base_facts={
                    "txn.type": "crypto",
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "crypto.exchange_regulated": [True, False],
                    "crypto.wallet_type": ["hosted", "unhosted"],
                    "crypto.mixer_indicators": [True, False],
                },
                appeal_rate=0.20,
                upheld_rate=0.85,
            ),
            # Layering - 60
            SeedScenario(
                code="TXN-LAYER",
                name="Layering Indicators",
                reason_codes=["RC-TXN-LAYER", "RC-TXN-RAPID"],
                count=60,
                outcome="investigate",
                deny_rate=0.15,
                base_facts={
                    "txn.rapid_movement": True,
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "txn.amount_band": ["25k_100k", "100k_500k"],
                    "txn.cross_border": [True, False],
                },
                appeal_rate=0.17,
                upheld_rate=0.90,
            ),
            # Unusual Patterns - 40
            SeedScenario(
                code="TXN-UNUSUAL",
                name="Unusual Pattern",
                reason_codes=["RC-TXN-UNUSUAL", "RC-TXN-DEVIATION"],
                count=40,
                outcome="investigate",
                deny_rate=0.08,
                base_facts={
                    "txn.pattern_matches_profile": False,
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "txn.amount_band": ["25k_100k", "100k_500k"],
                    "customer.relationship_length": ["new", "recent"],
                },
                appeal_rate=0.20,
                upheld_rate=0.82,
            ),
            # Trade-Based ML - 30
            SeedScenario(
                code="TXN-TRADE",
                name="Trade-Based ML",
                reason_codes=["RC-TXN-TRADE-ML"],
                count=30,
                outcome="investigate",
                deny_rate=0.12,
                base_facts={
                    "txn.type": "wire_international",
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "txn.amount_band": ["100k_500k", "over_1m"],
                },
                appeal_rate=0.20,
                upheld_rate=0.85,
            ),
        ],
    )


def create_kyc_onboarding_seed_config() -> SeedConfig:
    """
    Create seed configuration for KYC Onboarding.

    Generates 450 precedents across 7 scenario categories.
    """
    return SeedConfig(
        category="kyc",
        schema_id="decisiongraph:aml:kyc:v1",
        registry_id="decisiongraph:aml:kyc:v1",
        jurisdiction="CA",
        scenarios=[
            # Standard Approvals - 150
            SeedScenario(
                code="KYC-STANDARD",
                name="Standard Approval",
                reason_codes=["RC-KYC-COMPLETE", "RC-KYC-LOW-RISK"],
                count=150,
                outcome="approve",
                base_facts={
                    "kyc.id_verified": True,
                    "kyc.address_verified": True,
                    "screening.sanctions_match": False,
                    "screening.adverse_media": False,
                },
                variable_facts={
                    "customer.type": ["individual", "sole_prop", "corporation"],
                    "customer.risk_level": ["low", "medium"],
                },
                appeal_rate=0.04,
                upheld_rate=0.95,
            ),
            # PEP Handling - 80
            SeedScenario(
                code="KYC-PEP",
                name="PEP Onboarding",
                reason_codes=["RC-KYC-PEP-APPROVED", "RC-KYC-PENDING-EDD"],
                count=80,
                outcome="escalate",
                deny_rate=0.18,
                base_facts={
                    "customer.pep": True,
                    "kyc.id_verified": True,
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "customer.pep_type": ["domestic", "foreign", "international_org"],
                    "edd.complete": [True, False],
                    "edd.senior_approval": [True, False],
                },
                appeal_rate=0.20,
                upheld_rate=0.87,
            ),
            # High-Risk Industry - 70
            SeedScenario(
                code="KYC-HRI",
                name="High-Risk Industry",
                reason_codes=["RC-KYC-MSB", "RC-KYC-CRYPTO-VASP"],
                count=70,
                outcome="escalate",
                deny_rate=0.15,
                base_facts={
                    "customer.high_risk_industry": True,
                    "kyc.id_verified": True,
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "customer.industry_type": ["msb", "crypto", "gaming", "precious_metals"],
                    "edd.complete": [True, False],
                },
                appeal_rate=0.20,
                upheld_rate=0.85,
            ),
            # Missing Documentation - 50
            SeedScenario(
                code="KYC-MISSING",
                name="Missing Documentation",
                reason_codes=["RC-KYC-PENDING-ID", "RC-KYC-PENDING-BO", "RC-KYC-PENDING-ADDR"],
                count=50,
                outcome="hold",
                deny_rate=0.20,
                base_facts={
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "kyc.id_verified": [True, False],
                    "kyc.address_verified": [True, False],
                    "kyc.beneficial_owners_identified": [True, False],
                },
                appeal_rate=0.20,
                upheld_rate=0.80,
            ),
            # Adverse Media - 50
            SeedScenario(
                code="KYC-ADVERSE",
                name="Adverse Media",
                reason_codes=["RC-KYC-ADVERSE-MINOR", "RC-KYC-ADVERSE-MAJOR"],
                count=50,
                outcome="escalate",
                deny_rate=0.40,
                base_facts={
                    "screening.adverse_media": True,
                    "screening.sanctions_match": False,
                    "kyc.id_verified": True,
                },
                variable_facts={
                    "screening.adverse_media_severity": ["minor", "moderate", "major"],
                },
                appeal_rate=0.24,
                upheld_rate=0.80,
            ),
            # Shell Company - 30
            SeedScenario(
                code="KYC-SHELL",
                name="Shell Company Indicators",
                reason_codes=["RC-KYC-SHELL", "RC-KYC-SHELL-DECLINE"],
                count=30,
                outcome="escalate",
                deny_rate=0.60,
                base_facts={
                    "customer.type": "corporation",
                    "kyc.id_verified": True,
                    "screening.sanctions_match": False,
                },
                variable_facts={
                    "shell.nominee_directors": [True, False],
                    "shell.registered_agent_only": [True, False],
                    "shell.no_physical_presence": [True, False],
                },
                appeal_rate=0.27,
                upheld_rate=0.85,
            ),
            # Sanctions Decline - 20
            SeedScenario(
                code="KYC-SANCTION",
                name="Sanctions Match",
                reason_codes=["RC-KYC-SANCTION"],
                count=20,
                outcome="deny",
                deny_rate=1.0,
                base_facts={
                    "screening.sanctions_match": True,
                },
                variable_facts={
                    "customer.type": ["individual", "corporation"],
                },
                appeal_rate=0.10,
                upheld_rate=0.95,
            ),
        ],
    )


def create_reporting_seed_config() -> SeedConfig:
    """
    Create seed configuration for Reporting.

    Generates 200 precedents across 4 scenario categories.
    """
    return SeedConfig(
        category="report",
        schema_id="decisiongraph:aml:report:v1",
        registry_id="decisiongraph:aml:report:v1",
        jurisdiction="CA",
        scenarios=[
            # LCTR - 60
            SeedScenario(
                code="RPT-LCTR",
                name="Large Cash Transaction",
                reason_codes=["RC-RPT-LCTR", "RC-RPT-LCTR-MULTI"],
                count=60,
                outcome="report_lctr",
                base_facts={
                    "txn.cash_involved": True,
                    "terrorist.listed_entity": False,
                },
                variable_facts={
                    "txn.cash_amount_band": ["10k_25k", "25k_50k", "50k_plus"],
                    "txn.multiple_cash_same_day": [True, False],
                },
                appeal_rate=0.05,
                upheld_rate=0.95,
            ),
            # STR - 100
            SeedScenario(
                code="RPT-STR",
                name="Suspicious Transaction",
                reason_codes=["RC-RPT-STR", "RC-RPT-STR-STRUCT", "RC-RPT-STR-UNUSUAL"],
                count=100,
                outcome="report_str",
                deny_rate=0.03,
                base_facts={
                    "terrorist.listed_entity": False,
                },
                variable_facts={
                    "suspicious.structuring": [True, False],
                    "suspicious.unusual_pattern": [True, False],
                    "suspicious.third_party": [True, False],
                    "suspicious.layering": [True, False],
                    "suspicious.indicator_count": [2, 3, 4, 5],
                },
                appeal_rate=0.15,
                upheld_rate=0.85,
            ),
            # TPR - 20
            SeedScenario(
                code="RPT-TPR",
                name="Terrorist Property",
                reason_codes=["RC-RPT-TPR"],
                count=20,
                outcome="report_tpr",
                deny_rate=0.0,
                base_facts={
                    "terrorist.property_indicators": True,
                },
                variable_facts={
                    "terrorist.listed_entity": [True, False],
                    "terrorist.associated_entity": [True, False],
                },
                appeal_rate=0.10,
                upheld_rate=0.95,
            ),
            # No Report - 20
            SeedScenario(
                code="RPT-NONE",
                name="No Report Required",
                reason_codes=["RC-RPT-NONE", "RC-RPT-NONE-EXPLAINED"],
                count=20,
                outcome="no_report",
                base_facts={
                    "suspicious.unusual_explained": True,
                    "terrorist.listed_entity": False,
                    "txn.cash_involved": False,
                },
                variable_facts={
                    "suspicious.indicator_count": [0, 1],
                },
                appeal_rate=0.20,
                upheld_rate=0.75,
            ),
        ],
    )


def create_screening_seed_config() -> SeedConfig:
    """
    Create seed configuration for Sanctions/Screening.

    Generates 350 precedents across 6 scenario categories.
    """
    return SeedConfig(
        category="screening",
        schema_id="decisiongraph:aml:screening:v1",
        registry_id="decisiongraph:aml:screening:v1",
        jurisdiction="GLOBAL",
        scenarios=[
            # True Positive - 60
            SeedScenario(
                code="SCR-TP",
                name="True Positive",
                reason_codes=["RC-SCR-SANCTION", "RC-SCR-OFAC", "RC-SCR-SEMA"],
                count=60,
                outcome="block",
                deny_rate=1.0,
                base_facts={
                    "match.name_match_type": "exact",
                },
                variable_facts={
                    "match.list_source": ["ofac", "un", "ca_sema", "eu"],
                    "match.score_band": ["high", "exact"],
                },
                appeal_rate=0.08,
                upheld_rate=0.95,
            ),
            # False Positive - 120
            SeedScenario(
                code="SCR-FP",
                name="False Positive",
                reason_codes=["RC-SCR-FP", "RC-SCR-FP-NAME", "RC-SCR-FP-DOB"],
                count=120,
                outcome="clear",
                base_facts={
                    "match.secondary_identifiers": False,
                },
                variable_facts={
                    "match.name_match_type": ["fuzzy", "partial", "alias"],
                    "match.score_band": ["low", "medium"],
                },
                appeal_rate=0.17,
                upheld_rate=0.85,
            ),
            # Ownership Chain - 60
            SeedScenario(
                code="SCR-OWN",
                name="Ownership Chain",
                reason_codes=["RC-SCR-OWN-50", "RC-SCR-OWN-CLEAR"],
                count=60,
                outcome="escalate",
                deny_rate=0.40,
                variable_facts={
                    "ownership.direct_pct_band": ["minority", "significant", "controlling"],
                    "ownership.aggregated_over_50": [True, False],
                    "ownership.chain_depth": ["1", "2", "3"],
                },
                appeal_rate=0.20,
                upheld_rate=0.85,
            ),
            # De-listed - 40
            SeedScenario(
                code="SCR-DELIST",
                name="De-listed Entity",
                reason_codes=["RC-SCR-DELIST-CLEAR", "RC-SCR-DELIST-MONITOR"],
                count=40,
                outcome="approve",
                base_facts={
                    "delisted.status": True,
                },
                variable_facts={
                    "delisted.date_band": ["recent", "moderate", "old"],
                },
                appeal_rate=0.20,
                upheld_rate=0.85,
            ),
            # Secondary Sanctions - 40
            SeedScenario(
                code="SCR-SECONDARY",
                name="Secondary Sanctions",
                reason_codes=["RC-SCR-SECONDARY"],
                count=40,
                outcome="escalate",
                deny_rate=0.25,
                base_facts={
                    "secondary.exposure": True,
                },
                variable_facts={
                    "secondary.jurisdiction": ["iran", "russia", "dprk"],
                },
                appeal_rate=0.15,
                upheld_rate=0.88,
            ),
            # PEP Screening - 30
            SeedScenario(
                code="SCR-PEP",
                name="PEP Screening",
                reason_codes=["RC-SCR-PEP-CONF", "RC-SCR-PEP-FP"],
                count=30,
                outcome="escalate",
                base_facts={
                    "match.type": "pep",
                },
                variable_facts={
                    "match.score_band": ["medium", "high", "exact"],
                },
                appeal_rate=0.17,
                upheld_rate=0.85,
            ),
        ],
    )


def create_monitoring_seed_config() -> SeedConfig:
    """
    Create seed configuration for Ongoing Monitoring.

    Generates 300 precedents across 5 scenario categories.
    """
    return SeedConfig(
        category="monitoring",
        schema_id="decisiongraph:aml:monitoring:v1",
        registry_id="decisiongraph:aml:monitoring:v1",
        jurisdiction="CA",
        scenarios=[
            # Activity Triggers - 80
            SeedScenario(
                code="MON-ACTIVITY",
                name="Activity Trigger",
                reason_codes=["RC-MON-SPIKE", "RC-MON-NEW-PATTERN"],
                count=80,
                outcome="investigate",
                deny_rate=0.05,
                variable_facts={
                    "activity.volume_change_band": ["moderate", "significant", "extreme"],
                    "activity.value_change_band": ["moderate", "significant", "extreme"],
                    "activity.new_pattern": [True, False],
                },
                appeal_rate=0.15,
                upheld_rate=0.87,
            ),
            # Periodic Review - 70
            SeedScenario(
                code="MON-PERIODIC",
                name="Periodic Review",
                reason_codes=["RC-MON-REVIEW-CLEAR", "RC-MON-REVIEW-UPGRADE"],
                count=70,
                outcome="approve",
                base_facts={
                    "review.type": "annual",
                },
                variable_facts={
                    "review.risk_change": ["unchanged", "upgraded", "downgraded"],
                    "review.kyc_refresh_needed": [True, False],
                },
                appeal_rate=0.11,
                upheld_rate=0.90,
            ),
            # Profile Changes - 60
            SeedScenario(
                code="MON-PROFILE",
                name="Profile Change",
                reason_codes=["RC-MON-PROFILE-CHG", "RC-MON-BO-CHG"],
                count=60,
                outcome="escalate",
                deny_rate=0.05,
                variable_facts={
                    "profile.address_change": [True, False],
                    "profile.bo_change": [True, False],
                    "profile.industry_change": [True, False],
                },
                appeal_rate=0.17,
                upheld_rate=0.85,
            ),
            # Dormant Reactivation - 50
            SeedScenario(
                code="MON-DORMANT",
                name="Dormant Reactivation",
                reason_codes=["RC-MON-DORM-REACT", "RC-MON-DORM-SUSP"],
                count=50,
                outcome="investigate",
                deny_rate=0.08,
                variable_facts={
                    "dormant.months_inactive": ["short", "medium", "long", "very_long"],
                    "dormant.reactivation_pattern": ["normal", "unusual", "suspicious"],
                },
                appeal_rate=0.20,
                upheld_rate=0.82,
            ),
            # Exit Decisions - 40
            SeedScenario(
                code="MON-EXIT",
                name="Exit Decision",
                reason_codes=["RC-MON-EXIT", "RC-MON-EXIT-RISK", "RC-MON-EXIT-SAR"],
                count=40,
                outcome="exit",
                deny_rate=0.0,
                base_facts={
                    "exit.decision": "exit_recommended",
                },
                variable_facts={
                    "exit.reason": ["risk", "sar", "regulatory"],
                    "exit.sar_related": [True, False],
                },
                appeal_rate=0.20,
                upheld_rate=0.85,
            ),
        ],
    )


def generate_all_banking_seeds(
    salt: str = "decisiongraph-banking-seed-v1",
    random_seed: int = 42,
) -> list[JudgmentPayload]:
    """
    Generate all banking seed precedents.

    Args:
        salt: Salt for fingerprint hashing
        random_seed: Seed for random number generation

    Returns:
        List of 2,000 JudgmentPayload objects
    """
    fp_registry = AMLFingerprintSchemaRegistry()
    rc_registry = AMLReasonCodeRegistry()
    generator = SeedGenerator(fp_registry, rc_registry, salt, random_seed)

    all_precedents = []

    # Generate for each category
    configs = [
        create_txn_monitoring_seed_config(),    # 700
        create_kyc_onboarding_seed_config(),    # 450
        create_reporting_seed_config(),          # 200
        create_screening_seed_config(),          # 350
        create_monitoring_seed_config(),         # 300
    ]

    for config in configs:
        precedents = generator.generate_from_config(config)
        all_precedents.extend(precedents)

    return all_precedents


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "SeedGeneratorError",
    "SeedConfigError",
    "SeedLoadError",

    # Configuration
    "SeedScenario",
    "SeedConfig",

    # Generator
    "SeedGenerator",

    # Pre-built configs
    "create_txn_monitoring_seed_config",
    "create_kyc_onboarding_seed_config",
    "create_reporting_seed_config",
    "create_screening_seed_config",
    "create_monitoring_seed_config",

    # Convenience function
    "generate_all_banking_seeds",
]

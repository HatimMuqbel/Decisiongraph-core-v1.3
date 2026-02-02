"""
ClaimPilot Precedent System: Master Banding Library

This module implements the standardized banding rules for fingerprint generation.
Every case is reduced to logical risk categories BEFORE the hash is created.

Design Principles:
- Consistent: Same raw value always produces same band
- Meaningful: Bands represent actual risk categories, not arbitrary buckets
- Universal: Every vertical uses the same banding structure
- Extensible: New bands can be added without breaking existing fingerprints

The banding library ensures the fingerprint "sees" the logical shape of risk,
not just random numbers.

Example:
    >>> bander = BandingLibrary()
    >>> bander.band_value("auto", "driver.bac_level", 0.09)
    'FAIL'
    >>> bander.band_value("auto", "claim.amount", 85000)
    'HIGH_VALUE'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import re


# =============================================================================
# Universal Metadata Bands (All Verticals)
# =============================================================================

class RegimeBand(str, Enum):
    """Regulatory regime under which decision was made."""
    PRE_2026 = "PRE_2026"
    POST_2026 = "POST_2026"
    TRANSITIONAL = "TRANSITIONAL"


class AuthorityBand(str, Enum):
    """Decision authority level."""
    STAFF = "STAFF"              # Standard adjuster/analyst
    SENIOR = "SENIOR"            # Senior adjuster/manager
    TRIBUNAL = "TRIBUNAL"        # Administrative tribunal
    SUPERIOR_COURT = "SUPERIOR_COURT"  # Court decision
    APPEALS_COURT = "APPEALS_COURT"    # Appeals court
    REGULATORY = "REGULATORY"    # Regulatory body


class ConflictBand(str, Enum):
    """Decision consensus level."""
    UNANIMOUS = "UNANIMOUS"      # Clear decision
    CONTESTED = "CONTESTED"      # Split decision or appeal
    OVERTURNED = "OVERTURNED"    # Previously reversed


# =============================================================================
# Auto Insurance Bands (OAP 1)
# =============================================================================

class AutoBACBand(str, Enum):
    """Blood Alcohol Content bands."""
    ZERO = "ZERO"                # 0.00
    WARN = "WARN"                # 0.01-0.049
    WARN_RANGE = "WARN_RANGE"    # 0.05-0.079
    FAIL = "FAIL"                # 0.08+
    REFUSE = "REFUSE"            # Refused test


class AutoLicenseClassBand(str, Enum):
    """License class bands."""
    G1 = "G1"
    G2 = "G2"
    FULL = "FULL"
    M1 = "M1"
    M2 = "M2"
    M_FULL = "M_FULL"
    COMMERCIAL = "COMMERCIAL"
    NONE = "NONE"


class AutoLicenseStatusBand(str, Enum):
    """License status bands."""
    VALID = "VALID"
    EXPIRED_MINOR = "EXPIRED_MINOR"      # < 30 days
    EXPIRED_MAJOR = "EXPIRED_MAJOR"      # 30+ days
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    NEVER_LICENSED = "NEVER_LICENSED"


class AutoVehicleUseBand(str, Enum):
    """Vehicle use bands."""
    PERSONAL = "PERSONAL"
    COMMUTE = "COMMUTE"
    BUSINESS = "BUSINESS"
    RIDESHARE = "RIDESHARE"
    DELIVERY = "DELIVERY"
    COMMERCIAL = "COMMERCIAL"
    RACING = "RACING"


class AutoVehicleValueBand(str, Enum):
    """Vehicle value bands."""
    ECONOMY = "ECONOMY"          # < $15K
    STANDARD = "STANDARD"        # $15K-$40K
    PREMIUM = "PREMIUM"          # $40K-$75K
    HIGH_VALUE = "HIGH_VALUE"    # $75K-$150K
    EXOTIC = "EXOTIC"            # $150K+


class AutoModificationBand(str, Enum):
    """Vehicle modification bands."""
    STOCK = "STOCK"
    COSMETIC_MOD = "COSMETIC_MOD"
    PERFORMANCE_MOD = "PERFORMANCE_MOD"
    LIFT_LOWER = "LIFT_LOWER"
    RACING_MOD = "RACING_MOD"


class AutoFaultBand(str, Enum):
    """Fault percentage bands."""
    NOT_AT_FAULT = "NOT_AT_FAULT"        # 0%
    MINOR_FAULT = "MINOR_FAULT"          # 1-25%
    PARTIAL_FAULT = "PARTIAL_FAULT"      # 26-50%
    MAJORITY_FAULT = "MAJORITY_FAULT"    # 51-75%
    AT_FAULT = "AT_FAULT"                # 76-100%


class AutoSpeedingBand(str, Enum):
    """Speeding severity bands."""
    NONE = "NONE"
    MINOR = "MINOR"              # 1-15 over
    MODERATE = "MODERATE"        # 16-30 over
    EXCESSIVE = "EXCESSIVE"      # 31-49 over
    STUNT_DRIVING = "STUNT_DRIVING"  # 50+ over


class AutoImpactBand(str, Enum):
    """Impact type bands."""
    SINGLE_VEHICLE = "SINGLE_VEHICLE"
    REAR_END = "REAR_END"
    HEAD_ON = "HEAD_ON"
    T_BONE = "T_BONE"
    SIDESWIPE = "SIDESWIPE"
    ROLLOVER = "ROLLOVER"
    PEDESTRIAN = "PEDESTRIAN"
    CYCLIST = "CYCLIST"


# =============================================================================
# Marine Insurance Bands
# =============================================================================

class MarineNavigationBand(str, Enum):
    """Navigation distance bands."""
    INLAND = "INLAND"                    # Lakes/rivers
    COASTAL = "COASTAL"                  # Within 12nm
    BEYOND_COASTAL = "BEYOND_COASTAL"    # 12-200nm
    OFFSHORE = "OFFSHORE"                # 200nm+


class MarineJurisdictionBand(str, Enum):
    """Jurisdictional bands."""
    DOMESTIC = "DOMESTIC"
    GREAT_LAKES = "GREAT_LAKES"
    OUT_OF_COUNTRY = "OUT_OF_COUNTRY"
    INTERNATIONAL_WATERS = "INTERNATIONAL_WATERS"


class MarineLayupBand(str, Enum):
    """Layup period compliance bands."""
    COMPLIANT = "COMPLIANT"
    IN_WATER_PROHIBITED = "IN_WATER_PROHIBITED"
    STORAGE_VIOLATION = "STORAGE_VIOLATION"


class MarineMaintenanceBand(str, Enum):
    """Maintenance compliance bands."""
    CURRENT = "CURRENT"
    MINOR_LAPSE = "MINOR_LAPSE"
    NEGLECT = "NEGLECT"


class MarineVesselTypeBand(str, Enum):
    """Vessel type bands."""
    SAILBOAT = "SAILBOAT"
    POWERBOAT = "POWERBOAT"
    PERSONAL_WATERCRAFT = "PERSONAL_WATERCRAFT"
    HOUSEBOAT = "HOUSEBOAT"
    COMMERCIAL = "COMMERCIAL"


class MarineEngineTypeBand(str, Enum):
    """Engine type bands."""
    OUTBOARD_GAS = "OUTBOARD_GAS"
    INBOARD_GAS = "INBOARD_GAS"
    DIESEL = "DIESEL"
    ELECTRIC = "ELECTRIC"
    SAIL_ONLY = "SAIL_ONLY"


# =============================================================================
# CGL Insurance Bands
# =============================================================================

class CGLBusinessTypeBand(str, Enum):
    """Business type risk bands."""
    LOW_HAZARD = "LOW_HAZARD"              # Office, retail
    MODERATE_HAZARD = "MODERATE_HAZARD"    # Light manufacturing
    HIGH_HAZARD_TRADE = "HIGH_HAZARD_TRADE"  # Roofing, electrical
    PROFESSIONAL = "PROFESSIONAL"          # Lawyers, accountants
    HOSPITALITY = "HOSPITALITY"


class CGLRevenueBand(str, Enum):
    """Annual revenue bands."""
    MICRO = "MICRO"                  # < $500K
    SMALL = "SMALL"                  # $500K-$2M
    MID_COMMERCIAL = "MID_COMMERCIAL"  # $2M-$10M
    LARGE = "LARGE"                  # $10M-$50M
    ENTERPRISE = "ENTERPRISE"        # $50M+


class CGLInjuryTypeBand(str, Enum):
    """Injury severity bands."""
    NO_INJURY = "NO_INJURY"
    BODILY_INJURY_MINOR = "BODILY_INJURY_MINOR"
    BODILY_INJURY_MODERATE = "BODILY_INJURY_MODERATE"
    BODILY_INJURY_SEVERE = "BODILY_INJURY_SEVERE"
    FATALITY = "FATALITY"


class CGLLocationBand(str, Enum):
    """Incident location bands."""
    ON_PREMISES = "ON_PREMISES"
    OFF_PREMISES = "OFF_PREMISES"
    CLIENT_SITE = "CLIENT_SITE"
    PUBLIC_SPACE = "PUBLIC_SPACE"


class CGLNegligenceBand(str, Enum):
    """Negligence severity bands."""
    ORDINARY = "ORDINARY"
    CONTRIBUTORY = "CONTRIBUTORY"
    GROSS_NEGLIGENCE = "GROSS_NEGLIGENCE"
    WILLFUL = "WILLFUL"


# =============================================================================
# Property Insurance Bands (HO-3)
# =============================================================================

class PropertyLossCauseBand(str, Enum):
    """Loss cause bands."""
    FIRE = "FIRE"
    WATER_SUDDEN = "WATER_SUDDEN"
    WATER_GRADUAL = "WATER_GRADUAL"
    FLOOD = "FLOOD"
    WIND_HAIL = "WIND_HAIL"
    THEFT = "THEFT"
    VANDALISM = "VANDALISM"
    EARTHQUAKE = "EARTHQUAKE"
    COLLAPSE = "COLLAPSE"


class PropertyVacancyBand(str, Enum):
    """Vacancy duration bands."""
    OCCUPIED = "OCCUPIED"
    SHORT_VACANCY = "SHORT_VACANCY"      # 1-30 days
    MEDIUM_VACANCY = "MEDIUM_VACANCY"    # 31-60 days
    LONG_VACANCY = "LONG_VACANCY"        # 60+ days


class PropertyClaimAmountBand(str, Enum):
    """Claim amount bands."""
    MINOR = "MINOR"              # < $5K
    SMALL = "SMALL"              # $5K-$25K
    MEDIUM = "MEDIUM"            # $25K-$100K
    LARGE = "LARGE"              # $100K-$500K
    CATASTROPHIC = "CATASTROPHIC"  # $500K+


# =============================================================================
# Banking/AML Bands
# =============================================================================

class BankingAmountBand(str, Enum):
    """Transaction amount bands."""
    MICRO = "MICRO"                      # < $1K
    SMALL = "SMALL"                      # $1K-$5K
    MEDIUM = "MEDIUM"                    # $5K-$10K
    STRUCTURING_THRESHOLD = "STRUCTURING_THRESHOLD"  # Near $10K
    LARGE = "LARGE"                      # $10K-$50K
    SIGNIFICANT = "SIGNIFICANT"          # $50K-$100K
    MAJOR = "MAJOR"                      # $100K+


class BankingVelocityBand(str, Enum):
    """Transaction frequency bands."""
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"            # 5-10 in 24hrs
    HIGH_VELOCITY = "HIGH_VELOCITY"  # 10+ in 24hrs
    SUSPICIOUS = "SUSPICIOUS"        # Pattern detected


class BankingJurisdictionBand(str, Enum):
    """Geographic risk bands."""
    LOW_RISK = "LOW_RISK"
    MODERATE_RISK = "MODERATE_RISK"
    HIGH_RISK_JURISDICTION = "HIGH_RISK_JURISDICTION"
    SANCTIONED = "SANCTIONED"


class BankingPEPBand(str, Enum):
    """PEP status bands."""
    NOT_PEP = "NOT_PEP"
    PEP_DOMESTIC = "PEP_DOMESTIC"
    PEP_FOREIGN = "PEP_FOREIGN"
    PEP_FAMILY = "PEP_FAMILY"
    PEP_ASSOCIATE = "PEP_ASSOCIATE"


class BankingRiskScoreBand(str, Enum):
    """Risk score bands."""
    LOW_RISK = "LOW_RISK"            # 0-25
    MODERATE_RISK = "MODERATE_RISK"  # 26-50
    ELEVATED_RISK = "ELEVATED_RISK"  # 51-75
    HIGH_RISK = "HIGH_RISK"          # 76-90
    CRITICAL_RISK = "CRITICAL_RISK"  # 91+


class BankingAdverseMediaBand(str, Enum):
    """Adverse media bands."""
    NONE = "NONE"
    MINOR = "MINOR"
    REPUTATIONAL_RISK = "REPUTATIONAL_RISK"
    CRIMINAL_ALLEGATION = "CRIMINAL_ALLEGATION"
    SANCTIONS_RELATED = "SANCTIONS_RELATED"


# =============================================================================
# Banding Functions
# =============================================================================

def band_bac_level(value: float) -> str:
    """Band BAC level for auto insurance."""
    if value == 0:
        return AutoBACBand.ZERO.value
    elif value < 0.05:
        return AutoBACBand.WARN.value
    elif value < 0.08:
        return AutoBACBand.WARN_RANGE.value
    else:
        return AutoBACBand.FAIL.value


def band_license_status(status: str, days_expired: int = 0) -> str:
    """Band license status for auto insurance."""
    status_lower = status.lower()
    if status_lower in ["valid", "active"]:
        return AutoLicenseStatusBand.VALID.value
    elif status_lower == "expired":
        if days_expired < 30:
            return AutoLicenseStatusBand.EXPIRED_MINOR.value
        else:
            return AutoLicenseStatusBand.EXPIRED_MAJOR.value
    elif status_lower == "suspended":
        return AutoLicenseStatusBand.SUSPENDED.value
    elif status_lower == "revoked":
        return AutoLicenseStatusBand.REVOKED.value
    elif status_lower in ["never_licensed", "none"]:
        return AutoLicenseStatusBand.NEVER_LICENSED.value
    return AutoLicenseStatusBand.VALID.value


def band_vehicle_value(value: float) -> str:
    """Band vehicle value for auto insurance."""
    if value < 15000:
        return AutoVehicleValueBand.ECONOMY.value
    elif value < 40000:
        return AutoVehicleValueBand.STANDARD.value
    elif value < 75000:
        return AutoVehicleValueBand.PREMIUM.value
    elif value < 150000:
        return AutoVehicleValueBand.HIGH_VALUE.value
    else:
        return AutoVehicleValueBand.EXOTIC.value


def band_fault_percentage(pct: float) -> str:
    """Band fault percentage for auto insurance."""
    if pct == 0:
        return AutoFaultBand.NOT_AT_FAULT.value
    elif pct <= 25:
        return AutoFaultBand.MINOR_FAULT.value
    elif pct <= 50:
        return AutoFaultBand.PARTIAL_FAULT.value
    elif pct <= 75:
        return AutoFaultBand.MAJORITY_FAULT.value
    else:
        return AutoFaultBand.AT_FAULT.value


def band_speeding(over_limit: int) -> str:
    """Band speeding severity for auto insurance."""
    if over_limit <= 0:
        return AutoSpeedingBand.NONE.value
    elif over_limit <= 15:
        return AutoSpeedingBand.MINOR.value
    elif over_limit <= 30:
        return AutoSpeedingBand.MODERATE.value
    elif over_limit <= 49:
        return AutoSpeedingBand.EXCESSIVE.value
    else:
        return AutoSpeedingBand.STUNT_DRIVING.value


def band_navigation_distance(nm: float) -> str:
    """Band navigation distance for marine insurance."""
    if nm <= 0:
        return MarineNavigationBand.INLAND.value
    elif nm <= 12:
        return MarineNavigationBand.COASTAL.value
    elif nm <= 200:
        return MarineNavigationBand.BEYOND_COASTAL.value
    else:
        return MarineNavigationBand.OFFSHORE.value


def band_claim_amount(amount: float, policy_type: str = "property") -> str:
    """Band claim amount by policy type."""
    if policy_type == "property":
        if amount < 5000:
            return PropertyClaimAmountBand.MINOR.value
        elif amount < 25000:
            return PropertyClaimAmountBand.SMALL.value
        elif amount < 100000:
            return PropertyClaimAmountBand.MEDIUM.value
        elif amount < 500000:
            return PropertyClaimAmountBand.LARGE.value
        else:
            return PropertyClaimAmountBand.CATASTROPHIC.value
    else:
        # Generic amount banding
        if amount < 10000:
            return "SMALL"
        elif amount < 50000:
            return "MEDIUM"
        elif amount < 100000:
            return "LARGE"
        else:
            return "MAJOR"


def band_vacancy_days(days: int) -> str:
    """Band vacancy duration for property insurance."""
    if days == 0:
        return PropertyVacancyBand.OCCUPIED.value
    elif days <= 30:
        return PropertyVacancyBand.SHORT_VACANCY.value
    elif days <= 60:
        return PropertyVacancyBand.MEDIUM_VACANCY.value
    else:
        return PropertyVacancyBand.LONG_VACANCY.value


def band_transaction_amount(amount: float) -> str:
    """Band transaction amount for banking/AML."""
    if amount < 1000:
        return BankingAmountBand.MICRO.value
    elif amount < 5000:
        return BankingAmountBand.SMALL.value
    elif amount < 10000:
        return BankingAmountBand.MEDIUM.value
    elif amount < 11000:  # Near $10K threshold
        return BankingAmountBand.STRUCTURING_THRESHOLD.value
    elif amount < 50000:
        return BankingAmountBand.LARGE.value
    elif amount < 100000:
        return BankingAmountBand.SIGNIFICANT.value
    else:
        return BankingAmountBand.MAJOR.value


def band_transaction_velocity(count: int, hours: int = 24) -> str:
    """Band transaction velocity for banking/AML."""
    rate = count / max(hours, 1) * 24  # Normalize to 24 hours
    if rate < 5:
        return BankingVelocityBand.NORMAL.value
    elif rate < 10:
        return BankingVelocityBand.ELEVATED.value
    else:
        return BankingVelocityBand.HIGH_VELOCITY.value


def band_risk_score(score: float) -> str:
    """Band risk score for banking/AML."""
    if score <= 25:
        return BankingRiskScoreBand.LOW_RISK.value
    elif score <= 50:
        return BankingRiskScoreBand.MODERATE_RISK.value
    elif score <= 75:
        return BankingRiskScoreBand.ELEVATED_RISK.value
    elif score <= 90:
        return BankingRiskScoreBand.HIGH_RISK.value
    else:
        return BankingRiskScoreBand.CRITICAL_RISK.value


# =============================================================================
# Master Banding Library Class
# =============================================================================

@dataclass
class BandingRule:
    """A single banding rule configuration."""
    field_id: str
    bander: Callable[[Any], str]
    description: str = ""


class BandingLibrary:
    """
    Master Banding Library for fingerprint generation.

    Ensures every case is reduced to logical risk categories
    before the fingerprint hash is created.

    Usage:
        >>> library = BandingLibrary()
        >>> banded = library.band_facts("auto", {
        ...     "driver.bac_level": 0.09,
        ...     "claim.amount": 85000,
        ...     "driver.license_status": "valid"
        ... })
        >>> print(banded)
        {'driver.bac_level': 'FAIL', 'claim.amount': 'LARGE', 'driver.license_status': 'VALID'}
    """

    def __init__(self) -> None:
        """Initialize the banding library with all vertical rules."""
        self._rules: dict[str, dict[str, BandingRule]] = {
            "auto": self._build_auto_rules(),
            "marine": self._build_marine_rules(),
            "property": self._build_property_rules(),
            "cgl": self._build_cgl_rules(),
            "health": self._build_health_rules(),
            "wsib": self._build_wsib_rules(),
            "eo": self._build_eo_rules(),
            "travel": self._build_travel_rules(),
            "banking": self._build_banking_rules(),
        }

    def _build_auto_rules(self) -> dict[str, BandingRule]:
        """Build auto insurance banding rules."""
        return {
            "driver.bac_level": BandingRule(
                field_id="driver.bac_level",
                bander=lambda v: band_bac_level(float(v) if isinstance(v, (int, float)) else self._parse_bac(v)),
                description="Blood alcohol content level"
            ),
            "driver.license_status": BandingRule(
                field_id="driver.license_status",
                bander=lambda v: band_license_status(str(v)),
                description="License status"
            ),
            "auto.vehicle_value": BandingRule(
                field_id="auto.vehicle_value",
                bander=lambda v: band_vehicle_value(float(v)),
                description="Vehicle value"
            ),
            "auto.vehicle_use": BandingRule(
                field_id="auto.vehicle_use",
                bander=lambda v: self._band_vehicle_use(v),
                description="Vehicle use type"
            ),
            "auto.fault_percentage": BandingRule(
                field_id="auto.fault_percentage",
                bander=lambda v: band_fault_percentage(float(v)),
                description="Fault percentage"
            ),
            "auto.speeding_over": BandingRule(
                field_id="auto.speeding_over",
                bander=lambda v: band_speeding(int(v)),
                description="Speed over limit"
            ),
            "claim.amount": BandingRule(
                field_id="claim.amount",
                bander=lambda v: band_claim_amount(float(v), "auto"),
                description="Claim amount"
            ),
        }

    def _build_marine_rules(self) -> dict[str, BandingRule]:
        """Build marine insurance banding rules."""
        return {
            "marine.navigation_distance": BandingRule(
                field_id="marine.navigation_distance",
                bander=lambda v: band_navigation_distance(float(v)),
                description="Navigation distance in nautical miles"
            ),
            "marine.jurisdiction": BandingRule(
                field_id="marine.jurisdiction",
                bander=lambda v: self._band_marine_jurisdiction(v),
                description="Jurisdictional waters"
            ),
            "marine.layup_status": BandingRule(
                field_id="marine.layup_status",
                bander=lambda v: self._band_layup_status(v),
                description="Layup period compliance"
            ),
            "marine.maintenance_status": BandingRule(
                field_id="marine.maintenance_status",
                bander=lambda v: self._band_maintenance_status(v),
                description="Maintenance compliance"
            ),
            "marine.vessel_type": BandingRule(
                field_id="marine.vessel_type",
                bander=lambda v: self._band_vessel_type(v),
                description="Vessel type"
            ),
            "claim.amount": BandingRule(
                field_id="claim.amount",
                bander=lambda v: band_claim_amount(float(v), "marine"),
                description="Claim amount"
            ),
        }

    def _build_property_rules(self) -> dict[str, BandingRule]:
        """Build property insurance banding rules."""
        return {
            "prop.loss_cause": BandingRule(
                field_id="prop.loss_cause",
                bander=lambda v: self._band_loss_cause(v),
                description="Loss cause"
            ),
            "prop.days_vacant": BandingRule(
                field_id="prop.days_vacant",
                bander=lambda v: band_vacancy_days(int(v)),
                description="Days vacant"
            ),
            "claim.amount": BandingRule(
                field_id="claim.amount",
                bander=lambda v: band_claim_amount(float(v), "property"),
                description="Claim amount"
            ),
        }

    def _build_cgl_rules(self) -> dict[str, BandingRule]:
        """Build CGL insurance banding rules."""
        return {
            "cgl.business_type": BandingRule(
                field_id="cgl.business_type",
                bander=lambda v: self._band_business_type(v),
                description="Business type hazard level"
            ),
            "cgl.annual_revenue": BandingRule(
                field_id="cgl.annual_revenue",
                bander=lambda v: self._band_revenue(float(v)),
                description="Annual revenue"
            ),
            "cgl.injury_type": BandingRule(
                field_id="cgl.injury_type",
                bander=lambda v: self._band_injury_type(v),
                description="Injury severity"
            ),
            "cgl.negligence_type": BandingRule(
                field_id="cgl.negligence_type",
                bander=lambda v: self._band_negligence(v),
                description="Negligence type"
            ),
            "claim.amount": BandingRule(
                field_id="claim.amount",
                bander=lambda v: band_claim_amount(float(v), "cgl"),
                description="Claim amount"
            ),
        }

    def _build_health_rules(self) -> dict[str, BandingRule]:
        """Build health insurance banding rules."""
        return {
            "health.coverage_months": BandingRule(
                field_id="health.coverage_months",
                bander=lambda v: self._band_coverage_months(int(v)),
                description="Coverage duration"
            ),
            "health.drug_cost": BandingRule(
                field_id="health.drug_cost",
                bander=lambda v: self._band_drug_cost(float(v)),
                description="Drug cost"
            ),
        }

    def _build_wsib_rules(self) -> dict[str, BandingRule]:
        """Build WSIB banding rules."""
        return {
            "wsib.injury_type": BandingRule(
                field_id="wsib.injury_type",
                bander=lambda v: self._band_wsib_injury(v),
                description="WSIB injury type"
            ),
        }

    def _build_eo_rules(self) -> dict[str, BandingRule]:
        """Build E&O banding rules."""
        return {
            "eo.claim_amount": BandingRule(
                field_id="eo.claim_amount",
                bander=lambda v: band_claim_amount(float(v), "eo"),
                description="Claim amount"
            ),
        }

    def _build_travel_rules(self) -> dict[str, BandingRule]:
        """Build travel insurance banding rules."""
        return {
            "travel.treatment_cost": BandingRule(
                field_id="travel.treatment_cost",
                bander=lambda v: self._band_treatment_cost(float(v)),
                description="Treatment cost"
            ),
        }

    def _build_banking_rules(self) -> dict[str, BandingRule]:
        """Build banking/AML banding rules."""
        return {
            "transaction.amount": BandingRule(
                field_id="transaction.amount",
                bander=lambda v: band_transaction_amount(float(v)),
                description="Transaction amount"
            ),
            "transaction.frequency": BandingRule(
                field_id="transaction.frequency",
                bander=lambda v: band_transaction_velocity(int(v)),
                description="Transaction frequency"
            ),
            "subject.risk_score": BandingRule(
                field_id="subject.risk_score",
                bander=lambda v: band_risk_score(float(v)),
                description="Risk score"
            ),
            "subject.pep_status": BandingRule(
                field_id="subject.pep_status",
                bander=lambda v: self._band_pep_status(v),
                description="PEP status"
            ),
            "geography.jurisdiction": BandingRule(
                field_id="geography.jurisdiction",
                bander=lambda v: self._band_banking_jurisdiction(v),
                description="Geographic risk"
            ),
        }

    # =========================================================================
    # Helper banding functions
    # =========================================================================

    def _parse_bac(self, value: str) -> float:
        """Parse BAC from string like '0_08' to float."""
        if isinstance(value, (int, float)):
            return float(value)
        # Handle formats like "0_08" or "0.08"
        value = str(value).replace("_", ".")
        try:
            return float(value)
        except ValueError:
            return 0.0

    def _band_vehicle_use(self, value: str) -> str:
        """Band vehicle use type."""
        value_lower = str(value).lower()
        mapping = {
            "personal": AutoVehicleUseBand.PERSONAL.value,
            "commute": AutoVehicleUseBand.COMMUTE.value,
            "business": AutoVehicleUseBand.BUSINESS.value,
            "rideshare": AutoVehicleUseBand.RIDESHARE.value,
            "rideshare_delivery": AutoVehicleUseBand.RIDESHARE.value,
            "delivery": AutoVehicleUseBand.DELIVERY.value,
            "commercial": AutoVehicleUseBand.COMMERCIAL.value,
            "racing": AutoVehicleUseBand.RACING.value,
        }
        return mapping.get(value_lower, AutoVehicleUseBand.PERSONAL.value)

    def _band_marine_jurisdiction(self, value: str) -> str:
        """Band marine jurisdiction."""
        value_lower = str(value).lower()
        if "great_lakes" in value_lower or "great lakes" in value_lower:
            return MarineJurisdictionBand.GREAT_LAKES.value
        elif "international" in value_lower:
            return MarineJurisdictionBand.INTERNATIONAL_WATERS.value
        elif any(x in value_lower for x in ["us", "foreign", "out_of_country"]):
            return MarineJurisdictionBand.OUT_OF_COUNTRY.value
        return MarineJurisdictionBand.DOMESTIC.value

    def _band_layup_status(self, value: str) -> str:
        """Band layup status."""
        value_lower = str(value).lower()
        if value_lower in ["compliant", "true", "yes"]:
            return MarineLayupBand.COMPLIANT.value
        elif "in_water" in value_lower or "in water" in value_lower:
            return MarineLayupBand.IN_WATER_PROHIBITED.value
        return MarineLayupBand.STORAGE_VIOLATION.value

    def _band_maintenance_status(self, value: str) -> str:
        """Band maintenance status."""
        value_lower = str(value).lower()
        if value_lower in ["current", "true", "yes", "compliant"]:
            return MarineMaintenanceBand.CURRENT.value
        elif "minor" in value_lower:
            return MarineMaintenanceBand.MINOR_LAPSE.value
        return MarineMaintenanceBand.NEGLECT.value

    def _band_vessel_type(self, value: str) -> str:
        """Band vessel type."""
        value_lower = str(value).lower()
        if "sail" in value_lower:
            return MarineVesselTypeBand.SAILBOAT.value
        elif any(x in value_lower for x in ["pwc", "jet", "personal"]):
            return MarineVesselTypeBand.PERSONAL_WATERCRAFT.value
        elif "house" in value_lower:
            return MarineVesselTypeBand.HOUSEBOAT.value
        elif "commercial" in value_lower:
            return MarineVesselTypeBand.COMMERCIAL.value
        return MarineVesselTypeBand.POWERBOAT.value

    def _band_loss_cause(self, value: str) -> str:
        """Band property loss cause."""
        value_lower = str(value).lower()
        mapping = {
            "fire": PropertyLossCauseBand.FIRE.value,
            "pipe_burst": PropertyLossCauseBand.WATER_SUDDEN.value,
            "water_sudden": PropertyLossCauseBand.WATER_SUDDEN.value,
            "gradual": PropertyLossCauseBand.WATER_GRADUAL.value,
            "water_gradual": PropertyLossCauseBand.WATER_GRADUAL.value,
            "flood": PropertyLossCauseBand.FLOOD.value,
            "flood_surface_water": PropertyLossCauseBand.FLOOD.value,
            "wind": PropertyLossCauseBand.WIND_HAIL.value,
            "hail": PropertyLossCauseBand.WIND_HAIL.value,
            "wind_hail": PropertyLossCauseBand.WIND_HAIL.value,
            "theft": PropertyLossCauseBand.THEFT.value,
            "vandalism": PropertyLossCauseBand.VANDALISM.value,
            "earthquake": PropertyLossCauseBand.EARTHQUAKE.value,
        }
        return mapping.get(value_lower, "OTHER")

    def _band_business_type(self, value: str) -> str:
        """Band CGL business type."""
        value_lower = str(value).lower()
        high_hazard = ["roofing", "electrical", "plumbing", "construction", "demolition"]
        professional = ["lawyer", "accountant", "consultant", "architect", "engineer"]
        hospitality = ["restaurant", "hotel", "bar", "club"]

        if any(x in value_lower for x in high_hazard):
            return CGLBusinessTypeBand.HIGH_HAZARD_TRADE.value
        elif any(x in value_lower for x in professional):
            return CGLBusinessTypeBand.PROFESSIONAL.value
        elif any(x in value_lower for x in hospitality):
            return CGLBusinessTypeBand.HOSPITALITY.value
        elif any(x in value_lower for x in ["manufacturing", "warehouse"]):
            return CGLBusinessTypeBand.MODERATE_HAZARD.value
        return CGLBusinessTypeBand.LOW_HAZARD.value

    def _band_revenue(self, value: float) -> str:
        """Band annual revenue."""
        if value < 500000:
            return CGLRevenueBand.MICRO.value
        elif value < 2000000:
            return CGLRevenueBand.SMALL.value
        elif value < 10000000:
            return CGLRevenueBand.MID_COMMERCIAL.value
        elif value < 50000000:
            return CGLRevenueBand.LARGE.value
        return CGLRevenueBand.ENTERPRISE.value

    def _band_injury_type(self, value: str) -> str:
        """Band injury type."""
        value_lower = str(value).lower()
        if "fatal" in value_lower or "death" in value_lower:
            return CGLInjuryTypeBand.FATALITY.value
        elif any(x in value_lower for x in ["severe", "permanent", "catastrophic"]):
            return CGLInjuryTypeBand.BODILY_INJURY_SEVERE.value
        elif any(x in value_lower for x in ["moderate", "fracture", "surgery"]):
            return CGLInjuryTypeBand.BODILY_INJURY_MODERATE.value
        elif any(x in value_lower for x in ["minor", "bruise", "sprain"]):
            return CGLInjuryTypeBand.BODILY_INJURY_MINOR.value
        return CGLInjuryTypeBand.NO_INJURY.value

    def _band_negligence(self, value: str) -> str:
        """Band negligence type."""
        value_lower = str(value).lower()
        if "gross" in value_lower:
            return CGLNegligenceBand.GROSS_NEGLIGENCE.value
        elif "willful" in value_lower or "intentional" in value_lower:
            return CGLNegligenceBand.WILLFUL.value
        elif "contributory" in value_lower:
            return CGLNegligenceBand.CONTRIBUTORY.value
        return CGLNegligenceBand.ORDINARY.value

    def _band_coverage_months(self, months: int) -> str:
        """Band health coverage duration."""
        if months < 3:
            return "NEW"
        elif months < 12:
            return "WAITING"
        return "ESTABLISHED"

    def _band_drug_cost(self, cost: float) -> str:
        """Band drug cost."""
        if cost < 100:
            return "LOW"
        elif cost < 500:
            return "MEDIUM"
        elif cost < 1000:
            return "HIGH"
        return "SPECIALTY"

    def _band_wsib_injury(self, value: str) -> str:
        """Band WSIB injury type."""
        value_lower = str(value).lower()
        if "fatal" in value_lower:
            return "FATALITY"
        elif "mental" in value_lower or "psychological" in value_lower:
            return "MENTAL_HEALTH"
        elif "repetitive" in value_lower:
            return "REPETITIVE_STRAIN"
        elif "fracture" in value_lower:
            return "FRACTURE"
        elif "laceration" in value_lower:
            return "LACERATION"
        return "STRAIN_SPRAIN"

    def _band_treatment_cost(self, cost: float) -> str:
        """Band travel treatment cost."""
        if cost < 1000:
            return "LOW"
        elif cost < 10000:
            return "MEDIUM"
        elif cost < 50000:
            return "HIGH"
        return "CRITICAL"

    def _band_pep_status(self, value: str) -> str:
        """Band PEP status."""
        value_lower = str(value).lower()
        if value_lower in ["no", "false", "none", "not_pep"]:
            return BankingPEPBand.NOT_PEP.value
        elif "foreign" in value_lower:
            return BankingPEPBand.PEP_FOREIGN.value
        elif "family" in value_lower:
            return BankingPEPBand.PEP_FAMILY.value
        elif "associate" in value_lower:
            return BankingPEPBand.PEP_ASSOCIATE.value
        return BankingPEPBand.PEP_DOMESTIC.value

    def _band_banking_jurisdiction(self, value: str) -> str:
        """Band banking jurisdiction risk."""
        value_lower = str(value).lower()
        high_risk = ["cayman", "panama", "bvi", "cyprus", "malta"]
        sanctioned = ["iran", "north korea", "syria", "cuba", "russia"]

        if any(x in value_lower for x in sanctioned):
            return BankingJurisdictionBand.SANCTIONED.value
        elif any(x in value_lower for x in high_risk):
            return BankingJurisdictionBand.HIGH_RISK_JURISDICTION.value
        elif any(x in value_lower for x in ["offshore", "secrecy"]):
            return BankingJurisdictionBand.MODERATE_RISK.value
        return BankingJurisdictionBand.LOW_RISK.value

    # =========================================================================
    # Main banding method
    # =========================================================================

    def band_value(self, vertical: str, field_id: str, value: Any) -> str:
        """
        Band a single value.

        Args:
            vertical: The vertical (auto, marine, property, etc.)
            field_id: The field identifier
            value: The raw value to band

        Returns:
            The banded category string, or 'OTHER' if no rule found
        """
        vertical_lower = vertical.lower()
        if vertical_lower not in self._rules:
            return "OTHER"

        rules = self._rules[vertical_lower]
        if field_id not in rules:
            return "OTHER"

        try:
            return rules[field_id].bander(value)
        except Exception:
            return "OTHER"

    def band_facts(self, vertical: str, facts: dict[str, Any]) -> dict[str, str]:
        """
        Band all facts for a vertical.

        Args:
            vertical: The vertical (auto, marine, property, etc.)
            facts: Dictionary of field_id -> raw value

        Returns:
            Dictionary of field_id -> banded category
        """
        banded: dict[str, str] = {}
        for field_id, value in facts.items():
            banded[field_id] = self.band_value(vertical, field_id, value)
        return banded

    def get_supported_fields(self, vertical: str) -> list[str]:
        """Get list of supported fields for a vertical."""
        vertical_lower = vertical.lower()
        if vertical_lower not in self._rules:
            return []
        return list(self._rules[vertical_lower].keys())

    def get_supported_verticals(self) -> list[str]:
        """Get list of supported verticals."""
        return list(self._rules.keys())


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Library class
    "BandingLibrary",
    "BandingRule",

    # Universal bands
    "RegimeBand",
    "AuthorityBand",
    "ConflictBand",

    # Auto bands
    "AutoBACBand",
    "AutoLicenseClassBand",
    "AutoLicenseStatusBand",
    "AutoVehicleUseBand",
    "AutoVehicleValueBand",
    "AutoModificationBand",
    "AutoFaultBand",
    "AutoSpeedingBand",
    "AutoImpactBand",

    # Marine bands
    "MarineNavigationBand",
    "MarineJurisdictionBand",
    "MarineLayupBand",
    "MarineMaintenanceBand",
    "MarineVesselTypeBand",
    "MarineEngineTypeBand",

    # CGL bands
    "CGLBusinessTypeBand",
    "CGLRevenueBand",
    "CGLInjuryTypeBand",
    "CGLLocationBand",
    "CGLNegligenceBand",

    # Property bands
    "PropertyLossCauseBand",
    "PropertyVacancyBand",
    "PropertyClaimAmountBand",

    # Banking bands
    "BankingAmountBand",
    "BankingVelocityBand",
    "BankingJurisdictionBand",
    "BankingPEPBand",
    "BankingRiskScoreBand",
    "BankingAdverseMediaBand",

    # Banding functions
    "band_bac_level",
    "band_license_status",
    "band_vehicle_value",
    "band_fault_percentage",
    "band_speeding",
    "band_navigation_distance",
    "band_claim_amount",
    "band_vacancy_days",
    "band_transaction_amount",
    "band_transaction_velocity",
    "band_risk_score",
]

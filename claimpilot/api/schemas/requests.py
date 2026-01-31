"""Request schemas for the API."""

from pydantic import BaseModel, Field
from typing import Any


class FactInput(BaseModel):
    """A single fact about the claim."""
    field: str = Field(..., description="Fact field name, e.g., 'vehicle.use_at_loss'")
    value: Any = Field(..., description="Fact value")
    certainty: str = Field(default="reported", description="confirmed|reported|inferred|disputed")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"field": "vehicle.use_at_loss", "value": "personal", "certainty": "confirmed"},
                {"field": "driver.bac_level", "value": 0.0, "certainty": "confirmed"},
            ]
        }
    }


class EvidenceInput(BaseModel):
    """Evidence document collected."""
    doc_type: str = Field(..., description="Document type, e.g., 'police_report'")
    status: str = Field(default="verified", description="verified|received|requested")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"doc_type": "police_report", "status": "verified"},
                {"doc_type": "damage_estimate", "status": "verified"},
            ]
        }
    }


class EvaluateRequest(BaseModel):
    """Request to evaluate a claim."""
    policy_id: str = Field(..., description="Policy pack ID, e.g., 'CA-ON-OAP1-2024'")
    loss_type: str = Field(..., description="Type of loss, e.g., 'collision'")
    loss_date: str = Field(..., description="Date of loss (ISO format: YYYY-MM-DD)")
    report_date: str = Field(..., description="Date reported (ISO format: YYYY-MM-DD)")
    claimant_type: str = Field(default="insured", description="insured|third_party|claimant")
    facts: list[FactInput] = Field(..., description="List of claim facts")
    evidence: list[EvidenceInput] = Field(default=[], description="Evidence collected")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "policy_id": "CA-ON-OAP1-2024",
                    "loss_type": "collision",
                    "loss_date": "2024-06-15",
                    "report_date": "2024-06-15",
                    "claimant_type": "insured",
                    "facts": [
                        {"field": "policy.status", "value": "active"},
                        {"field": "vehicle.use_at_loss", "value": "personal"},
                        {"field": "driver.rideshare_app_active", "value": False},
                        {"field": "driver.bac_level", "value": 0.0},
                        {"field": "driver.license_status", "value": "valid"},
                    ],
                    "evidence": [
                        {"doc_type": "police_report", "status": "verified"},
                        {"doc_type": "damage_estimate", "status": "verified"},
                    ]
                }
            ]
        }
    }

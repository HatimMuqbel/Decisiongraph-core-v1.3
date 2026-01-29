"""
DecisionGraph FastAPI Service

REST API for bank-grade AML/KYC decision engine.

Endpoints:
    POST /decide - Run decision engine on a case
    GET /health - Health check
    GET /version - Version info
    POST /validate - Validate input against schema
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from decisiongraph.decision_pack import (
    build_decision_pack,
    compute_input_hash,
    ENGINE_VERSION,
    POLICY_VERSION,
)
from decisiongraph.escalation_gate import run_escalation_gate, EscalationDecision
from decisiongraph.str_gate import run_str_gate, dual_gate_decision

# Environment config
DG_ENGINE_VERSION = os.getenv("DG_ENGINE_VERSION", ENGINE_VERSION)
DG_POLICY_VERSION = os.getenv("DG_POLICY_VERSION", POLICY_VERSION)
DG_JURISDICTION = os.getenv("DG_JURISDICTION", "CA")

if HAS_FASTAPI:
    app = FastAPI(
        title="DecisionGraph",
        description="Bank-grade AML/KYC Decision Engine",
        version=DG_ENGINE_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    class DecisionRequest(BaseModel):
        """Input case for decision."""
        header: Dict[str, Any]
        alert_details: Dict[str, Any]
        customer_record: Dict[str, Any]
        transaction_history_slice: list
        screening_payload: Dict[str, Any]
        # Optional pre-extracted fields
        facts: Optional[Dict[str, Any]] = None
        obligations: Optional[list] = None
        indicators: Optional[list] = None
        typology_maturity: Optional[str] = "FORMING"
        mitigations: Optional[list] = None
        suspicion_evidence: Optional[Dict[str, bool]] = None
        instrument_type: Optional[str] = None
        evidence_quality: Optional[Dict[str, Any]] = None
        mitigation_status: Optional[Dict[str, Any]] = None
        typology_confirmed: Optional[bool] = False

    class HealthResponse(BaseModel):
        """Health check response."""
        status: str
        timestamp: str
        engine_version: str
        policy_version: str

    class VersionResponse(BaseModel):
        """Version info response."""
        engine_version: str
        policy_version: str
        input_schema_version: str
        output_schema_version: str
        jurisdiction: str

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(timezone.utc).isoformat(),
            engine_version=DG_ENGINE_VERSION,
            policy_version=DG_POLICY_VERSION,
        )

    @app.get("/version", response_model=VersionResponse)
    async def version_info():
        """Version information endpoint."""
        return VersionResponse(
            engine_version=DG_ENGINE_VERSION,
            policy_version=DG_POLICY_VERSION,
            input_schema_version="1.0.0",
            output_schema_version="1.0.0",
            jurisdiction=DG_JURISDICTION,
        )

    @app.post("/decide")
    async def decide(request: DecisionRequest):
        """
        Run decision engine on a case.

        Returns a complete decision pack with:
        - Decision outcome (verdict, action, STR required)
        - 6-layer taxonomy analysis
        - Dual-gate results
        - Rationale and compliance details
        - Reproducibility metadata
        """
        try:
            case_data = request.model_dump()

            # Extract case ID
            case_id = case_data.get("alert_details", {}).get("external_id", "UNKNOWN")

            # Use provided fields or extract from case
            facts = request.facts or extract_facts(case_data)
            obligations = request.obligations or extract_obligations(case_data)
            indicators = request.indicators or []
            typology_maturity = request.typology_maturity or "FORMING"
            mitigations = request.mitigations or []
            suspicion_evidence = request.suspicion_evidence or {
                "has_intent": False,
                "has_deception": False,
                "has_sustained_pattern": False,
            }
            instrument_type = request.instrument_type or extract_instrument_type(case_data)
            evidence_quality = request.evidence_quality or {}
            mitigation_status = request.mitigation_status or {}
            typology_confirmed = request.typology_confirmed

            # Run Gate 1
            esc_result = run_escalation_gate(
                facts=facts,
                instrument_type=instrument_type,
                obligations=obligations,
                indicators=indicators,
                typology_maturity=typology_maturity,
                mitigations=mitigations,
                suspicion_evidence=suspicion_evidence,
            )

            # Run Gate 2
            str_result = run_str_gate(
                suspicion_evidence=suspicion_evidence,
                evidence_quality=evidence_quality,
                mitigation_status=mitigation_status,
                typology_confirmed=typology_confirmed,
                facts=facts,
            )

            # Combine decisions
            final_decision = dual_gate_decision(
                escalation_allowed=(esc_result.decision == EscalationDecision.PERMITTED),
                str_result=str_result,
            )

            # Build decision pack
            decision_pack = build_decision_pack(
                case_id=case_id,
                input_data=case_data,
                facts=facts,
                obligations=obligations,
                indicators=indicators,
                typology_maturity=typology_maturity,
                mitigations=mitigations,
                suspicion_evidence=suspicion_evidence,
                esc_result=esc_result,
                str_result=str_result,
                final_decision=final_decision,
                jurisdiction=DG_JURISDICTION,
            )

            return JSONResponse(content=decision_pack)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/validate")
    async def validate_input(request: Request):
        """Validate input case against schema."""
        try:
            body = await request.json()
            input_hash = compute_input_hash(body)

            # Basic validation
            required_fields = [
                "header", "alert_details", "customer_record",
                "transaction_history_slice", "screening_payload"
            ]
            missing = [f for f in required_fields if f not in body]

            if missing:
                return JSONResponse(
                    status_code=400,
                    content={
                        "valid": False,
                        "errors": [f"Missing required field: {f}" for f in missing],
                        "input_hash": input_hash,
                    }
                )

            return JSONResponse(content={
                "valid": True,
                "errors": [],
                "input_hash": input_hash,
            })

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    def extract_facts(case_data: dict) -> dict:
        """Extract Layer 1 facts from case data."""
        screening = case_data.get("screening_payload", {})
        top_match = screening.get("top_match", {})

        sanctions_result = "NO_MATCH"
        if top_match and top_match.get("list_type", "").startswith(("OFAC", "UN_", "EU_", "UK_", "CA_")):
            if top_match.get("match_score", 0) >= 90:
                sanctions_result = "MATCH"

        adverse_media = screening.get("adverse_media", {})
        adverse_media_mltf = adverse_media.get("mltf_linked", False)

        return {
            "sanctions_result": sanctions_result,
            "document_status": "VALID",
            "customer_response": "COMPLIANT",
            "adverse_media_mltf": adverse_media_mltf,
            "legal_prohibition": False,
        }

    def extract_obligations(case_data: dict) -> list:
        """Extract Layer 2 obligations from case data."""
        obligations = []
        customer = case_data.get("customer_record", {})

        if customer.get("pep_flag") == "Y":
            category = customer.get("pep_category_code", "FOREIGN")
            obligations.append(f"PEP_{category}")

        return obligations

    def extract_instrument_type(case_data: dict) -> str:
        """Extract instrument type from transactions."""
        transactions = case_data.get("transaction_history_slice", [])
        if not transactions:
            return "unknown"

        methods = set(t.get("method", "").lower() for t in transactions)
        if len(methods) > 1:
            return "mixed"

        method = methods.pop() if methods else "unknown"
        return {
            "wire": "wire",
            "cash": "cash",
            "crypto": "crypto",
            "cheque": "cheque",
        }.get(method, "unknown")

else:
    # Fallback when FastAPI not installed
    print("FastAPI not installed. Install with: pip install fastapi uvicorn")
    print("Running in CLI-only mode.")

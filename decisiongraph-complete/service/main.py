"""
DecisionGraph FastAPI Service (Bank-Grade)

REST API for AML/KYC decision engine with full audit trail.

Endpoints:
    POST /decide      - Run decision engine, returns Decision Pack JSON
    GET  /health      - Liveness probe (process alive)
    GET  /ready       - Readiness probe (dependencies loaded)
    GET  /version     - Version info
    GET  /schemas     - Schema versions and content
    GET  /policy      - Policy pack info
    GET  /decisions/{id} - Replay decision by ID
    POST /validate    - Validate input against schema
"""

import hashlib
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    print("FastAPI not installed. Install with: pip install fastapi uvicorn")
    sys.exit(1)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from decisiongraph.decision_pack import (
    build_decision_pack,
    compute_input_hash,
    canonicalize_json,
    ENGINE_VERSION,
    POLICY_VERSION,
)
from decisiongraph.escalation_gate import run_escalation_gate, EscalationDecision
from decisiongraph.str_gate import run_str_gate, dual_gate_decision

# Precedent system imports
from decisiongraph.chain import Chain
from decisiongraph.cell import NULL_HASH
from decisiongraph.precedent_registry import PrecedentRegistry
from decisiongraph.aml_seed_generator import generate_all_banking_seeds
from decisiongraph.aml_fingerprint import (
    AMLFingerprintSchemaRegistry,
    apply_aml_banding,
    create_txn_amount_banding,
)
from decisiongraph.judgment import create_judgment_cell

# Import routers
from service.routers import demo, report, verify, templates
from service.template_loader import TemplateLoader, set_cache_decision, set_precedent_query

# =============================================================================
# Configuration
# =============================================================================

DG_ENGINE_VERSION = os.getenv("DG_ENGINE_VERSION", ENGINE_VERSION)
DG_POLICY_VERSION = os.getenv("DG_POLICY_VERSION", POLICY_VERSION)
DG_JURISDICTION = os.getenv("DG_JURISDICTION", "CA")
DG_DOMAIN = os.getenv("DG_DOMAIN", "banking_aml")
DG_LOG_LEVEL = os.getenv("DG_LOG_LEVEL", "INFO")
DG_DOCS_ENABLED = os.getenv("DG_DOCS_ENABLED", "true").lower() == "true"
DG_MAX_REQUEST_SIZE = int(os.getenv("DG_MAX_REQUEST_SIZE", "1048576"))  # 1MB default
DG_PRECEDENT_CODE_WEIGHT = float(os.getenv("DG_PRECEDENT_CODE_WEIGHT", "0.6"))
DG_PRECEDENT_FINGERPRINT_WEIGHT = float(os.getenv("DG_PRECEDENT_FINGERPRINT_WEIGHT", "0.4"))
DG_MODE = os.getenv("DG_MODE", "prod").lower()
DG_PRECEDENT_THRESHOLD_PROD = float(os.getenv("DG_PRECEDENT_THRESHOLD_PROD", "0.60"))
DG_PRECEDENT_THRESHOLD_DEMO = float(os.getenv("DG_PRECEDENT_THRESHOLD_DEMO", "0.50"))
DG_PRECEDENT_MIN_SCORE = float(os.getenv("DG_PRECEDENT_MIN_SCORE", "0.6"))
DG_PRECEDENT_SALT = os.getenv("DG_PRECEDENT_SALT", "decisiongraph-banking-seed-v1")

# Get git commit: prefer env var (set at build time), fallback to git command
DG_ENGINE_COMMIT = os.getenv("DG_ENGINE_COMMIT")
if not DG_ENGINE_COMMIT or DG_ENGINE_COMMIT == "unknown":
    try:
        import subprocess
        DG_ENGINE_COMMIT = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent.parent,
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except:
        DG_ENGINE_COMMIT = "unknown"

# Compute policy hash (full 64-char SHA-256 for reference, short for display)
POLICY_HASH_FULL = hashlib.sha256(
    f"{DG_POLICY_VERSION}:{DG_ENGINE_VERSION}".encode()
).hexdigest()
POLICY_HASH_SHORT = POLICY_HASH_FULL[:16]

# =============================================================================
# Precedent System (3,000 banking seeds)
# =============================================================================

PRECEDENT_CHAIN: Optional[Chain] = None
PRECEDENT_REGISTRY: Optional[PrecedentRegistry] = None
PRECEDENTS_LOADED = False
PRECEDENT_COUNT = 0
FINGERPRINT_REGISTRY = AMLFingerprintSchemaRegistry()

def load_precedent_seeds():
    """Load the 3,000 banking seed precedents into a Chain."""
    global PRECEDENT_CHAIN, PRECEDENT_REGISTRY, PRECEDENTS_LOADED, PRECEDENT_COUNT

    try:
        # Generate all banking seeds
        seeds = generate_all_banking_seeds()
        PRECEDENT_COUNT = len(seeds)

        # Create a chain and initialize with Genesis
        # Use canonical hash scheme to match JUDGMENT cells
        PRECEDENT_CHAIN = Chain()
        genesis = PRECEDENT_CHAIN.initialize(
            graph_name="BankingPrecedents",
            root_namespace="banking",
            creator="system:seed_loader",
            hash_scheme="canon:rfc8785:v1",
        )

        # Load seeds as JUDGMENT cells
        prev_hash = genesis.cell_id
        graph_id = genesis.header.graph_id

        for payload in seeds:
            # Determine namespace based on reason codes
            code_category = "general"
            if payload.exclusion_codes:
                first_code = payload.exclusion_codes[0]
                # Extract category from code like "RC-TXN-STRUCT" -> "txn"
                parts = first_code.split("-")
                if len(parts) >= 2:
                    code_category = parts[1].lower()

            # Create JUDGMENT cell from payload
            cell = create_judgment_cell(
                payload=payload,
                namespace=f"banking.aml.{code_category}",
                graph_id=graph_id,
                prev_cell_hash=prev_hash,
            )
            PRECEDENT_CHAIN.append(cell)
            prev_hash = cell.cell_id

        # Create the registry
        PRECEDENT_REGISTRY = PrecedentRegistry(PRECEDENT_CHAIN)
        PRECEDENTS_LOADED = True

        return PRECEDENT_COUNT

    except Exception as e:
        logger.error(f"Failed to load precedent seeds: {e}")
        import traceback
        logger.error(traceback.format_exc())
        PRECEDENTS_LOADED = False
        return 0

# =============================================================================
# Logging Setup (Structured JSON)
# =============================================================================

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "external_id"):
            log_entry["external_id"] = record.external_id
        if hasattr(record, "input_hash_short"):
            log_entry["input_hash_short"] = record.input_hash_short
        if hasattr(record, "decision_id_short"):
            log_entry["decision_id_short"] = record.decision_id_short
        if hasattr(record, "verdict"):
            log_entry["verdict"] = record.verdict
        if hasattr(record, "policy_version"):
            log_entry["policy_version"] = record.policy_version
        if hasattr(record, "policy_hash_short"):
            log_entry["policy_hash_short"] = record.policy_hash_short
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        return json.dumps(log_entry)

# Configure logging
logger = logging.getLogger("decisiongraph")
logger.setLevel(getattr(logging, DG_LOG_LEVEL.upper()))
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# =============================================================================
# Schema Loading
# =============================================================================

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"
INPUT_SCHEMA = None
OUTPUT_SCHEMA = None
SCHEMAS_LOADED = False

def load_schemas():
    """Load JSON schemas for validation."""
    global INPUT_SCHEMA, OUTPUT_SCHEMA, SCHEMAS_LOADED

    try:
        input_schema_path = SCHEMAS_DIR / "input.case.schema.json"
        output_schema_path = SCHEMAS_DIR / "output.report.schema.json"

        if input_schema_path.exists():
            with open(input_schema_path) as f:
                INPUT_SCHEMA = json.load(f)

        if output_schema_path.exists():
            with open(output_schema_path) as f:
                OUTPUT_SCHEMA = json.load(f)

        SCHEMAS_LOADED = INPUT_SCHEMA is not None and OUTPUT_SCHEMA is not None
        return SCHEMAS_LOADED
    except Exception as e:
        logger.error(f"Failed to load schemas: {e}")
        return False

# Load schemas on startup
load_schemas()

# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="DecisionGraph",
    description="Bank-grade AML/KYC Decision Engine",
    version=DG_ENGINE_VERSION,
    docs_url="/docs" if DG_DOCS_ENABLED else None,
    redoc_url="/redoc" if DG_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DG_DOCS_ENABLED else None,
)

# CORS (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Template loader
templates_dir = Path(__file__).parent.parent / "templates"
template_loader = TemplateLoader(templates_dir)

# Include routers
app.include_router(demo.router)
app.include_router(report.router)
app.include_router(verify.router)
app.include_router(templates.router)

# Static files for landing page
STATIC_DIR = Path(__file__).parent / "static"
try:
    if STATIC_DIR.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
except Exception as e:
    print(f"Warning: Could not mount static files: {e}")

# =============================================================================
# Request/Response Models
# =============================================================================

class HealthResponse(BaseModel):
    """Liveness probe response."""
    status: str
    timestamp: str
    engine_version: str
    policy_version: str

class ReadyResponse(BaseModel):
    """Readiness probe response."""
    status: str
    timestamp: str
    checks: Dict[str, bool]
    engine_version: str
    policy_version: str
    policy_hash: str
    input_schema_version: str
    output_schema_version: str
    engine_commit: str

class VersionResponse(BaseModel):
    """Version info response."""
    engine_version: str
    policy_version: str
    engine_commit: str
    policy_hash: str
    input_schema_version: str
    output_schema_version: str
    jurisdiction: str

class PolicyResponse(BaseModel):
    """Policy info response."""
    policy_version: str
    policy_hash: str
    engine_version: str
    engine_commit: str
    jurisdiction: str
    absolute_rules: List[str]

class SchemaResponse(BaseModel):
    """Schema info response."""
    input_schema_version: str
    output_schema_version: str
    input_schema: Optional[Dict] = None
    output_schema: Optional[Dict] = None

class ValidationResponse(BaseModel):
    """Validation response."""
    valid: bool
    errors: List[str]
    input_hash: str

class ErrorResponse(BaseModel):
    """Structured error response."""
    error: str
    code: str
    details: Optional[Dict] = None
    request_id: str

# =============================================================================
# Middleware
# =============================================================================

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests."""
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    request.state.start_time = time.time()

    response = await call_next(request)

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id

    return response

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit request body size."""
    if request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > DG_MAX_REQUEST_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request too large",
                    "code": "REQUEST_TOO_LARGE",
                    "details": {"max_size": DG_MAX_REQUEST_SIZE},
                    "request_id": getattr(request.state, "request_id", "unknown"),
                }
            )
    return await call_next(request)

# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Liveness probe - checks if process is alive.
    Always returns quickly. Use /ready for full readiness check.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        engine_version=DG_ENGINE_VERSION,
        policy_version=DG_POLICY_VERSION,
    )

@app.get("/ready", response_model=ReadyResponse, tags=["Health"])
async def readiness_check():
    """
    Readiness probe - checks if service is ready to accept requests.

    Checks:
    - Schemas loaded
    - Policy pack available
    - Required modules importable
    """
    checks = {
        "schemas_loaded": SCHEMAS_LOADED,
        "input_schema_valid": INPUT_SCHEMA is not None,
        "output_schema_valid": OUTPUT_SCHEMA is not None,
        "policy_pack_valid": True,  # Would check actual policy pack
        "jsonschema_available": HAS_JSONSCHEMA,
        "precedents_loaded": PRECEDENTS_LOADED,
    }

    all_ready = all(checks.values())

    response = ReadyResponse(
        status="ready" if all_ready else "not_ready",
        timestamp=datetime.now(timezone.utc).isoformat(),
        checks=checks,
        engine_version=DG_ENGINE_VERSION,
        policy_version=DG_POLICY_VERSION,
        policy_hash=POLICY_HASH_SHORT,
        input_schema_version="1.0.0",
        output_schema_version="1.0.0",
        engine_commit=DG_ENGINE_COMMIT,
    )

    if not all_ready:
        return JSONResponse(
            status_code=503,
            content=response.model_dump()
        )

    return response

# =============================================================================
# Info Endpoints
# =============================================================================

@app.get("/version", response_model=VersionResponse, tags=["Info"])
async def version_info():
    """Return version information for all components."""
    return VersionResponse(
        engine_version=DG_ENGINE_VERSION,
        policy_version=DG_POLICY_VERSION,
        engine_commit=DG_ENGINE_COMMIT,
        policy_hash=POLICY_HASH_SHORT,
        input_schema_version="1.0.0",
        output_schema_version="1.0.0",
        jurisdiction=DG_JURISDICTION,
    )

@app.get("/policy", response_model=PolicyResponse, tags=["Info"])
async def policy_info():
    """Return policy pack information (not content)."""
    return PolicyResponse(
        policy_version=DG_POLICY_VERSION,
        policy_hash=POLICY_HASH_SHORT,
        engine_version=DG_ENGINE_VERSION,
        engine_commit=DG_ENGINE_COMMIT,
        jurisdiction=DG_JURISDICTION,
        absolute_rules=[
            "PEP status alone can NEVER escalate",
            "Cross-border alone can NEVER escalate",
            "Risk score alone can NEVER escalate",
            "'High confidence' can NEVER override facts",
            "'Compliance comfort' is NOT a reason",
        ],
    )

@app.get("/schemas", response_model=SchemaResponse, tags=["Info"])
async def schemas_info(include_content: bool = False):
    """
    Return schema versions and optionally the schema content.

    Query params:
    - include_content: If true, includes full schema JSON
    """
    response = SchemaResponse(
        input_schema_version="1.0.0",
        output_schema_version="1.0.0",
    )

    if include_content:
        response.input_schema = INPUT_SCHEMA
        response.output_schema = OUTPUT_SCHEMA

    return response

# =============================================================================
# Decision Endpoints
# =============================================================================

def compute_decision_id(input_hash: str) -> str:
    """Compute deterministic decision ID from input + versions (full 64-char SHA-256)."""
    combined = f"{input_hash}:{DG_ENGINE_VERSION}:{DG_POLICY_VERSION}"
    return hashlib.sha256(combined.encode()).hexdigest()

def validate_input(data: dict) -> tuple:
    """Validate input against schema. Returns (valid, errors)."""
    if not HAS_JSONSCHEMA or INPUT_SCHEMA is None:
        return True, []

    try:
        validator = Draft202012Validator(INPUT_SCHEMA)
        errors = list(validator.iter_errors(data))
        if errors:
            error_messages = []
            for error in errors[:10]:
                path = " -> ".join(str(p) for p in error.absolute_path)
                error_messages.append(f"{path}: {error.message}" if path else error.message)
            return False, error_messages
        return True, []
    except Exception as e:
        return False, [str(e)]

@app.post("/decide", tags=["Decision"])
async def decide(request: Request):
    """
    Run decision engine on a case.

    Returns a complete Decision Pack JSON with:
    - meta: Reproducibility metadata (engine_version, policy_version, input_hash, etc.)
    - decision: Final verdict, action, STR required, escalation path
    - layers: 6-layer taxonomy analysis
    - gates: Dual-gate results (Gate 1 + Gate 2)
    - rationale: Summary and justification
    - compliance: Regulatory details

    The response includes a decision_id that can be used to replay the decision.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    start_time = getattr(request.state, "start_time", time.time())

    try:
        # Parse request body
        body = await request.json()

        # Validate input against schema
        valid, errors = validate_input(body)
        if not valid:
            logger.warning(
                "Schema validation failed",
                extra={"request_id": request_id}
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Schema validation failed",
                    "code": "SCHEMA_VALIDATION_ERROR",
                    "details": {"errors": errors},
                    "request_id": request_id,
                }
            )

        # Extract case metadata
        external_id = body.get("alert_details", {}).get("external_id", "UNKNOWN")
        input_hash = compute_input_hash(body)
        decision_id = compute_decision_id(input_hash)

        # Extract engine inputs
        facts = body.get("facts", extract_facts(body))
        obligations = body.get("obligations", extract_obligations(body))
        indicators = body.get("indicators", [])
        typology_maturity = body.get("typology_maturity", "FORMING")
        mitigations = body.get("mitigations", [])
        suspicion_evidence = body.get("suspicion_evidence", {
            "has_intent": False,
            "has_deception": False,
            "has_sustained_pattern": False,
        })
        instrument_type = body.get("instrument_type", extract_instrument_type(body))
        evidence_quality = body.get("evidence_quality", {})
        mitigation_status = body.get("mitigation_status", {})
        typology_confirmed = body.get("typology_confirmed", False)
        fintrac_indicators = body.get("fintrac_indicators", [])

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
            case_id=external_id,
            input_data=body,
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
            fintrac_indicators=fintrac_indicators,
            domain=DG_DOMAIN,
        )

        # Add engine commit (decision_pack.py doesn't know about git)
        decision_pack["meta"]["engine_commit"] = DG_ENGINE_COMMIT
        # Note: policy_hash and decision_id are computed by decision_pack.py with full SHA-256

        # Build fingerprint facts for precedent similarity
        fingerprint_facts = {}
        if isinstance(body.get("facts"), dict):
            fingerprint_facts.update(body.get("facts", {}))
        fingerprint_facts.update(facts)
        fingerprint_facts.setdefault("txn.type", instrument_type)
        fingerprint_facts.setdefault(
            "screening.sanctions_match",
            True if facts.get("sanctions_result") == "MATCH" else False,
        )
        fingerprint_facts.setdefault(
            "screening.adverse_media",
            bool(facts.get("adverse_media_mltf")) or bool(facts.get("adverse_media")),
        )
        fingerprint_facts.setdefault("customer.pep", any("PEP" in str(o) for o in obligations))
        fingerprint_facts.setdefault("customer.pep_type", "foreign" if any("FOREIGN" in str(o) for o in obligations) else "domestic")
        fingerprint_facts["gate1_allowed"] = esc_result.decision == EscalationDecision.PERMITTED
        fingerprint_facts["gate2_str_required"] = final_decision.get("str_required", False)

        # Enrich fingerprint facts from input payload when available
        primary_txn = None
        if isinstance(body.get("transaction"), dict):
            primary_txn = body.get("transaction")
        elif isinstance(body.get("events"), list):
            for event in body.get("events", []):
                if isinstance(event, dict) and event.get("event_type") == "transaction":
                    primary_txn = event
                    break

        if primary_txn:
            txn_method = (
                primary_txn.get("payment_method")
                or primary_txn.get("method")
                or primary_txn.get("type")
            )
            if txn_method:
                fingerprint_facts.setdefault("txn.type", txn_method)

            txn_amount = (
                primary_txn.get("amount_cad")
                or primary_txn.get("amount")
                or primary_txn.get("amount_value")
            )
            if txn_amount is not None and "txn.amount_band" not in fingerprint_facts:
                try:
                    amount_band = create_txn_amount_banding().apply(txn_amount)
                    fingerprint_facts["txn.amount_band"] = amount_band
                except Exception:
                    pass

            destination_country = (
                primary_txn.get("destination_country")
                or primary_txn.get("counterparty_country")
            )
            if destination_country and "txn.cross_border" not in fingerprint_facts:
                case_jurisdiction = (
                    (body.get("meta") or {}).get("jurisdiction")
                    or DG_JURISDICTION
                )
                fingerprint_facts["txn.cross_border"] = str(destination_country) != str(case_jurisdiction)

            if primary_txn.get("destination_country_risk") is not None:
                fingerprint_facts.setdefault(
                    "txn.destination_country_risk",
                    primary_txn.get("destination_country_risk"),
                )

        if "customer.type" not in fingerprint_facts:
            primary_entity_type = (body.get("meta") or {}).get("primary_entity_type")
            if primary_entity_type:
                fingerprint_facts["customer.type"] = primary_entity_type
            else:
                has_orgs = bool(body.get("organizations"))
                has_inds = bool(body.get("individuals"))
                if has_orgs and not has_inds:
                    fingerprint_facts["customer.type"] = "corporation"
                elif has_inds and not has_orgs:
                    fingerprint_facts["customer.type"] = "individual"
                elif has_orgs and has_inds:
                    fingerprint_facts["customer.type"] = "mixed"

        if "customer.relationship_length" not in fingerprint_facts and isinstance(body.get("assertions"), list):
            for assertion in body.get("assertions", []):
                if not isinstance(assertion, dict):
                    continue
                if assertion.get("predicate") in {"relationship_tenure", "relationship_length"}:
                    value = assertion.get("value")
                    if value is not None:
                        fingerprint_facts["customer.relationship_length"] = value
                        break

        # Query similar precedents and add to decision pack
        reason_codes = extract_reason_codes(facts, indicators, obligations)
        proposed_outcome = decision_pack["decision"]["verdict"].lower()
        # Map verdict to precedent outcome codes
        outcome_map = {
            "str": "escalate",
            "escalate": "escalate",
            "hard_stop": "deny",
            "pass": "pay",
            "pass_with_edd": "pay",
        }
        proposed_outcome = outcome_map.get(proposed_outcome, "escalate")

        precedent_analysis = query_similar_precedents(
            reason_codes=reason_codes,
            proposed_outcome=proposed_outcome,
            domain=decision_pack.get("meta", {}).get("domain"),
            case_facts=fingerprint_facts,
            jurisdiction=DG_JURISDICTION,
        )
        decision_pack["precedent_analysis"] = precedent_analysis

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log decision (short hashes for readability, full hashes in decision pack)
        logger.info(
            "Decision complete",
            extra={
                "request_id": request_id,
                "external_id": external_id,
                "input_hash_short": decision_pack["meta"]["input_hash"][:16],
                "decision_id_short": decision_pack["meta"]["decision_id"][:16],
                "verdict": decision_pack["decision"]["verdict"],
                "policy_version": DG_POLICY_VERSION,
                "policy_hash_short": decision_pack["meta"]["policy_hash"][:16],
                "duration_ms": duration_ms,
            }
        )

        # Cache decision for report generation
        report.cache_decision(decision_pack["meta"]["decision_id"], decision_pack)

        return JSONResponse(content=decision_pack)

    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid JSON",
                "code": "INVALID_JSON",
                "request_id": request_id,
            }
        )
    except Exception as e:
        logger.exception(f"Decision failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "code": "INTERNAL_ERROR",
                "request_id": request_id,
            }
        )

@app.get("/decisions/{decision_id}", tags=["Decision"])
async def replay_decision(decision_id: str, request: Request):
    """
    Replay a decision by ID.

    Note: This endpoint requires the original input to be provided
    as the system is stateless. The decision_id ensures the same
    input produces the same output.

    For full replay, POST to /decide with the original input.
    """
    return JSONResponse(
        status_code=501,
        content={
            "error": "Stateless replay not implemented",
            "code": "NOT_IMPLEMENTED",
            "details": {
                "message": "Decision replay requires original input. POST to /decide with the same input to reproduce the decision.",
                "decision_id": decision_id,
            },
            "request_id": getattr(request.state, "request_id", "unknown"),
        }
    )

@app.post("/validate", response_model=ValidationResponse, tags=["Validation"])
async def validate_input_endpoint(request: Request):
    """
    Validate input case against schema without running decision.

    Returns validation result with input hash.
    """
    try:
        body = await request.json()
        input_hash = compute_input_hash(body)
        valid, errors = validate_input(body)

        return ValidationResponse(
            valid=valid,
            errors=errors,
            input_hash=input_hash,
        )
    except json.JSONDecodeError:
        return ValidationResponse(
            valid=False,
            errors=["Invalid JSON"],
            input_hash="",
        )

# =============================================================================
# Helper Functions
# =============================================================================

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


def extract_reason_codes(facts: dict, indicators: list, obligations: list) -> list:
    """
    Extract reason codes from case facts for precedent matching.

    Maps case characteristics to AML reason codes used in the seed precedents.
    Uses codes that match the banking AML seed generator format.
    """
    codes = []

    # Sanctions-related (matches RC-SCR-* codes in seeds)
    if facts.get("sanctions_result") == "MATCH":
        codes.append("RC-SCR-SANCTION")
        codes.append("RC-SCR-OFAC")

    # Adverse media (matches RC-KYC-ADVERSE-* codes in seeds)
    if facts.get("adverse_media_mltf"):
        codes.append("RC-KYC-ADVERSE-MAJOR")
    elif facts.get("adverse_media"):
        codes.append("RC-KYC-ADVERSE-MINOR")

    # PEP-related (matches RC-TXN-PEP and RC-KYC-PEP-* codes in seeds)
    if any("PEP" in str(o) for o in obligations):
        codes.append("RC-TXN-PEP")
        codes.append("RC-TXN-PEP-EDD")
        codes.append("RC-KYC-PEP-APPROVED")

    # Structuring indicators (matches RC-TXN-STRUCT-* codes in seeds)
    for ind in indicators:
        ind_type = ind.get("type", "").upper() if isinstance(ind, dict) else str(ind).upper()
        if "STRUCTUR" in ind_type:
            codes.append("RC-TXN-STRUCT")
            codes.append("RC-TXN-STRUCT-MULTI")
        if "LAYER" in ind_type or "RAPID" in ind_type:
            codes.append("RC-TXN-LAYER")
            codes.append("RC-TXN-RAPID")
        if "CRYPTO" in ind_type or "VIRTUAL" in ind_type:
            codes.append("RC-TXN-CRYPTO-UNREG")
            codes.append("RC-TXN-CRYPTO-UNHOSTED")
        if "UNUSUAL" in ind_type or "DEVIATION" in ind_type:
            codes.append("RC-TXN-UNUSUAL")
            codes.append("RC-TXN-DEVIATION")

    # High-risk jurisdictions
    if facts.get("fatf_grey") or facts.get("high_risk_jurisdiction"):
        codes.append("RC-TXN-FATF-GREY")

    # Normal transaction baseline (for PASS cases)
    if not codes:
        codes.append("RC-TXN-NORMAL")
        codes.append("RC-TXN-PROFILE-MATCH")

    return list(set(codes))  # Deduplicate


# =============================================================================
# Precedent Outcome Normalization & Classification
# =============================================================================

def normalize_outcome(raw: str) -> str:
    """
    Normalize any outcome string to canonical form: pay, deny, or escalate.

    This is the SINGLE source of truth for outcome normalization.
    All precedent comparisons must use this function first.

    Args:
        raw: Raw outcome string (any case, any format)

    Returns:
        Canonical outcome: "pay", "deny", or "escalate"
    """
    if not raw:
        return "escalate"  # Unknown defaults to escalate (review state)

    # Normalize: lowercase, strip whitespace, collapse spaces, replace underscores
    normalized = " ".join(raw.lower().strip().split()).replace("_", " ")

    # PAY family (transaction approved, claim paid, account cleared)
    pay_terms = {
        "pay", "paid", "approve", "approved", "accept", "accepted",
        "clear", "cleared", "covered", "eligible", "pass", "passed",
        "no report", "report lctr", "close", "closed",
    }
    if normalized in pay_terms:
        return "pay"

    # DENY family (transaction blocked, claim denied)
    deny_terms = {
        "deny", "denied", "decline", "declined", "reject", "rejected",
        "block", "blocked", "refuse", "refused", "hard stop", "exit",
    }
    if normalized in deny_terms:
        return "deny"

    # ESCALATE family (review required, needs investigation)
    escalate_terms = {
        "escalate", "escalated", "investigate", "investigation",
        "review", "review required", "hold", "pending", "manual review",
        "needs info", "request more info", "str", "report str", "report tpr",
        "pass with edd",
    }
    if normalized in escalate_terms:
        return "escalate"

    # Default: unknown outcomes treated as escalate (safe default)
    return "escalate"


def map_aml_outcome_label(normalized: str) -> str:
    """Map normalized outcome to AML report label."""
    if normalized == "pay":
        return "NO_REPORT"
    if normalized == "deny":
        return "FILE_STR"
    if normalized == "escalate":
        return "EDD_REQUIRED"
    return normalized.upper()


AML_SIMILARITY_WEIGHTS_V1 = {
    "rules_overlap": 30,
    "gate_match": 25,
    "typology_overlap": 15,
    "amount_bucket": 10,
    "channel_method": 7,
    "corridor_match": 8,
    "pep_match": 5,
    "customer_profile": 5,
    "geo_risk": 5,
}
AML_SIMILARITY_WEIGHTS = {key: value / 100 for key, value in AML_SIMILARITY_WEIGHTS_V1.items()}
AML_SIMILARITY_VERSION = "v1"


def _code_weight(code: str) -> float:
    """Weight reason codes by AML materiality for similarity scoring."""
    c = code.upper()
    if "SANCTION" in c or c.startswith("RC-SCR-"):
        return 1.0
    if c.startswith("RC-RPT-") or "STR" in c or "TPR" in c or "LCTR" in c:
        return 0.95
    if "STRUCT" in c:
        return 0.9
    if "PEP" in c:
        return 0.85
    if "LAYER" in c or "RAPID" in c or "ROUNDTRIP" in c:
        return 0.8
    if "CRYPTO" in c:
        return 0.75
    if "FATF" in c or "CORRESP" in c:
        return 0.75
    if "SAR" in c:
        return 0.7
    if "UNUSUAL" in c or "DEVIATION" in c:
        return 0.6
    return 0.5


def _decision_level_weight(level: Optional[str]) -> float:
    """Weight precedents by decision authority level."""
    if not level:
        return 1.0
    level = level.lower()
    return {
        "adjuster": 0.9,
        "manager": 1.0,
        "tribunal": 1.1,
        "court": 1.15,
    }.get(level, 1.0)


def _recency_weight(decided_at: Optional[str]) -> float:
    """Weight precedents by recency (newer = higher weight)."""
    if not decided_at:
        return 1.0
    try:
        decided_dt = datetime.strptime(decided_at, "%Y-%m-%dT%H:%M:%SZ")
        age_days = max(0, (datetime.utcnow() - decided_dt).days)
        # 0.5 to 1.0 over ~1 year half-life
        return 0.5 + 0.5 * (2.71828 ** (-age_days / 365))
    except Exception:
        return 1.0


def _jurisdiction_weight(case_jurisdiction: Optional[str], precedent_jurisdiction: Optional[str]) -> float:
    """Down-weight cross-jurisdiction matches."""
    if not case_jurisdiction or not precedent_jurisdiction:
        return 1.0
    if case_jurisdiction == precedent_jurisdiction:
        return 1.0
    case_country = case_jurisdiction.split("-")[0]
    prec_country = precedent_jurisdiction.split("-")[0]
    return 0.9 if case_country == prec_country else 0.85




def _select_schema_id_for_codes(reason_codes: list[str]) -> str:
    """Select AML fingerprint schema based on reason code families."""
    prefixes = {code.split("-")[1] for code in reason_codes if code.startswith("RC-") and "-" in code}
    if "RPT" in prefixes:
        return "decisiongraph:aml:report:v1"
    if "SCR" in prefixes:
        return "decisiongraph:aml:screening:v1"
    if "KYC" in prefixes:
        return "decisiongraph:aml:kyc:v1"
    if "MON" in prefixes:
        return "decisiongraph:aml:monitoring:v1"
    return "decisiongraph:aml:txn:v1"


def _compute_case_banded_facts(facts: dict, schema_id: str) -> dict:
    """Compute banded facts for fingerprint similarity."""
    schema = FINGERPRINT_REGISTRY.get_schema_by_id(schema_id)
    return apply_aml_banding(facts, schema)


def _compute_fingerprint_similarity(case_banded: dict, payload) -> float:
    """Compute similarity between banded case facts and precedent anchor facts."""
    if not payload.anchor_facts:
        return 0.0
    precedent_facts = {af.field_id: af.value for af in payload.anchor_facts}
    if not case_banded:
        return 0.0

    matches = 0
    total = 0
    for field_id, value in case_banded.items():
        if value in [None, "unknown"]:
            continue
        total += 1
        if str(precedent_facts.get(field_id)) == str(value):
            matches += 1

    return matches / total if total > 0 else 0.0


def _anchor_value(payload, field_id: str) -> Optional[str]:
    for anchor in payload.anchor_facts:
        if anchor.field_id == field_id:
            return str(anchor.value)
    return None


def _truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).lower() in {"true", "yes", "1"}


def _typology_tokens_from_codes(codes: list[str]) -> set[str]:
    tokens = set()
    for code in codes:
        c = code.upper()
        if "STRUCT" in c:
            tokens.add("structuring")
        if "LAYER" in c or "RAPID" in c or "ROUNDTRIP" in c:
            tokens.add("layering")
        if "CRYPTO" in c:
            tokens.add("crypto")
        if "FATF" in c or "CORRESP" in c:
            tokens.add("geo_risk")
        if "PEP" in c:
            tokens.add("pep")
        if "SANCTION" in c or c.startswith("RC-SCR-"):
            tokens.add("sanctions")
        if "UNUSUAL" in c or "DEVIATION" in c:
            tokens.add("unusual")
        if "ADVERSE" in c:
            tokens.add("adverse_media")
    return tokens


def _bucket_similarity(case_bucket: Optional[str], precedent_bucket: Optional[str]) -> float:
    if not case_bucket or not precedent_bucket:
        return 0.0
    if case_bucket == precedent_bucket:
        return 1.0

    ordered_bands = [
        "under_3k",
        "3k_10k",
        "10k_25k",
        "25k_50k",
        "25k_100k",
        "50k_plus",
        "100k_500k",
        "500k_1m",
        "over_1m",
    ]
    if case_bucket in ordered_bands and precedent_bucket in ordered_bands:
        return 0.5 if abs(ordered_bands.index(case_bucket) - ordered_bands.index(precedent_bucket)) == 1 else 0.0

    return 0.0


def _channel_group(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    value = value.lower()
    if "wire" in value:
        return "wire"
    if "cash" in value:
        return "cash"
    if "crypto" in value:
        return "crypto"
    if "ach" in value:
        return "ach"
    if "check" in value or "cheque" in value:
        return "check"
    return value


def _channel_similarity(case_channel: Optional[str], precedent_channel: Optional[str]) -> float:
    if not case_channel or not precedent_channel:
        return 0.0
    if case_channel == precedent_channel:
        return 1.0
    return 0.5 if _channel_group(case_channel) == _channel_group(precedent_channel) else 0.0


def _build_outcome_distribution(payloads: list) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for payload in payloads:
        outcome = normalize_outcome(payload.outcome_code)
        distribution[outcome] = distribution.get(outcome, 0) + 1
    return distribution


# =============================================================================
# Precedent Domain Resolution
# =============================================================================

BANKING_DOMAINS = {"banking_aml", "banking", "aml", "bank"}


def resolve_precedent_namespace(domain: Optional[str], fallback: str) -> Optional[str]:
    """Resolve a precedent namespace based on decision domain."""
    if domain is None:
        return fallback

    domain_norm = str(domain).strip().lower()
    if domain_norm in BANKING_DOMAINS:
        return "banking.aml"

    return None


def classify_precedent_match(precedent_outcome: str, proposed_outcome: str) -> str:
    """
    Classify a precedent match as supporting, contrary, or neutral.

    Rules:
    - Same canonical outcome = SUPPORTING
    - pay vs deny = CONTRARY (opposite decisions)
    - escalate vs (pay or deny) = NEUTRAL (escalate is a review state, not a final decision)

    Args:
        precedent_outcome: The precedent's outcome (will be normalized)
        proposed_outcome: The proposed outcome (will be normalized)

    Returns:
        Classification: "supporting", "contrary", or "neutral"
    """
    prec = normalize_outcome(precedent_outcome)
    prop = normalize_outcome(proposed_outcome)

    # Same outcome = supporting
    if prec == prop:
        return "supporting"

    # Pay vs Deny = contrary (opposite final decisions)
    if {prec, prop} == {"pay", "deny"}:
        return "contrary"

    # Everything else is neutral (escalate vs pay/deny)
    return "neutral"


def stratified_precedent_sample(
    matches: list,
    proposed_outcome: str,
    max_total: int = 50,
    max_supporting: int = 35,
    max_contrary: int = 10,
    max_neutral: int = 15,
) -> tuple[list, dict]:
    """
    Create a stratified sample of precedent matches for balanced analysis.

    Ensures diversity of outcomes in the sample while maintaining:
    - Determinism (same input = same output)
    - Relevance-first ordering (highest overlap first within each bucket)

    Args:
        matches: List of (payload, overlap) tuples, pre-sorted by relevance
        proposed_outcome: The proposed outcome for classification
        max_total: Maximum total matches to include
        max_supporting: Maximum supporting matches
        max_contrary: Maximum contrary matches
        max_neutral: Maximum neutral matches

    Returns:
        Tuple of (sampled_matches, counts_dict)
    """
    supporting = []
    contrary = []
    neutral = []

    # Classify all matches
    for match in matches:
        if len(match) >= 4:
            payload, overlap, score, component_scores = match[0], match[1], match[2], match[3]
        elif len(match) >= 3:
            payload, overlap, score = match[0], match[1], match[2]
            component_scores = {}
        else:
            payload, overlap = match
            score = overlap
            component_scores = {}
        classification = classify_precedent_match(payload.outcome_code, proposed_outcome)

        if classification == "supporting" and len(supporting) < max_supporting:
            supporting.append((payload, overlap, classification, score, component_scores))
        elif classification == "contrary" and len(contrary) < max_contrary:
            contrary.append((payload, overlap, classification, score, component_scores))
        elif classification == "neutral" and len(neutral) < max_neutral:
            neutral.append((payload, overlap, classification, score, component_scores))

        # Stop if we have enough in all buckets
        if (len(supporting) >= max_supporting and
            len(contrary) >= max_contrary and
            len(neutral) >= max_neutral):
            break

    # Combine and sort by overlap (highest first) for consistent ordering
    sampled = supporting + contrary + neutral
    sampled.sort(key=lambda x: x[3], reverse=True)

    # Trim to max_total if needed
    sampled = sampled[:max_total]

    counts = {
        "supporting": len([x for x in sampled if x[2] == "supporting"]),
        "contrary": len([x for x in sampled if x[2] == "contrary"]),
        "neutral": len([x for x in sampled if x[2] == "neutral"]),
    }

    return sampled, counts


def query_similar_precedents(
    reason_codes: list,
    proposed_outcome: str,
    namespace_prefix: str = "banking.aml",
    domain: Optional[str] = None,
    case_facts: Optional[dict] = None,
    jurisdiction: Optional[str] = None,
) -> dict:
    """
    Query precedent registry for similar cases and return analysis.

    Uses stratified sampling and proper outcome classification:
    - Supporting: Same outcome family
    - Contrary: Opposite outcome (pay vs deny)
    - Neutral: Escalate vs final decision (review state)

    Returns a dict with:
    - match_count: Total matches found
    - sample_size: Number of matches analyzed (stratified sample)
    - outcome_distribution: Count by outcome
    - appeal_statistics: Appeal rates
    - precedent_confidence: Confidence score (0-1)
    - supporting/contrary/neutral counts
    - caution_precedents: Cases overturned on appeal
    """
    if not PRECEDENTS_LOADED or not PRECEDENT_REGISTRY:
        return {
            "available": False,
            "message": "Precedent system not loaded"
        }

    try:
        resolved_prefix = resolve_precedent_namespace(domain, namespace_prefix)
        if not resolved_prefix:
            return {
                "available": False,
                "message": "Precedent system not enabled for this domain"
            }

        # Normalize proposed outcome first
        proposed_normalized = normalize_outcome(proposed_outcome)

        mode = "demo" if DG_MODE == "demo" else "prod"
        threshold_used = DG_PRECEDENT_THRESHOLD_DEMO if mode == "demo" else DG_PRECEDENT_THRESHOLD_PROD

        # Select schema for fingerprint comparison
        schema_id = _select_schema_id_for_codes(reason_codes)
        case_banded = _compute_case_banded_facts(case_facts or {}, schema_id)
        case_reason_codes = list(set(reason_codes))
        case_typologies = _typology_tokens_from_codes(case_reason_codes)
        case_channel = (case_facts or {}).get("txn.type")
        case_amount_band = case_banded.get("txn.amount_band") or case_banded.get("txn.cash_amount_band")
        case_cross_border = case_banded.get("txn.cross_border")
        case_destination_risk = case_banded.get("txn.destination_country_risk")
        case_pep = (case_facts or {}).get("customer.pep")
        case_customer_type = (case_facts or {}).get("customer.type")
        case_relationship = (case_facts or {}).get("customer.relationship_length")
        case_sanctions_match = _truthy((case_facts or {}).get("screening.sanctions_match"))
        case_gate1_allowed = (case_facts or {}).get("gate1_allowed")
        case_gate2_str_required = (case_facts or {}).get("gate2_str_required")

        # Get statistics by reason codes
        stats = PRECEDENT_REGISTRY.get_statistics_by_codes(
            exclusion_codes=reason_codes,
            namespace_prefix=resolved_prefix,
            min_overlap=1,
        )

        # Find matching precedents (Tier 1 - overlapping codes)
        # Returns list sorted by overlap descending
        precedent_matches = PRECEDENT_REGISTRY.find_by_exclusion_codes(
            codes=reason_codes,
            namespace_prefix=resolved_prefix,
            min_overlap=1,
        )

        # Score matches with layered similarity
        scored_matches = []
        case_code_weights = sum(_code_weight(code) for code in case_reason_codes) or 1.0
        for payload, overlap in precedent_matches:
            # Stage A hard filters
            if payload.fingerprint_schema_id != schema_id:
                continue
            if jurisdiction and payload.jurisdiction_code and not _jurisdiction_weight(jurisdiction, payload.jurisdiction_code) == 1.0:
                continue

            precedent_customer_type = _anchor_value(payload, "customer.type") or _anchor_value(payload, "entity.type")
            if case_customer_type and precedent_customer_type and str(case_customer_type) != str(precedent_customer_type):
                continue

            precedent_sanctions = _truthy(_anchor_value(payload, "screening.sanctions_match"))
            if case_sanctions_match and not precedent_sanctions:
                continue

            overlap_codes = set(case_reason_codes).intersection(payload.reason_codes)
            weighted_overlap = sum(_code_weight(code) for code in overlap_codes)
            rules_overlap = weighted_overlap / case_code_weights

            outcome_normalized = normalize_outcome(payload.outcome_code)
            gate1_allowed_prec = outcome_normalized != "deny"
            gate2_str_prec = outcome_normalized in {"escalate", "deny"}
            gate1_allowed_case = bool(case_gate1_allowed) if case_gate1_allowed is not None else False
            gate2_str_case = bool(case_gate2_str_required) if case_gate2_str_required is not None else False
            gate_matches = int(gate1_allowed_case == gate1_allowed_prec) + int(gate2_str_case == gate2_str_prec)
            gate_match_score = 1.0 if gate_matches == 2 else 0.5 if gate_matches == 1 else 0.0

            precedent_typologies = _typology_tokens_from_codes(payload.reason_codes)
            typology_overlap = (
                len(case_typologies.intersection(precedent_typologies)) / len(case_typologies.union(precedent_typologies))
                if case_typologies or precedent_typologies
                else 0.0
            )

            precedent_amount_band = _anchor_value(payload, "txn.amount_band") or _anchor_value(payload, "txn.cash_amount_band")
            amount_bucket_score = _bucket_similarity(case_amount_band, precedent_amount_band)

            precedent_channel = _anchor_value(payload, "txn.type")
            channel_score = _channel_similarity(case_channel, precedent_channel)

            precedent_cross_border = _anchor_value(payload, "txn.cross_border")
            corridor_score = 0.0
            if case_cross_border is not None and precedent_cross_border is not None:
                corridor_score = 1.0 if str(case_cross_border) == str(precedent_cross_border) else 0.0
            elif case_destination_risk is not None:
                precedent_destination_risk = _anchor_value(payload, "txn.destination_country_risk")
                if precedent_destination_risk is not None:
                    corridor_score = 1.0 if str(case_destination_risk) == str(precedent_destination_risk) else 0.0

            precedent_pep = _anchor_value(payload, "customer.pep")
            pep_score = 0.0
            if case_pep is not None and precedent_pep is not None:
                pep_score = 1.0 if str(case_pep).lower() == str(precedent_pep).lower() else 0.0

            precedent_relationship = _anchor_value(payload, "customer.relationship_length")
            customer_profile_score = 0.0
            profile_matches = 0
            if case_customer_type and precedent_customer_type and str(case_customer_type) == str(precedent_customer_type):
                profile_matches += 1
            if case_relationship and precedent_relationship and str(case_relationship) == str(precedent_relationship):
                profile_matches += 1
            customer_profile_score = 1.0 if profile_matches == 2 else 0.5 if profile_matches == 1 else 0.0

            precedent_geo_risk = _anchor_value(payload, "txn.destination_country_risk")
            case_geo_risk = case_destination_risk
            geo_risk_score = 0.0
            if case_geo_risk is not None and precedent_geo_risk is not None:
                geo_risk_score = 1.0 if str(case_geo_risk) == str(precedent_geo_risk) else 0.0

            component_scores = {
                "rules_overlap": rules_overlap,
                "gate_match": gate_match_score,
                "typology_overlap": typology_overlap,
                "amount_bucket": amount_bucket_score,
                "channel_method": channel_score,
                "corridor_match": corridor_score,
                "pep_match": pep_score,
                "customer_profile": customer_profile_score,
                "geo_risk": geo_risk_score,
            }

            combined = sum(
                AML_SIMILARITY_WEIGHTS[key] * component_scores.get(key, 0.0)
                for key in AML_SIMILARITY_WEIGHTS
            )

            decision_weight = _decision_level_weight(payload.decision_level)
            recency_weight = _recency_weight(payload.decided_at)
            combined *= decision_weight * recency_weight

            if combined >= threshold_used:
                scored_matches.append(
                    (
                        payload,
                        overlap,
                        combined,
                        component_scores,
                        decision_weight,
                        recency_weight,
                    )
                )

        raw_overlap_count = len(precedent_matches)
        overlap_outcome_distribution = _build_outcome_distribution(
            [payload for payload, _overlap in precedent_matches]
        )
        match_outcome_distribution = _build_outcome_distribution(
            [payload for payload, _overlap, _score, _components, _dw, _rw in scored_matches]
        )

        # Get stratified sample for balanced analysis
        sampled, counts = stratified_precedent_sample(
            matches=scored_matches,
            proposed_outcome=proposed_normalized,
            max_total=50,
            max_supporting=35,
            max_contrary=10,
            max_neutral=15,
        )

        sorted_scores = sorted(
            (score for _payload, _overlap, score, _components, _dw, _rw in scored_matches),
            reverse=True,
        )
        top_scores = sorted_scores[:5]
        avg_top_k_similarity = round(sum(top_scores) / len(top_scores), 2) if top_scores else 0.0

        # Track caution precedents (overturned cases)
        caution_precedents = []
        for payload, overlap, classification, score, _component_scores in sampled:
            if payload.appealed and payload.appeal_outcome == "overturned":
                caution_precedents.append({
                    "precedent_id": payload.precedent_id[:8] + "...",
                    "outcome": payload.outcome_code,
                    "outcome_normalized": normalize_outcome(payload.outcome_code),
                    "classification": classification,
                    "appeal_outcome": payload.appeal_outcome,
                    "reason_codes": payload.reason_codes[:3],
                })

        # Build sample cases for report display
        sample_cases = []
        exact_match_count = 0
        reason_code_count = max(len(reason_codes), 1)
        for payload, overlap, classification, score, component_scores in sampled:
            overlap_codes = set(case_reason_codes).intersection(payload.reason_codes)
            weighted_overlap = sum(_code_weight(code) for code in overlap_codes)
            code_similarity = weighted_overlap / (sum(_code_weight(code) for code in case_reason_codes) or 1.0)
            fingerprint_similarity = _compute_fingerprint_similarity(case_banded, payload)
            exact_match = code_similarity >= 0.9 and fingerprint_similarity >= 0.9
            if exact_match:
                exact_match_count += 1

            normalized_outcome = normalize_outcome(payload.outcome_code)
            similarity_components = {
                "rules_overlap": int(round(component_scores.get("rules_overlap", 0) * 100)),
                "gate_match": int(round(component_scores.get("gate_match", 0) * 100)),
                "typology_overlap": int(round(component_scores.get("typology_overlap", 0) * 100)),
                "amount_bucket": int(round(component_scores.get("amount_bucket", 0) * 100)),
                "channel_method": int(round(component_scores.get("channel_method", 0) * 100)),
                "corridor_match": int(round(component_scores.get("corridor_match", 0) * 100)),
                "pep_match": int(round(component_scores.get("pep_match", 0) * 100)),
                "customer_profile": int(round(component_scores.get("customer_profile", 0) * 100)),
                "geo_risk": int(round(component_scores.get("geo_risk", 0) * 100)),
            }
            sample_cases.append({
                "precedent_id": payload.precedent_id[:8] + "...",
                "decision_level": payload.decision_level,
                "decided_at": payload.decided_at,
                "classification": classification,
                "overlap": overlap,
                "similarity_pct": int(round(score * 100)),
                "exact_match": exact_match,
                "outcome": payload.outcome_code,
                "outcome_normalized": normalized_outcome,
                "outcome_label": map_aml_outcome_label(normalized_outcome),
                "reason_codes": payload.reason_codes[:4],
                "appealed": payload.appealed,
                "appeal_outcome": payload.appeal_outcome,
                "code_similarity_pct": int(round(code_similarity * 100)),
                "fingerprint_similarity_pct": int(round(fingerprint_similarity * 100)),
                "similarity_components": similarity_components,
            })

        # Calculate confidence score
        decisive_total = counts["supporting"] + counts["contrary"]
        if len(scored_matches) == 0:
            precedent_confidence = 0.0
        elif decisive_total > 0:
            consistency_rate = counts["supporting"] / decisive_total
            upheld_rate = stats.appeal_stats.upheld_rate if stats.appeal_stats.total_appealed > 0 else 1.0
            precedent_confidence = (consistency_rate * 0.7) + (upheld_rate * 0.3)
        else:
            precedent_confidence = 0.5

        why_low_match = []
        missing_features = []
        if not case_amount_band:
            missing_features.append("amount_bucket")
        if not case_channel:
            missing_features.append("channel")
        if case_cross_border is None and case_destination_risk is None:
            missing_features.append("corridor")
        if not case_customer_type:
            missing_features.append("customer_type")
        if not case_relationship:
            missing_features.append("relationship_length")
        if case_pep is None:
            missing_features.append("pep")
        if missing_features:
            why_low_match.append({"missing_features": missing_features})

        gate_mismatch = []
        if case_gate1_allowed is None:
            gate_mismatch.append("gate1")
        if case_gate2_str_required is None:
            gate_mismatch.append("gate2")
        if gate_mismatch:
            why_low_match.append({"gate_mismatch": gate_mismatch})

        if not case_reason_codes:
            why_low_match.append({"rule_mismatch": ["reason_codes_missing"]})

        if not case_typologies:
            why_low_match.append({"typology_mismatch": ["typologies_missing"]})

        response = {
            "available": True,
            "match_count": len(scored_matches),
            "sample_size": len(sampled),
            "raw_overlap_count": raw_overlap_count,
            "overlap_outcome_distribution": overlap_outcome_distribution,
            "raw_outcome_distribution": overlap_outcome_distribution,
            "match_outcome_distribution": match_outcome_distribution,
            "outcome_distribution": match_outcome_distribution,
            "appeal_statistics": {
                "total_appealed": stats.appeal_stats.total_appealed,
                "upheld": stats.appeal_stats.upheld,
                "overturned": stats.appeal_stats.overturned,
                "upheld_rate": round(stats.appeal_stats.upheld_rate, 2),
            },
            "precedent_confidence": round(precedent_confidence, 2),
            "supporting_precedents": counts["supporting"],
            "contrary_precedents": counts["contrary"],
            "neutral_precedents": counts["neutral"],
            "exact_match_count": exact_match_count,
            "caution_precedents": caution_precedents[:5],
            "sample_cases": sample_cases[:10],
            "reason_codes_searched": reason_codes,
            "proposed_outcome_normalized": proposed_normalized,
            "proposed_outcome_label": map_aml_outcome_label(proposed_normalized),
            "min_similarity_pct": int(round(threshold_used * 100)),
            "threshold_used": threshold_used,
            "threshold_mode": mode,
            "precedent_scoring_version": AML_SIMILARITY_VERSION,
            "weights_version": AML_SIMILARITY_VERSION,
            "weights": AML_SIMILARITY_WEIGHTS_V1,
            "why_low_match": why_low_match,
            "avg_top_k_similarity": avg_top_k_similarity,
        }

        if len(scored_matches) == 0:
            response["message"] = "No precedents met the similarity threshold"

        return response

    except Exception as e:
        logger.warning(f"Precedent query failed: {e}")
        return {
            "available": False,
            "message": f"Precedent query failed: {str(e)}"
        }

# =============================================================================
# Startup/Shutdown
# =============================================================================

# =============================================================================
# Landing Page
# =============================================================================

@app.get("/", tags=["Landing"])
async def landing_page():
    """Serve the landing page."""
    try:
        from fastapi.responses import FileResponse
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
    except Exception as e:
        pass

    return JSONResponse(content={
        "service": "DecisionGraph",
        "version": DG_ENGINE_VERSION,
        "description": "Bank-Grade AML/KYC Decision Engine",
        "endpoints": {
            "decide": "POST /decide - Run decision engine",
            "demo_cases": "GET /demo/cases - List demo cases",
            "report": "GET /report/{id} - Get decision report",
            "verify": "POST /verify - Verify decision provenance",
            "docs": "GET /docs - API documentation"
        }
    })


@app.on_event("startup")
async def startup_event():
    """Log startup info."""
    logger.info(
        f"DecisionGraph starting",
        extra={
            "request_id": "startup",
            "external_id": "system",
        }
    )
    logger.info(f"Engine: v{DG_ENGINE_VERSION} ({DG_ENGINE_COMMIT})")
    logger.info(f"Policy: v{DG_POLICY_VERSION} ({POLICY_HASH_SHORT})")
    logger.info(f"Schemas loaded: {SCHEMAS_LOADED}")
    logger.info(f"Docs enabled: {DG_DOCS_ENABLED}")

    # Load case templates
    templates_loaded = template_loader.load_all()
    logger.info(f"Templates loaded: {templates_loaded}")
    templates.set_loader(template_loader)

    # Wire up report caching for Build Your Own Case
    set_cache_decision(report.cache_decision)

    # Load banking precedent seeds (2,000 precedents)
    precedents_loaded = load_precedent_seeds()
    logger.info(f"Precedent seeds loaded: {precedents_loaded}")

    # Wire up precedent query for Build Your Own Case reports
    set_precedent_query(query_similar_precedents)

@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown."""
    logger.info("DecisionGraph shutting down")

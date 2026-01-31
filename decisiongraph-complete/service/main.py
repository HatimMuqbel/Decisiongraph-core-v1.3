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

# Import routers
from service.routers import demo, report, verify

# =============================================================================
# Configuration
# =============================================================================

DG_ENGINE_VERSION = os.getenv("DG_ENGINE_VERSION", ENGINE_VERSION)
DG_POLICY_VERSION = os.getenv("DG_POLICY_VERSION", POLICY_VERSION)
DG_JURISDICTION = os.getenv("DG_JURISDICTION", "CA")
DG_LOG_LEVEL = os.getenv("DG_LOG_LEVEL", "INFO")
DG_DOCS_ENABLED = os.getenv("DG_DOCS_ENABLED", "true").lower() == "true"
DG_MAX_REQUEST_SIZE = int(os.getenv("DG_MAX_REQUEST_SIZE", "1048576"))  # 1MB default

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

# Include routers
app.include_router(demo.router)
app.include_router(report.router)
app.include_router(verify.router)

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
        )

        # Add engine commit (decision_pack.py doesn't know about git)
        decision_pack["meta"]["engine_commit"] = DG_ENGINE_COMMIT
        # Note: policy_hash and decision_id are computed by decision_pack.py with full SHA-256

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

@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown."""
    logger.info("DecisionGraph shutting down")

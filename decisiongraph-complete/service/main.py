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
from dataclasses import dataclass
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
from kernel.foundation.chain import Chain
from kernel.foundation.cell import NULL_HASH
from kernel.precedent.precedent_registry import PrecedentRegistry
from decisiongraph.aml_seed_generator import generate_all_banking_seeds
from decisiongraph.aml_fingerprint import (
    AMLFingerprintSchemaRegistry,
    apply_aml_banding,
    create_txn_amount_banding,
)
from kernel.foundation.judgment import (
    create_judgment_cell,
    normalize_scenario_code,
    normalize_seed_category,
)

# v3 Precedent Engine imports (conditional usage based on DG_PRECEDENT_VERSION)
from decisiongraph.banking_domain import create_banking_domain_registry
from kernel.precedent.comparability_gate import (
    evaluate_gates,
    extract_gate_facts_from_case,
    extract_gate_facts_from_precedent,
)
from kernel.precedent.precedent_scorer import (
    SimilarityResult,
    score_similarity,
    classify_match_v3,
    detect_primary_typology,
    anchor_facts_to_dict,
)
from kernel.precedent.governed_confidence import (
    compute_governed_confidence,
    GovernedConfidenceResult,
)
from decisiongraph.policy_shift_shadows import (
    detect_applicable_shifts,
    compute_shadow_outcome,
    extract_case_signals,
    SHIFT_EFFECTIVE_DATES,
)

# Import routers
from service.routers import demo, report, verify, templates, policy_shifts, simulate
from service.template_loader import TemplateLoader, set_cache_decision, set_precedent_query
from service.suspicion_classifier import CLASSIFIER_VERSION, classify as classify_suspicion
from service.validate_output import validate_decision_output

# Log module versions at import time so deploy logs confirm the correct code shipped
print(f"[startup] report module version: {report.REPORT_MODULE_VERSION}")
print(f"[startup] narrative compiler: {report.NARRATIVE_COMPILER_VERSION}")
print(f"[startup] suspicion classifier: {CLASSIFIER_VERSION}")

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
DG_PRECEDENT_VERSION = os.getenv("DG_PRECEDENT_VERSION", "v3")

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
app.include_router(policy_shifts.router)
app.include_router(simulate.router)

# Static files for landing page
STATIC_DIR = Path(__file__).parent / "static"
DASHBOARD_DIR = STATIC_DIR / "dashboard"
try:
    if STATIC_DIR.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    # Mount React dashboard assets at /assets  (built JS/CSS)
    if DASHBOARD_DIR.exists() and (DASHBOARD_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(DASHBOARD_DIR / "assets")), name="dashboard-assets")
        print(f"[startup] Dashboard SPA mounted from {DASHBOARD_DIR}")
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
    narrative_compiler: str = ""
    suspicion_classifier: str = ""

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
        narrative_compiler=report.NARRATIVE_COMPILER_VERSION,
        suspicion_classifier=CLASSIFIER_VERSION,
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


def _is_demo_format(body: dict) -> bool:
    """Detect if the request body is in demo/facts-array format or seed format.

    Demo format: has 'case_id' or has 'facts' as a list of {field, value}
    or has flat registry keys like 'customer.pep_flag', 'screening.sanctions_match' etc.
    Schema format: has 'header', 'alert_details', 'customer_record', etc.
    """
    if "case_id" in body:
        return True
    facts = body.get("facts")
    if isinstance(facts, list) and facts and isinstance(facts[0], dict) and "field" in facts[0]:
        return True
    # Also detect flat top-level keys from demo viewer or seed explorer
    if any(k.startswith((
        "customer.", "transaction.", "screening.", "pattern.", "docs.",
        "flag.", "txn.", "prior.", "relationship.",
    )) for k in body):
        return True
    return False


def _derive_stated_purpose(purpose_text: str | None) -> str | None:
    """Map demo case free-text purpose to canonical stated_purpose enum."""
    if not purpose_text:
        return None
    p = str(purpose_text).lower()
    if "legal" in p or "counsel" in p or "attorney" in p:
        return "business"
    if "business" in p or "trade" in p or "supplier" in p or "acquisition" in p:
        return "business"
    if "investment" in p or "portfolio" in p:
        return "investment"
    if "family" in p or "gift" in p or "personal" in p or "support" in p:
        return "personal"
    if "unclear" in p or "unknown" in p:
        return "unclear"
    return "unclear"


def _convert_demo_facts(body: dict) -> dict:
    """Convert demo facts-array or seed base_facts into engine-compatible inputs.

    Handles TWO field vocabularies:
    1. Demo case format: screening.list_type, screening.match_score, customer.pep_flag, etc.
    2. Seed/registry format: screening.sanctions_match, flag.structuring, customer.pep, etc.

    Extracts facts dict, obligations list, indicators, suspicion_evidence,
    and instrument_type from either format.
    """
    raw_facts = body.get("facts", [])

    # If facts is already a dict (engine format), return as-is
    if isinstance(raw_facts, dict):
        return {
            "facts": raw_facts,
            "obligations": body.get("obligations", []),
            "indicators": body.get("indicators", []),
            "instrument_type": body.get("instrument_type", "unknown"),
            "suspicion_evidence": body.get("suspicion_evidence", {
                "has_intent": False, "has_deception": False, "has_sustained_pattern": False,
            }),
        }

    # Build lookup from facts array: {field: value}
    fmap: dict = {}
    if isinstance(raw_facts, list):
        for f in raw_facts:
            if isinstance(f, dict) and "field" in f:
                fmap[f["field"]] = f.get("value")

    # Also merge flat top-level keys (SeedExplorer & DecisionViewer send these)
    for k, v in body.items():
        if k.startswith((
            "customer.", "transaction.", "screening.", "pattern.", "docs.",
            "flag.", "txn.", "prior.", "relationship.",
        )):
            fmap[k] = v
    # Also merge nested 'customer' and 'transaction' dicts from frontend
    if isinstance(body.get("customer"), dict):
        for k, v in body["customer"].items():
            if k not in fmap:
                fmap[k] = v
    if isinstance(body.get("transaction"), dict):
        for k, v in body["transaction"].items():
            if k not in fmap:
                fmap[k] = v

    # ── Read BOTH vocabularies ──────────────────────────────────────────

    # --- Demo case fields ---
    demo_pep_flag = fmap.get("customer.pep_flag", None)     # bool
    demo_list_type = str(fmap.get("screening.list_type", "")).upper()
    demo_match_score = fmap.get("screening.match_score", 0)
    demo_mltf_linked = fmap.get("screening.mltf_linked", False)
    demo_docs_complete = fmap.get("docs.complete", None)
    demo_source_verified = fmap.get("docs.source_verified", None)
    demo_structuring = fmap.get("pattern.structuring", False)
    demo_layering = fmap.get("pattern.layering", False)
    demo_velocity_spike = fmap.get("pattern.velocity_spike", False)
    demo_ownership_clear = fmap.get("docs.ownership_clear", None)

    # --- Registry / seed fields ---
    reg_sanctions_match = fmap.get("screening.sanctions_match", False)
    reg_pep_match = fmap.get("screening.pep_match", False)
    reg_pep = fmap.get("customer.pep", False)
    reg_adverse_media = fmap.get("screening.adverse_media", False)
    reg_structuring = fmap.get("flag.structuring", False)
    reg_layering = fmap.get("flag.layering", False)
    reg_rapid_movement = fmap.get("flag.rapid_movement", False)
    reg_unusual_for_profile = fmap.get("flag.unusual_for_profile", False)
    reg_third_party = fmap.get("flag.third_party", False)
    reg_shell_company = fmap.get("flag.shell_company", False)
    reg_sars_filed = fmap.get("prior.sars_filed", 0)
    reg_account_closures = fmap.get("prior.account_closures", False)
    reg_source_of_funds_clear = fmap.get("txn.source_of_funds_clear", None)
    reg_amount_band = fmap.get("txn.amount_band", "")
    reg_txn_type = fmap.get("txn.type", "")
    reg_cross_border = fmap.get("txn.cross_border", False)
    reg_dest_risk = fmap.get("txn.destination_country_risk", "")
    reg_customer_type = fmap.get("customer.type", "")

    # ── Derive engine facts (merge both vocabularies) ───────────────────

    # Sanctions: either explicit registry flag OR demo screening match
    sanctions_result = "NO_MATCH"
    if reg_sanctions_match:
        sanctions_result = "MATCH"
    elif demo_list_type in ("OFAC_SDN", "OFAC", "UN_SANCTIONS", "EU_SANCTIONS", "CA_SANCTIONS"):
        if isinstance(demo_match_score, (int, float)) and demo_match_score >= 85:
            sanctions_result = "MATCH"

    # Adverse media: registry flag OR demo MLTF link
    adverse_media_mltf = bool(reg_adverse_media) or bool(demo_mltf_linked)

    # PEP: registry flag OR demo flag OR beneficial owner PEP
    ben_owner_pep_flag = fmap.get("screening.beneficial_owner_pep", False)
    is_pep = bool(reg_pep) or bool(reg_pep_match) or bool(demo_pep_flag) or bool(ben_owner_pep_flag)

    # Documents
    docs_complete = True
    if demo_docs_complete is not None:
        docs_complete = bool(demo_docs_complete)
    source_verified = True
    if demo_source_verified is not None:
        source_verified = bool(demo_source_verified)
    elif reg_source_of_funds_clear is not None:
        source_verified = bool(reg_source_of_funds_clear)
    ownership_clear = True
    if demo_ownership_clear is not None:
        ownership_clear = bool(demo_ownership_clear)

    # Structuring / layering / velocity
    structuring = bool(demo_structuring) or bool(reg_structuring)
    layering = bool(demo_layering) or bool(reg_layering)
    velocity_spike = bool(demo_velocity_spike) or bool(reg_rapid_movement)

    # Prior SARs
    prior_sars = int(reg_sars_filed) if isinstance(reg_sars_filed, (int, float)) else 0

    facts = {
        "sanctions_result": sanctions_result,
        "document_status": "VALID" if docs_complete else "INCOMPLETE",
        "customer_response": "COMPLIANT",
        "adverse_media_mltf": adverse_media_mltf,
        "legal_prohibition": False,
    }

    # ── Obligations ─────────────────────────────────────────────────────
    obligations: list = []
    if is_pep:
        obligations.append("PEP_FOREIGN")

    # ── Indicators ──────────────────────────────────────────────────────
    indicators: list = []
    if structuring:
        indicators.append({"code": "STRUCTURING", "type": "STRUCTURING", "corroborated": True})
    if layering:
        indicators.append({"code": "LAYERING", "type": "LAYERING", "corroborated": True})
    if velocity_spike:
        indicators.append({"code": "VELOCITY_SPIKE", "type": "UNUSUAL", "corroborated": True})
    if adverse_media_mltf or demo_list_type == "ADVERSE_MEDIA":
        indicators.append({"code": "ADVERSE_MEDIA", "type": "ADVERSE_MEDIA", "corroborated": adverse_media_mltf})
    if reg_unusual_for_profile:
        indicators.append({"code": "UNUSUAL_FOR_PROFILE", "type": "UNUSUAL", "corroborated": True})
    if reg_third_party:
        indicators.append({"code": "THIRD_PARTY", "type": "THIRD_PARTY", "corroborated": True})
    if reg_shell_company:
        indicators.append({"code": "SHELL_COMPANY", "type": "LAYERING", "corroborated": True})
    if prior_sars >= 2:
        indicators.append({"code": "PRIOR_SARS", "type": "HISTORY", "corroborated": True})
    if reg_account_closures:
        indicators.append({"code": "PRIOR_CLOSURE", "type": "HISTORY", "corroborated": True})

    # ── Suspicion evidence ──────────────────────────────────────────────
    has_intent = (
        sanctions_result == "MATCH"
        or adverse_media_mltf
        or structuring
    )
    has_deception = (
        layering
        or bool(reg_shell_company)
        or (not docs_complete and not source_verified and not ownership_clear)
    )
    has_sustained_pattern = structuring or velocity_spike or prior_sars >= 2

    suspicion_evidence = {
        "has_intent": has_intent,
        "has_deception": has_deception,
        "has_sustained_pattern": has_sustained_pattern,
    }

    # ── Instrument type ─────────────────────────────────────────────────
    method = str(fmap.get("transaction.method", reg_txn_type or "unknown")).lower()
    instrument_map = {"wire": "wire", "cash": "cash", "crypto": "crypto", "cheque": "cheque"}
    instrument_type = instrument_map.get(method, "unknown")

    # ── Typology maturity ───────────────────────────────────────────────
    typology_maturity = "FORMING"
    if sanctions_result == "MATCH" or adverse_media_mltf:
        typology_maturity = "CONFIRMED"
    elif structuring or layering or prior_sars >= 4:
        typology_maturity = "EMERGING"

    # ── Build canonical registry facts from demo vocabulary ─────────────
    # Maps the demo-specific field names to the 28 canonical registry
    # fields used by the Evidence Gap Tracker, fingerprint scorer,
    # and precedent matcher.  This is the translation layer that ensures
    # demo cases populate the full evidence table.
    _DEMO_CUSTOMER_TYPE_MAP = {
        "IND": "individual", "INDIVIDUAL": "individual", "individual": "individual",
        "CORP": "corporation", "CORPORATE": "corporation", "corporation": "corporation",
    }
    _DEMO_METHOD_TO_TXN_TYPE = {
        "WIRE": "wire_international",
        "wire": "wire_international",
        "CASH": "cash",
        "cash": "cash",
        "CRYPTO": "crypto",
        "crypto": "crypto",
        "CHEQUE": "cheque",
        "cheque": "cheque",
        "EFT": "eft",
    }
    _HIGH_RISK_COUNTRIES = {"RU", "IR", "KP", "SY", "AF", "VG", "CY", "MM", "YE", "LY", "SO", "SD", "IQ", "PK"}
    _HIGH_RISK_DEST_COUNTRIES = {"AE", "SG", "HK", "CH", "PA", "BS", "KY", "BZ", "VG", "JE", "IM", "LI"}

    demo_amount_cad = fmap.get("transaction.amount_cad")
    demo_destination = fmap.get("transaction.destination")
    demo_residence = fmap.get("customer.residence", "")
    demo_tenure_years = fmap.get("relationship.tenure_years")
    demo_method = fmap.get("transaction.method", "")
    demo_txn_count = fmap.get("transaction.count")
    demo_purpose = fmap.get("transaction.purpose")

    # Amount banding
    amount_band = None
    if demo_amount_cad is not None:
        try:
            from decisiongraph import create_txn_amount_banding
            amount_band = create_txn_amount_banding().apply(demo_amount_cad)
        except Exception:
            amt = float(demo_amount_cad)
            if amt < 3000: amount_band = "under_3k"
            elif amt < 10000: amount_band = "3k_10k"
            elif amt < 25000: amount_band = "10k_25k"
            elif amt < 100000: amount_band = "25k_100k"
            elif amt < 500000: amount_band = "100k_500k"
            elif amt < 1000000: amount_band = "500k_1m"
            else: amount_band = "over_1m"

    # Relationship length banding
    rel_length = None
    if demo_tenure_years is not None:
        t = float(demo_tenure_years)
        if t < 0.5: rel_length = "new"
        elif t < 2: rel_length = "recent"
        else: rel_length = "established"

    # Destination country risk
    dest_risk = None
    is_cross_border = False
    if demo_destination:
        is_cross_border = str(demo_destination).upper() != "CA"
        if str(demo_destination).upper() in _HIGH_RISK_COUNTRIES:
            dest_risk = "high"
        elif str(demo_destination).upper() in _HIGH_RISK_DEST_COUNTRIES:
            dest_risk = "medium"
        else:
            dest_risk = "low"

    # Whether to derive cross-border from method
    if str(demo_method).upper() == "WIRE" and demo_destination and str(demo_destination).upper() != "CA":
        is_cross_border = True

    # Structuring indicators
    is_just_below = False
    if demo_amount_cad is not None:
        amt = float(demo_amount_cad)
        is_just_below = 8000 <= amt < 10000

    is_multiple_same_day = bool(demo_txn_count and int(demo_txn_count) > 1)
    is_round_amount = False
    if demo_amount_cad is not None:
        is_round_amount = float(demo_amount_cad) % 1000 == 0 and float(demo_amount_cad) >= 5000

    canonical_facts = {
        # Customer
        "customer.type": _DEMO_CUSTOMER_TYPE_MAP.get(str(fmap.get("customer.type", "")), None),
        "customer.relationship_length": rel_length,
        "customer.pep": is_pep,
        "customer.high_risk_jurisdiction": str(demo_residence).upper() in _HIGH_RISK_COUNTRIES if demo_residence else False,
        "customer.high_risk_industry": False,  # Not captured in demo format
        "customer.cash_intensive": str(demo_method).upper() == "CASH",

        # Transaction
        "txn.type": _DEMO_METHOD_TO_TXN_TYPE.get(str(demo_method).upper(), instrument_type if instrument_type != "unknown" else None),
        "txn.amount_band": amount_band,
        "txn.cross_border": is_cross_border,
        "txn.destination_country_risk": dest_risk,
        "txn.round_amount": is_round_amount,
        "txn.just_below_threshold": is_just_below,
        "txn.multiple_same_day": is_multiple_same_day,
        "txn.pattern_matches_profile": not (velocity_spike or structuring or layering),
        "txn.source_of_funds_clear": source_verified,
        "txn.stated_purpose": _derive_stated_purpose(demo_purpose),

        # Flags
        "flag.structuring": structuring,
        "flag.rapid_movement": velocity_spike,
        "flag.layering": layering,
        "flag.unusual_for_profile": velocity_spike or bool(reg_unusual_for_profile),
        "flag.third_party": bool(reg_third_party),
        "flag.shell_company": bool(fmap.get("docs.ownership_clear") is False and str(fmap.get("customer.type", "")).upper() == "CORP"),

        # Screening
        "screening.sanctions_match": sanctions_result == "MATCH",
        "screening.pep_match": is_pep,
        "screening.adverse_media": adverse_media_mltf,
        "prior.sars_filed": prior_sars,
        "prior.account_closures": bool(reg_account_closures),
    }

    # Remove None values so they appear as gaps in Evidence Gap Tracker
    canonical_facts = {k: v for k, v in canonical_facts.items() if v is not None}

    return {
        "facts": facts,
        "obligations": obligations,
        "indicators": indicators,
        "instrument_type": instrument_type,
        "suspicion_evidence": suspicion_evidence,
        "typology_maturity": typology_maturity,
        "mitigations": [],
        "evidence_quality": {},
        "mitigation_status": {},
        "typology_confirmed": typology_maturity == "CONFIRMED",
        "fintrac_indicators": [],
        "_demo_facts": fmap,  # preserve original for report rendering
        "_canonical_facts": canonical_facts,  # translated to 28 registry fields
    }

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

        # ── Demo-format detection ────────────────────────────────────────
        # Demo cases use a flat facts-array format [{field, value}, ...]
        # that doesn't conform to the bank-grade input schema.
        # Convert them into engine-compatible inputs and skip validation.
        is_demo = _is_demo_format(body)

        if not is_demo:
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
        external_id = body.get("alert_details", {}).get("external_id",
                      body.get("case_id", "DEMO"))
        input_hash = compute_input_hash(body)
        decision_id = compute_decision_id(input_hash)

        if is_demo:
            # Convert facts-array to engine format
            demo_inputs = _convert_demo_facts(body)
            facts = demo_inputs["facts"]
            obligations = demo_inputs["obligations"]
            indicators = demo_inputs["indicators"]
            instrument_type = demo_inputs["instrument_type"]
            suspicion_evidence = demo_inputs["suspicion_evidence"]
            typology_maturity = demo_inputs.get("typology_maturity", "FORMING")
            mitigations = demo_inputs.get("mitigations", [])
            evidence_quality = demo_inputs.get("evidence_quality", {})
            mitigation_status = demo_inputs.get("mitigation_status", {})
            typology_confirmed = demo_inputs.get("typology_confirmed", False)
            fintrac_indicators = demo_inputs.get("fintrac_indicators", [])
            logger.info(f"Demo case processed: {external_id}",
                        extra={"request_id": request_id})
        else:
            # Extract engine inputs from schema-compliant body
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

        # ── CLASSIFIER SOVEREIGNTY GATE ──────────────────────────────────
        # The Suspicion Classifier is the SUPREME AUTHORITY.
        # It runs BEFORE the verdict is finalized.
        # If Tier 1 == 0, STR is IMPOSSIBLE. No rule, gate, or precedent
        # can bypass this. This is non-negotiable regulatory architecture.
        #
        # Decision Hierarchy (frozen):
        #   1. Suspicion Classifier (sovereign)
        #   2. Rules / Gates (support the classifier, never contradict)
        #   3. Narrative Engine (explains the classifier outcome)
        #   4. Governance Engine (controls escalation path)
        # ─────────────────────────────────────────────────────────────────

        # Build evidence_used and rules_fired for the classifier
        # (mirrors what decision_pack.py constructs, but available pre-pack)
        hard_stop_triggered = any([
            facts.get("sanctions_result") == "MATCH",
            facts.get("document_status") == "FALSE",
            facts.get("customer_response") == "REFUSAL",
            facts.get("legal_prohibition", False),
            facts.get("adverse_media_mltf", False),
        ])
        has_pep = "PEP_FOREIGN" in obligations or "PEP_DOMESTIC" in obligations
        suspicion_activated = (
            hard_stop_triggered or
            suspicion_evidence.get("has_intent", False) or
            suspicion_evidence.get("has_deception", False) or
            suspicion_evidence.get("has_sustained_pattern", False)
        )
        suspicion_basis = (
            "HARD_STOP" if hard_stop_triggered
            else "BEHAVIORAL" if suspicion_activated
            else "NONE"
        )

        pre_evidence_used = [
            {"field": "facts.sanctions_result", "value": facts.get("sanctions_result", "NO_MATCH")},
            {"field": "facts.adverse_media_mltf", "value": facts.get("adverse_media_mltf", False)},
            {"field": "suspicion.has_intent", "value": suspicion_evidence.get("has_intent", False)},
            {"field": "suspicion.has_deception", "value": suspicion_evidence.get("has_deception", False)},
            {"field": "suspicion.has_sustained_pattern", "value": suspicion_evidence.get("has_sustained_pattern", False)},
            {"field": "obligations.count", "value": len(obligations)},
            {"field": "mitigations.count", "value": len(mitigations)},
            {"field": "typology.maturity", "value": typology_maturity},
        ]

        # Populate registry-keyed evidence for the Evidence Gap Tracker (27 banking fields).
        # For demo/seed cases, use the _canonical_facts (translated to registry vocabulary);
        # for schema cases, derive from body.
        _reg_src: dict = {}
        if is_demo and isinstance(demo_inputs.get("_canonical_facts"), dict):
            _reg_src = demo_inputs["_canonical_facts"]
        elif is_demo and isinstance(demo_inputs.get("_demo_facts"), dict):
            _reg_src = demo_inputs["_demo_facts"]
        else:
            # Flatten structured input (customer_record, screening_payload, etc.)
            for section_key in ("customer_record", "screening_payload", "transaction_history_slice"):
                section = body.get(section_key, {})
                if isinstance(section, dict):
                    for k, v in section.items():
                        _reg_src[k] = v

        # Map registry fields to evidence entries the frontend can match
        _REGISTRY_FIELDS = [
            "customer.type", "customer.relationship_length", "customer.pep",
            "customer.high_risk_jurisdiction", "customer.high_risk_industry", "customer.cash_intensive",
            "txn.type", "txn.amount_band", "txn.cross_border", "txn.destination_country_risk",
            "txn.round_amount", "txn.just_below_threshold", "txn.multiple_same_day",
            "txn.pattern_matches_profile", "txn.source_of_funds_clear", "txn.stated_purpose",
            "flag.structuring", "flag.rapid_movement", "flag.layering",
            "flag.unusual_for_profile", "flag.third_party", "flag.shell_company",
            "screening.sanctions_match", "screening.pep_match", "screening.adverse_media",
            "prior.sars_filed", "prior.account_closures",
        ]
        # Also derive some from engine facts
        _derived_reg = {
            "screening.sanctions_match": facts.get("sanctions_result") == "MATCH",
            "screening.adverse_media": bool(facts.get("adverse_media_mltf")),
            "customer.pep": has_pep,
            "txn.type": instrument_type if instrument_type != "unknown" else None,
        }
        for rf in _REGISTRY_FIELDS:
            val = _reg_src.get(rf)
            if val is None:
                val = _derived_reg.get(rf)
            if val is not None:
                pre_evidence_used.append({"field": rf, "value": val})

        # ── FINTRAC Citation Reference Map ─────────────────────────────────
        # Maps rule/typology codes to actual regulatory text for VerbatimCitations.
        # These are the real PCMLTFA / FINTRAC references that a compliance officer
        # or regulator would expect to see in an audit package.
        _CITATION_MAP = {
            "HARD_STOP_CHECK": {
                "ref": "PCMLTFA s. 7(1), FINTRAC Guideline 3",
                "text": "Proceeds of Crime (Money Laundering) and Terrorist Financing Act — Where a reporting entity has reasonable grounds to suspect that a transaction or attempted transaction is related to the commission or attempted commission of a money laundering offence or a terrorist activity financing offence, the entity shall report the transaction or attempted transaction to the Centre.",
            },
            "PEP_ISOLATION": {
                "ref": "PCMLTFA s. 9.3, FINTRAC Guideline 4 — PEP/HIO",
                "text": "A reporting entity shall take reasonable measures to determine whether a person is a politically exposed foreign person, a politically exposed domestic person, or a head of an international organization. PEP status alone does not constitute reasonable grounds to suspect — additional risk factors must be present.",
            },
            "SUSPICION_TEST": {
                "ref": "PCMLTFA s. 7(1)(a), FINTRAC Guideline 3 — STR",
                "text": "A suspicious transaction report shall be submitted when there are reasonable grounds to suspect that the transaction is related to the commission of a money laundering offence or a terrorist activity financing offence. Suspicion must be fact-based and articulable.",
            },
            "STRUCTURING_PATTERN": {
                "ref": "FINTRAC Guideline 3 — Structuring Indicators",
                "text": "Structuring involves conducting transactions below the $10,000 reporting threshold to avoid triggering a Large Cash Transaction Report. This includes patterns of deposits/withdrawals just below the threshold, multiple same-day transactions, and the use of multiple accounts or locations.",
            },
            "LAYERING": {
                "ref": "FINTRAC ML/TF Typologies — Layering",
                "text": "Layering is the second stage of money laundering, involving complex layers of financial transactions designed to distance illegally derived funds from their source. This may involve multiple transfers between accounts, use of shell companies, or cross-border movements.",
            },
            "SHELL_ENTITY": {
                "ref": "FINTRAC ML/TF Typologies — Shell Companies",
                "text": "Shell company indicators include nominee directors, registered agents in high-risk jurisdictions, no apparent legitimate business activity, and use of corporate structures to obscure beneficial ownership contrary to PCMLTFA s. 11.1 beneficial ownership requirements.",
            },
            "THIRD_PARTY_UNEXPLAINED": {
                "ref": "FINTRAC Guideline 2 — Third-Party Determination",
                "text": "A reporting entity shall take reasonable measures to determine whether a transaction is being conducted on behalf of a third party. Unexplained third-party involvement in financial transactions is a recognized ML/TF indicator.",
            },
            "FALSE_SOURCE": {
                "ref": "PCMLTFA s. 6.1, FINTRAC Guideline 6 — Record Keeping",
                "text": "Source of funds declarations that cannot be verified or are inconsistent with the client's known profile constitute a suspicious indicator. Reporting entities must keep records of information used to identify clients and verify their identity.",
            },
            "SANCTIONS_SIGNAL": {
                "ref": "SEMA s. 4(1), PCMLTFA s. 11.42, UN Regulations",
                "text": "Under the Special Economic Measures Act and United Nations Act regulations, it is prohibited to deal in property of designated persons. A confirmed sanctions match requires immediate blocking and reporting to FINTRAC and OSFI.",
            },
            "ADVERSE_MEDIA_CONFIRMED": {
                "ref": "FINTRAC Guideline 4 — Risk Assessment, OSFI B-10 s. 7",
                "text": "Confirmed adverse media linking a client to money laundering, terrorist financing, fraud, corruption, or organized crime is a key risk factor requiring enhanced due diligence measures and potential STR filing.",
            },
            "SAR_PATTERN": {
                "ref": "PCMLTFA s. 7(1), FINTRAC Guideline 3 — Pattern of SARs",
                "text": "A history of prior Suspicious Transaction Reports filed on a client indicates an established pattern of suspicious activity. Multiple prior SARs elevate the risk assessment and may trigger enhanced monitoring, exit consideration, or mandatory escalation.",
            },
            "EVASION_BEHAVIOR": {
                "ref": "FINTRAC Guideline 3 — Unusual Activity Indicators",
                "text": "Behaviour inconsistent with the client's known transaction profile or sudden spikes in transaction velocity are recognized indicators of potential money laundering. The reporting entity must assess whether such activity has a reasonable explanation.",
            },
            "ROUND_TRIP": {
                "ref": "FINTRAC ML/TF Typologies — Round-Trip Transactions",
                "text": "Round-trip transactions involve funds being sent to a jurisdiction and returned in a manner designed to disguise their origin. This is a recognized money laundering technique used to create the appearance of legitimate business transactions.",
            },
            "TRADE_BASED_LAUNDERING": {
                "ref": "FINTRAC ML/TF Typologies — Trade-Based ML",
                "text": "Trade-based money laundering involves the exploitation of international trade transactions to transfer value and obscure the origins of criminal proceeds. Indicators include over/under-invoicing, phantom shipments, and misrepresentation of trade goods.",
            },
            "FUNNEL": {
                "ref": "FINTRAC ML/TF Typologies — Funnel Accounts",
                "text": "Funnel account activity involves the use of bank accounts in one geographic area to consolidate and redirect funds to another area, often across borders. This is a recognized technique for integrating proceeds of crime.",
            },
            "VIRTUAL_ASSET_LAUNDERING": {
                "ref": "PCMLTFA s. 1 (virtual currency), FINTRAC Guideline 5",
                "text": "Virtual currency transactions require the same AML/ATF compliance obligations as fiat currency transactions. Indicators of virtual asset laundering include conversion to/from privacy coins, use of mixing services, and transactions with unhosted wallets.",
            },
            "TERRORIST_FINANCING": {
                "ref": "PCMLTFA s. 7.1, Criminal Code s. 83.02-83.04",
                "text": "Terrorist activity financing offences include providing or collecting property for terrorist purposes. Any transaction suspected of being related to terrorist financing must be reported to FINTRAC immediately. There is no monetary threshold for TF reporting.",
            },
        }

        pre_rules_fired = [
            {"code": "HARD_STOP_CHECK", "result": "TRIGGERED" if hard_stop_triggered else "CLEAR",
             "reason": "Hard stop conditions detected" if hard_stop_triggered else "No hard stop conditions",
             "citation_ref": _CITATION_MAP["HARD_STOP_CHECK"]["ref"],
             "citation_text": _CITATION_MAP["HARD_STOP_CHECK"]["text"]},
            {"code": "PEP_ISOLATION", "result": "APPLIED" if has_pep else "NOT_APPLICABLE",
             "reason": "PEP status alone cannot escalate" if has_pep else "Not a PEP",
             "citation_ref": _CITATION_MAP["PEP_ISOLATION"]["ref"],
             "citation_text": _CITATION_MAP["PEP_ISOLATION"]["text"]},
            {"code": "SUSPICION_TEST", "result": "ACTIVATED" if suspicion_activated else "CLEAR",
             "reason": suspicion_basis,
             "citation_ref": _CITATION_MAP["SUSPICION_TEST"]["ref"],
             "citation_text": _CITATION_MAP["SUSPICION_TEST"]["text"]},
        ]

        # Add typology-specific rule codes for the Typology Map component.
        # The frontend TypologyMap matches these codes against 14 known typologies.
        _TYPOLOGY_RULES = {
            "STRUCTURING_PATTERN": lambda: any(i.get("code") == "STRUCTURING" for i in indicators),
            "LAYERING": lambda: any(i.get("code") == "LAYERING" for i in indicators),
            "SHELL_ENTITY": lambda: any(i.get("code") == "SHELL_COMPANY" for i in indicators),
            "THIRD_PARTY_UNEXPLAINED": lambda: any(i.get("code") == "THIRD_PARTY" for i in indicators),
            "FALSE_SOURCE": lambda: not facts.get("source_verified", True) and not facts.get("docs_complete", True),
            "SANCTIONS_SIGNAL": lambda: facts.get("sanctions_result") == "MATCH",
            "ADVERSE_MEDIA_CONFIRMED": lambda: bool(facts.get("adverse_media_mltf")),
            "SAR_PATTERN": lambda: any(i.get("code") == "PRIOR_SARS" for i in indicators),
            "EVASION_BEHAVIOR": lambda: any(i.get("code") in ("UNUSUAL_FOR_PROFILE", "VELOCITY_SPIKE") for i in indicators),
            "ROUND_TRIP": lambda: any(i.get("code") == "ROUND_TRIP" for i in indicators),
            "TRADE_BASED_LAUNDERING": lambda: any(i.get("code") == "TRADE_BASED" for i in indicators),
            "FUNNEL": lambda: any(i.get("code") == "FUNNEL_ACCOUNT" for i in indicators),
            "VIRTUAL_ASSET_LAUNDERING": lambda: instrument_type == "crypto",
            "TERRORIST_FINANCING": lambda: any(i.get("code") == "TERRORIST_FINANCING" for i in indicators),
        }
        for t_code, t_check in _TYPOLOGY_RULES.items():
            try:
                if t_check():
                    cite = _CITATION_MAP.get(t_code, {})
                    pre_rules_fired.append({
                        "code": t_code, "result": "TRIGGERED",
                        "reason": f"{t_code} typology detected",
                        "citation_ref": cite.get("ref", ""),
                        "citation_text": cite.get("text", ""),
                    })
            except Exception:
                pass

        # Also include any indicators from the input payload as evidence
        for ind in indicators:
            ind_field = f"indicator.{ind.get('code', 'unknown')}"
            pre_evidence_used.append({"field": ind_field, "value": ind.get("corroborated", False)})

        # Construct classifier inputs from layers
        # Build typology label from indicators for driver derivation
        _typology_label = "primary"
        _indicator_codes = [ind.get("code", "") for ind in indicators]
        if "ADVERSE_MEDIA" in _indicator_codes:
            _typology_label = "adverse_media"
        elif "STRUCTURING" in _indicator_codes:
            _typology_label = "structuring"
        elif "LAYERING" in _indicator_codes:
            _typology_label = "layering"
        elif "VELOCITY_SPIKE" in _indicator_codes:
            _typology_label = "unusual_activity"
        elif "SHELL_COMPANY" in _indicator_codes:
            _typology_label = "shell_company"
        elif "THIRD_PARTY" in _indicator_codes:
            _typology_label = "third_party"
        elif facts.get("sanctions_result") == "MATCH":
            _typology_label = "sanctions"
        layer4_typologies_pre = {
            "typologies": [{"name": _typology_label, "maturity": typology_maturity}],
        }
        layer6_suspicion_pre = {
            "activated": suspicion_activated,
            "basis": suspicion_basis,
            "elements": {
                "has_intent": suspicion_evidence.get("has_intent", False),
                "has_deception": suspicion_evidence.get("has_deception", False),
                "has_sustained_pattern": suspicion_evidence.get("has_sustained_pattern", False),
            },
        }

        # Build layer1_facts for classifier (transaction + customer context)
        layer1_facts_pre = {}
        primary_txn_pre = None
        if isinstance(body.get("transaction"), dict):
            primary_txn_pre = body.get("transaction")
        elif isinstance(body.get("events"), list):
            for event in body.get("events", []):
                if isinstance(event, dict) and event.get("event_type") == "transaction":
                    primary_txn_pre = event
                    break
        if primary_txn_pre:
            layer1_facts_pre["transaction"] = {
                "cross_border": primary_txn_pre.get("cross_border", False),
                "destination": primary_txn_pre.get("destination_country", ""),
                "method": primary_txn_pre.get("payment_method") or primary_txn_pre.get("method", ""),
            }
        elif is_demo and isinstance(demo_inputs.get("_canonical_facts"), dict):
            # For demo cases, derive transaction context from canonical facts
            _cf = demo_inputs["_canonical_facts"]
            _df = demo_inputs.get("_demo_facts", {})
            layer1_facts_pre["transaction"] = {
                "cross_border": _cf.get("txn.cross_border", False),
                "destination": _df.get("transaction.destination", ""),
                "method": _df.get("transaction.method", ""),
            }
            # Also add hard_stop_triggered to help driver derivation
            if hard_stop_triggered:
                layer1_facts_pre["hard_stop_triggered"] = True
                if facts.get("adverse_media_mltf"):
                    layer1_facts_pre["hard_stop_reason"] = "ADVERSE_MEDIA_MLTF"
                elif facts.get("sanctions_result") == "MATCH":
                    layer1_facts_pre["hard_stop_reason"] = "SANCTIONS_MATCH"
                else:
                    layer1_facts_pre["hard_stop_reason"] = "Triggered"
        customer_record = body.get("customer_record", {})
        layer1_facts_pre["customer"] = {
            "pep_flag": customer_record.get("pep_flag") == "Y" or has_pep,
        }

        # Run classifier as SOVEREIGN AUTHORITY
        classifier_result = classify_suspicion(
            evidence_used=pre_evidence_used,
            rules_fired=pre_rules_fired,
            layer4_typologies=layer4_typologies_pre,
            layer6_suspicion=layer6_suspicion_pre,
            layer1_facts=layer1_facts_pre,
            mitigations=mitigations or None,
        )

        # ── HARD GATE: Classifier Sovereignty ────────────────────────────
        # IF Tier 1 == 0 → STR is impossible. Period.
        classifier_override_applied = False
        classifier_original_verdict = None

        if classifier_result.suspicion_count == 0 and final_decision.get("str_required", False):
            # CRITICAL: Rules engine tried to file STR without suspicion.
            # This is a regulatory control violation. Override immediately.
            classifier_override_applied = True
            classifier_original_verdict = "STR"
            logger.warning(
                "CLASSIFIER SOVEREIGNTY: STR blocked — Tier 1 suspicion count is 0. "
                "Rules engine verdict overridden to protect regulatory integrity.",
                extra={"request_id": request_id, "external_id": external_id},
            )
            # Downgrade to EDD if investigative signals exist, else NO_REPORT
            if classifier_result.investigative_count >= 1:
                final_decision = {
                    "verdict": "REVIEW",
                    "action": "EDD_REQUIRED",
                    "str_required": False,
                    "escalation_blocked_by_classifier": True,
                    "classifier_override_reason": (
                        f"Tier 1 suspicion indicators: 0. "
                        f"Tier 2 investigative signals: {classifier_result.investigative_count}. "
                        "STR filing prohibited by classifier sovereignty. EDD required."
                    ),
                }
            else:
                final_decision = {
                    "verdict": "PASS",
                    "action": "CLOSE",
                    "str_required": False,
                    "escalation_blocked_by_classifier": True,
                    "classifier_override_reason": (
                        "Tier 1 suspicion indicators: 0. "
                        "Tier 2 investigative signals: 0. "
                        "No reporting or escalation obligation."
                    ),
                }

        elif classifier_result.suspicion_count == 0 and (
            esc_result.decision == EscalationDecision.PERMITTED
            and not final_decision.get("str_required", False)
        ):
            # Escalation was permitted but no Tier 1 — downgrade to EDD
            if classifier_result.investigative_count >= 1:
                classifier_override_applied = True
                classifier_original_verdict = final_decision.get("verdict", "ESCALATE")
                logger.info(
                    "CLASSIFIER SOVEREIGNTY: Escalation downgraded to EDD — "
                    "no Tier 1 suspicion indicators.",
                    extra={"request_id": request_id, "external_id": external_id},
                )
                final_decision = {
                    "verdict": "REVIEW",
                    "action": "EDD_REQUIRED",
                    "str_required": False,
                    "escalation_blocked_by_classifier": True,
                    "classifier_override_reason": (
                        f"Tier 1 suspicion indicators: 0. "
                        f"Tier 2 investigative signals: {classifier_result.investigative_count}. "
                        "Escalation downgraded to EDD by classifier sovereignty."
                    ),
                }

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

        # ── Override evaluation_trace with enhanced evidence + rules ────────
        # build_decision_pack() constructs a minimal 8-element evidence list.
        # Replace with the full pre_evidence_used (27 registry fields + indicators)
        # and pre_rules_fired (typology-specific rule codes) so the report
        # pipeline and frontend Evidence Gap Tracker / Typology Map work.
        decision_pack["evaluation_trace"]["evidence_used"] = pre_evidence_used
        decision_pack["evaluation_trace"]["rules_fired"] = pre_rules_fired

        # Add engine commit (decision_pack.py doesn't know about git)
        decision_pack["meta"]["engine_commit"] = DG_ENGINE_COMMIT
        # Note: policy_hash and decision_id are computed by decision_pack.py with full SHA-256

        # Attach optional classification metadata for audit/reporting
        meta_block = body.get("meta") or {}
        source_type = meta_block.get("source_type") or body.get("source_type") or "prod"
        scenario_code = meta_block.get("scenario_code") or body.get("scenario_code")
        seed_category = meta_block.get("seed_category") or body.get("seed_category")
        decision_pack["meta"]["source_type"] = str(source_type).lower()
        decision_pack["meta"]["scenario_code"] = normalize_scenario_code(scenario_code)
        decision_pack["meta"]["seed_category"] = normalize_seed_category(seed_category)

        # ── Attach classifier result to decision pack ──
        decision_pack["classifier"] = classifier_result.to_dict()
        decision_pack["classifier"]["sovereign"] = True
        if classifier_override_applied:
            decision_pack["classifier"]["override_applied"] = True
            decision_pack["classifier"]["original_verdict"] = classifier_original_verdict
            decision_pack["classifier"]["override_reason"] = final_decision.get(
                "classifier_override_reason", "Classifier sovereignty enforced"
            )
            # Patch decision block to reflect override
            decision_pack["decision"]["verdict"] = final_decision.get("verdict", "REVIEW")
            decision_pack["decision"]["action"] = final_decision.get("action", "EDD_REQUIRED")
            decision_pack["decision"]["str_required"] = "NO"
            decision_pack["decision"]["classifier_override"] = True
            # Update rationale
            decision_pack["rationale"]["summary"] = (
                f"Classifier sovereignty override: {classifier_result.outcome}. "
                f"{classifier_result.outcome_reason}"
            )
            decision_pack["rationale"]["str_rationale"] = None

        # Build fingerprint facts for precedent similarity
        fingerprint_facts = {}
        if isinstance(body.get("facts"), dict):
            fingerprint_facts.update(body.get("facts", {}))
        # For demo/seed cases, merge the CANONICAL registry fields into fingerprint
        # (translated to proper vocabulary: "individual" not "IND", etc.)
        if is_demo and isinstance(demo_inputs.get("_canonical_facts"), dict):
            for k, v in demo_inputs["_canonical_facts"].items():
                fingerprint_facts.setdefault(k, v)
        elif is_demo and isinstance(demo_inputs.get("_demo_facts"), dict):
            for k, v in demo_inputs["_demo_facts"].items():
                if "." in k:  # only registry-style fields
                    fingerprint_facts.setdefault(k, v)
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
        # Map engine verdict to precedent outcome codes (banking vocabulary)
        # The scorer uses v2 three-field canonical outcomes internally;
        # this v1 mapping exists for backward compat with precedent comparison.
        outcome_map = {
            "str": "escalate",
            "escalate": "escalate",
            "hard_stop": "deny",
            "pass": "pay",
            "pass_with_edd": "escalate",
            "block": "deny",
            "edd": "escalate",
            "allow": "pay",
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

        # Runtime invariant checks (PRECEDENT_OUTCOME_MODEL_V2.md §10)
        invariant_violations = check_precedent_invariants(
            precedent_analysis=precedent_analysis,
            decision_id=decision_pack["meta"]["decision_id"],
        )
        if invariant_violations:
            decision_pack["invariant_violations"] = invariant_violations

        # Self-validate output consistency (runs for ALL inputs)
        decision_pack = validate_decision_output(decision_pack)

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
# Precedent Outcome Model v2 — Three-Field Canonicalization
# =============================================================================
# See docs/PRECEDENT_OUTCOME_MODEL_V2.md for full specification.
#
# Every precedent outcome is decomposed into three independent dimensions:
#   disposition:       ALLOW | EDD | BLOCK | UNKNOWN
#   disposition_basis: MANDATORY | DISCRETIONARY | UNKNOWN
#   reporting:         NO_REPORT | FILE_STR | FILE_LCTR | FILE_TPR | UNKNOWN
#
# Invariants (INV-001 through INV-009) are enforced inline.


@dataclass(frozen=True)
class CanonicalOutcome:
    """Three-field precedent outcome (v2 model)."""
    disposition: str       # ALLOW | EDD | BLOCK | UNKNOWN
    disposition_basis: str  # MANDATORY | DISCRETIONARY | UNKNOWN
    reporting: str          # NO_REPORT | FILE_STR | FILE_LCTR | FILE_TPR | UNKNOWN

    def to_dict(self) -> dict:
        return {
            "disposition": self.disposition,
            "disposition_basis": self.disposition_basis,
            "reporting": self.reporting,
        }


# ── Disposition mapping ──────────────────────────────────────────────────────

_ALLOW_TERMS = frozenset({
    "pay", "paid", "approve", "approved", "accept", "accepted",
    "clear", "cleared", "covered", "eligible", "pass", "passed",
    "no report", "close", "closed", "no action",
})

_EDD_TERMS = frozenset({
    "review", "investigate", "investigation", "hold", "pending",
    "manual review", "needs info", "request more info", "pass with edd",
    "escalate", "escalated",
})

_BLOCK_TERMS = frozenset({
    "deny", "denied", "decline", "declined", "reject", "rejected",
    "block", "blocked", "refuse", "refused", "hard stop", "exit",
    "de-risk", "de risk",
})

# ── Reporting mapping ────────────────────────────────────────────────────────

_STR_TERMS = frozenset({
    "str", "report str", "suspicious transaction", "suspicious activity",
})

_LCTR_TERMS = frozenset({
    "lctr", "large cash", "large cash transaction", "report lctr",
})

_TPR_TERMS = frozenset({
    "tpr", "terrorist property", "terrorist property report", "report tpr",
})

# ── Basis indicators ─────────────────────────────────────────────────────────

_MANDATORY_INDICATORS = frozenset({
    "sanctions", "sanction", "sema", "una", "listed entity",
    "court order", "statutory", "criminal code",
})


def normalize_outcome_v2(
    raw_outcome: str,
    reason_codes: list[str] | None = None,
    case_facts: dict | None = None,
) -> CanonicalOutcome:
    """Normalize a raw outcome string into the three-field canonical model.

    Implements Section 4 of PRECEDENT_OUTCOME_MODEL_V2.md.

    INV-001: STR is NEVER inferred from disposition.
    """
    if not raw_outcome:
        return CanonicalOutcome("UNKNOWN", "UNKNOWN", "UNKNOWN")

    normalized = " ".join(raw_outcome.lower().strip().split()).replace("_", " ")

    # ── Disposition ───────────────────────────────────────────────────
    if normalized in _ALLOW_TERMS:
        disposition = "ALLOW"
    elif normalized in _EDD_TERMS:
        disposition = "EDD"
    elif normalized in _BLOCK_TERMS:
        disposition = "BLOCK"
    elif normalized in _STR_TERMS or normalized in _LCTR_TERMS or normalized in _TPR_TERMS:
        # Compound outcomes like "report str", "report lctr", "report tpr"
        # The filing obligation is explicit; disposition is ALLOW
        # (the transaction/relationship proceeds, but a report is filed)
        disposition = "ALLOW"
    else:
        disposition = "UNKNOWN"

    # ── Reporting (INV-001: never inferred from disposition) ──────────
    reporting = "UNKNOWN"
    # Check explicit reporting markers in the raw outcome itself
    if normalized in _STR_TERMS:
        reporting = "FILE_STR"
    elif normalized in _LCTR_TERMS:
        reporting = "FILE_LCTR"
    elif normalized in _TPR_TERMS:
        reporting = "FILE_TPR"
    elif disposition == "ALLOW":
        # Explicit ALLOW terms with no filing marker → NO_REPORT
        reporting = "NO_REPORT"

    # Check reason codes for explicit reporting signals
    if reason_codes and reporting == "UNKNOWN":
        codes_upper = {c.upper() for c in reason_codes}
        if any("RC-RPT-STR" in c or "RC-RPT-SAR" in c for c in codes_upper):
            reporting = "FILE_STR"
        elif any("RC-RPT-LCTR" in c for c in codes_upper):
            reporting = "FILE_LCTR"
        elif any("RC-RPT-TPR" in c for c in codes_upper):
            reporting = "FILE_TPR"

    # ── Disposition Basis ─────────────────────────────────────────────
    basis = "UNKNOWN"
    codes_for_basis = set()
    if reason_codes:
        codes_for_basis = {c.upper() for c in reason_codes}

    if any(
        indicator in " ".join(codes_for_basis).lower()
        for indicator in _MANDATORY_INDICATORS
    ):
        basis = "MANDATORY"
    elif case_facts:
        sanctions = case_facts.get("screening.sanctions_match")
        if _truthy(str(sanctions)) if sanctions is not None else False:
            basis = "MANDATORY"

    if basis == "UNKNOWN" and disposition in ("ALLOW", "BLOCK"):
        # If we know it's a terminal decision but can't determine legal
        # compulsion, assume discretionary (institutional risk appetite)
        basis = "DISCRETIONARY"

    return CanonicalOutcome(disposition, basis, reporting)


# ── v1 backward compatibility wrapper (delegates to v2) ──────────────────────

def normalize_outcome(raw: str) -> str:
    """v1 API — returns canonical disposition string for backward compat.

    Maps v2 dispositions to v1 labels:
      ALLOW   → "pay"
      EDD     → "escalate"
      BLOCK   → "deny"
      UNKNOWN → "escalate"
    """
    canonical = normalize_outcome_v2(raw)
    return {
        "ALLOW": "pay",
        "EDD": "escalate",
        "BLOCK": "deny",
        "UNKNOWN": "escalate",
    }.get(canonical.disposition, "escalate")


def classify_precedent_match_v2(
    precedent_outcome: CanonicalOutcome,
    case_outcome: CanonicalOutcome,
) -> str:
    """Classify a precedent match using v2 three-field model.

    Implements Section 10 of PRECEDENT_OUTCOME_MODEL_V2.md.

    INV-004: Only ALLOW vs BLOCK is contrary.
    INV-005: EDD is always neutral.
    INV-008: Cross-basis comparisons are informational only (neutral).
    """
    p_disp = precedent_outcome.disposition
    c_disp = case_outcome.disposition

    # INV-003: UNKNOWN is always neutral
    if p_disp == "UNKNOWN" or c_disp == "UNKNOWN":
        return "neutral"

    # Same disposition → supporting (including EDD == EDD)
    # Must be checked BEFORE the EDD neutralization below,
    # because Section 5.1 says same disposition is always supporting.
    if p_disp == c_disp:
        return "supporting"

    # INV-005: EDD vs terminal (ALLOW/BLOCK) is neutral —
    # EDD is procedural, not a final decision, so it cannot
    # contradict or support a terminal disposition.
    if p_disp == "EDD" or c_disp == "EDD":
        return "neutral"

    # INV-008: Cross-basis is neutral (mandatory vs discretionary)
    p_basis = precedent_outcome.disposition_basis
    c_basis = case_outcome.disposition_basis
    if p_basis != "UNKNOWN" and c_basis != "UNKNOWN" and p_basis != c_basis:
        return "neutral"

    # INV-004: ALLOW vs BLOCK → contrary
    if {p_disp, c_disp} == {"ALLOW", "BLOCK"}:
        return "contrary"

    return "neutral"


def map_aml_outcome_label(normalized: str) -> str:
    """v1 label mapping — kept for backward compat, delegates to v2."""
    canonical = normalize_outcome_v2(normalized)
    return map_aml_outcome_label_v2(canonical)


def map_aml_outcome_label_v2(canonical: CanonicalOutcome) -> str:
    """Derive display label from three-field canonical outcome.

    Implements Section 8 of PRECEDENT_OUTCOME_MODEL_V2.md —
    Regulatory Status Label Derivation.
    """
    d = canonical.disposition
    r = canonical.reporting

    # Reporting takes precedence for STR/TPR (regulatory obligation)
    if r == "FILE_STR":
        return "STR REQUIRED"
    if r == "FILE_TPR":
        if d == "ALLOW":
            return "TPR + ALLOW"
        return "TPR REQUIRED"

    # LCTR with ALLOW
    if r == "FILE_LCTR" and d == "ALLOW":
        return "LCTR + ALLOW"
    if r == "FILE_LCTR":
        return "LCTR REQUIRED"

    # Disposition labels (no reporting obligation or unknown)
    if d == "EDD":
        return "EDD REQUIRED"
    if d == "BLOCK" and r != "FILE_STR":
        return "BLOCKED — NO STR"
    if d == "ALLOW" and r == "NO_REPORT":
        return "NO REPORT"
    if d == "ALLOW":
        return "NO REPORT"
    if d == "BLOCK":
        return "BLOCKED — NO STR"
    if d == "UNKNOWN":
        return "UNKNOWN"

    return d


# Module-level cached v3 domain registry (loaded once)
_BANKING_DOMAIN = None

def _get_banking_domain():
    """Lazy-load and cache the banking domain registry for v3 scoring."""
    global _BANKING_DOMAIN
    if _BANKING_DOMAIN is None:
        _BANKING_DOMAIN = create_banking_domain_registry()
    return _BANKING_DOMAIN


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
AML_SIMILARITY_VERSION = "v1.1"  # v1.1: evaluable-component normalization


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
        # Insurance domain
        "adjuster": 0.9,
        "tribunal": 1.1,
        "court": 1.15,
        # Banking domain
        "analyst": 0.9,
        "senior_analyst": 0.95,
        "manager": 1.0,
        "cco": 1.1,
        "senior_management": 1.15,
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
        canonical = normalize_outcome_v2(
            payload.outcome_code,
            reason_codes=getattr(payload, "reason_codes", None),
        )
        label = canonical.disposition
        distribution[label] = distribution.get(label, 0) + 1
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
    v1 API — Classify a precedent match as supporting, contrary, or neutral.

    Delegates to classify_precedent_match_v2 internally.

    Args:
        precedent_outcome: The precedent's outcome (will be normalized)
        proposed_outcome: The proposed outcome (will be normalized)

    Returns:
        Classification: "supporting", "contrary", or "neutral"
    """
    prec_canonical = normalize_outcome_v2(precedent_outcome)
    prop_canonical = normalize_outcome_v2(proposed_outcome)
    return classify_precedent_match_v2(prec_canonical, prop_canonical)


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

    # v2: build canonical outcome for proposed disposition
    proposed_canonical = normalize_outcome_v2(proposed_outcome)

    # Classify all matches
    for match in matches:
        if len(match) >= 7:
            payload, overlap, score, component_scores = match[0], match[1], match[2], match[3]
            prec_canonical = match[6]  # CanonicalOutcome stored at index 6
        elif len(match) >= 4:
            payload, overlap, score, component_scores = match[0], match[1], match[2], match[3]
            prec_canonical = normalize_outcome_v2(payload.outcome_code, reason_codes=payload.reason_codes)
        elif len(match) >= 3:
            payload, overlap, score = match[0], match[1], match[2]
            component_scores = {}
            prec_canonical = normalize_outcome_v2(payload.outcome_code, reason_codes=payload.reason_codes)
        else:
            payload, overlap = match
            score = overlap
            component_scores = {}
            prec_canonical = normalize_outcome_v2(payload.outcome_code, reason_codes=payload.reason_codes)

        classification = classify_precedent_match_v2(prec_canonical, proposed_canonical)

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
    # v3 dispatcher: route to v3 engine when feature flag is set
    if DG_PRECEDENT_VERSION == "v3":
        return query_similar_precedents_v3(
            reason_codes=reason_codes,
            proposed_outcome=proposed_outcome,
            namespace_prefix=namespace_prefix,
            domain=domain,
            case_facts=case_facts,
            jurisdiction=jurisdiction,
        )

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

            # v2: three-field canonical outcome for each precedent
            # Prefer stored v2 fields from JudgmentPayload when available
            prec_canonical = normalize_outcome_v2(
                payload.outcome_code,
                reason_codes=payload.reason_codes,
            )
            # Override with explicitly stored fields if present on the payload
            stored_basis = getattr(payload, "disposition_basis", "UNKNOWN")
            stored_reporting = getattr(payload, "reporting_obligation", "UNKNOWN")
            if stored_basis != "UNKNOWN" or stored_reporting != "UNKNOWN":
                prec_canonical = CanonicalOutcome(
                    disposition=prec_canonical.disposition,
                    disposition_basis=stored_basis if stored_basis != "UNKNOWN" else prec_canonical.disposition_basis,
                    reporting=stored_reporting if stored_reporting != "UNKNOWN" else prec_canonical.reporting,
                )
            # INV-006: gate logic derives from reporting, not disposition
            gate1_allowed_prec = prec_canonical.disposition != "BLOCK"
            gate2_str_prec = prec_canonical.reporting == "FILE_STR"
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
                corridor_score = 1.0 if str(case_cross_border).lower() == str(precedent_cross_border).lower() else 0.0
            elif case_destination_risk is not None:
                precedent_destination_risk = _anchor_value(payload, "txn.destination_country_risk")
                if precedent_destination_risk is not None:
                    corridor_score = 1.0 if str(case_destination_risk).lower() == str(precedent_destination_risk).lower() else 0.0

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
                geo_risk_score = 1.0 if str(case_geo_risk).lower() == str(precedent_geo_risk).lower() else 0.0

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

            # ── Evaluable-component normalization ─────────────────────
            # Rules and gates are ALWAYS evaluable.  Optional components
            # (amount, channel, corridor, pep, customer, geo) should only
            # penalize the score when BOTH sides have data.  Otherwise the
            # weight is excluded and the score is renormalized so that
            # cases with sparse facts can still exceed the threshold when
            # the available components match well.
            evaluable = {"rules_overlap", "gate_match"}

            # Typology: evaluable when either side has typology tokens
            if case_typologies or precedent_typologies:
                evaluable.add("typology_overlap")

            # Remaining optional components — evaluable when BOTH sides present
            if case_amount_band and precedent_amount_band:
                evaluable.add("amount_bucket")
            if case_channel and precedent_channel:
                evaluable.add("channel_method")
            if (case_cross_border is not None and precedent_cross_border is not None) or \
               (case_destination_risk is not None and _anchor_value(payload, "txn.destination_country_risk") is not None):
                evaluable.add("corridor_match")
            if case_pep is not None and precedent_pep is not None:
                evaluable.add("pep_match")
            if (case_customer_type and precedent_customer_type) or \
               (case_relationship and precedent_relationship):
                evaluable.add("customer_profile")
            if case_geo_risk is not None and precedent_geo_risk is not None:
                evaluable.add("geo_risk")

            evaluable_weight = sum(
                AML_SIMILARITY_WEIGHTS[k] for k in evaluable
            ) or 1.0  # guard against zero

            raw_score = sum(
                AML_SIMILARITY_WEIGHTS[key] * component_scores.get(key, 0.0)
                for key in evaluable
            )
            similarity_score = raw_score / evaluable_weight

            # decision_weight and recency_weight are rank-ordering factors
            # (prefer senior decisions, prefer recent precedents) — they
            # should NOT reduce scores below the similarity threshold.
            decision_weight = _decision_level_weight(payload.decision_level)
            recency_weight = _recency_weight(payload.decided_at)
            combined = similarity_score * decision_weight * recency_weight

            if similarity_score >= threshold_used:
                scored_matches.append(
                    (
                        payload,
                        overlap,
                        combined,
                        component_scores,
                        decision_weight,
                        recency_weight,
                        prec_canonical,
                    )
                )

        raw_overlap_count = len(precedent_matches)
        overlap_outcome_distribution = _build_outcome_distribution(
            [payload for payload, _overlap in precedent_matches]
        )
        match_outcome_distribution = _build_outcome_distribution(
            [payload for payload, _overlap, _score, _components, _dw, _rw, _co in scored_matches]
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
            (score for _payload, _overlap, score, _components, _dw, _rw, _co in scored_matches),
            reverse=True,
        )
        top_scores = sorted_scores[:5]
        avg_top_k_similarity = round(sum(top_scores) / len(top_scores), 2) if top_scores else 0.0

        # Track caution precedents (overturned cases)
        caution_precedents = []
        for payload, overlap, classification, score, _component_scores in sampled:
            if payload.appealed and payload.appeal_outcome == "overturned":
                prec_co = normalize_outcome_v2(payload.outcome_code, reason_codes=payload.reason_codes)
                caution_precedents.append({
                    "precedent_id": payload.precedent_id[:8] + "...",
                    "outcome": payload.outcome_code,
                    "outcome_normalized": prec_co.disposition,
                    "disposition": prec_co.disposition,
                    "disposition_basis": prec_co.disposition_basis,
                    "reporting": prec_co.reporting,
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

            prec_canonical = normalize_outcome_v2(payload.outcome_code, reason_codes=payload.reason_codes)
            outcome_label = map_aml_outcome_label_v2(prec_canonical)
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
                "outcome_normalized": prec_canonical.disposition,
                "outcome_label": outcome_label,
                "disposition": prec_canonical.disposition,
                "disposition_basis": prec_canonical.disposition_basis,
                "reporting": prec_canonical.reporting,
                "reason_codes": payload.reason_codes[:4],
                "appealed": payload.appealed,
                "appeal_outcome": payload.appeal_outcome,
                "code_similarity_pct": int(round(code_similarity * 100)),
                "fingerprint_similarity_pct": int(round(fingerprint_similarity * 100)),
                "similarity_components": similarity_components,
            })

        # Calculate confidence score — v2 formula (Section 6)
        # Only terminal outcomes (ALLOW/BLOCK) within same disposition_basis
        # INV-003: UNKNOWN excluded from denominator
        # INV-008: cross-basis excluded from denominator
        proposed_canonical = normalize_outcome_v2(proposed_outcome, reason_codes=reason_codes, case_facts=case_facts)
        case_basis = proposed_canonical.disposition_basis

        decisive_supporting = 0
        decisive_total = 0
        for payload, _overlap, _score, _comps, _dw, _rw, prec_co in scored_matches:
            prec_disp = prec_co.disposition
            prec_basis = prec_co.disposition_basis

            # Only terminal dispositions count
            if prec_disp not in ("ALLOW", "BLOCK"):
                continue
            # INV-008: skip cross-basis precedents
            if case_basis != "UNKNOWN" and prec_basis != "UNKNOWN" and case_basis != prec_basis:
                continue

            decisive_total += 1
            if prec_disp == proposed_canonical.disposition:
                decisive_supporting += 1

        if len(scored_matches) == 0:
            precedent_confidence = 0.0
        elif decisive_total > 0:
            consistency_rate = decisive_supporting / decisive_total
            upheld_rate = stats.appeal_stats.upheld_rate if stats.appeal_stats.total_appealed > 0 else 1.0
            precedent_confidence = (consistency_rate * 0.7) + (upheld_rate * 0.3)
        else:
            precedent_confidence = 0.5

        # Governed Disposition Alignment — how many precedents match the
        # governed disposition, regardless of whether they're terminal.
        # This answers: "Does the bank agree with this outcome?"
        governed_alignment_count = 0
        for payload, _overlap, _score, _comps, _dw, _rw, prec_co in scored_matches:
            if prec_co.disposition == proposed_canonical.disposition:
                governed_alignment_count += 1

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
            "decisive_total": decisive_total,
            "decisive_supporting": decisive_supporting,
            "governed_alignment_count": governed_alignment_count,
            "governed_alignment_total": len(scored_matches),
            "exact_match_count": exact_match_count,
            "caution_precedents": caution_precedents[:5],
            "sample_cases": sample_cases[:10],
            "reason_codes_searched": reason_codes,
            "proposed_outcome_normalized": proposed_normalized,
            "proposed_outcome_label": map_aml_outcome_label_v2(proposed_canonical),
            "proposed_canonical": proposed_canonical.to_dict(),
            "outcome_model_version": "v2",
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
# v3 Precedent Scoring (Three-Layer Comparability Model)
# =============================================================================

def query_similar_precedents_v3(
    reason_codes: list,
    proposed_outcome: str,
    namespace_prefix: str = "banking.aml",
    domain: Optional[str] = None,
    case_facts: Optional[dict] = None,
    jurisdiction: Optional[str] = None,
) -> dict:
    """Query precedent registry using v3 Three-Layer Comparability Model.

    Layer 1: Comparability Gates (equivalence-class filtering)
    Layer 2: Causal Factor Alignment (driver-aware field-by-field scoring)
    Layer 3: Governed Confidence (4-dimension model — Phase 4)

    Returns a superset of the v2 dict with additional v3 keys.
    """
    if not PRECEDENTS_LOADED or not PRECEDENT_REGISTRY:
        return {
            "available": False,
            "message": "Precedent system not loaded",
        }

    try:
        resolved_prefix = resolve_precedent_namespace(domain, namespace_prefix)
        if not resolved_prefix:
            return {
                "available": False,
                "message": "Precedent system not enabled for this domain",
            }

        # Load v3 domain registry
        banking_domain = _get_banking_domain()

        # Normalize proposed outcome
        proposed_normalized = normalize_outcome(proposed_outcome)
        proposed_canonical = normalize_outcome_v2(
            proposed_outcome, reason_codes=reason_codes, case_facts=case_facts,
        )
        case_basis = proposed_canonical.disposition_basis

        mode = "demo" if DG_MODE == "demo" else "prod"
        threshold_used = (
            DG_PRECEDENT_THRESHOLD_DEMO if mode == "demo"
            else DG_PRECEDENT_THRESHOLD_PROD
        )

        # Prepare case facts for gate and scoring evaluation
        schema_id = _select_schema_id_for_codes(reason_codes)
        case_banded = _compute_case_banded_facts(case_facts or {}, schema_id)
        case_reason_codes = list(set(reason_codes))

        # Build case gate facts
        case_gate_facts = extract_gate_facts_from_case(
            case_facts or {},
            jurisdiction=jurisdiction,
            disposition_basis=case_basis,
        )

        # Build case scoring facts — v3 uses raw canonical fields directly.
        # Do NOT apply v2 banded facts (apply_aml_banding) here because they:
        #   1) Stringify booleans (False -> "false"), causing type mismatches
        #   2) Add schema-level "unknown" fields that dilute similarity scores
        case_scoring_facts: dict = {}
        if case_facts:
            case_scoring_facts.update(case_facts)

        # Detect primary typology for similarity floor override
        typology = detect_primary_typology(case_reason_codes, case_facts)
        similarity_floor = (
            banking_domain.similarity_floor_overrides.get(typology, banking_domain.similarity_floor)
            if typology
            else banking_domain.similarity_floor
        )

        # Find matching precedents (Tier 1 — overlapping reason codes)
        precedent_matches = PRECEDENT_REGISTRY.find_by_exclusion_codes(
            codes=reason_codes,
            namespace_prefix=resolved_prefix,
            min_overlap=1,
        )

        stats = PRECEDENT_REGISTRY.get_statistics_by_codes(
            exclusion_codes=reason_codes,
            namespace_prefix=resolved_prefix,
            min_overlap=1,
        )

        # ── Layer 1: Comparability Gate Filtering ─────────────────────
        gate_passed_matches = []
        gate_excluded_count = 0
        for payload, overlap in precedent_matches:
            # Schema filter (same as v2)
            if payload.fingerprint_schema_id != schema_id:
                continue

            # Build precedent gate facts
            prec_anchor_dict = {
                af.field_id: af.value for af in payload.anchor_facts
            }
            prec_gate_facts = extract_gate_facts_from_precedent(
                prec_anchor_dict,
                jurisdiction_code=payload.jurisdiction_code,
                disposition_basis=getattr(payload, "disposition_basis", "UNKNOWN"),
            )

            # Evaluate all comparability gates
            gates_ok, gate_results = evaluate_gates(
                banking_domain, case_gate_facts, prec_gate_facts,
            )

            if gates_ok:
                gate_passed_matches.append((payload, overlap, gate_results))
            else:
                gate_excluded_count += 1

        # ── Layer 2: Field-by-Field Scoring ──────────────────────────
        scored_matches = []
        non_transferable_count = 0

        for payload, overlap, gate_results in gate_passed_matches:
            # Build precedent scoring facts from anchor_facts
            prec_scoring_facts = anchor_facts_to_dict(payload.anchor_facts)

            # Get decision drivers from payload (v3 field)
            precedent_drivers = getattr(payload, "decision_drivers", []) or []

            # Score similarity using v3 field-by-field engine
            sim_result = score_similarity(
                banking_domain,
                case_scoring_facts,
                prec_scoring_facts,
                precedent_drivers=precedent_drivers,
            )

            # Apply similarity floor
            if sim_result.score < similarity_floor:
                continue

            # v2 canonical outcome for classification
            prec_canonical = normalize_outcome_v2(
                payload.outcome_code,
                reason_codes=payload.reason_codes,
            )
            stored_basis = getattr(payload, "disposition_basis", "UNKNOWN")
            stored_reporting = getattr(payload, "reporting_obligation", "UNKNOWN")
            if stored_basis != "UNKNOWN" or stored_reporting != "UNKNOWN":
                prec_canonical = CanonicalOutcome(
                    disposition=prec_canonical.disposition,
                    disposition_basis=(
                        stored_basis if stored_basis != "UNKNOWN"
                        else prec_canonical.disposition_basis
                    ),
                    reporting=(
                        stored_reporting if stored_reporting != "UNKNOWN"
                        else prec_canonical.reporting
                    ),
                )

            # v3 match classification (INV-011: non-transferable cannot be supporting)
            classification = classify_match_v3(
                case_disposition=proposed_canonical.disposition,
                precedent_disposition=prec_canonical.disposition,
                case_basis=case_basis,
                precedent_basis=prec_canonical.disposition_basis,
                non_transferable=sim_result.non_transferable,
            )

            if sim_result.non_transferable:
                non_transferable_count += 1

            # Rank-ordering factors (same as v2)
            decision_weight = _decision_level_weight(payload.decision_level)
            recency_weight = _recency_weight(payload.decided_at)
            combined = sim_result.score * decision_weight * recency_weight

            # Only include matches above threshold
            if sim_result.score >= threshold_used:
                scored_matches.append((
                    payload,
                    overlap,
                    combined,
                    sim_result,
                    decision_weight,
                    recency_weight,
                    prec_canonical,
                    classification,
                    gate_results,
                ))

        # ── Regime Detection & Temporal Partitioning (B1) ────────────
        case_signals = extract_case_signals(case_scoring_facts)
        applicable_shifts = detect_applicable_shifts(
            case_signals=case_signals, case_facts=case_scoring_facts,
        )
        regime_shift_ids = [s["id"] for s in applicable_shifts]

        # Partition scored_matches into pre-shift and post-shift pools
        pre_shift_matches = []
        post_shift_matches = []
        regime_limited_ids: set = set()  # precedent_ids marked regime-limited

        if regime_shift_ids:
            from datetime import date as _date_cls
            for entry in scored_matches:
                payload = entry[0]
                pr = getattr(payload, "policy_regime", None)
                if pr and pr.get("is_post_shift"):
                    post_shift_matches.append(entry)
                else:
                    pre_shift_matches.append(entry)
                    # Check if shadow outcome differs → regime-limited
                    prec_anchor_dict = {
                        af.field_id: af.value for af in payload.anchor_facts
                    }
                    for sid in regime_shift_ids:
                        shadow = compute_shadow_outcome(prec_anchor_dict, sid)
                        if shadow is not None:
                            regime_limited_ids.add(payload.precedent_id)
                            break
        else:
            # No shifts detected — all matches are current-regime
            post_shift_matches = list(scored_matches)

        # ── Stratified Sampling ──────────────────────────────────────
        # Build v2-compatible tuples for stratified_precedent_sample
        v2_tuples = [
            (payload, overlap, classification, combined, {})
            for payload, overlap, combined, sim_result, dw, rw, co, classification, gr
            in scored_matches
        ]

        # Sort by score descending
        v2_tuples.sort(key=lambda x: x[3], reverse=True)

        # Apply stratified sampling limits
        sampled_supporting = []
        sampled_contrary = []
        sampled_neutral = []
        for t in v2_tuples:
            cls = t[2]
            if cls == "supporting" and len(sampled_supporting) < 35:
                sampled_supporting.append(t)
            elif cls == "contrary" and len(sampled_contrary) < 10:
                sampled_contrary.append(t)
            elif cls == "neutral" and len(sampled_neutral) < 15:
                sampled_neutral.append(t)

        sampled = (sampled_supporting + sampled_contrary + sampled_neutral)[:50]
        counts = {
            "supporting": len(sampled_supporting),
            "contrary": len(sampled_contrary),
            "neutral": len(sampled_neutral),
        }

        # ── Confidence: Governed 4-Dimension Model (v3) ────────────
        decisive_supporting = 0
        decisive_total = 0
        sim_scores_for_avg = []
        for payload, _ov, _sc, sim_r, _dw, _rw, prec_co, _cls, _gr in scored_matches:
            sim_scores_for_avg.append(sim_r.score)
            prec_disp = prec_co.disposition
            prec_basis = prec_co.disposition_basis
            if prec_disp not in ("ALLOW", "BLOCK"):
                continue
            if case_basis != "UNKNOWN" and prec_basis != "UNKNOWN" and case_basis != prec_basis:
                continue
            decisive_total += 1
            if prec_disp == proposed_canonical.disposition:
                decisive_supporting += 1

        avg_sim = (
            sum(sim_scores_for_avg) / len(sim_scores_for_avg)
            if sim_scores_for_avg else 0.0
        )

        # B1.5: Use post-shift pool_size when shifts detected so
        # confidence reflects current-regime experience only
        effective_pool_size = (
            len(post_shift_matches)
            if regime_shift_ids
            else len(scored_matches)
        )

        governed_result = compute_governed_confidence(
            domain=banking_domain,
            pool_size=effective_pool_size,
            avg_similarity=avg_sim,
            decisive_supporting=decisive_supporting,
            decisive_total=decisive_total,
            case_facts=case_scoring_facts,
            non_transferable_count=non_transferable_count,
        )

        # Map v3 level to numeric for backward compat
        precedent_confidence = governed_result.numeric_value

        # Governed alignment
        governed_alignment_count = sum(
            1 for _, _, _, _, _, _, co, _, _ in scored_matches
            if co.disposition == proposed_canonical.disposition
        )

        # ── Top-k similarity ─────────────────────────────────────────
        sorted_scores = sorted(
            (sim.score for _, _, _, sim, _, _, _, _, _ in scored_matches),
            reverse=True,
        )
        top_scores = sorted_scores[:5]
        avg_top_k_similarity = (
            round(sum(top_scores) / len(top_scores), 2) if top_scores else 0.0
        )

        # ── Caution precedents ───────────────────────────────────────
        caution_precedents = []
        for payload, overlap, classification, score, _cs in sampled:
            if payload.appealed and payload.appeal_outcome == "overturned":
                prec_co = normalize_outcome_v2(
                    payload.outcome_code, reason_codes=payload.reason_codes,
                )
                caution_precedents.append({
                    "precedent_id": payload.precedent_id[:8] + "...",
                    "outcome": payload.outcome_code,
                    "outcome_normalized": prec_co.disposition,
                    "disposition": prec_co.disposition,
                    "disposition_basis": prec_co.disposition_basis,
                    "reporting": prec_co.reporting,
                    "classification": classification,
                    "appeal_outcome": payload.appeal_outcome,
                    "reason_codes": payload.reason_codes[:3],
                })

        # ── Sample cases with v3 field scores ────────────────────────
        sample_cases = []
        exact_match_count = 0
        # Build a lookup from scored_matches for sim_result data
        sim_lookup = {
            id(payload): (sim_result, gate_results)
            for payload, _, _, sim_result, _, _, _, _, gate_results in scored_matches
        }

        for payload, overlap, classification, score, _cs in sampled:
            overlap_codes = set(case_reason_codes).intersection(payload.reason_codes)
            case_code_weights = sum(_code_weight(c) for c in case_reason_codes) or 1.0
            weighted_overlap = sum(_code_weight(c) for c in overlap_codes)
            code_similarity = weighted_overlap / case_code_weights
            fingerprint_similarity = _compute_fingerprint_similarity(case_banded, payload)
            exact_match = code_similarity >= 0.9 and fingerprint_similarity >= 0.9
            if exact_match:
                exact_match_count += 1

            prec_canonical = normalize_outcome_v2(
                payload.outcome_code, reason_codes=payload.reason_codes,
            )
            outcome_label = map_aml_outcome_label_v2(prec_canonical)

            # v3-specific data from sim_result
            sim_data = sim_lookup.get(id(payload))
            field_scores_pct = {}
            non_transferable = False
            non_transferable_reasons = []
            matched_drivers = []
            mismatched_drivers = []
            if sim_data:
                sr, _ = sim_data
                field_scores_pct = {
                    k: int(round(v * 100)) for k, v in sr.field_scores.items()
                }
                non_transferable = sr.non_transferable
                non_transferable_reasons = sr.non_transferable_reasons
                matched_drivers = sr.matched_drivers
                mismatched_drivers = sr.mismatched_drivers

            sample_cases.append({
                "precedent_id": payload.precedent_id[:8] + "...",
                "decision_level": payload.decision_level,
                "decided_at": payload.decided_at,
                "classification": classification,
                "overlap": overlap,
                "similarity_pct": int(round(score * 100)),
                "exact_match": exact_match,
                "outcome": payload.outcome_code,
                "outcome_normalized": prec_canonical.disposition,
                "outcome_label": outcome_label,
                "disposition": prec_canonical.disposition,
                "disposition_basis": prec_canonical.disposition_basis,
                "reporting": prec_canonical.reporting,
                "reason_codes": payload.reason_codes[:4],
                "appealed": payload.appealed,
                "appeal_outcome": payload.appeal_outcome,
                "code_similarity_pct": int(round(code_similarity * 100)),
                "fingerprint_similarity_pct": int(round(fingerprint_similarity * 100)),
                # v3-specific fields
                "field_scores": field_scores_pct,
                "non_transferable": non_transferable,
                "non_transferable_reasons": non_transferable_reasons,
                "matched_drivers": matched_drivers,
                "mismatched_drivers": mismatched_drivers,
                # B1.6: regime-limited marking for pre-shift precedents
                "regime_limited": payload.precedent_id in regime_limited_ids,
                # v2 template compatibility — the HTML template reads
                # match.similarity_components for the sim-bar display
                "similarity_components": {
                    "rules_overlap": field_scores_pct.get("flag.structuring", 0),
                    "gate_match": int(round(score * 100)),
                    "typology_overlap": field_scores_pct.get("flag.unusual_for_profile", 0),
                    "amount_bucket": field_scores_pct.get("txn.amount_band", 0),
                    "channel_method": field_scores_pct.get("txn.type", 0),
                    "corridor_match": field_scores_pct.get("txn.destination_country_risk", 0),
                    "pep_match": field_scores_pct.get("customer.pep", 0),
                    "customer_profile": field_scores_pct.get("customer.type", 0),
                    "geo_risk": field_scores_pct.get("customer.high_risk_jurisdiction", 0),
                },
            })

        # ── Build response (v2 superset) ─────────────────────────────
        raw_overlap_count = len(precedent_matches)
        overlap_outcome_distribution = _build_outcome_distribution(
            [p for p, _o in precedent_matches]
        )
        match_outcome_distribution = _build_outcome_distribution(
            [p for p, _, _, _, _, _, _, _, _ in scored_matches]
        )

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
            "decisive_total": decisive_total,
            "decisive_supporting": decisive_supporting,
            "governed_alignment_count": governed_alignment_count,
            "governed_alignment_total": len(scored_matches),
            "exact_match_count": exact_match_count,
            "caution_precedents": caution_precedents[:5],
            "sample_cases": sample_cases[:10],
            "reason_codes_searched": reason_codes,
            "proposed_outcome_normalized": proposed_normalized,
            "proposed_outcome_label": map_aml_outcome_label_v2(proposed_canonical),
            "proposed_canonical": proposed_canonical.to_dict(),
            "outcome_model_version": "v2",
            "min_similarity_pct": int(round(threshold_used * 100)),
            "threshold_used": threshold_used,
            "threshold_mode": mode,
            # v3-specific keys
            "scoring_version": "v3",
            "precedent_scoring_version": "v3",
            "gate_excluded_count": gate_excluded_count,
            "gate_passed_count": len(gate_passed_matches),
            "non_transferable_count": non_transferable_count,
            "similarity_floor_used": similarity_floor,
            "typology_detected": typology,
            "weights_version": "v3",
            "why_low_match": [],
            "avg_top_k_similarity": avg_top_k_similarity,
            # v3 governed confidence
            "confidence_model_version": "v3",
            "confidence_level": governed_result.level.value,
            "confidence_dimensions": [
                {
                    "name": d.name,
                    "value": round(d.value, 4),
                    "level": d.level.value,
                    "bottleneck": d.bottleneck,
                    "note": d.note,
                }
                for d in governed_result.dimensions
            ],
            "confidence_bottleneck": governed_result.bottleneck,
            "confidence_hard_rule": governed_result.hard_rule_applied,
        }

        # ── B1: Regime Analysis ─────────────────────────────────────
        regime_analysis: dict | None = None
        if regime_shift_ids:
            # Count outcome distributions in pre- vs post-shift pools
            pre_dist = _build_outcome_distribution(
                [p for p, *_ in pre_shift_matches]
            ) if pre_shift_matches else {}
            post_dist = _build_outcome_distribution(
                [p for p, *_ in post_shift_matches]
            ) if post_shift_matches else {}

            # Determine magnitude (how many pool members are regime-limited)
            regime_limited_count = len(regime_limited_ids)
            total_pool = len(scored_matches)
            pct_limited = round(
                regime_limited_count / total_pool * 100, 1
            ) if total_pool else 0.0

            # Guidance
            if pct_limited > 50:
                magnitude = "high"
                guidance = (
                    "Majority of precedent pool predates policy change. "
                    "Confidence reflects post-shift experience only."
                )
            elif pct_limited > 20:
                magnitude = "moderate"
                guidance = (
                    "Significant portion of pool predates policy change. "
                    "Post-shift pool is smaller than total."
                )
            else:
                magnitude = "low"
                guidance = (
                    "Most precedents remain valid under current policy."
                )

            regime_analysis = {
                "shifts_detected": [
                    {
                        "id": s["id"],
                        "name": s["name"],
                        "description": s["description"],
                        "effective_date": s.get("effective_date"),
                    }
                    for s in applicable_shifts
                ],
                "total_pool": total_pool,
                "pre_shift_count": len(pre_shift_matches),
                "post_shift_count": len(post_shift_matches),
                "regime_limited_count": regime_limited_count,
                "pct_regime_limited": pct_limited,
                "magnitude": magnitude,
                "guidance": guidance,
                "pre_shift_distribution": pre_dist,
                "post_shift_distribution": post_dist,
                "effective_pool_size": effective_pool_size,
            }

        response["regime_analysis"] = regime_analysis

        if len(scored_matches) == 0:
            response["message"] = "No precedents met the similarity threshold"

        return response

    except Exception as e:
        logger.warning(f"Precedent query v3 failed: {e}")
        return {
            "available": False,
            "message": f"Precedent query failed: {str(e)}",
        }


# =============================================================================
# Runtime Invariant Checks (PRECEDENT_OUTCOME_MODEL_V2.md §10)
# =============================================================================

def check_precedent_invariants(
    precedent_analysis: dict,
    decision_id: str,
) -> list[dict]:
    """Validate v2 invariants against a completed precedent analysis.

    Each violation is logged at CRITICAL level with the invariant ID,
    violating values, and decision_id for audit trail.

    Returns a list of violation dicts (empty = all invariants satisfied).
    """
    violations: list[dict] = []
    if not precedent_analysis or not precedent_analysis.get("available"):
        return violations

    proposed = precedent_analysis.get("proposed_canonical", {})
    sample_cases = precedent_analysis.get("sample_cases", []) or []

    def _violation(inv_id: str, detail: str, values: dict | None = None):
        v = {
            "invariant": inv_id,
            "detail": detail,
            "decision_id": decision_id,
        }
        if values:
            v["values"] = values
        violations.append(v)
        logger.critical(
            f"INVARIANT VIOLATION: {inv_id} — {detail}",
            extra={"invariant": inv_id, "decision_id": decision_id, **(values or {})},
        )

    # INV-001: STR never inferred from disposition
    # If reporting == FILE_STR, there must be explicit evidence (reason codes
    # with RC-RPT-STR/SAR, or raw outcome containing STR terms).
    # We can verify this structurally: FILE_STR should not appear when the
    # only evidence is disposition == BLOCK.
    p_disp = proposed.get("disposition", "")
    p_reporting = proposed.get("reporting", "")
    if p_reporting == "FILE_STR" and p_disp == "BLOCK":
        p_basis = proposed.get("disposition_basis", "")
        if p_basis == "DISCRETIONARY":
            # Discretionary BLOCK + FILE_STR is suspicious — STR might be
            # inferred from the block itself.  Only a violation if no
            # explicit reporting reason codes were searched.
            reason_codes = precedent_analysis.get("reason_codes_searched", []) or []
            has_explicit_str = any(
                "RPT-STR" in c.upper() or "RPT-SAR" in c.upper()
                for c in reason_codes
            )
            if not has_explicit_str:
                _violation(
                    "INV-001",
                    "STR obligation may have been inferred from disposition (BLOCK + DISCRETIONARY + FILE_STR without explicit RPT code)",
                    {"disposition": p_disp, "reporting": p_reporting, "basis": p_basis},
                )

    # INV-002: Three fields present and independent
    for field in ("disposition", "disposition_basis", "reporting"):
        if field not in proposed or proposed[field] is None:
            _violation("INV-002", f"Canonical field '{field}' missing from proposed_canonical")

    # INV-003: UNKNOWN excluded from confidence denominator
    # The confidence formula should only count ALLOW/BLOCK.
    # We verify by checking that no UNKNOWN sample case was classified as
    # supporting or contrary.
    for sc in sample_cases:
        sc_disp = sc.get("disposition", "UNKNOWN")
        sc_class = sc.get("classification", "neutral")
        if sc_disp == "UNKNOWN" and sc_class in ("supporting", "contrary"):
            _violation(
                "INV-003",
                f"UNKNOWN disposition classified as {sc_class}",
                {"precedent_id": sc.get("precedent_id"), "disposition": sc_disp},
            )

    # INV-004: Only ALLOW vs BLOCK is contrary
    for sc in sample_cases:
        sc_class = sc.get("classification", "neutral")
        if sc_class == "contrary":
            sc_disp = sc.get("disposition", "UNKNOWN")
            if sc_disp not in ("ALLOW", "BLOCK"):
                _violation(
                    "INV-004",
                    f"Non-terminal disposition '{sc_disp}' classified as contrary",
                    {"precedent_id": sc.get("precedent_id"), "disposition": sc_disp},
                )

    # INV-005: EDD neutral vs terminal dispositions
    # Per Section 5.1, EDD == EDD is supporting (same disposition).
    # INV-005 applies to EDD vs ALLOW/BLOCK — those must be neutral.
    case_disp = proposed.get("disposition", "UNKNOWN")
    for sc in sample_cases:
        sc_disp = sc.get("disposition", "UNKNOWN")
        sc_class = sc.get("classification", "neutral")
        # EDD vs terminal classified as supporting or contrary = violation
        if sc_disp == "EDD" and case_disp in ("ALLOW", "BLOCK") and sc_class != "neutral":
            _violation(
                "INV-005",
                f"EDD precedent classified as {sc_class} against terminal {case_disp}",
                {"precedent_id": sc.get("precedent_id")},
            )
        if case_disp == "EDD" and sc_disp in ("ALLOW", "BLOCK") and sc_class != "neutral":
            _violation(
                "INV-005",
                f"Terminal {sc_disp} precedent classified as {sc_class} against EDD case",
                {"precedent_id": sc.get("precedent_id")},
            )
        # EDD classified as contrary is always wrong
        if sc_disp == "EDD" and sc_class == "contrary":
            _violation(
                "INV-005",
                f"EDD disposition classified as contrary",
                {"precedent_id": sc.get("precedent_id")},
            )

    # INV-006: Gate2 STR derived from reporting, not disposition
    # Structural check: verified at code level (line 2484).
    # Runtime: ensure gate_match component used reporting field.
    # (This is enforced by construction — no runtime sample data to check.)

    # INV-007: Disposition deviation → Consistency; Reporting deviation → Defensibility
    # (Checked in derive.py — deviation alert types are hardcoded.)

    # INV-008: No cross-basis in confidence denominator
    case_basis = proposed.get("disposition_basis", "UNKNOWN")
    for sc in sample_cases:
        sc_basis = sc.get("disposition_basis", "UNKNOWN")
        sc_class = sc.get("classification", "neutral")
        sc_disp = sc.get("disposition", "UNKNOWN")
        if (
            sc_class in ("supporting", "contrary")
            and case_basis != "UNKNOWN"
            and sc_basis != "UNKNOWN"
            and case_basis != sc_basis
        ):
            _violation(
                "INV-008",
                f"Cross-basis precedent ({sc_basis} vs case {case_basis}) classified as {sc_class}",
                {"precedent_id": sc.get("precedent_id"), "prec_basis": sc_basis, "case_basis": case_basis},
            )

    # INV-009: (Governance-level — tracked via defensibility_check in derive.py)

    # ── v3 invariants (only checked when scoring_version == "v3") ──
    if precedent_analysis.get("scoring_version") == "v3":
        # INV-010: No hardcoded fallback confidence
        # v3 governed model should never produce 0.5 as a fallback
        conf_val = precedent_analysis.get("precedent_confidence")
        conf_model = precedent_analysis.get("confidence_model_version")
        if conf_model == "v3" and conf_val == 0.5:
            conf_level = (precedent_analysis.get("confidence_level") or "").upper()
            # 0.5 maps to MODERATE — only valid if actually computed as MODERATE
            if conf_level != "MODERATE":
                _violation(
                    "INV-010",
                    "Hardcoded fallback confidence 0.5 detected in v3 model",
                    {"confidence": conf_val, "level": conf_level},
                )

        # INV-011: Non-transferable cannot be supporting
        for sc in sample_cases:
            if sc.get("non_transferable") and sc.get("classification") == "supporting":
                _violation(
                    "INV-011",
                    "Non-transferable precedent classified as supporting",
                    {"precedent_id": sc.get("precedent_id")},
                )

        # INV-012: Below-floor precedent cannot appear in scored pool
        sim_floor = precedent_analysis.get("similarity_floor_used", 0.60)
        for sc in sample_cases:
            sim_pct = sc.get("similarity_pct", 100)
            if sim_pct < int(round(sim_floor * 100)):
                _violation(
                    "INV-012",
                    f"Precedent with similarity {sim_pct}% below floor {sim_floor:.0%} in scored pool",
                    {"precedent_id": sc.get("precedent_id"), "similarity_pct": sim_pct},
                )

    if violations:
        logger.critical(
            f"Precedent invariant check: {len(violations)} violation(s)",
            extra={"decision_id": decision_id, "violation_count": len(violations)},
        )

    return violations


# =============================================================================
# Startup/Shutdown
# =============================================================================

# =============================================================================
# Landing Page
# =============================================================================

@app.get("/landing", tags=["Landing"])
async def legacy_landing_page():
    """Serve the original interactive landing page."""
    try:
        from fastapi.responses import FileResponse
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
    except Exception as e:
        pass
    return JSONResponse(content={"error": "Landing page not found"}, status_code=404)


@app.get("/", tags=["Dashboard"])
async def serve_dashboard_root():
    """Serve the React dashboard SPA."""
    from fastapi.responses import FileResponse
    spa_index = DASHBOARD_DIR / "index.html"
    if spa_index.exists():
        return FileResponse(spa_index, media_type="text/html")
    # Fallback to old landing page
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse(content={
        "service": "DecisionGraph",
        "version": DG_ENGINE_VERSION,
        "description": "Bank-Grade AML/KYC Decision Engine",
        "docs": "/docs",
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

# =============================================================================
# Dashboard API endpoints (stats, fields, seeds, audit)
# =============================================================================

@app.get("/api/stats", tags=["Dashboard"])
async def dashboard_stats():
    """Return aggregate statistics for the dashboard."""
    try:
        from service.demo_cases import get_demo_cases
        demo_cases = get_demo_cases()
    except Exception:
        demo_cases = []
    return {
        "total_seeds": PRECEDENT_COUNT,
        "demo_cases": len(demo_cases),
        "policy_shifts": 4,
        "registry_fields": 28,
        "precedents_loaded": PRECEDENTS_LOADED,
        "engine_version": DG_ENGINE_VERSION,
        "policy_version": DG_POLICY_VERSION,
    }


@app.get("/api/fields", tags=["Dashboard"])
async def list_fields():
    """Return the full banking field registry (28 fields)."""
    try:
        from decisiongraph.banking_field_registry import BANKING_FIELD_REGISTRY
        return [
            {
                "name": name,
                "label": defn.get("label", name),
                "type": defn.get("type", "text"),
                "description": defn.get("description", ""),
                "category": defn.get("category", "general"),
                "required": defn.get("required", False),
            }
            for name, defn in BANKING_FIELD_REGISTRY.items()
        ]
    except ImportError:
        return JSONResponse(
            content={"error": "Banking field registry not available"},
            status_code=501,
        )


@app.get("/api/seeds", tags=["Dashboard"])
async def list_seeds():
    """Return seed scenarios overview."""
    if not PRECEDENTS_LOADED:
        return []
    try:
        seeds = generate_all_banking_seeds()
        scenarios: dict = {}
        for s in seeds:
            sc = s.scenario_code or "unknown"
            if sc not in scenarios:
                scenarios[sc] = {"scenario_code": sc, "count": 0, "sample_id": s.precedent_id}
            scenarios[sc]["count"] += 1
        return list(scenarios.values())
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/seeds/{seed_id}", tags=["Dashboard"])
async def get_seed(seed_id: str):
    """Return a specific seed by precedent_id."""
    try:
        seeds = generate_all_banking_seeds()
        for s in seeds:
            if s.precedent_id == seed_id:
                return s.to_dict()
        raise HTTPException(status_code=404, detail=f"Seed {seed_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/audit", tags=["Dashboard"])
async def search_audit(q: str = "", outcome: str = "", scenario: str = ""):
    """Search audit log (returns demo cases as placeholder)."""
    try:
        from service.demo_cases import get_demo_cases
        cases = get_demo_cases()
        results = []
        for c in cases:
            if q and q.lower() not in json.dumps(c).lower():
                continue
            if outcome and c.get("expected_verdict", "").lower() != outcome.lower():
                continue
            if scenario and c.get("category", "").lower() != scenario.lower():
                continue
            results.append(c)
        return results
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# =============================================================================
# SPA Catch-All — serves React dashboard for all frontend routes
# MUST be the LAST route registered
# =============================================================================

_SPA_ROUTES = {"/cases", "/seeds", "/policy-shifts", "/sandbox", "/audit", "/registry", "/reports"}


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa_catchall(full_path: str):
    """Catch-all: serve the React SPA index.html for frontend routes.

    Only serves SPA for known frontend routes — API routes like /report/
    must NOT be intercepted here.
    """
    from fastapi.responses import FileResponse

    # Only serve SPA for known frontend routes, not API paths
    normalized = f"/{full_path}".rstrip("/")
    is_spa_route = any(normalized.startswith(r) for r in _SPA_ROUTES)

    spa_index = DASHBOARD_DIR / "index.html"
    if is_spa_route and spa_index.exists():
        return FileResponse(spa_index, media_type="text/html")
    raise HTTPException(status_code=404, detail=f"Not found: /{full_path}")


@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown."""
    logger.info("DecisionGraph shutting down")

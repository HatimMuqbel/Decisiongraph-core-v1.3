"""
ClaimPilot API

Product-agnostic insurance claims evaluation engine.
"""

import sys
from pathlib import Path
from typing import Optional

# Add src directory to path for claimpilot imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add decisiongraph path for chain/precedent support
dg_path = Path(__file__).parent.parent.parent / "decisiongraph-complete" / "src"
if str(dg_path) not in sys.path:
    sys.path.insert(0, str(dg_path))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from claimpilot.packs.loader import PolicyPackLoader
from claimpilot.models import Policy

# Precedent system imports
try:
    from decisiongraph.chain import Chain
    from decisiongraph.cell import NULL_HASH
    from decisiongraph.precedent_registry import PrecedentRegistry
    from decisiongraph.judgment import create_judgment_cell
    from claimpilot.precedent.cli import generate_all_insurance_seeds
    PRECEDENT_SYSTEM_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Precedent system not available: {e}")
    PRECEDENT_SYSTEM_AVAILABLE = False
    Chain = None
    PrecedentRegistry = None

from api.routes import policies, evaluate, demo, verify, memo, templates
from api.template_loader import TemplateLoader


# Policy loader and cache
loader = PolicyPackLoader(strict_version=False)
policies_cache: dict[str, Policy] = {}

# Template loader
templates_dir = Path(__file__).parent.parent / "templates"
template_loader = TemplateLoader(templates_dir)

# Precedent system globals
PRECEDENT_CHAIN: Optional[Chain] = None
PRECEDENT_REGISTRY: Optional[PrecedentRegistry] = None
PRECEDENTS_LOADED = False
PRECEDENT_COUNT = 0


def load_precedent_seeds() -> int:
    """
    Load the 2,150 insurance seed precedents into a Chain.

    Returns:
        Number of precedents loaded
    """
    global PRECEDENT_CHAIN, PRECEDENT_REGISTRY, PRECEDENTS_LOADED, PRECEDENT_COUNT

    if not PRECEDENT_SYSTEM_AVAILABLE:
        print("  [SKIP] Precedent system not available")
        return 0

    try:
        # Generate all seed precedents
        seeds = generate_all_insurance_seeds()
        PRECEDENT_COUNT = len(seeds)

        # Create and initialize the chain
        PRECEDENT_CHAIN = Chain()
        genesis = PRECEDENT_CHAIN.initialize(
            graph_name="ClaimPilotPrecedents",
            root_namespace="claims_precedents",
            creator="system:seed_loader",
            hash_scheme="canon:rfc8785:v1",
        )

        # Append all JUDGMENT cells
        prev_hash = genesis.cell_id
        graph_id = genesis.header.graph_id

        for payload in seeds:
            # Derive namespace from policy type, normalize to valid format
            policy_type = payload.policy_pack_id.split(":")[-1] if payload.policy_pack_id else "general"
            # Normalize: lowercase, replace hyphens with underscores
            policy_type = policy_type.lower().replace("-", "_")

            cell = create_judgment_cell(
                payload=payload,
                namespace=f"claims_precedents_{policy_type}",
                graph_id=graph_id,
                prev_cell_hash=prev_hash,
            )
            PRECEDENT_CHAIN.append(cell)
            prev_hash = cell.cell_id

        # Create the registry for queries
        PRECEDENT_REGISTRY = PrecedentRegistry(PRECEDENT_CHAIN)
        PRECEDENTS_LOADED = True

        return PRECEDENT_COUNT

    except Exception as e:
        print(f"  [ERROR] Failed to load precedent seeds: {e}")
        import traceback
        traceback.print_exc()
        PRECEDENTS_LOADED = False
        return 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load policy packs on startup."""
    print("Loading policy packs...")

    packs_dir = Path(__file__).parent.parent / "packs"

    policy_files = [
        "auto/ontario_oap1.yaml",
        "property/homeowners_ho3.yaml",
        "marine/pleasure_craft.yaml",
        "health/group_health.yaml",
        "workers_comp/ontario_wsib.yaml",
        "liability/cgl.yaml",
        "liability/professional_eo.yaml",
        "travel/travel_medical.yaml",
    ]

    loaded = 0
    for policy_file in policy_files:
        path = packs_dir / policy_file
        if path.exists():
            try:
                policy = loader.load(str(path))
                policies_cache[policy.id] = policy
                print(f"  [OK] Loaded {policy.id}")
                loaded += 1
            except Exception as e:
                print(f"  [ERROR] Failed to load {policy_file}: {e}")
        else:
            print(f"  [SKIP] Not found: {policy_file}")

    print(f"Loaded {loaded} policy packs")

    # Load templates
    print("Loading case templates...")
    templates_loaded = template_loader.load_all()
    print(f"Loaded {templates_loaded} case templates")

    # Load precedent seeds
    print("Loading precedent seeds...")
    precedents_loaded = load_precedent_seeds()
    print(f"Loaded {precedents_loaded} precedent seeds")

    # Share loader with routes
    policies.set_loader(loader, policies_cache)
    evaluate.set_loader(loader, policies_cache)
    verify.set_loader(loader, policies_cache)
    templates.set_loader(template_loader)

    yield

    print("Shutting down...")


# Create app
app = FastAPI(
    title="ClaimPilot API",
    description="""
**Product-agnostic insurance claims evaluation engine.**

ClaimPilot evaluates claims against policy rules and returns recommendations
with full reasoning chains and provenance.

## Features

- **8 Policy Packs**: Auto, Property, Marine, Health, Workers Comp, CGL, E&O, Travel
- **Deterministic Evaluation**: Same facts = same recommendation
- **Full Audit Trail**: Reasoning steps, citations, provenance hashes
- **Real Policy Wording**: Actual exclusion language cited

## Quick Start

1. `GET /policies` - See available policy packs
2. `GET /demo/cases` - See pre-built scenarios
3. `POST /evaluate` - Evaluate a claim
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://claimpilot.io",
        "https://claimpilot.ca",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(policies.router)
app.include_router(evaluate.router)
app.include_router(demo.router)
app.include_router(verify.router)
app.include_router(memo.router)
app.include_router(templates.router)

# Mount static files (for CSS, JS, images if needed)
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", tags=["Landing"], include_in_schema=False)
async def root():
    """Serve the landing page."""
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    # Fallback to JSON if no landing page
    return {
        "service": "ClaimPilot API",
        "version": "1.0.0",
        "status": "running",
        "policies_loaded": len(policies_cache),
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/api", tags=["Health"])
async def api_info():
    """API info endpoint - JSON health check and info."""
    return {
        "service": "ClaimPilot API",
        "version": "1.0.0",
        "status": "running",
        "policies_loaded": len(policies_cache),
        "precedents_loaded": PRECEDENT_COUNT,
        "precedent_system_available": PRECEDENTS_LOADED,
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint."""
    return {
        "healthy": True,
        "policies_loaded": len(policies_cache),
        "precedents_loaded": PRECEDENT_COUNT,
        "precedent_system_available": PRECEDENTS_LOADED
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""
ClaimPilot API

Product-agnostic insurance claims evaluation engine.
"""

import sys
from pathlib import Path

# Add src directory to path for claimpilot imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from claimpilot.packs.loader import PolicyPackLoader
from claimpilot.models import Policy

from api.routes import policies, evaluate, demo, verify


# Policy loader and cache
loader = PolicyPackLoader(strict_version=False)
policies_cache: dict[str, Policy] = {}


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

    # Share loader with routes
    policies.set_loader(loader, policies_cache)
    evaluate.set_loader(loader, policies_cache)
    verify.set_loader(loader, policies_cache)

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


@app.get("/", tags=["Health"])
async def root():
    """API root - health check and info."""
    return {
        "service": "ClaimPilot API",
        "version": "1.0.0",
        "status": "running",
        "policies_loaded": len(policies_cache),
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint."""
    return {
        "healthy": True,
        "policies_loaded": len(policies_cache)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

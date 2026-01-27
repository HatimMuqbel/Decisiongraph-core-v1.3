# External Integrations

**Analysis Date:** 2026-01-27

## APIs & External Services

**None Detected:**

DecisionGraph is a self-contained, zero-dependency library. There are no external API calls, webhooks, or third-party service integrations in the codebase.

## Data Storage

**Databases:**
- None - Not applicable. DecisionGraph uses in-memory data structures exclusively.

**File Storage:**
- Local filesystem only (optional JSON serialization)
  - `Chain.to_json()` method exports chain to JSON string
  - `Chain.from_json()` method imports chain from JSON string
  - No cloud storage integration

**Caching:**
- In-memory indexes only
  - `ScholarIndex` class in `src/decisiongraph/scholar.py` maintains multi-level indexes:
    - `cell_by_id`: Direct cell lookup
    - `by_namespace`: Cells grouped by namespace
    - `by_key`: Cells indexed by (namespace, subject, predicate)
    - `by_ns_subject`: Cells indexed by (namespace, subject)
  - Built on-demand via `build_index_from_chain()` function
  - No persistent cache layer

## Authentication & Identity

**Auth Provider:**
- None - Not applicable. DecisionGraph is a library with no authentication system.

**Authorization:**
- Internal namespace bridge system (cryptographic verification)
  - Namespace isolation via regex patterns (`NAMESPACE_PATTERN`, `ROOT_NAMESPACE_PATTERN`)
  - Bridge rules for cross-namespace access (`src/decisiongraph/namespace.py`)
  - `Scholar.check_visibility()` enforces access control based on bridges
  - No external identity provider

## Monitoring & Observability

**Error Tracking:**
- None - Not integrated with external error tracking services

**Logs:**
- No logging framework integrated
- No log output/analytics
- Errors raised as exceptions (Python built-in) with descriptive messages

## CI/CD & Deployment

**Hosting:**
- Not applicable - This is a library package, not a deployed service

**CI Pipeline:**
- Not detected - No GitHub Actions, Jenkins, CircleCI, or other CI config files found

**Deployment:**
- PyPI package distribution (via setuptools)
- Install via: `pip install decisiongraph`

## Environment Configuration

**Required env vars:**
- None - All configuration via Python function parameters

**Secrets location:**
- Not applicable - No secrets management required

## Webhooks & Callbacks

**Incoming:**
- None - No HTTP endpoints or webhook receivers

**Outgoing:**
- None - No callbacks to external systems

## Graph Serialization Format

**JSON Format Only:**

Cells are serialized to/from JSON via:
- `DecisionCell.to_dict()` - Convert cell to dictionary
- `DecisionCell.from_dict()` - Construct cell from dictionary
- `Chain.to_json(indent=2)` - Export entire chain to JSON string
- `Chain.from_json(json_str)` - Import chain from JSON

Example JSON structure (inferred from code):
```json
{
  "graph_id": "uuid-generated",
  "root_namespace": "corp",
  "cells": [
    {
      "cell_id": "sha256-hash",
      "header": {
        "graph_id": "uuid",
        "cell_type": "genesis",
        "prev_cell_hash": "0000...",
        "system_time": "2026-01-27T16:19:00Z",
        "signer_key_id": null
      },
      "fact": {
        "namespace": "corp",
        "subject": "graph",
        "predicate": "created",
        "object": "genesis",
        "source_quality": "verified",
        "confidence": 1.0,
        "valid_from": null,
        "valid_to": null
      },
      "logic_anchor": {
        "rule_id": "genesis_rule",
        "rule_logic_hash": "sha256-hash"
      },
      "proof": {
        "evidence_cell_ids": []
      }
    }
  ]
}
```

## No External Dependencies

**Dependency Analysis:**

The entire stack relies only on Python standard library. This design choice enables:
- Zero installation overhead
- Maximum portability
- No version conflicts
- Minimal security surface area
- Pure Python execution (no compiled bindings required)

---

*Integration audit: 2026-01-27*

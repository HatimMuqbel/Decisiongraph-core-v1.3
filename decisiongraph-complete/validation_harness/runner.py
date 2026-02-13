"""Single-report validation engine."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from .catalog import get_enabled_checks
from .types import Severity, Violation

# Ensure service and src are importable
ROOT = Path(__file__).parent.parent
if str(ROOT / "service") not in sys.path:
    sys.path.insert(0, str(ROOT / "service"))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# Force v3
os.environ.setdefault("DG_PRECEDENT_VERSION", "v3")

_client = None
_seeds_loaded = False


def _get_client():
    global _client
    if _client is None:
        from fastapi.testclient import TestClient
        from service.main import app
        _client = TestClient(app)
    return _client


def _ensure_seeds():
    global _seeds_loaded
    if not _seeds_loaded:
        from service.main import load_precedent_seeds
        load_precedent_seeds()
        _seeds_loaded = True


def generate_report_context(case: dict) -> dict | None:
    """Run a demo case through the pipeline and return the report context."""
    _ensure_seeds()
    client = _get_client()

    payload = {
        "case_id": case["id"],
        "facts": [{"field": f["field"], "value": f["value"]} for f in case["facts"]],
    }

    resp = client.post("/decide", json=payload)
    if resp.status_code != 200:
        return None

    decision = resp.json()
    decision_id = decision.get("meta", {}).get("decision_id", "")

    json_resp = client.get(f"/report/{decision_id}/json")
    if json_resp.status_code != 200:
        return None

    return json_resp.json().get("report", {})


def validate_single_report(
    case_id: str,
    pre_generated_ctx: dict[str, Any] | None = None,
) -> list[Violation]:
    """Validate a single report, running all enabled checks.

    If pre_generated_ctx is provided, uses it directly.
    Otherwise, generates fresh data via TestClient.
    """
    if pre_generated_ctx is not None:
        ctx = pre_generated_ctx
    else:
        from service.demo_cases import DEMO_CASES
        case = next((c for c in DEMO_CASES if c["id"] == case_id), None)
        if case is None:
            return [Violation(
                check_id="RUNNER",
                severity=Severity.ERROR,
                case_id=case_id,
                message=f"Unknown case_id: {case_id}",
            )]
        ctx = generate_report_context(case)
        if ctx is None:
            return [Violation(
                check_id="RUNNER",
                severity=Severity.ERROR,
                case_id=case_id,
                message=f"Failed to generate report for {case_id}",
            )]

    violations: list[Violation] = []
    for check_def in get_enabled_checks():
        try:
            check_violations = check_def.fn(ctx, case_id)
            violations.extend(check_violations)
        except Exception as exc:
            violations.append(Violation(
                check_id=check_def.id,
                severity=Severity.ERROR,
                case_id=case_id,
                message=f"Check {check_def.id} raised exception: {exc}",
            ))

    return violations

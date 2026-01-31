"""Demo cases endpoints for the interactive banking demo."""

from fastapi import APIRouter, HTTPException
from typing import Optional

from service.demo_cases import get_demo_cases, get_demo_case, get_demo_cases_by_category

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.get("/cases")
async def list_demo_cases(category: Optional[str] = None):
    """
    List pre-built demo cases for the interactive demo.

    Categories:
    - PASS: Cases that should NOT escalate (false positive prevention)
    - ESCALATE: Cases that MUST escalate (true positive detection)
    - EDGE: Boundary condition cases

    Returns summary info only. Use /demo/cases/{id} for full input JSON.
    """
    if category:
        cases = get_demo_cases_by_category(category.upper())
        return [{
            "id": c["id"],
            "name": c["name"],
            "description": c["description"],
            "category": c["category"],
            "expected_verdict": c["expected_verdict"],
            "key_levers": c["key_levers"],
            "tags": c["tags"]
        } for c in cases]

    return get_demo_cases()


@router.get("/cases/{case_id}")
async def get_demo_case_by_id(case_id: str):
    """
    Get a specific demo case by ID with full input JSON.

    The input field contains the complete JSON that can be sent to /decide.
    Users can modify this JSON in the UI before running the decision.
    """
    case = get_demo_case(case_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail=f"Demo case '{case_id}' not found"
        )

    return case

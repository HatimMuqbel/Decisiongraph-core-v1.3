"""Demo cases endpoint."""

from fastapi import APIRouter, HTTPException
from typing import Optional

from api.demo_cases import get_demo_cases, get_demo_case, get_demo_cases_by_line
from api.schemas.responses import DemoCase

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.get("/cases", response_model=list[DemoCase])
async def list_demo_cases(line_of_business: Optional[str] = None):
    """
    List pre-built demo cases.

    Optionally filter by line of business: auto, property, marine, health,
    workers_comp, liability
    """
    if line_of_business:
        cases = get_demo_cases_by_line(line_of_business)
    else:
        cases = get_demo_cases()

    return [DemoCase(**c) for c in cases]


@router.get("/cases/{case_id}", response_model=DemoCase)
async def get_demo_case_by_id(case_id: str):
    """Get a specific demo case by ID."""
    case = get_demo_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Demo case '{case_id}' not found")

    return DemoCase(**case)

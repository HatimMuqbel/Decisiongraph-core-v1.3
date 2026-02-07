"""Report pipeline — single entry point for all report generation.

Every caller — API endpoints, standalone scripts, CLI — uses this one function.
There is exactly ONE rendering path in the codebase.
"""

from .normalize import normalize_decision
from .derive import derive_regulatory_model
from .view_model import build_view_model
from .render_md import render_markdown


def compile_report(decision_pack: dict) -> str:
    """Run the full 4-stage report compiler and return Markdown.

    Stages:
      1. normalize  — canonical field names, defaults, source-label guard
      2. derive     — regulatory model, canonical outcome, defensibility,
                      EDD recommendations, SLA timeline, precedent alignment
      3. view_model — flat dict ready for template rendering
      4. render_md  — Markdown string with all FIX-001 → FIX-012 sections

    Parameters
    ----------
    decision_pack : dict
        Canonical decision pack as produced by ``build_decision_pack()``.

    Returns
    -------
    str
        Rendered Markdown report.
    """
    normalized = normalize_decision(decision_pack)
    derived = derive_regulatory_model(normalized)
    view_model = build_view_model(normalized, derived)
    return render_markdown(view_model)


def compile_report_context(decision_pack: dict) -> dict:
    """Run normalize → derive → view_model and return the view-model dict.

    Used by the API endpoints that need the context dict (HTML, JSON).
    """
    normalized = normalize_decision(decision_pack)
    derived = derive_regulatory_model(normalized)
    return build_view_model(normalized, derived)

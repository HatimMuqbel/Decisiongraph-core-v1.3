"""report — Report Compiler Pipeline package.

Re-exports the public surface that ``main.py`` and other callers rely on
so that ``from service.routers import report`` continues to work unchanged.

Pipeline stages:
  A. normalize  → NormalizedDecision
  B. derive     → DerivedRegulatoryModel
  C. view_model → ReportViewModel
  D. render_*   → HTML / Markdown / JSON
"""

# ── Router (FastAPI) ──────────────────────────────────────────────────────────
from .router import router  # noqa: F401

# ── Module identity constants (used in main.py startup logs) ──────────────────
from .view_model import REPORT_MODULE_VERSION, NARRATIVE_COMPILER_VERSION  # noqa: F401

# ── Store API (used in main.py for caching decisions) ─────────────────────────
from .store import cache_decision, get_cached_decision  # noqa: F401

# ── Pipeline stages (importable for testing / BYOC / advanced use) ────────────
from .normalize import normalize_decision  # noqa: F401
from .derive import derive_regulatory_model  # noqa: F401
from .view_model import build_view_model  # noqa: F401
from .render_md import render_markdown  # noqa: F401

# ── Single compile_report entry point ─────────────────────────────────────────
from .pipeline import compile_report, compile_report_context  # noqa: F401

# ── Backward-compat: build_report_context ─────────────────────────────────────
# Alias kept for callers that used the old name.
build_report_context = compile_report_context

"""
DecisionGraph Report Template Module (v2.0)

Declarative report templates that drive deterministic rendering.

Templates define:
- Section ordering and structure
- Cell type to section mapping
- Label mappings (code → human readable)
- Layout rules (key-value, table, grid, prose)
- Citation formatting

The renderer is generic: given template + manifest + cells → deterministic bytes.

Key principle: Two machines with same inputs produce identical output bytes.

USAGE:
    from decisiongraph.template import (
        ReportTemplate, render_report, create_aml_alert_template
    )

    template = create_aml_alert_template()
    report_bytes = render_report(template, manifest, cells)

    # Verify determinism
    assert render_report(template, manifest, cells) == report_bytes
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
from datetime import datetime
import re

from .cell import DecisionCell, CellType, get_current_timestamp
from .report import ReportManifest


# =============================================================================
# EXCEPTIONS
# =============================================================================

class TemplateError(Exception):
    """Base exception for template errors."""
    pass


class TemplateValidationError(TemplateError):
    """Raised when template validation fails."""
    pass


class RenderError(TemplateError):
    """Raised when rendering fails."""
    pass


# =============================================================================
# ENUMS
# =============================================================================

class SectionLayout(str, Enum):
    """Layout types for report sections."""
    KEY_VALUE = "key_value"      # Label: Value pairs
    TABLE = "table"              # Tabular data with columns
    GRID = "grid"                # Score/rating grid
    PROSE = "prose"              # Free-form text paragraphs
    LIST = "list"                # Bulleted or numbered list
    SIGNALS = "signals"          # Signal-specific formatting
    CITATIONS = "citations"      # Citation-specific formatting
    HEADER = "header"            # Report header


class Alignment(str, Enum):
    """Text alignment for table columns."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

@dataclass
class ColumnDefinition:
    """Definition for a table column."""
    key: str                            # Field key to extract
    header: str                         # Column header text
    width: int = 20                     # Column width in characters
    alignment: Alignment = Alignment.LEFT
    format_fn: Optional[str] = None     # Named format function


@dataclass
class SectionDefinition:
    """
    Definition for a report section.

    Sections are rendered in order. Each section specifies:
    - Which cells to include (by type and/or predicate pattern)
    - How to lay them out
    - Optional transformations
    """
    id: str                             # Section identifier
    title: str                          # Display title (empty for no header)
    layout: SectionLayout               # How to render content
    cell_types: List[CellType] = field(default_factory=list)
    predicate_patterns: List[str] = field(default_factory=list)  # Regex patterns
    columns: List[ColumnDefinition] = field(default_factory=list)  # For TABLE layout
    required: bool = False              # Whether section must have content
    show_empty: bool = False            # Show section even if no matching cells
    subsections: List['SectionDefinition'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Layout-specific config


@dataclass
class CitationFormat:
    """Configuration for citation rendering."""
    style: str = "inline"               # "inline", "footnotes", "endnotes"
    include_cell_id: bool = True        # Include cell ID in citation
    include_timestamp: bool = True      # Include timestamp
    include_confidence: bool = True     # Include confidence level
    truncate_id: int = 16               # Characters to show from cell ID


@dataclass
class ScoreGridFormat:
    """Configuration for score/rating grid rendering."""
    show_component_scores: bool = True
    show_thresholds: bool = True
    score_labels: Dict[str, str] = field(default_factory=dict)  # score_id → label


@dataclass
class ReportTemplate:
    """
    Complete report template definition.

    Templates are declarative and portable. The same template
    produces identical output for identical inputs.
    """
    template_id: str
    template_version: str
    name: str
    description: str = ""
    sections: List[SectionDefinition] = field(default_factory=list)
    label_map: Dict[str, str] = field(default_factory=dict)  # code → label
    citation_format: CitationFormat = field(default_factory=CitationFormat)
    score_grid_format: ScoreGridFormat = field(default_factory=ScoreGridFormat)
    header_fields: List[str] = field(default_factory=list)  # Fields to show in header
    footer_text: str = ""
    line_width: int = 80                # Max line width for wrapping
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_label(self, code: str) -> str:
        """Get human-readable label for a code."""
        return self.label_map.get(code, code.replace("_", " ").title())

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate template structure."""
        errors = []

        if not self.template_id:
            errors.append("template_id is required")
        if not self.template_version:
            errors.append("template_version is required")
        if not self.sections:
            errors.append("At least one section is required")

        section_ids = set()
        for section in self.sections:
            if section.id in section_ids:
                errors.append(f"Duplicate section id: {section.id}")
            section_ids.add(section.id)

            if section.layout == SectionLayout.TABLE and not section.columns:
                errors.append(f"Section {section.id} has TABLE layout but no columns")

        return len(errors) == 0, errors


# =============================================================================
# CELL FILTERING AND SORTING
# =============================================================================

def filter_cells_for_section(
    cells: List[DecisionCell],
    section: SectionDefinition
) -> List[DecisionCell]:
    """
    Filter cells that belong to a section.

    Matching rules:
    1. Cell type must be in section.cell_types (if specified)
    2. Predicate must match at least one pattern (if patterns specified)
    """
    result = []

    for cell in cells:
        # Check cell type
        if section.cell_types and cell.header.cell_type not in section.cell_types:
            continue

        # Check predicate patterns
        if section.predicate_patterns:
            predicate = cell.fact.predicate
            matched = False
            for pattern in section.predicate_patterns:
                if re.match(pattern, predicate):
                    matched = True
                    break
            if not matched:
                continue

        result.append(cell)

    return result


def sort_cells_deterministic(cells: List[DecisionCell]) -> List[DecisionCell]:
    """
    Sort cells in deterministic order.

    Sort order:
    1. By system_time (ascending)
    2. By cell_id (ascending) for ties
    """
    return sorted(cells, key=lambda c: (c.header.system_time, c.cell_id))


# =============================================================================
# VALUE EXTRACTION
# =============================================================================

def extract_value(cell: DecisionCell, key: str, template: ReportTemplate) -> str:
    """
    Extract a value from a cell by key path.

    Supports:
    - "header.cell_type" → cell.header.cell_type
    - "fact.subject" → cell.fact.subject
    - "fact.object.field" → cell.fact.object["field"]
    - "cell_id" → cell.cell_id
    """
    parts = key.split(".")

    if parts[0] == "cell_id":
        return cell.cell_id
    elif parts[0] == "header":
        obj = cell.header
        for part in parts[1:]:
            obj = getattr(obj, part, None)
            if obj is None:
                return ""
        return str(obj.value if hasattr(obj, 'value') else obj)
    elif parts[0] == "fact":
        if len(parts) == 1:
            return ""
        if parts[1] == "object" and len(parts) > 2:
            # Navigate into fact.object dict
            obj = cell.fact.object
            if isinstance(obj, dict):
                for part in parts[2:]:
                    if isinstance(obj, dict):
                        obj = obj.get(part, "")
                    else:
                        return ""
                return template.get_label(str(obj)) if obj else ""
            return ""
        else:
            obj = cell.fact
            for part in parts[1:]:
                obj = getattr(obj, part, None)
                if obj is None:
                    return ""
            return str(obj)

    return ""


# =============================================================================
# LAYOUT RENDERERS
# =============================================================================

def render_header_section(
    section: SectionDefinition,
    cells: List[DecisionCell],
    manifest: ReportManifest,
    template: ReportTemplate
) -> List[str]:
    """Render report header."""
    lines = []
    width = template.line_width

    # Title bar
    lines.append("=" * width)
    lines.append(section.title.center(width))
    lines.append("=" * width)
    lines.append("")

    # Header fields from manifest
    if template.header_fields:
        for field_key in template.header_fields:
            value = getattr(manifest, field_key, "")
            label = template.get_label(field_key)
            lines.append(f"{label}: {value}")
        lines.append("")

    return lines


def render_key_value_section(
    section: SectionDefinition,
    cells: List[DecisionCell],
    template: ReportTemplate
) -> List[str]:
    """Render key-value pairs from cells."""
    lines = []

    # Section header
    if section.title:
        lines.append("-" * template.line_width)
        lines.append(section.title)
        lines.append("-" * template.line_width)

    for cell in cells:
        obj = cell.fact.object
        if isinstance(obj, dict):
            for key, value in sorted(obj.items()):
                if key == "schema_version":
                    continue
                label = template.get_label(key)
                display_value = template.get_label(str(value)) if isinstance(value, str) else str(value)
                lines.append(f"  {label}: {display_value}")
        else:
            lines.append(f"  {cell.fact.predicate}: {obj}")

    if lines and section.title:
        lines.append("")

    return lines


def render_table_section(
    section: SectionDefinition,
    cells: List[DecisionCell],
    template: ReportTemplate
) -> List[str]:
    """Render cells as a table."""
    lines = []

    if not section.columns:
        return lines

    # Section header
    if section.title:
        lines.append("-" * template.line_width)
        lines.append(section.title)
        lines.append("-" * template.line_width)

    # Build header row
    headers = []
    for col in section.columns:
        header = col.header[:col.width].ljust(col.width)
        headers.append(header)
    lines.append(" | ".join(headers))
    lines.append("-" * len(" | ".join(headers)))

    # Build data rows
    for cell in cells:
        row = []
        for col in section.columns:
            value = extract_value(cell, col.key, template)
            # Truncate and pad
            value = str(value)[:col.width]
            if col.alignment == Alignment.RIGHT:
                value = value.rjust(col.width)
            elif col.alignment == Alignment.CENTER:
                value = value.center(col.width)
            else:
                value = value.ljust(col.width)
            row.append(value)
        lines.append(" | ".join(row))

    lines.append("")
    return lines


def render_grid_section(
    section: SectionDefinition,
    cells: List[DecisionCell],
    template: ReportTemplate
) -> List[str]:
    """Render score/rating grid."""
    lines = []

    if section.title:
        lines.append("-" * template.line_width)
        lines.append(section.title)
        lines.append("-" * template.line_width)

    # Find score cells
    score_cells = [c for c in cells if c.header.cell_type == CellType.SCORE]
    verdict_cells = [c for c in cells if c.header.cell_type == CellType.VERDICT]

    # Render scores
    if score_cells:
        lines.append("")
        lines.append("  RISK SCORES")
        lines.append("  " + "-" * 40)
        for cell in score_cells:
            obj = cell.fact.object
            if isinstance(obj, dict):
                score = obj.get("final_score", obj.get("score", "N/A"))
                label = template.get_label(obj.get("score_type", "Score"))
                lines.append(f"  {label}: {score}")
        lines.append("")

    # Render verdict
    if verdict_cells:
        lines.append("  VERDICT")
        lines.append("  " + "-" * 40)
        for cell in verdict_cells:
            obj = cell.fact.object
            if isinstance(obj, dict):
                outcome = template.get_label(obj.get("outcome", "Unknown"))
                confidence = obj.get("confidence", "N/A")
                lines.append(f"  Outcome: {outcome}")
                lines.append(f"  Confidence: {confidence}")
        lines.append("")

    return lines


def render_signals_section(
    section: SectionDefinition,
    cells: List[DecisionCell],
    template: ReportTemplate
) -> List[str]:
    """Render signals with severity indicators."""
    lines = []

    if section.title:
        lines.append("-" * template.line_width)
        lines.append(section.title)
        lines.append("-" * template.line_width)

    # Group by severity
    by_severity: Dict[str, List[DecisionCell]] = {}
    for cell in cells:
        if cell.header.cell_type == CellType.SIGNAL:
            obj = cell.fact.object
            severity = obj.get("severity", "MEDIUM") if isinstance(obj, dict) else "MEDIUM"
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(cell)

    # Render in severity order
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        if severity in by_severity:
            lines.append(f"  [{severity}]")
            for cell in by_severity[severity]:
                obj = cell.fact.object
                code = obj.get("code", "Unknown") if isinstance(obj, dict) else str(obj)
                label = template.get_label(code)
                lines.append(f"    - {label}")
                # Add trigger facts if present
                if isinstance(obj, dict) and obj.get("trigger_facts"):
                    lines.append(f"      Triggers: {len(obj['trigger_facts'])} facts")
            lines.append("")

    return lines


def render_list_section(
    section: SectionDefinition,
    cells: List[DecisionCell],
    template: ReportTemplate
) -> List[str]:
    """Render cells as a bulleted list."""
    lines = []

    if section.title:
        lines.append("-" * template.line_width)
        lines.append(section.title)
        lines.append("-" * template.line_width)

    for cell in cells:
        obj = cell.fact.object
        if isinstance(obj, dict):
            # Try to find a meaningful display value
            display = obj.get("description", obj.get("code", obj.get("action", str(obj))))
            if isinstance(display, str):
                display = template.get_label(display)
            lines.append(f"  * {display}")
        else:
            lines.append(f"  * {obj}")

    if lines and section.title:
        lines.append("")

    return lines


def render_prose_section(
    section: SectionDefinition,
    cells: List[DecisionCell],
    template: ReportTemplate
) -> List[str]:
    """Render cells as prose paragraphs."""
    lines = []

    if section.title:
        lines.append("-" * template.line_width)
        lines.append(section.title)
        lines.append("-" * template.line_width)
        lines.append("")

    for cell in cells:
        obj = cell.fact.object
        if isinstance(obj, dict):
            # Look for text-like fields
            text = obj.get("rationale", obj.get("description", obj.get("summary", "")))
            if text:
                # Word wrap
                words = str(text).split()
                current_line = "  "
                for word in words:
                    if len(current_line) + len(word) + 1 > template.line_width:
                        lines.append(current_line)
                        current_line = "  " + word
                    else:
                        current_line += " " + word if current_line.strip() else "  " + word
                if current_line.strip():
                    lines.append(current_line)
                lines.append("")
        elif isinstance(obj, str):
            lines.append(f"  {obj}")
            lines.append("")

    return lines


def render_citations_section(
    section: SectionDefinition,
    cells: List[DecisionCell],
    template: ReportTemplate,
    all_cells: List[DecisionCell]
) -> List[str]:
    """Render citations/references."""
    lines = []

    if section.title:
        lines.append("-" * template.line_width)
        lines.append(section.title)
        lines.append("-" * template.line_width)

    fmt = template.citation_format

    # Collect all referenced cell IDs
    referenced_ids = set()
    for cell in all_cells:
        obj = cell.fact.object
        if isinstance(obj, dict):
            # Look for reference fields
            for key in ["trigger_facts", "basis_fact_ids", "evidence_refs", "policy_refs", "included_cell_ids"]:
                refs = obj.get(key, [])
                if isinstance(refs, list):
                    referenced_ids.update(refs)

    # Build citation map
    cell_map = {c.cell_id: c for c in all_cells}
    citations = []

    for ref_id in sorted(referenced_ids):
        if ref_id in cell_map:
            cell = cell_map[ref_id]
            citation_parts = []

            if fmt.include_cell_id:
                short_id = ref_id[:fmt.truncate_id]
                citation_parts.append(f"[{short_id}...]")

            citation_parts.append(f"{cell.header.cell_type.value}")
            citation_parts.append(f"{cell.fact.predicate}")

            if fmt.include_timestamp:
                citation_parts.append(f"@ {cell.header.system_time}")

            if fmt.include_confidence:
                citation_parts.append(f"(conf: {cell.fact.confidence})")

            citations.append("  " + " ".join(citation_parts))

    lines.extend(citations)

    if lines and section.title:
        lines.append("")

    return lines


# =============================================================================
# MAIN RENDERER
# =============================================================================

def render_section(
    section: SectionDefinition,
    cells: List[DecisionCell],
    manifest: ReportManifest,
    template: ReportTemplate,
    all_cells: List[DecisionCell]
) -> List[str]:
    """Render a single section."""
    # Filter and sort cells for this section
    section_cells = filter_cells_for_section(cells, section)
    section_cells = sort_cells_deterministic(section_cells)

    # Skip empty sections unless configured to show
    if not section_cells and not section.show_empty and section.layout != SectionLayout.HEADER:
        return []

    # Dispatch to layout renderer
    if section.layout == SectionLayout.HEADER:
        return render_header_section(section, section_cells, manifest, template)
    elif section.layout == SectionLayout.KEY_VALUE:
        return render_key_value_section(section, section_cells, template)
    elif section.layout == SectionLayout.TABLE:
        return render_table_section(section, section_cells, template)
    elif section.layout == SectionLayout.GRID:
        return render_grid_section(section, section_cells, template)
    elif section.layout == SectionLayout.SIGNALS:
        return render_signals_section(section, section_cells, template)
    elif section.layout == SectionLayout.LIST:
        return render_list_section(section, section_cells, template)
    elif section.layout == SectionLayout.PROSE:
        return render_prose_section(section, section_cells, template)
    elif section.layout == SectionLayout.CITATIONS:
        return render_citations_section(section, section_cells, template, all_cells)
    else:
        return []


def render_report(
    template: ReportTemplate,
    manifest: ReportManifest,
    cells: List[DecisionCell]
) -> bytes:
    """
    Render a report to deterministic bytes.

    Args:
        template: Report template defining structure
        manifest: Report manifest with metadata
        cells: All cells included in the report

    Returns:
        UTF-8 encoded report bytes

    Raises:
        RenderError: If rendering fails
        TemplateValidationError: If template is invalid
    """
    # Validate template
    is_valid, errors = template.validate()
    if not is_valid:
        raise TemplateValidationError(f"Invalid template: {', '.join(errors)}")

    # Sort cells deterministically for consistent output
    sorted_cells = sort_cells_deterministic(cells)

    # Render each section
    all_lines: List[str] = []

    for section in template.sections:
        section_lines = render_section(section, sorted_cells, manifest, template, sorted_cells)
        all_lines.extend(section_lines)

    # Add footer
    if template.footer_text:
        all_lines.append("-" * template.line_width)
        all_lines.append(template.footer_text)
        all_lines.append("")

    # Add generation metadata (deterministic)
    all_lines.append("=" * template.line_width)
    all_lines.append(f"Generated: {manifest.rendered_at}")
    all_lines.append(f"Template: {template.template_id} v{template.template_version}")
    all_lines.append(f"Manifest Hash: {manifest.compute_content_hash()[:32]}...")
    all_lines.append("=" * template.line_width)

    # Join with consistent line endings
    text = "\n".join(all_lines) + "\n"

    return text.encode("utf-8")


def render_report_text(
    template: ReportTemplate,
    manifest: ReportManifest,
    cells: List[DecisionCell]
) -> str:
    """
    Render a report to text string.

    Convenience wrapper around render_report.
    """
    return render_report(template, manifest, cells).decode("utf-8")


# =============================================================================
# INTEGRITY SECTION RENDERER
# =============================================================================

def render_integrity_section(
    manifest: ReportManifest,
    cells: List[DecisionCell],
    template: ReportTemplate
) -> List[str]:
    """
    Render integrity audit section.

    Checks:
    - All included cells present
    - Justification coverage
    - Citation completeness
    """
    lines = []
    lines.append("-" * template.line_width)
    lines.append("INTEGRITY AUDIT")
    lines.append("-" * template.line_width)
    lines.append("")

    # Check: All included cells present
    cell_ids = {c.cell_id for c in cells}
    missing = [cid for cid in manifest.included_cell_ids if cid not in cell_ids]

    if missing:
        lines.append("  [FAIL] Cell Inclusion Check")
        lines.append(f"         Missing {len(missing)} cells")
    else:
        lines.append("  [PASS] Cell Inclusion Check")
        lines.append(f"         All {len(manifest.included_cell_ids)} cells present")

    # Check: Justification coverage
    justification_cells = [c for c in cells if c.header.cell_type == CellType.JUSTIFICATION]
    material_cells = [c for c in cells if c.header.cell_type in [
        CellType.SIGNAL, CellType.MITIGATION, CellType.SCORE, CellType.VERDICT
    ]]

    justified_ids = set()
    for j in justification_cells:
        if isinstance(j.fact.object, dict):
            target = j.fact.object.get("target_cell_id")
            if target:
                justified_ids.add(target)

    unjustified = [c for c in material_cells if c.cell_id not in justified_ids]

    if unjustified:
        lines.append("  [WARN] Justification Coverage")
        lines.append(f"         {len(unjustified)} cells without justification")
    else:
        lines.append("  [PASS] Justification Coverage")
        lines.append(f"         All {len(material_cells)} material cells justified")

    # Check: Evidence chain
    evidence_cells = [c for c in cells if c.header.cell_type == CellType.EVIDENCE]
    lines.append(f"  [INFO] Evidence Cells: {len(evidence_cells)}")

    lines.append("")
    return lines


# =============================================================================
# AML ALERT TEMPLATE
# =============================================================================

def create_aml_alert_template() -> ReportTemplate:
    """
    Create the standard AML alert report template.

    This is the first "pack template" - a declarative definition
    that can be serialized and versioned.
    """
    return ReportTemplate(
        template_id="aml_alert",
        template_version="1.0.0",
        name="Transaction Monitoring Alert Report",
        description="Standard AML/BSA transaction monitoring alert report",
        header_fields=["case_id", "pack_id", "pack_version"],
        sections=[
            # Header
            SectionDefinition(
                id="header",
                title="TRANSACTION MONITORING ALERT REPORT",
                layout=SectionLayout.HEADER,
                show_empty=True
            ),

            # Alert Summary (scores and verdict)
            SectionDefinition(
                id="alert_summary",
                title="ALERT SUMMARY",
                layout=SectionLayout.GRID,
                cell_types=[CellType.SCORE, CellType.VERDICT],
                show_empty=False
            ),

            # Customer Profile
            SectionDefinition(
                id="customer_profile",
                title="CUSTOMER PROFILE",
                layout=SectionLayout.KEY_VALUE,
                cell_types=[CellType.FACT],
                predicate_patterns=["customer\\..*", "profile\\..*"],
            ),

            # Transaction Analysis
            SectionDefinition(
                id="transactions",
                title="TRANSACTION ANALYSIS",
                layout=SectionLayout.TABLE,
                cell_types=[CellType.FACT],
                predicate_patterns=["transaction\\..*"],
                columns=[
                    ColumnDefinition(key="fact.object.date", header="Date", width=12),
                    ColumnDefinition(key="fact.object.type", header="Type", width=10),
                    ColumnDefinition(key="fact.object.amount", header="Amount", width=15, alignment=Alignment.RIGHT),
                    ColumnDefinition(key="fact.object.counterparty", header="Counterparty", width=20),
                ]
            ),

            # Risk Indicators (signals)
            SectionDefinition(
                id="risk_indicators",
                title="RISK INDICATORS",
                layout=SectionLayout.SIGNALS,
                cell_types=[CellType.SIGNAL],
            ),

            # Mitigating Factors
            SectionDefinition(
                id="mitigating_factors",
                title="MITIGATING FACTORS",
                layout=SectionLayout.LIST,
                cell_types=[CellType.MITIGATION],
            ),

            # Decision Rationale
            SectionDefinition(
                id="decision_rationale",
                title="DECISION RATIONALE",
                layout=SectionLayout.PROSE,
                cell_types=[CellType.JUSTIFICATION],
            ),

            # Recommendations
            SectionDefinition(
                id="recommendations",
                title="RECOMMENDATIONS",
                layout=SectionLayout.LIST,
                cell_types=[CellType.JUDGMENT],
                predicate_patterns=["recommendation\\..*"],
            ),

            # Citations
            SectionDefinition(
                id="citations",
                title="EVIDENCE CITATIONS",
                layout=SectionLayout.CITATIONS,
            ),
        ],
        label_map={
            # Signal codes
            "HIGH_VALUE_TXN": "High Value Transaction",
            "RAPID_MOVEMENT": "Rapid Movement of Funds",
            "STRUCTURING": "Potential Structuring",
            "UNUSUAL_PATTERN": "Unusual Transaction Pattern",
            "HIGH_RISK_COUNTRY": "High Risk Country",
            "PEP_MATCH": "Politically Exposed Person Match",
            "SANCTIONS_NEAR_MATCH": "Near Sanctions Match",

            # Verdict outcomes
            "APPROVE": "Approved",
            "REVIEW": "Requires Review",
            "ESCALATE": "Escalate to Senior Analyst",
            "SAR": "File SAR",
            "BLOCK": "Block Account",

            # Field labels
            "case_id": "Case ID",
            "pack_id": "Pack",
            "pack_version": "Version",
            "anchor_head_cell_id": "Anchor",
            "final_score": "Final Risk Score",
            "outcome": "Decision Outcome",
            "confidence": "Confidence",

            # Severities
            "CRITICAL": "Critical",
            "HIGH": "High",
            "MEDIUM": "Medium",
            "LOW": "Low",
            "INFO": "Informational",
        },
        citation_format=CitationFormat(
            style="inline",
            include_cell_id=True,
            include_timestamp=True,
            include_confidence=True,
            truncate_id=16
        ),
        footer_text="This report was generated automatically. All decisions are traceable to source evidence.",
        line_width=80
    )


# =============================================================================
# TEMPLATE SERIALIZATION
# =============================================================================

def template_to_dict(template: ReportTemplate) -> Dict[str, Any]:
    """Serialize template to dict for storage/transmission."""
    def section_to_dict(section: SectionDefinition) -> Dict[str, Any]:
        return {
            "id": section.id,
            "title": section.title,
            "layout": section.layout.value,
            "cell_types": [ct.value for ct in section.cell_types],
            "predicate_patterns": section.predicate_patterns,
            "columns": [
                {
                    "key": col.key,
                    "header": col.header,
                    "width": col.width,
                    "alignment": col.alignment.value,
                }
                for col in section.columns
            ],
            "required": section.required,
            "show_empty": section.show_empty,
            "metadata": section.metadata,
        }

    return {
        "template_id": template.template_id,
        "template_version": template.template_version,
        "name": template.name,
        "description": template.description,
        "sections": [section_to_dict(s) for s in template.sections],
        "label_map": template.label_map,
        "citation_format": {
            "style": template.citation_format.style,
            "include_cell_id": template.citation_format.include_cell_id,
            "include_timestamp": template.citation_format.include_timestamp,
            "include_confidence": template.citation_format.include_confidence,
            "truncate_id": template.citation_format.truncate_id,
        },
        "header_fields": template.header_fields,
        "footer_text": template.footer_text,
        "line_width": template.line_width,
        "metadata": template.metadata,
    }


def template_from_dict(data: Dict[str, Any]) -> ReportTemplate:
    """Deserialize template from dict."""
    def section_from_dict(s: Dict[str, Any]) -> SectionDefinition:
        return SectionDefinition(
            id=s["id"],
            title=s["title"],
            layout=SectionLayout(s["layout"]),
            cell_types=[CellType(ct) for ct in s.get("cell_types", [])],
            predicate_patterns=s.get("predicate_patterns", []),
            columns=[
                ColumnDefinition(
                    key=col["key"],
                    header=col["header"],
                    width=col.get("width", 20),
                    alignment=Alignment(col.get("alignment", "left")),
                )
                for col in s.get("columns", [])
            ],
            required=s.get("required", False),
            show_empty=s.get("show_empty", False),
            metadata=s.get("metadata", {}),
        )

    cf_data = data.get("citation_format", {})
    citation_format = CitationFormat(
        style=cf_data.get("style", "inline"),
        include_cell_id=cf_data.get("include_cell_id", True),
        include_timestamp=cf_data.get("include_timestamp", True),
        include_confidence=cf_data.get("include_confidence", True),
        truncate_id=cf_data.get("truncate_id", 16),
    )

    return ReportTemplate(
        template_id=data["template_id"],
        template_version=data["template_version"],
        name=data.get("name", ""),
        description=data.get("description", ""),
        sections=[section_from_dict(s) for s in data.get("sections", [])],
        label_map=data.get("label_map", {}),
        citation_format=citation_format,
        header_fields=data.get("header_fields", []),
        footer_text=data.get("footer_text", ""),
        line_width=data.get("line_width", 80),
        metadata=data.get("metadata", {}),
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'TemplateError',
    'TemplateValidationError',
    'RenderError',
    # Enums
    'SectionLayout',
    'Alignment',
    # Schema
    'ColumnDefinition',
    'SectionDefinition',
    'CitationFormat',
    'ScoreGridFormat',
    'ReportTemplate',
    # Filtering
    'filter_cells_for_section',
    'sort_cells_deterministic',
    # Rendering
    'render_report',
    'render_report_text',
    'render_section',
    'render_integrity_section',
    # Templates
    'create_aml_alert_template',
    # Serialization
    'template_to_dict',
    'template_from_dict',
]

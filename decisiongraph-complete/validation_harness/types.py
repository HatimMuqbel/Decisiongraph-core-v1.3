"""Core data types for the validation harness."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class CheckCategory(Enum):
    M = "Math"
    C = "Consistency"
    O = "Operational"
    R = "Regulatory"
    N = "Narrative"
    E = "Evidence"


@dataclass
class FixSuggestion:
    file: str
    function: str
    line_range: str
    before_snippet: str
    after_snippet: str
    root_cause_id: str
    explanation: str


@dataclass
class Violation:
    check_id: str
    severity: Severity
    case_id: str
    message: str
    current_value: object = None
    expected_value: object = None
    fix_suggestion: FixSuggestion | None = None


@dataclass
class CheckResult:
    check_id: str
    violations: list[Violation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0


@dataclass
class CheckDefinition:
    id: str
    category: CheckCategory
    severity: Severity
    description: str
    fn: object  # callable(ctx, case_id) -> list[Violation]


@dataclass
class RootCause:
    root_cause_id: str
    file: str
    function: str
    violation_count: int
    affected_cases: list[str]
    explanation: str
    fix_suggestion: FixSuggestion | None = None


@dataclass
class ValidationReport:
    cases_validated: int
    checks_run: int
    matrix: dict[str, dict[str, str]] = field(default_factory=dict)
    violations: list[Violation] = field(default_factory=list)
    root_causes: list[RootCause] = field(default_factory=list)
    exceptions_applied: list[tuple[str, str, str]] = field(default_factory=list)

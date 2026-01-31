"""
Contract assertion helpers for claim recommendations.

Provides a single source of truth for "what good looks like"
across all lines of business.
"""
from typing import TYPE_CHECKING

from claimpilot.models import RecommendationRecord

if TYPE_CHECKING:
    from .contract import Expected


# =============================================================================
# Core Assertions
# =============================================================================

def assert_disposition(rec: RecommendationRecord, expected: "Expected"):
    """Assert recommendation has expected disposition."""
    actual = rec.recommended_disposition.value.upper()
    expected_disp = expected.disposition.upper()
    assert actual == expected_disp, (
        f"Expected disposition {expected_disp}, got {actual}"
    )


def assert_exclusions(rec: RecommendationRecord, expected: "Expected"):
    """Assert correct exclusions apply/don't apply."""
    applied = set(rec.exclusions_triggered)

    # Check must-apply exclusions
    for ex_id in expected.must_apply_exclusions:
        assert ex_id in applied, (
            f"Expected exclusion '{ex_id}' to apply, "
            f"but only got: {applied or '(none)'}"
        )

    # Check must-not-apply exclusions (negative assertions)
    for ex_id in expected.must_not_apply_exclusions:
        assert ex_id not in applied, (
            f"Expected exclusion '{ex_id}' NOT to apply, "
            f"but it was in: {applied}"
        )


def assert_coverages(rec: RecommendationRecord, expected: "Expected"):
    """Assert correct coverages are triggered."""
    triggered = set(rec.coverages_evaluated)

    for cov_id in expected.must_trigger_coverages:
        assert cov_id in triggered, (
            f"Expected coverage '{cov_id}' to trigger, "
            f"but only got: {triggered or '(none)'}"
        )


def assert_reasoning(rec: RecommendationRecord, expected: "Expected"):
    """Assert recommendation has sufficient reasoning."""
    step_count = len(rec.reasoning_steps)
    assert step_count >= expected.min_reasoning_steps, (
        f"Expected at least {expected.min_reasoning_steps} reasoning steps, "
        f"got {step_count}"
    )

    # Each step should have required fields
    for step in rec.reasoning_steps:
        assert step.id, "Reasoning step missing ID"
        assert step.sequence > 0, "Reasoning step missing sequence"
        assert step.step_type is not None, "Reasoning step missing type"
        assert step.description, "Reasoning step missing description"


def assert_provenance(rec: RecommendationRecord):
    """Assert recommendation has valid provenance."""
    assert rec.policy_pack_id, "Missing policy_pack_id"
    assert rec.policy_pack_version, "Missing policy_pack_version"
    assert rec.policy_pack_hash, "Missing policy_pack_hash"
    assert len(rec.policy_pack_hash) == 64, (
        f"policy_pack_hash should be 64 hex chars (SHA-256), "
        f"got {len(rec.policy_pack_hash)}"
    )
    assert rec.evaluated_at is not None, "Missing evaluated_at"
    assert rec.engine_version is not None, "Missing engine_version"


def assert_citations(rec: RecommendationRecord, expected: "Expected"):
    """Assert required authority sections are cited."""
    if not expected.must_cite_sections:
        return

    cited_sections = set()
    for auth in rec.authorities_cited:
        if auth.section:
            cited_sections.add(auth.section)

    for section in expected.must_cite_sections:
        found = any(section in s for s in cited_sections)
        assert found, (
            f"Expected section '{section}' to be cited, "
            f"but only found: {cited_sections or '(none)'}"
        )


def assert_certainty(rec: RecommendationRecord, expected: "Expected"):
    """Assert recommendation has expected certainty level."""
    if expected.certainty is None:
        return

    actual = rec.certainty.value.lower()
    expected_cert = expected.certainty.lower()
    assert actual == expected_cert, (
        f"Expected certainty {expected_cert}, got {actual}"
    )


# =============================================================================
# Combined Contract Assertion
# =============================================================================

def assert_contract(rec: RecommendationRecord, expected: "Expected"):
    """
    Assert recommendation meets all expected contract requirements.

    This is the main assertion helper - use this in parametrized tests.
    """
    assert_disposition(rec, expected)
    assert_reasoning(rec, expected)

    if expected.require_provenance:
        assert_provenance(rec)

    assert_exclusions(rec, expected)
    assert_coverages(rec, expected)
    assert_citations(rec, expected)
    assert_certainty(rec, expected)


# =============================================================================
# Specialized Assertions
# =============================================================================

def assert_denied_by_exclusion(
    rec: RecommendationRecord,
    exclusion_id: str,
    *,
    must_not_apply: set[str] = None,
):
    """
    Assert recommendation is DENY due to specific exclusion.

    Convenience method for common denial scenario assertions.
    """
    assert rec.recommended_disposition.value == "deny", (
        f"Expected DENY, got {rec.recommended_disposition.value}"
    )
    assert exclusion_id in rec.exclusions_triggered, (
        f"Expected exclusion '{exclusion_id}' to trigger, "
        f"got: {rec.exclusions_triggered}"
    )

    if must_not_apply:
        for ex_id in must_not_apply:
            assert ex_id not in rec.exclusions_triggered, (
                f"Expected exclusion '{ex_id}' NOT to apply"
            )


def assert_approved_clean(
    rec: RecommendationRecord,
    *,
    coverage_id: str = None,
    must_not_apply: set[str] = None,
):
    """
    Assert recommendation is PAY with no exclusions.

    Convenience method for clean approval scenario assertions.
    """
    assert rec.recommended_disposition.value == "pay", (
        f"Expected PAY, got {rec.recommended_disposition.value}"
    )
    assert len(rec.exclusions_triggered) == 0, (
        f"Expected no exclusions, got: {rec.exclusions_triggered}"
    )

    if coverage_id:
        assert coverage_id in rec.coverages_evaluated, (
            f"Expected coverage '{coverage_id}' to be evaluated"
        )

    if must_not_apply:
        for ex_id in must_not_apply:
            assert ex_id not in rec.exclusions_triggered


def assert_has_authority_citation(rec: RecommendationRecord):
    """
    Assert at least one authority is cited.

    Should be true for any denial or exclusion-based recommendation.
    """
    has_exclusions = len(rec.exclusions_triggered) > 0
    has_citations = len(rec.authorities_cited) > 0

    if has_exclusions:
        assert has_citations, (
            f"Exclusions triggered ({rec.exclusions_triggered}) "
            "but no authorities cited"
        )

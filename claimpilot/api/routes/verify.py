"""Verification and validation endpoints."""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from api.schemas.responses import (
    VerifyRequest, VerifyResponse,
    ValidatePoliciesResponse, PolicyValidationResult, ValidationError
)
from claimpilot.packs.loader import PolicyPackLoader
from claimpilot.packs.schema import validate_policy_pack
from claimpilot.canon import compute_policy_pack_hash
from claimpilot.models import Policy
import yaml
from pydantic import ValidationError as PydanticValidationError

router = APIRouter(tags=["Verification"])

# Shared loader instance
loader: PolicyPackLoader = None
policies_cache: dict[str, Policy] = {}


def set_loader(l: PolicyPackLoader, cache: dict[str, Policy]):
    global loader, policies_cache
    loader = l
    policies_cache = cache


@router.post("/verify", response_model=VerifyResponse)
async def verify_recommendation(request: VerifyRequest):
    """
    Verify a recommendation's provenance.

    Checks that:
    - The policy pack exists and matches the claimed hash
    - The exclusions are valid for that policy
    - The recommendation is consistent with the rules

    This answers: "Was this recommendation made with the rules claimed?"
    """
    checks_performed = []
    mismatches = []

    # Check 1: Policy pack exists
    checks_performed.append("policy_pack_exists")
    policy = policies_cache.get(request.policy_pack_id)
    if not policy:
        return VerifyResponse(
            valid=False,
            reason=f"Policy pack '{request.policy_pack_id}' not found",
            checks_performed=checks_performed,
            mismatches=[f"Unknown policy: {request.policy_pack_id}"]
        )

    # Check 2: Version matches
    checks_performed.append("version_match")
    if policy.version != request.policy_pack_version:
        mismatches.append(
            f"Version mismatch: claimed {request.policy_pack_version}, "
            f"current {policy.version}"
        )

    # Check 3: Hash matches (critical)
    checks_performed.append("hash_match")
    current_hash = compute_policy_pack_hash(policy)
    if current_hash != request.policy_pack_hash:
        mismatches.append(
            f"Hash mismatch: claimed {request.policy_pack_hash[:16]}..., "
            f"current {current_hash[:16]}..."
        )

    # Check 4: Exclusions exist in policy
    checks_performed.append("exclusions_valid")
    policy_exclusion_codes = {e.code for e in policy.exclusions}
    for exc_code in request.exclusions_triggered:
        if exc_code not in policy_exclusion_codes:
            mismatches.append(f"Unknown exclusion code: {exc_code}")

    # Check 5: Disposition is valid
    checks_performed.append("disposition_valid")
    valid_dispositions = ["pay", "deny", "partial", "escalate", "request_info", "hold", "refer_siu"]
    if request.recommended_disposition not in valid_dispositions:
        mismatches.append(f"Invalid disposition: {request.recommended_disposition}")

    # Determine validity
    if mismatches:
        # Hash mismatch is critical
        if any("Hash mismatch" in m for m in mismatches):
            reason = "Policy pack has changed since recommendation was made"
        else:
            reason = f"Verification failed: {len(mismatches)} issue(s) found"
        return VerifyResponse(
            valid=False,
            reason=reason,
            checks_performed=checks_performed,
            mismatches=mismatches
        )

    return VerifyResponse(
        valid=True,
        reason="Recommendation provenance verified successfully",
        checks_performed=checks_performed,
        mismatches=[]
    )


@router.get("/validate/policies", response_model=ValidatePoliciesResponse)
async def validate_policies():
    """
    Validate all policy pack YAML files.

    Returns validation status for each pack, including detailed errors
    for any that fail schema validation.

    Use this to catch YAML errors early when editing policy packs.
    """
    packs_dir = Path(__file__).parent.parent.parent / "packs"

    valid_policies = []
    invalid_policies = []

    for yaml_file in packs_dir.rglob("*.yaml"):
        # Skip example files
        if "example" in str(yaml_file).lower():
            continue

        relative_path = str(yaml_file.relative_to(packs_dir))

        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            # Validate against schema
            schema = validate_policy_pack(data)
            policy_id = schema.id

            valid_policies.append(policy_id)

        except PydanticValidationError as e:
            errors = []
            for error in e.errors():
                loc = " -> ".join(str(x) for x in error["loc"])
                errors.append(ValidationError(
                    location=loc,
                    message=error["msg"],
                    error_type=error["type"]
                ))

            invalid_policies.append(PolicyValidationResult(
                file=relative_path,
                policy_id=data.get("id") if isinstance(data, dict) else None,
                valid=False,
                errors=errors
            ))

        except yaml.YAMLError as e:
            invalid_policies.append(PolicyValidationResult(
                file=relative_path,
                valid=False,
                errors=[ValidationError(
                    location="file",
                    message=f"YAML parse error: {str(e)[:200]}",
                    error_type="yaml_error"
                )]
            ))

        except Exception as e:
            invalid_policies.append(PolicyValidationResult(
                file=relative_path,
                valid=False,
                errors=[ValidationError(
                    location="unknown",
                    message=str(e)[:200],
                    error_type="unknown_error"
                )]
            ))

    return ValidatePoliciesResponse(
        total_files=len(valid_policies) + len(invalid_policies),
        valid_count=len(valid_policies),
        invalid_count=len(invalid_policies),
        valid_policies=valid_policies,
        invalid_policies=invalid_policies
    )

#!/usr/bin/env python3
"""
Policy Pack Validator

Validates all policy packs and reports detailed errors.
Run: python -m api.validate_packs
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from claimpilot.packs.loader import PolicyPackLoader
from claimpilot.exceptions import PolicyValidationError, PolicyLoadError
from pydantic import ValidationError


def validate_all_packs():
    """Validate all policy packs and report errors."""
    packs_dir = Path(__file__).parent.parent / "packs"

    policy_files = [
        "auto/ontario_oap1.yaml",
        "property/homeowners_ho3.yaml",
        "marine/pleasure_craft.yaml",
        "health/group_health.yaml",
        "workers_comp/ontario_wsib.yaml",
        "liability/cgl.yaml",
        "liability/professional_eo.yaml",
        "travel/travel_medical.yaml",
    ]

    loader = PolicyPackLoader(strict_version=False)

    valid = []
    invalid = []

    for policy_file in policy_files:
        path = packs_dir / policy_file
        print(f"\n{'='*60}")
        print(f"Validating: {policy_file}")
        print('='*60)

        if not path.exists():
            print(f"  [SKIP] File not found")
            invalid.append({"file": policy_file, "error": "File not found"})
            continue

        try:
            policy = loader.load(str(path))
            print(f"  [OK] Loaded successfully: {policy.id}")
            valid.append({"file": policy_file, "id": policy.id})

        except PolicyValidationError as e:
            print(f"  [ERROR] Validation failed")
            print(f"\n  Message: {e.message}")

            if e.details and "errors" in e.details:
                errors = e.details["errors"]
                if isinstance(errors, list):
                    print(f"\n  Errors ({len(errors)} total):")
                    for i, err in enumerate(errors[:20], 1):  # Show first 20
                        loc = " -> ".join(str(x) for x in err.get("loc", []))
                        msg = err.get("msg", "Unknown")
                        err_type = err.get("type", "")
                        print(f"\n    {i}. Location: {loc}")
                        print(f"       Message: {msg}")
                        print(f"       Type: {err_type}")

                    if len(errors) > 20:
                        print(f"\n    ... and {len(errors) - 20} more errors")
                else:
                    print(f"\n  Error details: {errors}")

            invalid.append({
                "file": policy_file,
                "error": str(e.message),
                "error_count": len(e.details.get("errors", [])) if e.details else 0
            })

        except PolicyLoadError as e:
            print(f"  [ERROR] Load failed: {e.message}")
            invalid.append({"file": policy_file, "error": str(e.message)})

        except Exception as e:
            print(f"  [ERROR] Unexpected: {type(e).__name__}: {e}")
            invalid.append({"file": policy_file, "error": str(e)})

    # Summary
    print(f"\n\n{'='*60}")
    print("VALIDATION SUMMARY")
    print('='*60)
    print(f"\nValid packs:   {len(valid)}")
    print(f"Invalid packs: {len(invalid)}")

    if valid:
        print(f"\nValid:")
        for v in valid:
            print(f"  - {v['file']} ({v['id']})")

    if invalid:
        print(f"\nInvalid:")
        for inv in invalid:
            print(f"  - {inv['file']}: {inv.get('error_count', 'N/A')} errors")

    return len(invalid) == 0


if __name__ == "__main__":
    success = validate_all_packs()
    sys.exit(0 if success else 1)

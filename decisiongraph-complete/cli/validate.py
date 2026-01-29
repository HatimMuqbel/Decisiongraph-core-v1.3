#!/usr/bin/env python3
"""
DecisionGraph CLI: Validate Tool

Validate input cases and output reports against JSON schemas.
Used for schema compliance testing and integration validation.

Usage:
    python -m cli.validate --input case.json
    python -m cli.validate --output report.json
    python -m cli.validate --corpus test_corpus/cases/
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import validate, ValidationError, Draft202012Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def load_schema(schema_path: Path) -> dict:
    """Load JSON schema from file."""
    with open(schema_path) as f:
        return json.load(f)


def load_json(file_path: Path) -> dict:
    """Load JSON file."""
    with open(file_path) as f:
        return json.load(f)


def validate_against_schema(data: dict, schema: dict) -> tuple:
    """
    Validate data against schema.
    Returns (valid, errors).
    """
    if not HAS_JSONSCHEMA:
        return True, ["jsonschema not installed - validation skipped"]

    try:
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(data))
        if errors:
            error_messages = []
            for error in errors[:10]:  # First 10 errors
                path = " -> ".join(str(p) for p in error.absolute_path)
                error_messages.append(f"{path}: {error.message}")
            return False, error_messages
        return True, []
    except Exception as e:
        return False, [str(e)]


def validate_input(file_path: Path, schemas_dir: Path) -> tuple:
    """Validate input case against input schema."""
    schema = load_schema(schemas_dir / "input.case.schema.json")
    data = load_json(file_path)
    return validate_against_schema(data, schema)


def validate_output(file_path: Path, schemas_dir: Path) -> tuple:
    """Validate output report against output schema."""
    schema = load_schema(schemas_dir / "output.report.schema.json")
    data = load_json(file_path)
    return validate_against_schema(data, schema)


def validate_corpus(corpus_dir: Path, schemas_dir: Path, is_input: bool = True) -> dict:
    """Validate all files in corpus directory."""
    schema_file = "input.case.schema.json" if is_input else "output.report.schema.json"
    schema = load_schema(schemas_dir / schema_file)

    results = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "errors": {},
    }

    for json_file in sorted(corpus_dir.glob("*.json")):
        results["total"] += 1
        data = load_json(json_file)
        valid, errors = validate_against_schema(data, schema)

        if valid:
            results["valid"] += 1
        else:
            results["invalid"] += 1
            results["errors"][json_file.name] = errors

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Validate cases and reports against JSON schemas"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input case JSON file to validate"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output report JSON file to validate"
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        help="Directory of JSON files to validate"
    )
    parser.add_argument(
        "--corpus-type",
        choices=["input", "output"],
        default="input",
        help="Type of corpus files (default: input)"
    )
    parser.add_argument(
        "--schemas-dir",
        type=Path,
        default=Path(__file__).parent.parent / "schemas",
        help="Directory containing schemas"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    if not HAS_JSONSCHEMA:
        print("WARNING: jsonschema not installed. Install with: pip install jsonschema")
        print("Validation will be skipped.")

    exit_code = 0

    if args.input:
        print(f"Validating input: {args.input}")
        valid, errors = validate_input(args.input, args.schemas_dir)
        if valid:
            print("  VALID")
        else:
            print("  INVALID")
            for error in errors:
                print(f"    - {error}")
            exit_code = 1

    if args.output:
        print(f"Validating output: {args.output}")
        valid, errors = validate_output(args.output, args.schemas_dir)
        if valid:
            print("  VALID")
        else:
            print("  INVALID")
            for error in errors:
                print(f"    - {error}")
            exit_code = 1

    if args.corpus:
        is_input = args.corpus_type == "input"
        print(f"Validating corpus: {args.corpus} (type: {args.corpus_type})")
        results = validate_corpus(args.corpus, args.schemas_dir, is_input)

        print(f"\nResults: {results['valid']}/{results['total']} valid")

        if results["invalid"] > 0:
            print(f"\nInvalid files ({results['invalid']}):")
            for filename, errors in results["errors"].items():
                print(f"  {filename}:")
                for error in errors[:3]:  # First 3 errors per file
                    print(f"    - {error}")
            exit_code = 1

    if not (args.input or args.output or args.corpus):
        parser.print_help()
        return 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

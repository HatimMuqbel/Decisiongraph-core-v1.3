"""YAML exception loader for known acceptable deviations."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def load_exceptions(path: str | Path) -> list[dict[str, Any]]:
    """Load exception entries from a YAML file.

    Each entry: {case_id: str, check_id: str, reason: str}
    Supports wildcard '*' for case_id or check_id.
    """
    path = Path(path)
    if not path.exists():
        return []

    try:
        import yaml
    except ImportError:
        # Fall back to a simple parser if PyYAML is not available
        return _parse_simple_yaml(path)

    with open(path) as f:
        data = yaml.safe_load(f)

    if not data or not isinstance(data, dict):
        return []

    return data.get("exceptions", [])


def _parse_simple_yaml(path: Path) -> list[dict[str, Any]]:
    """Minimal YAML parser for the exceptions file (no PyYAML dependency)."""
    exceptions = []
    current: dict[str, str] = {}
    in_exceptions = False

    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped == "exceptions:":
            in_exceptions = True
            continue
        if not in_exceptions:
            continue
        if stripped.startswith("- "):
            if current:
                exceptions.append(current)
            current = {}
            # Parse "- key: value"
            rest = stripped[2:]
            if ":" in rest:
                k, v = rest.split(":", 1)
                current[k.strip()] = v.strip().strip('"').strip("'")
        elif stripped and ":" in stripped:
            k, v = stripped.split(":", 1)
            current[k.strip()] = v.strip().strip('"').strip("'")

    if current:
        exceptions.append(current)

    return exceptions


def is_excepted(
    case_id: str,
    check_id: str,
    exceptions: list[dict[str, Any]],
) -> str | None:
    """Return the reason string if (case_id, check_id) is excepted, else None.

    Supports wildcard '*' matching on case_id or check_id.
    """
    for exc in exceptions:
        exc_case = exc.get("case_id", "")
        exc_check = exc.get("check_id", "")
        case_match = exc_case == "*" or exc_case == case_id
        check_match = exc_check == "*" or exc_check == check_id
        if case_match and check_match:
            return exc.get("reason", "excepted")
    return None

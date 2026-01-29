"""
Case Mapper - Pure Transformation Layer

Maps vendor-specific case exports to canonical CaseBundle format using
declarative YAML adapters. No business logic, no rules, no scoring.

One question only: "How do I turn your export into our CaseBundle?"

Usage:
    from decisiongraph.case_mapper import CaseMapper, load_adapter

    adapter = load_adapter("adapters/fincrime/actimize/mapping.yaml")
    mapper = CaseMapper(adapter)
    bundle = mapper.map(input_data)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


# ============================================================================
# EXCEPTIONS
# ============================================================================

class AdapterError(Exception):
    """Base exception for adapter errors."""
    pass


class AdapterValidationError(AdapterError):
    """Adapter YAML is invalid."""
    pass


class MappingError(AdapterError):
    """Mapping failed during transformation."""
    pass


class RequiredFieldError(MappingError):
    """Required field is missing from source."""
    pass


# ============================================================================
# JSONPATH IMPLEMENTATION (minimal, no dependencies)
# ============================================================================

def jsonpath_extract(data: Any, path: str) -> Any:
    """
    Extract value from data using JSONPath expression.

    Supports:
        $.field           - Root-level field
        $.parent.child    - Nested field
        $[*]              - All array elements (returns list)
        $.array[0]        - Array index
        $.array[*].field  - Field from all array elements

    Returns None if path doesn't match.
    """
    if not path or not path.startswith("$"):
        return None

    # Remove leading $
    path = path[1:]
    if not path:
        return data

    # Remove leading dot if present
    if path.startswith("."):
        path = path[1:]

    current = data
    tokens = _tokenize_path(path)

    for token in tokens:
        if current is None:
            return None

        if token == "*":
            # Wildcard - current must be list
            if not isinstance(current, list):
                return None
            # Return list as-is for further processing
            continue

        if token.startswith("[") and token.endswith("]"):
            # Array access
            inner = token[1:-1]
            if inner == "*":
                # Wildcard array access
                if not isinstance(current, list):
                    return None
                continue
            else:
                # Numeric index
                try:
                    idx = int(inner)
                    if isinstance(current, list) and 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
                except ValueError:
                    return None
        else:
            # Field access
            if isinstance(current, list):
                # Extract field from all list items
                current = [
                    item.get(token) if isinstance(item, dict) else None
                    for item in current
                ]
                # Filter out None values
                current = [v for v in current if v is not None]
                if not current:
                    return None
            elif isinstance(current, dict):
                current = current.get(token)
            else:
                return None

    return current


def _tokenize_path(path: str) -> list:
    """Tokenize JSONPath into components."""
    tokens = []
    current = ""
    i = 0

    while i < len(path):
        char = path[i]

        if char == ".":
            if current:
                tokens.append(current)
                current = ""
        elif char == "[":
            if current:
                tokens.append(current)
                current = ""
            # Find closing bracket
            j = i + 1
            while j < len(path) and path[j] != "]":
                j += 1
            tokens.append(path[i:j+1])
            i = j
        else:
            current += char

        i += 1

    if current:
        tokens.append(current)

    return tokens


# ============================================================================
# ADAPTER DATA STRUCTURES
# ============================================================================

@dataclass
class AdapterMetadata:
    """Adapter identification and metadata."""
    name: str
    vendor: str
    version: str
    input_format: str
    description: str = ""


@dataclass
class Adapter:
    """Complete adapter definition."""
    metadata: AdapterMetadata
    roots: dict[str, str]
    mappings: dict[str, str]
    transforms: dict[str, dict[str, str]] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# ADAPTER LOADING AND VALIDATION
# ============================================================================

def load_adapter(path: str | Path) -> Adapter:
    """
    Load and validate an adapter from YAML file.

    Args:
        path: Path to adapter YAML file

    Returns:
        Validated Adapter instance

    Raises:
        AdapterError: If file not found
        AdapterValidationError: If adapter is invalid
    """
    path = Path(path)

    if not path.exists():
        raise AdapterError(f"Adapter file not found: {path}")

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise AdapterValidationError(f"Invalid YAML: {e}")

    if not isinstance(data, dict):
        raise AdapterValidationError("Adapter must be a YAML dictionary")

    return _validate_adapter(data)


def _validate_adapter(data: dict) -> Adapter:
    """Validate adapter structure and return Adapter instance."""

    # Validate adapter metadata
    if "adapter" not in data:
        raise AdapterValidationError("Missing 'adapter' section")

    adapter_meta = data["adapter"]
    required_meta = ["name", "vendor", "version", "input_format"]
    for field in required_meta:
        if field not in adapter_meta:
            raise AdapterValidationError(f"Missing adapter.{field}")

    metadata = AdapterMetadata(
        name=adapter_meta["name"],
        vendor=adapter_meta["vendor"],
        version=adapter_meta["version"],
        input_format=adapter_meta["input_format"],
        description=adapter_meta.get("description", ""),
    )

    # Validate roots
    if "roots" not in data:
        raise AdapterValidationError("Missing 'roots' section")

    roots = data["roots"]
    if "case" not in roots:
        raise AdapterValidationError("Missing roots.case")

    # Validate JSONPath syntax in roots
    for name, path in roots.items():
        if not path.startswith("$"):
            raise AdapterValidationError(
                f"Invalid JSONPath in roots.{name}: must start with $"
            )

    # Validate mappings
    if "mappings" not in data:
        raise AdapterValidationError("Missing 'mappings' section")

    mappings = data["mappings"]

    # Check required CaseMeta mappings
    required_case_meta = [
        "CaseMeta.case_id",
        "CaseMeta.case_type",
        "CaseMeta.jurisdiction",
        "CaseMeta.primary_entity_id",
    ]

    for field in required_case_meta:
        if field not in mappings:
            raise AdapterValidationError(f"Missing required mapping: {field}")

    # Validate mapping paths
    for target, source in mappings.items():
        if not source.startswith("$") and not source.startswith("!literal"):
            raise AdapterValidationError(
                f"Invalid mapping {target}: source must be JSONPath ($) or literal (!literal)"
            )

    # Validate transforms (optional)
    transforms = data.get("transforms", {})
    for transform_name, transform_map in transforms.items():
        if not isinstance(transform_map, dict):
            raise AdapterValidationError(
                f"Transform '{transform_name}' must be a dictionary"
            )

    # Validate defaults (optional)
    defaults = data.get("defaults", {})

    return Adapter(
        metadata=metadata,
        roots=roots,
        mappings=mappings,
        transforms=transforms,
        defaults=defaults,
    )


# ============================================================================
# CASE MAPPER
# ============================================================================

class CaseMapper:
    """
    Maps vendor exports to CaseBundle format using an adapter.

    Pure transformation - no business logic.
    """

    def __init__(self, adapter: Adapter):
        """
        Initialize mapper with an adapter.

        Args:
            adapter: Validated Adapter instance
        """
        self.adapter = adapter

    def map(self, input_data: dict) -> dict:
        """
        Map input data to CaseBundle format.

        Args:
            input_data: Vendor export data (parsed JSON/dict)

        Returns:
            CaseBundle-compatible dictionary

        Raises:
            MappingError: If mapping fails
            RequiredFieldError: If required field is missing
        """
        bundle = {
            "meta": {},
            "individuals": [],
            "organizations": [],
            "accounts": [],
            "relationships": [],
            "evidence": [],
            "events": [],
            "assertions": [],
        }

        # Map CaseMeta
        bundle["meta"] = self._map_case_meta(input_data)

        # Get primary entity for relationship generation
        primary_entity_id = bundle["meta"].get("primary_entity_id")
        primary_entity_type = bundle["meta"].get("primary_entity_type", "individual")

        # Map entities
        if "customers" in self.adapter.roots:
            customers = self._extract_root(input_data, "customers")
            if customers:
                bundle["individuals"] = self._map_individuals(customers)

        # Map accounts
        if "accounts" in self.adapter.roots:
            accounts = self._extract_root(input_data, "accounts")
            if accounts:
                bundle["accounts"] = self._map_accounts(accounts)
                # Generate account holder relationships
                if primary_entity_id:
                    bundle["relationships"] = self._generate_account_relationships(
                        primary_entity_id, primary_entity_type, bundle["accounts"]
                    )

        # Map events
        events = []

        if "transactions" in self.adapter.roots:
            transactions = self._extract_root(input_data, "transactions")
            if transactions:
                events.extend(self._map_transactions(transactions))

        if "alerts" in self.adapter.roots:
            alerts = self._extract_root(input_data, "alerts")
            if alerts:
                events.extend(self._map_alerts(alerts))

        if "screenings" in self.adapter.roots:
            screenings = self._extract_root(input_data, "screenings")
            if screenings:
                events.extend(self._map_screenings(screenings))

        bundle["events"] = events

        return bundle

    def _extract_root(self, data: dict, root_name: str) -> Optional[list]:
        """Extract data from a root path."""
        if root_name not in self.adapter.roots:
            return None

        path = self.adapter.roots[root_name]
        result = jsonpath_extract(data, path)

        if result is None:
            return None

        # Ensure result is a list
        if not isinstance(result, list):
            result = [result]

        return result

    def _map_case_meta(self, data: dict) -> dict:
        """Map CaseMeta fields."""
        meta = {}

        for target, source in self.adapter.mappings.items():
            if not target.startswith("CaseMeta."):
                continue

            field_name = target.replace("CaseMeta.", "")
            value = self._extract_value(data, source)

            if value is not None:
                # Apply transforms
                value = self._apply_transform(field_name, value)
                # Normalize to lowercase for enums
                if field_name in ("case_type", "case_phase", "status", "priority", "sensitivity"):
                    value = str(value).lower()
                meta[self._to_bundle_field(field_name)] = value

        # Apply defaults
        for default_key, default_value in self.adapter.defaults.items():
            if default_key.startswith("CaseMeta."):
                field_name = default_key.replace("CaseMeta.", "")
                bundle_field = self._to_bundle_field(field_name)
                if bundle_field not in meta or meta[bundle_field] is None:
                    meta[bundle_field] = default_value

        # Rename case_id to id for CaseBundle format
        if "case_id" in meta:
            meta["id"] = meta.pop("case_id")

        return meta

    def _map_individuals(self, customers: list) -> list:
        """Map customer data to Individual format."""
        individuals = []

        for customer in customers:
            individual = {}

            for target, source in self.adapter.mappings.items():
                if not target.startswith("Individual."):
                    continue

                field_name = target.replace("Individual.", "")
                # For array items, source path is relative
                value = self._extract_relative_value(customer, source)

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("pep_status", "risk_rating", "sensitivity"):
                        value = str(value).lower()
                    individual[field_name] = value

            # Apply defaults
            for default_key, default_value in self.adapter.defaults.items():
                if default_key.startswith("Individual."):
                    field_name = default_key.replace("Individual.", "")
                    if field_name not in individual or individual[field_name] is None:
                        individual[field_name] = default_value

            if individual.get("id"):
                individuals.append(individual)

        return individuals

    def _map_accounts(self, accounts: list) -> list:
        """Map account data to Account format."""
        result = []

        for account in accounts:
            mapped = {}

            for target, source in self.adapter.mappings.items():
                if not target.startswith("Account."):
                    continue

                field_name = target.replace("Account.", "")
                value = self._extract_relative_value(account, source)

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("account_type", "status", "sensitivity"):
                        value = str(value).lower()
                    mapped[field_name] = value

            # Apply defaults
            for default_key, default_value in self.adapter.defaults.items():
                if default_key.startswith("Account."):
                    field_name = default_key.replace("Account.", "")
                    if field_name not in mapped or mapped[field_name] is None:
                        mapped[field_name] = default_value

            if mapped.get("id"):
                result.append(mapped)

        return result

    def _map_transactions(self, transactions: list) -> list:
        """Map transaction data to TransactionEvent format."""
        events = []

        for txn in transactions:
            event = {"event_type": "transaction"}

            for target, source in self.adapter.mappings.items():
                if not target.startswith("TransactionEvent."):
                    continue

                field_name = target.replace("TransactionEvent.", "")
                value = self._extract_relative_value(txn, source)

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("direction", "payment_method", "sensitivity"):
                        value = str(value).lower()
                    event[field_name] = value

            # Apply defaults
            for default_key, default_value in self.adapter.defaults.items():
                if default_key.startswith("TransactionEvent."):
                    field_name = default_key.replace("TransactionEvent.", "")
                    if field_name not in event or event[field_name] is None:
                        event[field_name] = default_value

            if event.get("id"):
                events.append(event)

        return events

    def _map_alerts(self, alerts: list) -> list:
        """Map alert data to AlertEvent format."""
        events = []

        for alert in alerts:
            event = {"event_type": "alert"}

            for target, source in self.adapter.mappings.items():
                if not target.startswith("AlertEvent."):
                    continue

                field_name = target.replace("AlertEvent.", "")
                value = self._extract_relative_value(alert, source)

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("alert_type", "sensitivity"):
                        value = str(value).lower()
                    event[field_name] = value

            # Apply defaults
            for default_key, default_value in self.adapter.defaults.items():
                if default_key.startswith("AlertEvent."):
                    field_name = default_key.replace("AlertEvent.", "")
                    if field_name not in event or event[field_name] is None:
                        event[field_name] = default_value

            if event.get("id"):
                events.append(event)

        return events

    def _map_screenings(self, screenings: list) -> list:
        """Map screening data to ScreeningEvent format."""
        events = []

        for screening in screenings:
            event = {"event_type": "screening"}

            for target, source in self.adapter.mappings.items():
                if not target.startswith("ScreeningEvent."):
                    continue

                field_name = target.replace("ScreeningEvent.", "")
                value = self._extract_relative_value(screening, source)

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("screening_type", "disposition", "sensitivity"):
                        value = str(value).lower()
                    event[field_name] = value

            # Apply defaults
            for default_key, default_value in self.adapter.defaults.items():
                if default_key.startswith("ScreeningEvent."):
                    field_name = default_key.replace("ScreeningEvent.", "")
                    if field_name not in event or event[field_name] is None:
                        event[field_name] = default_value

            # Add description if not present
            if "description" not in event:
                event["description"] = f"{event.get('screening_type', 'Screening').title()} screening"

            if event.get("id"):
                events.append(event)

        return events

    def _generate_account_relationships(
        self,
        primary_entity_id: str,
        primary_entity_type: str,
        accounts: list
    ) -> list:
        """Generate account holder relationships.

        Note: Uses 'individual' as to_entity_type since EntityType enum
        only supports 'individual' and 'organization'. The to_entity_id
        still correctly references the account.
        """
        relationships = []

        for account in accounts:
            account_id = account.get("id")
            if not account_id:
                continue

            # Use 'individual' as to_entity_type to match schema constraints
            # The relationship semantics are preserved via relationship_type
            rel = {
                "id": f"REL-{primary_entity_id}-{account_id}",
                "relationship_type": "account_holder",
                "from_entity_type": primary_entity_type,
                "from_entity_id": primary_entity_id,
                "to_entity_type": "individual",  # Schema constraint: EntityType only has individual/organization
                "to_entity_id": account_id,
                "sensitivity": "internal",
                "access_tags": ["aml"],
            }
            relationships.append(rel)

        return relationships

    def _extract_value(self, data: dict, source: str) -> Any:
        """Extract value from data using source path."""
        if source.startswith("!literal "):
            return source.replace("!literal ", "")

        return jsonpath_extract(data, source)

    def _extract_relative_value(self, item: dict, source: str) -> Any:
        """Extract value from item using relative path (within array item)."""
        if source.startswith("!literal "):
            return source.replace("!literal ", "")

        # Convert absolute path to relative (remove $. prefix)
        if source.startswith("$."):
            relative_path = source[2:]
            # Handle array wildcards in path
            if "[*]" in relative_path:
                # Extract just the field name after [*].
                parts = relative_path.split("[*].")
                if len(parts) > 1:
                    relative_path = parts[-1]
            return item.get(relative_path)

        return item.get(source)

    def _apply_transform(self, field_name: str, value: Any) -> Any:
        """Apply value transform if defined."""
        if value is None:
            return None

        # Check for direct transform
        if field_name in self.adapter.transforms:
            transform_map = self.adapter.transforms[field_name]
            str_value = str(value)
            if str_value in transform_map:
                return transform_map[str_value]

        # Check for common transform names
        transform_aliases = {
            "pep_status": "pep_status",
            "risk_rating": "risk_rating",
            "direction": "direction",
            "case_type": "case_type",
            "status": "account_status",
            "account_status": "account_status",
            "disposition": "screening_disposition",
            "priority": "priority",
        }

        alias = transform_aliases.get(field_name)
        if alias and alias in self.adapter.transforms:
            transform_map = self.adapter.transforms[alias]
            str_value = str(value)
            if str_value in transform_map:
                return transform_map[str_value]

        return value

    def _to_bundle_field(self, field_name: str) -> str:
        """Convert adapter field name to CaseBundle field name."""
        # Most are the same, but some need mapping
        field_map = {
            "case_id": "id",
        }
        return field_map.get(field_name, field_name)


# ============================================================================
# HIGH-LEVEL API
# ============================================================================

def map_case(
    input_path: str | Path,
    adapter_path: str | Path,
    output_path: Optional[str | Path] = None,
) -> dict:
    """
    Map a vendor export to CaseBundle format.

    Args:
        input_path: Path to vendor export file (JSON)
        adapter_path: Path to adapter YAML file
        output_path: Optional path to write output JSON

    Returns:
        CaseBundle dictionary

    Raises:
        AdapterError: If adapter is invalid
        MappingError: If mapping fails
    """
    # Load adapter
    adapter = load_adapter(adapter_path)

    # Load input
    input_path = Path(input_path)
    if not input_path.exists():
        raise AdapterError(f"Input file not found: {input_path}")

    with open(input_path, "r") as f:
        input_data = json.load(f)

    # Map
    mapper = CaseMapper(adapter)
    bundle = mapper.map(input_data)

    # Write output if requested
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(bundle, f, indent=2)

    return bundle


def validate_adapter(path: str | Path) -> tuple[bool, list[str]]:
    """
    Validate an adapter YAML file.

    Args:
        path: Path to adapter YAML file

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    try:
        adapter = load_adapter(path)
        return True, []
    except AdapterValidationError as e:
        return False, [str(e)]
    except AdapterError as e:
        return False, [str(e)]

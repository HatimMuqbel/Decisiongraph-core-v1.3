"""
Case Mapper - Pure Transformation Layer

Maps vendor-specific case exports to canonical CaseBundle format using
declarative YAML adapters. No business logic, no rules, no scoring.

One question only: "How do I turn your export into our CaseBundle?"

Features:
- Deterministic adapter hash for governance
- Provenance stamping (source system, file hash, timestamp)
- Error collection mode for batch processing
- Field-level required/optional handling

Usage:
    from decisiongraph.case_mapper import CaseMapper, load_adapter

    adapter = load_adapter("adapters/fincrime/actimize/mapping.yaml")
    mapper = CaseMapper(adapter)
    result = mapper.map(input_data, source_file_hash="abc123...")

    bundle = result.bundle
    errors = result.errors
    provenance = result.provenance
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
# DATA STRUCTURES
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
class FieldOptions:
    """Options for a mapped field."""
    required: bool = False
    on_missing: str = "NULL"  # ERROR | DEFAULT | NULL | SKIP_RECORD
    default_value: Any = None


@dataclass
class Adapter:
    """Complete adapter definition."""
    metadata: AdapterMetadata
    roots: dict[str, str]
    mappings: dict[str, str]
    transforms: dict[str, dict[str, str]] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    field_options: dict[str, FieldOptions] = field(default_factory=dict)
    adapter_hash: str = ""


@dataclass
class MappingErrorRecord:
    """A single mapping error."""
    record_type: str
    record_index: int
    field: str
    error: str
    source_path: Optional[str] = None
    raw_value: Optional[str] = None


@dataclass
class Provenance:
    """Provenance metadata for mapped bundle."""
    adapter_name: str
    adapter_version: str
    adapter_hash: str
    source_system: str
    source_file_hash: Optional[str] = None
    ingested_at: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "adapter_hash": self.adapter_hash,
            "source_system": self.source_system,
            "source_file_hash": self.source_file_hash,
            "ingested_at": self.ingested_at,
        }


@dataclass
class MappingResult:
    """Result of a mapping operation."""
    bundle: dict
    provenance: Provenance
    errors: list[MappingErrorRecord] = field(default_factory=list)
    records_processed: int = 0
    records_mapped: int = 0
    records_skipped: int = 0

    def to_summary(self) -> dict:
        return {
            "records_processed": self.records_processed,
            "records_mapped": self.records_mapped,
            "records_skipped": self.records_skipped,
            "error_count": len(self.errors),
        }


# ============================================================================
# ADAPTER HASH COMPUTATION
# ============================================================================

def compute_adapter_hash(adapter_dict: dict) -> str:
    """
    Compute deterministic hash of adapter.

    Uses canonical JSON representation (sorted keys, no whitespace).
    """
    # Remove any runtime-computed fields
    clean_dict = {k: v for k, v in adapter_dict.items()}

    # Canonical JSON: sorted keys, no extra whitespace
    canonical = json.dumps(clean_dict, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# ============================================================================
# ADAPTER LOADING AND VALIDATION
# ============================================================================

def load_adapter(path: str | Path) -> Adapter:
    """
    Load and validate an adapter from YAML file.

    Args:
        path: Path to adapter YAML file

    Returns:
        Validated Adapter instance with computed adapter_hash

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
    for field_name in required_meta:
        if field_name not in adapter_meta:
            raise AdapterValidationError(f"Missing adapter.{field_name}")

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

    for field_name in required_case_meta:
        if field_name not in mappings:
            raise AdapterValidationError(f"Missing required mapping: {field_name}")

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

    # Parse field_options (optional)
    field_options = {}
    if "field_options" in data:
        for field_name, opts in data["field_options"].items():
            field_options[field_name] = FieldOptions(
                required=opts.get("required", False),
                on_missing=opts.get("on_missing", "NULL"),
                default_value=opts.get("default_value"),
            )

    # Compute adapter hash
    adapter_hash = compute_adapter_hash(data)

    return Adapter(
        metadata=metadata,
        roots=roots,
        mappings=mappings,
        transforms=transforms,
        defaults=defaults,
        field_options=field_options,
        adapter_hash=adapter_hash,
    )


# ============================================================================
# CASE MAPPER
# ============================================================================

class CaseMapper:
    """
    Maps vendor exports to CaseBundle format using an adapter.

    Pure transformation - no business logic.
    """

    def __init__(self, adapter: Adapter, max_errors: int = 0):
        """
        Initialize mapper with an adapter.

        Args:
            adapter: Validated Adapter instance
            max_errors: Maximum errors before aborting (0 = no limit)
        """
        self.adapter = adapter
        self.max_errors = max_errors
        self._errors: list[MappingErrorRecord] = []
        self._records_processed = 0
        self._records_mapped = 0
        self._records_skipped = 0

    def map(
        self,
        input_data: dict,
        source_file_hash: Optional[str] = None,
    ) -> MappingResult:
        """
        Map input data to CaseBundle format.

        Args:
            input_data: Vendor export data (parsed JSON/dict)
            source_file_hash: Optional SHA256 of source file for provenance

        Returns:
            MappingResult with bundle, provenance, and any errors

        Raises:
            MappingError: If mapping fails (when not in error collection mode)
            RequiredFieldError: If required field is missing
        """
        # Reset counters
        self._errors = []
        self._records_processed = 0
        self._records_mapped = 0
        self._records_skipped = 0

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

        # Create provenance
        provenance = Provenance(
            adapter_name=self.adapter.metadata.name,
            adapter_version=self.adapter.metadata.version,
            adapter_hash=self.adapter.adapter_hash,
            source_system=self.adapter.metadata.vendor,
            source_file_hash=source_file_hash,
            ingested_at=datetime.now(timezone.utc).isoformat(),
        )

        # Add provenance to bundle meta
        bundle["meta"]["provenance"] = provenance.to_dict()

        return MappingResult(
            bundle=bundle,
            provenance=provenance,
            errors=self._errors,
            records_processed=self._records_processed,
            records_mapped=self._records_mapped,
            records_skipped=self._records_skipped,
        )

    def _add_error(
        self,
        record_type: str,
        record_index: int,
        field_name: str,
        error: str,
        source_path: Optional[str] = None,
        raw_value: Optional[str] = None,
    ) -> bool:
        """
        Add an error and check if we should abort.

        Returns True if we should continue, False if max_errors exceeded.
        """
        self._errors.append(MappingErrorRecord(
            record_type=record_type,
            record_index=record_index,
            field=field_name,
            error=error,
            source_path=source_path,
            raw_value=str(raw_value)[:100] if raw_value else None,  # Truncate for safety
        ))

        if self.max_errors > 0 and len(self._errors) >= self.max_errors:
            return False
        return True

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

        for idx, customer in enumerate(customers):
            self._records_processed += 1
            individual = {}
            skip_record = False

            for target, source in self.adapter.mappings.items():
                if not target.startswith("Individual."):
                    continue

                field_name = target.replace("Individual.", "")
                # For array items, source path is relative
                value = self._extract_relative_value(customer, source)

                # Check field options
                opts = self.adapter.field_options.get(target, FieldOptions())

                if value is None:
                    if opts.required or opts.on_missing == "ERROR":
                        if not self._add_error("individual", idx, field_name,
                                               "required field missing", source):
                            raise RequiredFieldError(f"Too many errors")
                        if opts.on_missing == "SKIP_RECORD":
                            skip_record = True
                            break
                        continue
                    elif opts.on_missing == "DEFAULT":
                        value = opts.default_value
                    elif opts.on_missing == "NULL":
                        continue  # Skip this field

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("pep_status", "risk_rating", "sensitivity"):
                        value = str(value).lower()
                    individual[field_name] = value

            if skip_record:
                self._records_skipped += 1
                continue

            # Apply defaults
            for default_key, default_value in self.adapter.defaults.items():
                if default_key.startswith("Individual."):
                    field_name = default_key.replace("Individual.", "")
                    if field_name not in individual or individual[field_name] is None:
                        individual[field_name] = default_value

            if individual.get("id"):
                individuals.append(individual)
                self._records_mapped += 1

        return individuals

    def _map_accounts(self, accounts: list) -> list:
        """Map account data to Account format."""
        result = []

        for idx, account in enumerate(accounts):
            self._records_processed += 1
            mapped = {}
            skip_record = False

            for target, source in self.adapter.mappings.items():
                if not target.startswith("Account."):
                    continue

                field_name = target.replace("Account.", "")
                value = self._extract_relative_value(account, source)

                # Check field options
                opts = self.adapter.field_options.get(target, FieldOptions())

                if value is None:
                    if opts.required or opts.on_missing == "ERROR":
                        if not self._add_error("account", idx, field_name,
                                               "required field missing", source):
                            raise RequiredFieldError(f"Too many errors")
                        if opts.on_missing == "SKIP_RECORD":
                            skip_record = True
                            break
                        continue
                    elif opts.on_missing == "DEFAULT":
                        value = opts.default_value
                    elif opts.on_missing == "NULL":
                        continue

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("account_type", "status", "sensitivity"):
                        value = str(value).lower()
                    mapped[field_name] = value

            if skip_record:
                self._records_skipped += 1
                continue

            # Apply defaults
            for default_key, default_value in self.adapter.defaults.items():
                if default_key.startswith("Account."):
                    field_name = default_key.replace("Account.", "")
                    if field_name not in mapped or mapped[field_name] is None:
                        mapped[field_name] = default_value

            if mapped.get("id"):
                result.append(mapped)
                self._records_mapped += 1

        return result

    def _map_transactions(self, transactions: list) -> list:
        """Map transaction data to TransactionEvent format."""
        events = []

        for idx, txn in enumerate(transactions):
            self._records_processed += 1
            event = {"event_type": "transaction"}
            skip_record = False

            for target, source in self.adapter.mappings.items():
                if not target.startswith("TransactionEvent."):
                    continue

                field_name = target.replace("TransactionEvent.", "")
                value = self._extract_relative_value(txn, source)

                # Check field options
                opts = self.adapter.field_options.get(target, FieldOptions())

                if value is None:
                    if opts.required or opts.on_missing == "ERROR":
                        if not self._add_error("transaction", idx, field_name,
                                               "required field missing", source):
                            raise RequiredFieldError(f"Too many errors")
                        if opts.on_missing == "SKIP_RECORD":
                            skip_record = True
                            break
                        continue
                    elif opts.on_missing == "DEFAULT":
                        value = opts.default_value
                    elif opts.on_missing == "NULL":
                        continue

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("direction", "payment_method", "sensitivity"):
                        value = str(value).lower()
                    event[field_name] = value

            if skip_record:
                self._records_skipped += 1
                continue

            # Apply defaults
            for default_key, default_value in self.adapter.defaults.items():
                if default_key.startswith("TransactionEvent."):
                    field_name = default_key.replace("TransactionEvent.", "")
                    if field_name not in event or event[field_name] is None:
                        event[field_name] = default_value

            if event.get("id"):
                events.append(event)
                self._records_mapped += 1

        return events

    def _map_alerts(self, alerts: list) -> list:
        """Map alert data to AlertEvent format."""
        events = []

        for idx, alert in enumerate(alerts):
            self._records_processed += 1
            event = {"event_type": "alert"}
            skip_record = False

            for target, source in self.adapter.mappings.items():
                if not target.startswith("AlertEvent."):
                    continue

                field_name = target.replace("AlertEvent.", "")
                value = self._extract_relative_value(alert, source)

                # Check field options
                opts = self.adapter.field_options.get(target, FieldOptions())

                if value is None:
                    if opts.required or opts.on_missing == "ERROR":
                        if not self._add_error("alert", idx, field_name,
                                               "required field missing", source):
                            raise RequiredFieldError(f"Too many errors")
                        if opts.on_missing == "SKIP_RECORD":
                            skip_record = True
                            break
                        continue
                    elif opts.on_missing == "DEFAULT":
                        value = opts.default_value
                    elif opts.on_missing == "NULL":
                        continue

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("alert_type", "sensitivity"):
                        value = str(value).lower()
                    event[field_name] = value

            if skip_record:
                self._records_skipped += 1
                continue

            # Apply defaults
            for default_key, default_value in self.adapter.defaults.items():
                if default_key.startswith("AlertEvent."):
                    field_name = default_key.replace("AlertEvent.", "")
                    if field_name not in event or event[field_name] is None:
                        event[field_name] = default_value

            if event.get("id"):
                events.append(event)
                self._records_mapped += 1

        return events

    def _map_screenings(self, screenings: list) -> list:
        """Map screening data to ScreeningEvent format."""
        events = []

        for idx, screening in enumerate(screenings):
            self._records_processed += 1
            event = {"event_type": "screening"}
            skip_record = False

            for target, source in self.adapter.mappings.items():
                if not target.startswith("ScreeningEvent."):
                    continue

                field_name = target.replace("ScreeningEvent.", "")
                value = self._extract_relative_value(screening, source)

                # Check field options
                opts = self.adapter.field_options.get(target, FieldOptions())

                if value is None:
                    if opts.required or opts.on_missing == "ERROR":
                        if not self._add_error("screening", idx, field_name,
                                               "required field missing", source):
                            raise RequiredFieldError(f"Too many errors")
                        if opts.on_missing == "SKIP_RECORD":
                            skip_record = True
                            break
                        continue
                    elif opts.on_missing == "DEFAULT":
                        value = opts.default_value
                    elif opts.on_missing == "NULL":
                        continue

                if value is not None:
                    value = self._apply_transform(field_name, value)
                    if field_name in ("screening_type", "disposition", "sensitivity"):
                        value = str(value).lower()
                    event[field_name] = value

            if skip_record:
                self._records_skipped += 1
                continue

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
                self._records_mapped += 1

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
    max_errors: int = 0,
    error_file: Optional[str | Path] = None,
) -> MappingResult:
    """
    Map a vendor export to CaseBundle format.

    Args:
        input_path: Path to vendor export file (JSON)
        adapter_path: Path to adapter YAML file
        output_path: Optional path to write output JSON
        max_errors: Maximum errors before aborting (0 = no limit)
        error_file: Optional path to write errors JSONL

    Returns:
        MappingResult with bundle, provenance, and errors

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
        input_bytes = f.read()
        input_data = json.loads(input_bytes)

    # Compute source file hash
    source_file_hash = hashlib.sha256(input_bytes.encode('utf-8')).hexdigest()

    # Map
    mapper = CaseMapper(adapter, max_errors=max_errors)
    result = mapper.map(input_data, source_file_hash=source_file_hash)

    # Write output if requested
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result.bundle, f, indent=2)

    # Write errors if requested
    if error_file and result.errors:
        error_file = Path(error_file)
        error_file.parent.mkdir(parents=True, exist_ok=True)
        with open(error_file, "w") as f:
            for err in result.errors:
                f.write(json.dumps({
                    "record_type": err.record_type,
                    "record_index": err.record_index,
                    "field": err.field,
                    "error": err.error,
                    "source_path": err.source_path,
                    "raw_value": err.raw_value,
                }) + "\n")

    return result


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

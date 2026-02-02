"""
ClaimPilot Precedent System: Seed Configuration Loader

This module provides utilities for loading seed configurations from YAML files.

Example:
    >>> from claimpilot.precedent.seeds import load_seed_config, list_seed_configs
    >>> configs = list_seed_configs()
    >>> auto_config = load_seed_config("auto_oap1")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml


# =============================================================================
# Constants
# =============================================================================

SEEDS_DIR = Path(__file__).parent


# =============================================================================
# Exceptions
# =============================================================================

class SeedConfigLoadError(Exception):
    """Raised when seed configuration loading fails."""
    pass


# =============================================================================
# Loader Functions
# =============================================================================

def list_seed_configs() -> list[str]:
    """
    List all available seed configuration files.

    Returns:
        List of config names (without .yaml extension)
    """
    configs = []
    for yaml_file in SEEDS_DIR.glob("*.yaml"):
        configs.append(yaml_file.stem)
    return sorted(configs)


def load_seed_config(name: str) -> dict[str, Any]:
    """
    Load a seed configuration by name.

    Args:
        name: Config name (e.g., "auto_oap1") without .yaml extension

    Returns:
        Parsed YAML configuration dictionary

    Raises:
        SeedConfigLoadError: If config file not found or invalid
    """
    yaml_path = SEEDS_DIR / f"{name}.yaml"

    if not yaml_path.exists():
        available = list_seed_configs()
        raise SeedConfigLoadError(
            f"Seed config '{name}' not found. "
            f"Available configs: {available}"
        )

    try:
        with open(yaml_path, "r") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise SeedConfigLoadError(f"Invalid YAML in {name}.yaml: {e}")


def load_all_seed_configs() -> dict[str, dict[str, Any]]:
    """
    Load all seed configurations.

    Returns:
        Dict mapping config name to parsed configuration
    """
    result = {}
    for name in list_seed_configs():
        result[name] = load_seed_config(name)
    return result


def get_seed_config_path(name: str) -> Path:
    """
    Get the path to a seed configuration file.

    Args:
        name: Config name without .yaml extension

    Returns:
        Path to the YAML file
    """
    return SEEDS_DIR / f"{name}.yaml"


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "SeedConfigLoadError",

    # Functions
    "list_seed_configs",
    "load_seed_config",
    "load_all_seed_configs",
    "get_seed_config_path",

    # Constants
    "SEEDS_DIR",
]

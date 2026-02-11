"""Shared pytest configuration — path setup for service & src imports."""

import sys
from pathlib import Path

# Root of decisiongraph-complete
_ROOT = Path(__file__).resolve().parent.parent

# Allow ``from decisiongraph import ...`` (src is the package root)
sys.path.insert(0, str(_ROOT / "src"))

# Allow ``from service.routers import ...`` (service is a sub-package)
sys.path.insert(0, str(_ROOT))

# Allow ``from main import ...`` (main.py lives inside service/)
sys.path.insert(0, str(_ROOT / "service"))

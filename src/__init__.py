"""trading-research package. Shared helpers only; each module owns one phase."""
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None):
    """Read config.yaml (the single source of truth for every phase)."""
    with open(path or PROJECT_ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)

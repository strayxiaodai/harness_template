"""Load agent prompts from prompts.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

_PATH = Path(__file__).resolve().parent / "prompts.yaml"

with _PATH.open(encoding="utf-8") as handle:
    PROMPTS: dict[str, dict[str, str]] = yaml.safe_load(handle)

"""Load config files with optional personal overrides from config/local/ (git-ignored)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
LOCAL_DIR = CONFIG_DIR / "local"


def deep_merge(base: dict, override: dict) -> dict:
    """Merge `override` into `base`. Nested dicts merge key by key; lists and scalars replace."""
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(name: str) -> dict:
    """Shared `config/<name>`, with `config/local/<name>` merged on top if it exists.

    The local file only needs the keys it changes, e.g. `brand:` in theme.yaml.
    """
    shared = yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8")) or {}
    local = LOCAL_DIR / name
    if local.exists():
        shared = deep_merge(shared, yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    return shared

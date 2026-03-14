# ================================
# FILE: config_override.py
# ================================
import json
from copy import deepcopy
from pathlib import Path

import yaml
from config_loader import ConfigError
from config_schema import Settings


def deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def persist_override(ctx, override: dict):
    """
    Persist user intent to settings.override.yaml.

    IMPORTANT:
    Validation must be done against the FULL resolved base config,
    not settings.yaml (which only contains includes).
    """
    from config_loader import load_settings

    override_path = ctx.base_dir / "settings.override.yaml"
    override_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if override_path.exists():
        existing = yaml.safe_load(override_path.read_text()) or {}

    merged_override = deep_merge(existing, override)

    # ✅ Load FULL base config (includes resolved)
    base = load_settings()
    base_dict = json.loads(json.dumps(base, default=lambda o: o.__dict__))

    # ✅ Validate FULL merged config
    final_cfg = deep_merge(base_dict, merged_override)
    Settings.model_validate(final_cfg)

    override_path.write_text(yaml.safe_dump(merged_override, sort_keys=False))

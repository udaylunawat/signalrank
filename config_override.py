# ================================
# FILE: config_override.py
# ================================
from pathlib import Path
import yaml
from config_schema import Settings
from config_loader import ConfigError
from copy import deepcopy


def deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for k, v in override.items():
        if (
            k in result
            and isinstance(result[k], dict)
            and isinstance(v, dict)
        ):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def persist_override(ctx, override: dict):
    """
    Persist user intent to settings.override.yaml
    """
    override_path = ctx.base_dir / "settings.override.yaml"
    override_path.parent.mkdir(parents=True, exist_ok=True)

    if override_path.exists():
        existing = yaml.safe_load(override_path.read_text()) or {}
    else:
        existing = {}

    merged = deep_merge(existing, override)

    # Validate override *after* merge with base
    Settings.model_validate(
        deep_merge(
            yaml.safe_load(Path("settings.yaml").read_text()),
            merged,
        )
    )

    override_path.write_text(
        yaml.safe_dump(merged, sort_keys=False)
    )
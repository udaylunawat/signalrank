# ================================
# FILE: config_loader.py
# ================================
from pathlib import Path
import yaml
from types import SimpleNamespace

from config_schema import Settings
from pydantic import ValidationError


_CONFIG_CACHE = None


class ConfigError(RuntimeError):
    pass


def _to_namespace(obj):
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_to_namespace(x) for x in obj]
    return obj


def load_settings(path: str = "settings.yaml"):
    global _CONFIG_CACHE

    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    cfg_path = Path(path)
    if not cfg_path.exists():
        raise ConfigError(f"settings.yaml not found at {cfg_path.resolve()}")

    raw = yaml.safe_load(cfg_path.read_text())
    if not isinstance(raw, dict):
        raise ConfigError("settings.yaml must be a mapping")

    try:
        Settings.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(
            "Invalid settings.yaml configuration:\n" + str(e)
        ) from e

    _CONFIG_CACHE = _to_namespace(raw)
    return _CONFIG_CACHE

def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
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

def load_effective_settings(ctx):
    base = yaml.safe_load(Path("settings.yaml").read_text())

    override_path = ctx.base_dir / "settings.override.yaml"
    if not override_path.exists():
        return base

    override = yaml.safe_load(override_path.read_text())
    if not isinstance(override, dict):
        raise ConfigError("settings.override.yaml must be a mapping")

    merged = deep_merge(base, override)

    Settings.model_validate(merged)
    return merged


import hashlib
import json

def fingerprint_settings(obj) -> str:
    """
    Stable fingerprint for caching.
    """
    return hashlib.md5(
        json.dumps(obj, sort_keys=True).encode()
    ).hexdigest()

# canonical import
settings = load_settings()
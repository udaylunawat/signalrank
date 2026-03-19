# ================================
# FILE: config_loader.py
# ================================
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import yaml
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

    root = yaml.safe_load(cfg_path.read_text())
    if not isinstance(root, dict):
        raise ConfigError("settings.yaml must be a mapping")

    merged = {}
    for inc in root.get("includes", []):
        p = Path(inc)
        if not p.exists():
            raise ConfigError(f"Included config missing: {p}")
        part = yaml.safe_load(p.read_text())
        merged = deep_merge(merged, part)

    merged["version"] = root.get("version", 2)

    try:
        Settings.model_validate(merged)
    except ValidationError as e:
        raise ConfigError("Invalid merged configuration:\n" + str(e)) from e

    _CONFIG_CACHE = _to_namespace(merged)
    return _CONFIG_CACHE


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_effective_settings(ctx):
    """
    Load fully-resolved settings (includes applied),
    then merge user override on top, then validate.
    """

    # 1. Load FULL base config (includes resolved)
    base = load_settings()  # <-- CRITICAL FIX
    base_dict = json.loads(json.dumps(base, default=lambda o: o.__dict__))

    # 2. Apply user override if present
    override_path = ctx.base_dir / "settings.override.yaml"
    if override_path.exists():
        override = yaml.safe_load(override_path.read_text())
        if not isinstance(override, dict):
            raise ConfigError("settings.override.yaml must be a mapping")
        merged = deep_merge(base_dict, override)
    else:
        merged = base_dict

    # 3. Validate final config
    Settings.model_validate(merged)

    return merged


def fingerprint_settings(obj) -> str:
    """
    Stable fingerprint for caching.
    """
    return hashlib.md5(json.dumps(obj, sort_keys=True).encode()).hexdigest()


# canonical import
settings = load_settings()

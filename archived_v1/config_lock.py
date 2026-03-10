import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from config_loader import load_effective_settings

LOCK_FILE = "settings.lock.json"


def _stable_fingerprint(obj: dict) -> str:
    return hashlib.md5(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def generate_settings_lock(ctx) -> dict:
    """
    Generate a deterministic settings.lock.json payload.
    """
    settings = load_effective_settings(ctx)

    # discover source files
    sources = ["settings.yaml"]
    root = Path("settings.yaml")
    root_cfg = yaml.safe_load(root.read_text())
    includes = root_cfg.get("includes", [])

    sources.extend(includes)

    override = ctx.base_dir / "settings.override.yaml"
    if override.exists():
        sources.append(str(override))

    payload = {
        "version": settings.get("version", 2),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": settings,
    }

    payload["fingerprint"] = _stable_fingerprint(settings)
    payload["source_files"] = sorted(set(sources))

    return payload


def write_settings_lock(ctx, *, effective_settings: dict, force: bool = False) -> dict:
    """
    Write settings.lock.json from the EXACT config used in this run.
    """
    lock_path = ctx.base_dir / LOCK_FILE

    if lock_path.exists() and not force:
        return json.loads(lock_path.read_text())

    # discover source files
    sources = ["settings.yaml"]
    root_cfg = yaml.safe_load(Path("settings.yaml").read_text())
    sources.extend(root_cfg.get("includes", []))

    override = ctx.base_dir / "settings.override.yaml"
    if override.exists():
        sources.append(str(override))

    payload = {
        "version": effective_settings.get("version", 2),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": effective_settings,
        "fingerprint": _stable_fingerprint(effective_settings),
        "source_files": sorted(set(sources)),
    }

    lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload

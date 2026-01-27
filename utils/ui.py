from pathlib import Path
from config_loader import settings

def discover_users():
    users_dir = Path(settings.paths.users_dir)
    if not users_dir.exists():
        return []
    return sorted(p.name for p in users_dir.iterdir() if p.is_dir())

def discover_use_cases(user: str):
    base = Path(settings.paths.users_dir) / user
    if not base.exists():
        return ["default"]
    cases = sorted(p.name for p in base.iterdir() if p.is_dir())
    return cases or ["default"]

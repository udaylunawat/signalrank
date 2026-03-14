def resolve_profile_name(effective_cfg: dict) -> str:
    """
    Single source of truth for profile selection.
    """
    profiles_cfg = effective_cfg.get("profiles", {})
    if len(profiles_cfg) == 1:
        return next(iter(profiles_cfg.keys()))
    return "senior_ic"

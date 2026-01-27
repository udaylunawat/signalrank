# ================================
# FILE: profiles.py
# ================================
from dataclasses import dataclass
from typing import List, Dict

from config_loader import settings


@dataclass
class Profile:
    name: str
    description: str

    skip_junior_roles: bool
    skip_manager_roles: bool
    exclude_keywords: List[str]

    preferred_companies: List[str]
    deprioritized_companies: List[str]

    use_llm_search: bool
    use_llm_skill_norm: bool
    use_llm_explanations: bool

    workspace_dir: str


def _build_profiles() -> Dict[str, Profile]:
    profiles = {}

    for key, cfg in settings.profiles.__dict__.items():
        profiles[key] = Profile(
            name=key,
            description=cfg.description,

            skip_junior_roles=cfg.skip_junior_roles,
            skip_manager_roles=cfg.skip_manager_roles,
            exclude_keywords=list(cfg.exclude_keywords),

            # NOTE: preferred companies intentionally empty here
            # Global preference is handled by CompanyScorer
            preferred_companies=[],
            deprioritized_companies=list(
                getattr(cfg, "deprioritized_companies", [])
            ),

            use_llm_search=cfg.llm.use_search_expansion,
            use_llm_skill_norm=cfg.llm.use_skill_normalization,
            use_llm_explanations=cfg.llm.use_match_explanations,

            workspace_dir="",
        )

    return profiles


# Canonical export
PROFILES = _build_profiles()
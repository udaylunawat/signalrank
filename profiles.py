from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Profile:
    name: str
    description: str

    # filtering
    skip_junior_roles: bool
    skip_manager_roles: bool
    exclude_keywords: List[str]

    # ranking
    preferred_companies: List[str]
    deprioritized_companies: List[str]

    # LLM feature flags
    use_llm_search: bool
    use_llm_skill_norm: bool
    use_llm_explanations: bool


PROFILES: Dict[str, Profile] = {
    "senior_ic": Profile(
        name="Senior IC",
        description="Senior individual contributor roles. Calm, IC-only.",
        skip_junior_roles=True,
        skip_manager_roles=True,
        exclude_keywords=[
            "intern", "junior", "graduate",
            "manager", "director", "head",
            "sales", "marketing", "hr",
        ],
        preferred_companies=[],
        deprioritized_companies=["accenture", "wipro", "infosys", "epam"],
        use_llm_search=True,
        use_llm_skill_norm=True,
        use_llm_explanations=True,
    ),
}
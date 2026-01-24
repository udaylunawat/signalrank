from dataclasses import dataclass
from typing import List, Dict
from pathlib import Path


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

    workspace_dir: str  # 👈 NEW


PROFILES = {
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
        workspace_dir="",  # set dynamically
    )
}
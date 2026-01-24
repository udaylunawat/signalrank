from typing import List, Dict
import yaml
from pathlib import Path


class CompanyScorer:
    def __init__(
        self,
        preferred: List[str] | None = None,
        deprioritized: List[str] | None = None,
        config_path: str = "config/company_tiers.yaml",
    ):
        self.preferred = [c.lower() for c in (preferred or [])]
        self.deprioritized = [c.lower() for c in (deprioritized or [])]

        self.default_weight = 0.5
        self.rules: Dict[str, float] = {}

        if Path(config_path).exists():
            self._load_defaults(config_path)

    def _load_defaults(self, path: str):
        data = yaml.safe_load(Path(path).read_text())
        self.default_weight = data.get("default_weight", 0.5)

        for tier in data.get("tiers", {}).values():
            for c in tier.get("companies", []):
                self.rules[c.lower()] = tier["weight"]

    def score(self, company: str) -> float:
        if not isinstance(company, str):
            return self.default_weight

        name = company.lower()

        for c in self.preferred:
            if c in name:
                return 1.0

        for c in self.deprioritized:
            if c in name:
                return 0.3

        for key, weight in self.rules.items():
            if key in name:
                return weight

        return self.default_weight
# company_scoring.py
from typing import List, Dict
from pathlib import Path
import yaml
import re


def normalize_company(name: str) -> str:
    """
    Normalize company names for robust substring matching.
    """
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


class CompanyScorer:
    def __init__(
        self,
        preferred: List[str] | None = None,
        deprioritized: List[str] | None = None,
        config_path: str = "config/company_tiers.yaml",
    ):
        self.preferred = [normalize_company(c) for c in (preferred or [])]
        self.deprioritized = [normalize_company(c) for c in (deprioritized or [])]

        self.default_weight = 0.4
        self.rules: Dict[str, float] = {}

        if Path(config_path).exists():
            self._load_defaults(config_path)

    def _load_defaults(self, path: str):
        data = yaml.safe_load(Path(path).read_text())
        self.default_weight = data.get("default_weight", self.default_weight)

        for tier in data.get("tiers", {}).values():
            for c in tier.get("companies", []):
                self.rules[normalize_company(c)] = tier["weight"]

    def score(self, company: str) -> float:
        if not isinstance(company, str):
            return self.default_weight

        name = normalize_company(company)

        for c in self.preferred:
            if c in name:
                return 1.0

        for c in self.deprioritized:
            if c in name:
                return 0.25

        for key, weight in self.rules.items():
            if key in name:
                return weight

        return self.default_weight
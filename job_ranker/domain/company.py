# domain/company.py
import re
from typing import Dict


def _norm(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


class CompanyScorer:
    """
    Deterministic, conservative company preference scorer.

    Rules:
    - No hard filtering
    - Small bounded influence
    - Alias-aware
    - User-configurable
    """

    def __init__(self, cfg: dict):
        c = cfg.get("company_scoring", {})

        self.default_weight = float(c.get("default_weight", 1.0))
        self.preferred_weight = float(c.get("preferred_weight", 1.10))
        self.deprioritized_weight = float(c.get("deprioritized_weight", 0.85))

        self.preferred = {_norm(x) for x in c.get("preferred_companies", [])}
        self.deprioritized = {_norm(x) for x in c.get("deprioritized_companies", [])}

        raw_aliases = c.get("aliases", {})
        self.aliases: Dict[str, str] = {
            _norm(k): _norm(v)
            for k, v in raw_aliases.items()
            if isinstance(k, str) and isinstance(v, str)
        }

    def _canonical(self, company: str) -> str:
        name = _norm(company)
        return self.aliases.get(name, name)

    def score(self, company: str) -> float:
        name = self._canonical(company)

        for p in self.preferred:
            if p and p in name:
                return self.preferred_weight

        for d in self.deprioritized:
            if d and d in name:
                return self.deprioritized_weight

        return self.default_weight

    def classify(self, company: str) -> str:
        """Returns 'preferred', 'deprioritized', or 'default'."""
        name = self._canonical(company)

        for p in self.preferred:
            if p and p in name:
                return "preferred"

        for d in self.deprioritized:
            if d and d in name:
                return "deprioritized"

        return "default"

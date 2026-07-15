# domain/company.py
import re
from typing import Dict


def _norm(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


_LEGAL_SUFFIXES = {
    "co",
    "company",
    "consulting",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "india",
    "global",
    "group",
    "labs",
    "limited",
    "llc",
    "llp",
    "ltd",
    "plc",
    "private",
    "pvt",
    "services",
    "solutions",
    "systems",
    "technologies",
    "technology",
}


def _strip_legal_suffixes(name: str) -> str:
    tokens = name.split()
    while len(tokens) > 1 and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


class CompanyScorer:
    """Normalize company identities and match explicit preferences."""

    # Ordered highest to lowest priority
    _TIERS = ["tier_s", "tier_a", "tier_b", "tier_c", "tier_d"]

    def __init__(self, cfg: dict):
        c = cfg.get("company_scoring", {})

        raw_aliases = c.get("aliases", {})
        self.aliases: Dict[str, str] = {
            _norm(k): _norm(v)
            for k, v in raw_aliases.items()
            if isinstance(k, str) and isinstance(v, str)
        }

        self._tier_lookup: Dict[str, str] = {}
        for tier in self._TIERS:
            for name in c.get(tier, []):
                self._tier_lookup[_norm(name)] = tier

    def _canonical(self, company: str) -> str:
        name = _norm(company)
        canonical = self.aliases.get(name, name)
        stripped = _strip_legal_suffixes(canonical)
        return self.aliases.get(stripped, stripped)

    def matches(self, company: str, candidates: list[str]) -> bool:
        company_name = self._canonical(company)
        return bool(company_name) and any(
            company_name == self._canonical(candidate) for candidate in candidates
        )

    def classify(self, company: str) -> str:
        """Returns tier name or 'default'."""
        name = self._canonical(company)
        for key, tier in self._tier_lookup.items():
            if key and self._canonical(key) == name:
                return tier
        return "default"

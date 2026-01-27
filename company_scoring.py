# ================================
# FILE: company_scoring.py
# ================================
from typing import List, Dict
import re
import yaml
from pathlib import Path

from config_loader import settings


def normalize_company(name: str) -> str:
    if not isinstance(name, str):
        return ""
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


class CompanyScorer:
    """
    Company scoring precedence (highest → lowest):

    1. Global preferred companies (settings.yaml)
    2. Profile / CLI preferred companies
    3. Profile / CLI deprioritized companies
    4. Tier-based weights
    5. Default weight
    """

    def __init__(
        self,
        preferred: List[str] | None = None,
        deprioritized: List[str] | None = None,
    ):
        cfg = settings.company_scoring

        # --------------------------------------------------
        # Aliases (SimpleNamespace-safe)
        # --------------------------------------------------
        raw_aliases = getattr(cfg, "aliases", None)
        if raw_aliases:
            alias_items = raw_aliases.__dict__.items()
        else:
            alias_items = []

        self.aliases: Dict[str, str] = {
            normalize_company(k): normalize_company(v)
            for k, v in alias_items
        }

        # --------------------------------------------------
        # Preferred / deprioritized
        # --------------------------------------------------
        global_preferred = getattr(cfg, "preferred_companies", [])

        self.preferred = {
            normalize_company(c) for c in global_preferred
        }

        if preferred:
            self.preferred |= {normalize_company(c) for c in preferred}

        self.deprioritized = {
            normalize_company(c) for c in (deprioritized or [])
        }

        # --------------------------------------------------
        # Defaults
        # --------------------------------------------------
        self.default_weight: float = cfg.default_weight
        self.rules: Dict[str, float] = {}

        # --------------------------------------------------
        # Tier rules
        # --------------------------------------------------
        tiers_path = Path(cfg.tiers_file)
        if tiers_path.exists():
            self._load_tiers(tiers_path)

    # --------------------------------------------------
    # Internal helpers
    # --------------------------------------------------
    def _apply_alias(self, name: str) -> str:
        return self.aliases.get(name, name)

    def _load_tiers(self, path: Path):
        data = yaml.safe_load(path.read_text()) or {}

        self.default_weight = data.get(
            "default_weight",
            self.default_weight,
        )

        for tier in data.get("tiers", {}).values():
            weight = tier.get("weight", self.default_weight)
            for c in tier.get("companies", []):
                self.rules[normalize_company(c)] = weight

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------
    def score(self, company: str) -> float:
        if not isinstance(company, str):
            return self.default_weight

        name = normalize_company(company)
        name = self._apply_alias(name)

        # Preferred override
        for c in self.preferred:
            if c and c in name:
                return 1.0

        # Deprioritized override
        for c in self.deprioritized:
            if c and c in name:
                return 0.25

        # Tier-based weight
        for key, weight in self.rules.items():
            if key in name:
                return weight

        return self.default_weight
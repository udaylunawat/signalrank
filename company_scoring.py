from pathlib import Path
import yaml


class CompanyScorer:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.default_weight = self.config.get("default_weight", 0.5)
        self.rules = self._build_rules(self.config.get("tiers", {}))

    def _load_config(self, path: str) -> dict:
        config_file = Path(path)
        if not config_file.exists():
            raise FileNotFoundError(f"Company tier config not found: {path}")

        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _build_rules(self, tiers: dict):
        rules = []
        for tier_name, tier_data in tiers.items():
            weight = tier_data["weight"]
            companies = tier_data.get("companies", [])
            for c in companies:
                rules.append((c.lower(), weight))
        return rules

    def score(self, company_name: str) -> float:
        if not isinstance(company_name, str):
            return self.default_weight

        name = company_name.lower()
        for keyword, weight in self.rules:
            if keyword in name:
                return weight

        return self.default_weight
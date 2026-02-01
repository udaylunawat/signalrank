# batch/logging_utils.py
import logging

logger = logging.getLogger(__name__)

ENGINE_ROLE_KEYS = {
    "agentic_systems",
    "mlops_llmops",
    "platform_devops",
    "software_general",
    "security",
}


def log_config_override(user: str, override: dict):
    """
    Structured, human-readable config override logging.
    """

    logger.info("Config override loaded: user=%s", user)

    # Resume intent
    resume = override.get("resume", {})
    prefix = resume.get("embedding_prefix")
    if prefix:
        short = " ".join(prefix.strip().split()[:6])
        logger.info("Persona intent: embedding_prefix (%s…)", short)

    # Role penalties
    ranking = override.get("ranking", {})
    penalties = ranking.get("functional_role_penalties", {})
    if penalties:
        parts = [
            f"{k.replace('_systems','').replace('_llmops','')}={v}"
            for k, v in penalties.items()
            if k in ENGINE_ROLE_KEYS
        ]
        if parts:
            logger.info("Role weights: %s", " ".join(parts))

    # Experience
    exp = override.get("experience", {})
    if "max_yoe" in exp:
        logger.info("Experience filter: max_yoe=%s", exp["max_yoe"])

    # Title blocklist
    blocklist = override.get("title_blocklist", [])
    if blocklist:
        logger.info("Title exclusions: %d terms", len(blocklist))

    # Company preferences
    company = override.get("company_scoring", {})
    preferred = company.get("preferred_companies", [])
    if preferred:
        logger.info("Company preferences: %d preferred", len(preferred))

    # Location preferences
    loc = override.get("location_scoring", {})
    preferred_locs = loc.get("preferred_locations", [])
    if preferred_locs:
        logger.info("Location preferences: %d locations", len(preferred_locs))

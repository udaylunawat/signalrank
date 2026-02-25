import logging

from dotenv import load_dotenv

from job_ranker.batch.context import resolve_context
from job_ranker.scrapers.linkedin_api import LinkedInRapidAPIScraper

load_dotenv()
logger = logging.getLogger(__name__)
# RAPID_API_KEY = "3a79494e54msheacb68a356e60dap1473c4jsn2ac4204b12db"
RAPID_API_KEY = "dd8d4e05e8mshc5ab62dcd8a5f08p14b028jsna2726a63a74d"

ctx = resolve_context("example", "default")
cfg = ctx.config
scraper = LinkedInRapidAPIScraper(
    api_key=RAPID_API_KEY,
    cfg=cfg,
    logger=logger,
)

rows = scraper.search(
    title="MLOps Engineer",
    location="India",
    cfg=cfg,
)

print(f"Total rows: {len(rows)}")

if rows:
    print("Keys:", rows[0].keys())
else:
    print("No rows returned")
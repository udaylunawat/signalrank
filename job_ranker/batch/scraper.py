# batch/scraper.py
import logging
import re

import pandas as pd
from jobspy import scrape_jobs

logger = logging.getLogger(__name__)


def scrape(*, ctx, search: str, hours_old: int, force_refresh: bool) -> pd.DataFrame:
    queries = [q.strip() for q in search.split("|") if q.strip()]
    if not queries:
        logger.warning("[SCRAPE] No queries parsed")
        return pd.DataFrame()

    all_rows = []
    scraping = ctx.config.get("scraping", {})
    for q in queries:
        jobs = scrape_jobs(
            site_name=scraping.get("sites", {}).get("enabled", ["indeed"]),
            search_term=q,
            location=scraping.get(
                "country", "India"
            ),  # ctx.config["scraping"]["country"],
            country_indeed=scraping.get("country", "India"),
            hours_old=hours_old,
            results_wanted=scraping.get(
                "max_results", "500"
            ),  # ctx.config["scraping"]["max_results"],
            use_multiprocessing=scraping.get(
                "use_multiprocessing", False
            ),  # ctx.config["scraping"].get("use_multiprocessing", False),
        )

        count = "None" if jobs is None else getattr(jobs, "__len__", lambda: "NA")()
        logger.warning(
            "[SCRAPE DEBUG] query=%r type=%s count=%s",
            q,
            type(jobs),
            count,
        )

        if jobs is None:
            continue

        # JobSpy sometimes returns list
        if isinstance(jobs, list):
            df = pd.DataFrame(jobs)
        else:
            df = jobs

        if df.empty:
            continue

        for col in ["title", "company", "description", "location"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)

        df = df[df["description"].str.len() >= 100]

        if not df.empty:
            all_rows.append(df)

    if not all_rows:
        logger.warning("[SCRAPE] No rows collected from any query")
        return pd.DataFrame()

    merged = (
        pd.concat(all_rows, ignore_index=True)
        .drop_duplicates(subset=["job_url"])
        .reset_index(drop=True)
    )

    blocklist = ctx.config.get("ranking", {}).get("hard_title_blocklist", [])
    if blocklist:
        rx = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, blocklist)), re.I)
        merged = merged[~merged["title"].str.contains(rx, na=False)]

    logger.info("[SCRAPE] Final rows=%d", len(merged))
    return merged

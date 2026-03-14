import logging
import random
import time
from pathlib import Path

import pandas as pd
from jobspy import scrape_jobs

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("jobspy-test")

def load_proxies(path="working_proxies.txt"):
    p = Path(path)
    if not p.exists():
        logger.warning("working_proxies.txt not found, running without proxies")
        return []
    proxies = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "://" not in line:
            line = "http://" + line
        proxies.append(line)
    logger.info(f"Loaded {len(proxies)} proxies")
    return proxies

def try_scrape(search_term, location, proxy):
    kwargs = {
        "site_name": ["indeed"],
        "search_term": search_term,
        "location": location,
        "results_wanted": 20,
    }
    if proxy:
        kwargs["proxy"] = proxy

    logger.info(f"Calling scrape_jobs with proxy={proxy}")
    try:
        df = scrape_jobs(**kwargs)
        return df
    except Exception as e:
        logger.warning(f"Scrape failed with proxy {proxy}: {e}")
        return pd.DataFrame()

def main():
    proxies = load_proxies()
    search = "software engineer"
    location = "Pune, Maharashtra, India"
    attempts = max(3, len(proxies))

    for attempt in range(attempts):
        proxy = random.choice(proxies) if proxies else None
        df = try_scrape(search, location, proxy)
        if not df.empty:
            print("Success, head of results:")
            print(df.head().to_string())
            return
        sleep = random.uniform(3, 7)
        logger.info(f"Retrying in {sleep:.1f}s")
        time.sleep(sleep)

    logger.error("All attempts failed")

if __name__ == "__main__":
    main()
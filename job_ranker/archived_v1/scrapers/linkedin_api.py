# ================================
# FILE: scrapers/linkedin_api.py
# ================================
import http.client
import json
import time
from typing import Dict, List, Optional
from urllib.parse import quote


class LinkedInRapidAPIScraper:
    """
    Deterministic, rate-safe RapidAPI LinkedIn scraper.

    Guarantees:
    - Obeys per-minute limits
    - Avoids redundant API usage
    - No retry storms
    - Fully synchronous
    """

    HOST_JB = "linkedin-job-search-api.p.rapidapi.com"
    HOST_ATS = "active-jobs-db.p.rapidapi.com"

    def __init__(self, api_key: str, cfg, logger=None):
        self.api_key = api_key
        self.cfg = cfg
        self.logger = logger

        max_rpm = getattr(cfg, "max_requests_per_minute", 30)
        self._min_interval = 60.0 / max(1, max_rpm)
        self._last_call_ts = 0.0

    # --------------------------------------------------
    # PUBLIC ENTRYPOINT
    # --------------------------------------------------
    def search(
        self,
        *,
        title: str,
        location: str,
        cfg=None,
        limit: int = 25,
        page_limit: int = 4,
    ) -> List[Dict]:
        limit = min(limit, cfg.volume.max_jobs_per_query)
        page_limit = min(page_limit, cfg.volume.max_pages)
        sources = getattr(self.cfg, "sources", [])

        # URL-safe once, here
        title_q = quote(f'"{title}"')
        location_q = quote(f'"{location}"')

        all_jobs: List[Dict] = []

        for source in sources:
            if source == "active-jb-7d":
                all_jobs.extend(
                    self._paged_fetch(
                        host=self.HOST_JB,
                        endpoint="active-jb-7d",
                        title_q=title_q,
                        location_q=location_q,
                        limit=limit,
                        page_limit=page_limit,
                    )
                )

            elif source == "active-ats-7d":
                all_jobs.extend(
                    self._paged_fetch(
                        host=self.HOST_ATS,
                        endpoint="active-ats-7d",
                        title_q=title_q,
                        location_q=location_q,
                        limit=limit,
                        page_limit=page_limit,
                    )
                )

        return all_jobs

    # --------------------------------------------------
    # PAGINATION + RATE LIMIT
    # --------------------------------------------------
    def _paged_fetch(
        self,
        *,
        host: str,
        endpoint: str,
        title_q: str,
        location_q: str,
        limit: int,
        page_limit: int,
    ) -> List[Dict]:
        out: List[Dict] = []

        for page in range(page_limit):
            offset = page * limit
            self._throttle()

            rows = self._call_api(
                host=host,
                endpoint=endpoint,
                title_q=title_q,
                location_q=location_q,
                limit=limit,
                offset=offset,
            )

            if not rows:
                break

            out.extend(rows)

            if len(rows) < limit:
                break

        return out

    # --------------------------------------------------
    # RATE LIMITER
    # --------------------------------------------------
    def _throttle(self):
        now = time.time()
        delta = now - self._last_call_ts

        if delta < self._min_interval:
            time.sleep(self._min_interval - delta)

        self._last_call_ts = time.time()

    # --------------------------------------------------
    # CORE API CALL
    # --------------------------------------------------
    def _call_api(
        self,
        *,
        host: str,
        endpoint: str,
        title_q: str,
        location_q: str,
        limit: int,
        offset: int,
    ) -> List[Dict]:
        conn = http.client.HTTPSConnection(
            host,
            timeout=getattr(self.cfg, "timeout_seconds", 20),
        )

        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": host,
        }

        path = (
            f"/{endpoint}"
            f"?limit={limit}"
            f"&offset={offset}"
            f"&title_filter={title_q}"
            f"&location_filter={location_q}"
            f"&description_type=text"
        )

        try:
            conn.request("GET", path, headers=headers)
            res = conn.getresponse()
            payload = json.loads(res.read().decode("utf-8"))
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[LINKEDIN_API ERROR] {endpoint}: {e}")
            return []
        finally:
            conn.close()

        if not isinstance(payload, list):
            return []

        normalized = []
        for row in payload:
            job = self._normalize_row(row)
            if job:
                normalized.append(job)

        if self.logger and normalized:
            self.logger.info(f"[LINKEDIN_API] {endpoint} → {len(normalized)} jobs")

        return normalized

    # --------------------------------------------------
    # NORMALIZATION
    # --------------------------------------------------
    def _normalize_row(self, row: Dict) -> Optional[Dict]:
        title = row.get("title") or ""
        company = row.get("organization") or ""
        description = row.get("description_text") or ""
        job_url = row.get("url") or ""

        if not title or not description or not job_url:
            return None

        location = ""
        if isinstance(row.get("locations_derived"), list) and row["locations_derived"]:
            location = row["locations_derived"][0]
        elif (
            isinstance(row.get("countries_derived"), list) and row["countries_derived"]
        ):
            location = row["countries_derived"][0]

        return {
            "job_url": job_url,
            "job_url_direct": row.get("external_apply_url") or "",
            "title": title,
            "company": company,
            "description": description,
            "location": location,
            "date_posted": row.get("date_posted") or row.get("date_created"),
            "site": row.get("source") or "linkedin",
            "is_remote": bool(row.get("remote_derived", False)),
            "employment_type": (
                row.get("employment_type", [None])[0]
                if isinstance(row.get("employment_type"), list)
                else None
            ),
        }

# scrapers/linkedin_api.py
from __future__ import annotations

import http.client
import json
import time
from typing import Dict, List
from urllib.parse import quote

import requests


class LinkedInRapidAPIScraper:
    """
    Unified RapidAPI job ingestion layer.

    Design goals:
    - Deterministic, synchronous
    - Fail-soft per source
    - Strong normalization guarantees
    - Drop-in replacement for existing linkedin_api.py
    """

    # ---------------------------
    # HOSTS
    # ---------------------------
    HOST_LINKEDIN_JB = "linkedin-job-search-api.p.rapidapi.com"
    HOST_LINKEDIN_ATS = "active-jobs-db.p.rapidapi.com"
    HOST_JSEARCH = "jsearch.p.rapidapi.com"
    HOST_INDEED_SCRAPER = "indeed-scraper-api.p.rapidapi.com"
    HOST_INDEED_COMPANY = "indeed12.p.rapidapi.com"
    HOST_GOOGLE_JOBS = "google-jobs-api.p.rapidapi.com"
    HOST_GENERIC = "jobs-search-api.p.rapidapi.com"

    def __init__(self, api_key: str, cfg, logger=None):
        self.api_key = api_key
        self.cfg = cfg
        self.logger = logger

        max_rpm = getattr(cfg, "max_requests_per_minute", 30)
        self._min_interval = 60.0 / max(1, max_rpm)
        self._last_call_ts = 0.0

    # ============================================================
    # PUBLIC ENTRYPOINT
    # ============================================================
    def search(
        self,
        *,
        title: str,
        location: str,
        cfg=None,
        limit: int = 25,
        page_limit: int = 5,
    ) -> List[Dict]:

        limit = min(limit, 25)
        page_limit = min(page_limit, 5)

        # all_rows: List[Dict] = []

        title_q = title.strip()
        location_q = location.strip()

        all_rows: List[Dict] = []

        def _extend(label: str, fn):
            before = len(all_rows)
            rows = fn()
            all_rows.extend(rows)
            after = len(all_rows)
            if self.logger:
                self.logger.warning(
                    "[SCRAPER] %-12s → %d rows",
                    label,
                    after - before,
                )

        # _extend(
        #     "linkedin",
        #     lambda: self._search_linkedin(title_q, location_q, limit, page_limit),
        # )
        _extend(
            "jsearch",
            lambda: self._search_jsearch(title_q, location_q, limit, page_limit),
        )
        _extend(
            "generic",
            lambda: self._search_generic(),
        )
        # _extend(
        #     "indeed",
        #     lambda: self._search_indeed_scraper(title_q, location_q, limit),
        # )
        # _extend(
        #     "google",
        #     lambda: self._search_google_jobs(title_q),
        # )
        self._debug(
            "[SCRAPER] summary",
            total=len(all_rows),
            sources=len({r.get("site") for r in all_rows}),
        )
        return all_rows

    # ============================================================
    # RATE LIMIT
    # ============================================================
    def _throttle(self):
        now = time.time()
        delta = now - self._last_call_ts
        if delta < self._min_interval:
            time.sleep(self._min_interval - delta)
        self._last_call_ts = time.time()

    def _headers(self, host: str) -> Dict[str, str]:
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": host,
            "Content-Type": "application/json",
        }

    # ============================================================
    # LINKEDIN (EXISTING BEHAVIOR)
    # ============================================================
    def _search_linkedin(self, title, location, limit, page_limit) -> List[Dict]:
        out: List[Dict] = []
        title_q = quote(f'"{title}"')
        location_q = quote(f'"{location}"')

        for endpoint, host in [
            ("active-jb-7d", self.HOST_LINKEDIN_JB),
            ("active-ats-7d", self.HOST_LINKEDIN_ATS),
        ]:
            for page in range(page_limit):
                self._throttle()
                offset = page * limit
                rows = self._call_linkedin_api(
                    host, endpoint, title_q, location_q, limit, offset
                )
                if not rows:
                    break
                out.extend(rows)
                if len(rows) < limit:
                    break
        return out
    
    def _call_linkedin_api(self, host, endpoint, title_q, location_q, limit, offset):
        conn = http.client.HTTPSConnection(host, timeout=20)
        path = (
            f"/{endpoint}"
            f"?limit={limit}"
            f"&offset={offset}"
            f"&title_filter={title_q}"
            f"&location_filter={location_q}"
            f"&description_type=text"
        )

        try:
            conn.request("GET", path, headers=self._headers(host))
            res = conn.getresponse()
            status = res.status
            raw = res.read().decode("utf-8", errors="ignore")
        except Exception as e:
            self._debug(
                "[LINKEDIN] request_failed",
                endpoint=endpoint,
                error=type(e).__name__,
            )
            return []
        finally:
            conn.close()

        self._debug(
            "[LINKEDIN] response",
            endpoint=endpoint,
            status=status,
            bytes=len(raw),
        )

        try:
            payload = json.loads(raw)
        except Exception:
            self._debug(
                "[LINKEDIN] json_decode_failed",
                endpoint=endpoint,
                preview=raw[:120],
            )
            return []

        # -----------------------------
        # Normalize payload shape
        # -----------------------------
        if isinstance(payload, dict):
            rows = payload.get("data") or payload.get("results") or []
            self._debug(
                "[LINKEDIN] payload_dict",
                endpoint=endpoint,
                keys=list(payload.keys()),
                rows=len(rows) if isinstance(rows, list) else "non_list",
            )
        elif isinstance(payload, list):
            rows = payload
            self._debug(
                "[LINKEDIN] payload_list",
                endpoint=endpoint,
                rows=len(rows),
            )
        else:
            self._debug(
                "[LINKEDIN] payload_unknown",
                endpoint=endpoint,
                type=type(payload).__name__,
            )
            return []

        if not isinstance(rows, list):
            return []

        out = []
        dropped = 0

        for row in rows:
            if not isinstance(row, dict):
                dropped += 1
                continue
            job = self._normalize_linkedin(row)
            if job:
                out.append(job)
            else:
                dropped += 1

        self._debug(
            "[LINKEDIN] normalized",
            endpoint=endpoint,
            kept=len(out),
            dropped=dropped,
        )

        return out

    # ============================================================
    # JSEARCH
    # ============================================================
    def _search_jsearch(self, title, location, limit, page_limit):
        out = []
        for page in range(1, page_limit + 1):
            self._throttle()
            try:
                r = requests.get(
                    "https://jsearch.p.rapidapi.com/search",
                    headers=self._headers(self.HOST_JSEARCH),
                    params={
                        "query": f"{title} jobs in {location}",
                        "page": page,
                        "num_pages": 1,
                    },
                    timeout=15,
                )
                status = r.status_code
                data = r.json().get("data", [])
            except requests.exceptions.Timeout:
                self._debug("[JSEARCH] timeout", page=page)
                break
            except Exception as e:
                self._debug(
                    "[JSEARCH] failed",
                    page=page,
                    error=type(e).__name__,
                )
                break

            self._debug(
                "[JSEARCH] response",
                page=page,
                status=status,
                rows=len(data),
            )

            rows = []
            dropped = 0
            for x in data:
                job = self._normalize_jsearch(x)
                if job:
                    rows.append(job)
                else:
                    dropped += 1

            self._debug(
                "[JSEARCH] normalized",
                page=page,
                kept=len(rows),
                dropped=dropped,
            )

            out.extend(rows)

            if len(data) < limit:
                break

        return out

    # ============================================================
    # INDEED SCRAPER (POST)
    # ============================================================
    def _search_indeed_scraper(self, title, location, limit):
        self._throttle()
        try:
            r = requests.post(
                "https://indeed-scraper-api.p.rapidapi.com/api/job",
                headers=self._headers(self.HOST_INDEED_SCRAPER),
                json={
                    "scraper": {
                        "query": title,
                        "location": location,
                        "maxRows": limit,
                        "fromDays": 7,
                    }
                },
                timeout=30,
            )
            jobs = r.json().get("returnvalue", {}).get("data", [])
        except Exception as e:
            self._log(f"[INDEED_SCRAPER] failed: {e}")
            return []

        return [j for j in map(self._normalize_indeed, jobs) if j]

    # ============================================================
    # INDEED COMPANY (BEST EFFORT)
    # ============================================================
    def _search_indeed_company(self, title, location, limit):
        # No real search; best-effort placeholder
        return []

    # ============================================================
    # GOOGLE JOBS
    # ============================================================
    def _search_google_jobs(self, title):
        self._throttle()
        try:
            r = requests.get(
                "https://google-jobs-api.p.rapidapi.com/google-jobs/relocation",
                headers=self._headers(self.HOST_GOOGLE_JOBS),
                params={"include": title},
                timeout=20,
            )
            jobs = r.json().get("jobs", [])
        except Exception as e:
            self._log(f"[GOOGLE_JOBS] failed: {e}")
            return []

        return [j for j in map(self._normalize_google, jobs) if j]

    # ============================================================
    # GENERIC JOBS SEARCH API
    # ============================================================
    def _search_generic(self):
        self._throttle()
        try:
            r = requests.get(
                "https://jobs-search-api.p.rapidapi.com/",
                headers=self._headers(self.HOST_GENERIC),
                timeout=20,
            )
            jobs = r.json().get("data", [])
        except Exception:
            return []
        return []

    # ============================================================
    # NORMALIZERS
    # ============================================================
    def _normalize_linkedin(self, row):
        if not isinstance(row, dict):
            return None

        title = row.get("title")
        desc = row.get("description_text")

        if not title or not desc:
            return None

        return {
            "job_url": row.get("url"),
            "job_url_direct": row.get("external_apply_url"),
            "title": title,
            "company": row.get("organization"),
            "description": desc,
            "location": (row.get("locations_derived") or [""])[0],
            "date_posted": row.get("date_posted"),
            "site": "linkedin",
        }

    def _normalize_jsearch(self, row):
        return {
            "job_url": row.get("job_apply_link"),
            "job_url_direct": row.get("job_apply_link"),
            "title": row.get("job_title"),
            "company": row.get("employer_name"),
            "description": row.get("job_description") or "",
            "location": row.get("job_city") or row.get("job_country"),
            "date_posted": row.get("job_posted_at_datetime_utc"),
            "site": "jsearch",
        }

    def _normalize_indeed(self, row):
        return {
            "job_url": row.get("jobUrl"),
            "job_url_direct": row.get("jobUrl"),
            "title": row.get("title"),
            "company": row.get("companyName"),
            "description": row.get("descriptionText") or "",
            "location": row.get("location", {}).get("formattedAddressShort"),
            "date_posted": row.get("datePublished"),
            "site": "indeed",
        }

    def _normalize_google(self, row):
        return {
            "job_url": row.get("url"),
            "job_url_direct": row.get("url"),
            "title": row.get("title"),
            "company": row.get("company_name"),
            "description": row.get("description") or "",
            "location": row.get("location"),
            "date_posted": row.get("posted_at"),
            "site": "google",
        }

    # ============================================================
    # LOGGING
    # ============================================================
    def _log(self, msg: str):
        if self.logger:
            self.logger.warning(msg)

    def _debug(self, msg: str, **kv):
        if not self.logger:
            return
        extra = " ".join(f"{k}={v}" for k, v in kv.items())
        self.logger.warning(f"{msg} {extra}".strip())
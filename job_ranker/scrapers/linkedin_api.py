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
    HOST_ARBEITNOW = "arbeitnow-free-job-board.p.rapidapi.com"

    # Direct (no RapidAPI key needed) endpoints
    URL_HIMALAYAS = "https://himalayas.app/jobs/api"
    URL_REMOTIVE = "https://remotive.com/api/remote-jobs"
    URL_JOBICY = "https://jobicy.com/api/v2/remote-jobs"

    # Per-request timeout defaults (seconds)
    TIMEOUT_LINKEDIN = 30
    TIMEOUT_JSEARCH = 30
    TIMEOUT_INDEED = 30
    TIMEOUT_GOOGLE = 30
    TIMEOUT_FREE = 20

    # Retry config
    MAX_RETRIES = 2
    RETRY_BACKOFF = 2  # seconds

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
        max_results: int = 100,
    ) -> List[Dict]:

        # LinkedIn API pages are 25 results each
        page_size = 25
        page_limit = max(1, max_results // page_size)

        title_q = title.strip()
        location_q = location.strip()

        all_rows: List[Dict] = []

        def _extend(label: str, fn):
            before = len(all_rows)
            try:
                rows = fn()
            except Exception as e:
                self._debug(f"[SCRAPER] {label} crashed", error=str(e))
                rows = []
            all_rows.extend(rows)
            after = len(all_rows)
            if self.logger:
                self.logger.info(
                    "[SCRAPER] %-20s → %d rows",
                    label,
                    after - before,
                )

        _extend(
            "linkedin",
            lambda: self._search_linkedin(title_q, location_q, page_size, page_limit),
        )
        _extend(
            "jsearch",
            lambda: self._search_jsearch(title_q, location_q, page_size, page_limit),
        )
        _extend(
            "indeed",
            lambda: self._search_indeed_scraper(title_q, location_q, max_results),
        )
        _extend(
            "google",
            lambda: self._search_google_jobs(title_q),
        )
        # Free direct APIs (no RapidAPI key needed)
        _extend(
            "himalayas",
            lambda: self._search_himalayas(title_q, max_results),
        )
        _extend(
            "remotive",
            lambda: self._search_remotive(title_q),
        )
        _extend(
            "jobicy",
            lambda: self._search_jobicy(title_q),
        )
        _extend(
            "arbeitnow",
            lambda: self._search_arbeitnow(title_q, max_results),
        )
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

    def _request_with_retry(self, method, url, *, headers, timeout, **kwargs):
        """Make an HTTP request with retry on transient failures."""
        last_exc = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            self._throttle()
            try:
                r = requests.request(
                    method, url, headers=headers, timeout=timeout, **kwargs
                )
                if r.status_code == 429:
                    wait = self.RETRY_BACKOFF * attempt
                    self._debug(f"[RETRY] 429 rate-limited, waiting {wait}s", url=url)
                    time.sleep(wait)
                    continue
                if r.status_code == 401:
                    self._debug("[RETRY] 401 unauthorized, skipping", url=url)
                    return None
                return r
            except requests.exceptions.Timeout:
                self._debug(f"[RETRY] timeout attempt={attempt}", url=url)
                last_exc = TimeoutError(f"timeout after {timeout}s")
            except requests.exceptions.RequestException as e:
                self._debug(f"[RETRY] request failed attempt={attempt}", error=str(e))
                last_exc = e
                time.sleep(self.RETRY_BACKOFF * attempt)

        self._debug("[RETRY] all attempts exhausted", url=url)
        if last_exc:
            raise last_exc
        return None

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
            consecutive_empty = 0
            for page in range(page_limit):
                self._throttle()
                offset = page * limit
                rows = self._call_linkedin_api(
                    host, endpoint, title_q, location_q, limit, offset
                )
                if not rows:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        self._debug(
                            "[LINKEDIN] stopping pagination",
                            endpoint=endpoint,
                            reason="2 consecutive empty pages",
                        )
                        break
                    continue
                consecutive_empty = 0
                out.extend(rows)
                if len(rows) < limit:
                    break
        return out

    def _call_linkedin_api(self, host, endpoint, title_q, location_q, limit, offset):
        conn = http.client.HTTPSConnection(host, timeout=self.TIMEOUT_LINKEDIN)
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

        if status in (401, 403):
            self._debug("[LINKEDIN] auth_error", endpoint=endpoint, status=status)
            return []

        if status == 429:
            self._debug("[LINKEDIN] rate_limited", endpoint=endpoint)
            time.sleep(self.RETRY_BACKOFF)
            return []

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
        consecutive_empty = 0
        for page in range(1, page_limit + 1):
            try:
                r = self._request_with_retry(
                    "GET",
                    "https://jsearch.p.rapidapi.com/search",
                    headers=self._headers(self.HOST_JSEARCH),
                    timeout=self.TIMEOUT_JSEARCH,
                    params={
                        "query": f"{title} jobs in {location}",
                        "page": page,
                        "num_pages": 1,
                    },
                )
                if r is None:
                    self._debug("[JSEARCH] skipped (auth or exhausted)", page=page)
                    break
                status = r.status_code
                data = r.json().get("data") or []
            except Exception as e:
                self._debug("[JSEARCH] failed", page=page, error=str(e))
                break

            self._debug(
                "[JSEARCH] response",
                page=page,
                status=status,
                rows=len(data),
            )

            if not data:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                continue
            consecutive_empty = 0

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
        try:
            r = self._request_with_retry(
                "POST",
                "https://indeed-scraper-api.p.rapidapi.com/api/job",
                headers=self._headers(self.HOST_INDEED_SCRAPER),
                timeout=self.TIMEOUT_INDEED,
                json={
                    "scraper": {
                        "query": title,
                        "location": location,
                        "maxRows": min(limit, 100),
                        "fromDays": 15,
                    }
                },
            )
            if r is None:
                self._debug("[INDEED] skipped (auth or exhausted)")
                return []
            if r.status_code != 200:
                self._debug("[INDEED] bad status", status=r.status_code)
                return []
            jobs = r.json().get("returnvalue", {}).get("data", [])
        except Exception as e:
            self._log(f"[INDEED_SCRAPER] failed: {e}")
            return []

        return [j for j in map(self._normalize_indeed, jobs) if j]

    # ============================================================
    # GOOGLE JOBS
    # ============================================================
    def _search_google_jobs(self, title):
        try:
            r = self._request_with_retry(
                "GET",
                "https://google-jobs-api.p.rapidapi.com/google-jobs/relocation",
                headers=self._headers(self.HOST_GOOGLE_JOBS),
                timeout=self.TIMEOUT_GOOGLE,
                params={"include": title},
            )
            if r is None:
                self._debug("[GOOGLE] skipped (auth or exhausted)")
                return []
            if r.status_code != 200:
                self._debug("[GOOGLE] bad status", status=r.status_code)
                return []
            jobs = r.json().get("jobs", [])
        except Exception as e:
            self._log(f"[GOOGLE_JOBS] failed: {e}")
            return []

        return [j for j in map(self._normalize_google, jobs) if j]

    # ============================================================
    # HIMALAYAS (direct, free, paginated)
    # ============================================================
    def _search_himalayas(self, title, max_results):
        out = []
        limit_per_page = 50
        pages = max(1, min(max_results // limit_per_page, 20))
        for page_offset in range(0, pages * limit_per_page, limit_per_page):
            self._throttle()
            try:
                r = requests.get(
                    self.URL_HIMALAYAS,
                    params={"q": title, "limit": limit_per_page, "offset": page_offset},
                    timeout=self.TIMEOUT_FREE,
                )
                if r.status_code != 200:
                    self._debug("[HIMALAYAS] bad status", status=r.status_code)
                    break
                data = r.json().get("jobs") or []
            except Exception as e:
                self._debug("[HIMALAYAS] failed", error=str(e))
                break

            if not data:
                break

            for row in data:
                job = self._normalize_himalayas(row)
                if job:
                    out.append(job)

            self._debug("[HIMALAYAS] page", offset=page_offset, rows=len(data))

            if len(data) < limit_per_page:
                break
        return out

    # ============================================================
    # REMOTIVE (direct, free)
    # ============================================================
    def _search_remotive(self, title):
        self._throttle()
        try:
            r = requests.get(
                self.URL_REMOTIVE,
                params={"search": title, "limit": 100},
                timeout=self.TIMEOUT_FREE,
            )
            if r.status_code != 200:
                self._debug("[REMOTIVE] bad status", status=r.status_code)
                return []
            jobs = r.json().get("jobs") or []
        except Exception as e:
            self._debug("[REMOTIVE] failed", error=str(e))
            return []
        return [j for j in map(self._normalize_remotive, jobs) if j]

    # ============================================================
    # JOBICY (direct, free)
    # ============================================================
    def _search_jobicy(self, title):
        self._throttle()
        try:
            r = requests.get(
                self.URL_JOBICY,
                params={"count": 50, "tag": title},
                timeout=self.TIMEOUT_FREE,
            )
            if r.status_code != 200:
                self._debug("[JOBICY] bad status", status=r.status_code)
                return []
            jobs = r.json().get("jobs") or []
        except Exception as e:
            self._debug("[JOBICY] failed", error=str(e))
            return []
        return [j for j in map(self._normalize_jobicy, jobs) if j]

    # ============================================================
    # ARBEITNOW (RapidAPI, free tier, paginated)
    # ============================================================
    def _search_arbeitnow(self, title, max_results):
        out = []
        max_pages = max(1, min(max_results // 100, 10))
        for page in range(1, max_pages + 1):
            self._throttle()
            try:
                r = requests.get(
                    f"https://{self.HOST_ARBEITNOW}/api/job-board-api",
                    headers=self._headers(self.HOST_ARBEITNOW),
                    params={"page": page},
                    timeout=self.TIMEOUT_FREE,
                )
                if r.status_code == 403:
                    self._debug("[ARBEITNOW] not subscribed, skipping")
                    return out
                if r.status_code != 200:
                    self._debug("[ARBEITNOW] bad status", status=r.status_code)
                    break
                data = r.json().get("data") or []
            except Exception as e:
                self._debug("[ARBEITNOW] failed", error=str(e))
                break

            if not data:
                break

            # Filter by title keyword (Arbeitnow has no search param)
            title_lower = title.lower()
            for row in data:
                row_title = (row.get("title") or "").lower()
                row_tags = " ".join(row.get("tags") or []).lower()
                row_desc = (row.get("description") or "")[:500].lower()
                if title_lower in row_title or title_lower in row_tags or title_lower in row_desc:
                    job = self._normalize_arbeitnow(row)
                    if job:
                        out.append(job)

            self._debug("[ARBEITNOW] page", page=page, matched=len(out))
        return out

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

    def _normalize_himalayas(self, row):
        title = row.get("title")
        desc = row.get("description") or row.get("excerpt") or ""
        if not title:
            return None
        return {
            "job_url": row.get("applicationLink") or row.get("guid"),
            "job_url_direct": row.get("applicationLink"),
            "title": title,
            "company": row.get("companyName"),
            "description": desc,
            "location": ", ".join(row.get("locationRestrictions") or []) or "Remote",
            "date_posted": row.get("pubDate"),
            "site": "himalayas",
        }

    def _normalize_remotive(self, row):
        title = row.get("title")
        desc = row.get("description") or ""
        if not title:
            return None
        return {
            "job_url": row.get("url"),
            "job_url_direct": row.get("url"),
            "title": title,
            "company": row.get("company_name"),
            "description": desc,
            "location": row.get("candidate_required_location") or "Remote",
            "date_posted": row.get("publication_date"),
            "site": "remotive",
        }

    def _normalize_jobicy(self, row):
        title = row.get("jobTitle")
        desc = row.get("jobDescription") or row.get("jobExcerpt") or ""
        if not title:
            return None
        return {
            "job_url": row.get("url"),
            "job_url_direct": row.get("url"),
            "title": title,
            "company": row.get("companyName"),
            "description": desc,
            "location": row.get("jobGeo") or "Remote",
            "date_posted": row.get("pubDate"),
            "site": "jobicy",
        }

    def _normalize_arbeitnow(self, row):
        title = row.get("title")
        desc = row.get("description") or ""
        if not title:
            return None
        return {
            "job_url": row.get("url"),
            "job_url_direct": row.get("url"),
            "title": title,
            "company": row.get("company_name"),
            "description": desc,
            "location": row.get("location") or "Remote",
            "date_posted": row.get("created_at"),
            "site": "arbeitnow",
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
        self.logger.info(f"{msg} {extra}".strip())

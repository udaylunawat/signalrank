import asyncio
import html
import logging
import re
import time as time_module
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from time import perf_counter
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import pandas as pd
from api.models import JobRaw
from jobspy import scrape_jobs
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
HIMALAYAS_URL = "https://himalayas.app/jobs/api"
JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"
_HTML_TAG = re.compile(r"<[^>]+>")
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "ref",
    "referrer",
    "source",
    "trk",
}
_ROLE_EXPANSIONS = {
    "ai_ml": (
        "AI Engineer",
        "Machine Learning Engineer",
        "Applied AI Engineer",
        "Generative AI Engineer",
    ),
    "agentic": (
        "AI Agent Engineer",
        "LLM Engineer",
        "Generative AI Engineer",
        "Applied AI Engineer",
    ),
    "platform": (
        "Platform Engineer",
        "Cloud Platform Engineer",
        "Site Reliability Engineer",
        "DevOps Engineer",
    ),
    "mlops": (
        "MLOps Engineer",
        "AI Platform Engineer",
        "Machine Learning Platform Engineer",
        "LLMOps Engineer",
    ),
    "backend": (
        "Backend Engineer",
        "Python Engineer",
        "Software Engineer Backend",
        "Distributed Systems Engineer",
    ),
    "fullstack": (
        "Full Stack Engineer",
        "Software Engineer",
        "Backend Engineer",
        "Frontend Engineer",
    ),
    "data": (
        "Data Scientist",
        "Machine Learning Engineer",
        "Applied Scientist",
        "Data Engineer",
    ),
    "security": (
        "Security Engineer",
        "Cloud Security Engineer",
        "Application Security Engineer",
    ),
}
_DEFAULT_QUERIES = (
    "AI Engineer",
    "Machine Learning Engineer",
    "AI Platform Engineer",
    "Platform Engineer",
    "Backend Engineer",
    "Software Engineer",
)
JOBSPY_INTER_QUERY_DELAY = 3.0
JOBSPY_RETRY_BACKOFF = 2.0
JOBSPY_MAX_ATTEMPTS = 2
_JOB_FIELD_LIMITS = {
    "title": 500,
    "company": 255,
    "location": 255,
    "site": 100,
}


@dataclass(frozen=True)
class SearchRequest:
    query: str
    location: str


@dataclass(frozen=True)
class SourceReport:
    source: str
    query: str | None
    location: str | None
    status: str
    jobs_found: int
    duration_ms: int
    error_summary: str | None = None

    @property
    def jobs_persisted(self) -> int:
        return self.jobs_found


@dataclass(frozen=True)
class IngestResult:
    jobs_discovered: int
    jobs_persisted: int
    reports: tuple[SourceReport, ...]

    def __int__(self) -> int:
        return self.jobs_persisted


def _canonicalize_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in _TRACKING_QUERY_KEYS
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            urlencode(query),
            "",
        )
    )


def _plain_text(value: Any) -> str:
    text = html.unescape(_HTML_TAG.sub(" ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _parse_posted(value: Any) -> datetime | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    if isinstance(value, (int, float)) or str(value).strip().isdigit():
        try:
            timestamp = float(value)
            if timestamp > 1_000_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, TypeError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Invalid publication date: %s", value)
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def normalize_remotive_job(job: dict) -> dict | None:
    url = _canonicalize_url(job.get("url"))
    title = str(job.get("title") or "").strip()
    if not url or not title:
        return None
    return {
        "job_url": url,
        "title": title,
        "company": str(job.get("company_name") or "").strip() or None,
        "description": _plain_text(job.get("description")) or None,
        "location": str(job.get("candidate_required_location") or "Remote").strip(),
        "site": "remotive",
        "date_posted": _parse_posted(job.get("publication_date")),
    }


def normalize_himalayas_job(job: dict) -> dict | None:
    url = _canonicalize_url(job.get("applicationLink") or job.get("guid"))
    title = str(job.get("title") or "").strip()
    if not url or not title:
        return None
    restrictions = job.get("locationRestrictions") or []
    location = ", ".join(str(item) for item in restrictions if item) or "Remote"
    return {
        "job_url": url,
        "title": title,
        "company": str(job.get("companyName") or "").strip() or None,
        "description": _plain_text(job.get("description") or job.get("excerpt"))
        or None,
        "location": location,
        "site": "himalayas",
        "date_posted": _parse_posted(job.get("pubDate")),
    }


def normalize_jobicy_job(job: dict) -> dict | None:
    url = _canonicalize_url(job.get("url"))
    title = str(job.get("jobTitle") or "").strip()
    if not url or not title:
        return None
    return {
        "job_url": url,
        "title": title,
        "company": str(job.get("companyName") or "").strip() or None,
        "description": _plain_text(job.get("jobDescription") or job.get("jobExcerpt"))
        or None,
        "location": str(job.get("jobGeo") or "Remote").strip(),
        "site": "jobicy",
        "date_posted": _parse_posted(job.get("pubDate")),
    }


def _clean(value: Any) -> str | None:
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _fit_storage_fields(job: dict) -> dict:
    fitted = dict(job)
    for field, limit in _JOB_FIELD_LIMITS.items():
        value = fitted.get(field)
        if value is not None:
            fitted[field] = str(value)[:limit]
    return fitted


def normalize_jobspy_job(job: dict) -> dict | None:
    url = _canonicalize_url(
        _clean(job.get("job_url_direct")) or _clean(job.get("job_url"))
    )
    title = _clean(job.get("title"))
    if not url or not title:
        return None
    return {
        "job_url": url,
        "title": title,
        "company": _clean(job.get("company")),
        "description": _clean(job.get("description")),
        "location": _clean(job.get("location")),
        "site": _clean(job.get("site")) or "jobspy",
        "date_posted": _parse_posted(job.get("date_posted")),
    }


def _role_family(role: str) -> str | None:
    value = role.lower()
    if any(term in value for term in ("agent", "llm", "generative", "genai")):
        return "agentic"
    if (
        "mlops" in value
        or "ai platform" in value
        or "machine learning platform" in value
    ):
        return "mlops"
    if any(term in value for term in ("machine learning", "ai/ml", "ai engineer")):
        return "ai_ml"
    if any(term in value for term in ("devops", "sre", "infrastructure", "platform")):
        return "platform"
    if "full" in value and "stack" in value:
        return "fullstack"
    if any(term in value for term in ("backend", "back-end", "api engineer")):
        return "backend"
    if any(
        term in value
        for term in ("data scientist", "data engineer", "applied scientist")
    ):
        return "data"
    if "security" in value:
        return "security"
    return None


def expand_role_queries(roles: list[str] | None, max_queries: int = 6) -> list[str]:
    candidates: list[str] = []
    for role in roles or []:
        cleaned = re.sub(r"\s+", " ", str(role).replace("/", " ")).strip()
        family = _role_family(str(role))
        if family:
            candidates.extend(_ROLE_EXPANSIONS[family])
        elif cleaned:
            candidates.append(cleaned)
    if not candidates:
        candidates.extend(_DEFAULT_QUERIES)

    unique: list[str] = []
    seen: set[str] = set()
    for query in candidates:
        key = query.casefold()
        if key not in seen:
            unique.append(query)
            seen.add(key)
        if len(unique) >= max(1, max_queries):
            break
    return unique


def _normalize_location_lane(location: str) -> str | None:
    value = re.sub(r"\s+", " ", str(location or "")).strip()
    lower = value.casefold()
    if not value or lower in {"open to relocation", "open relocation"}:
        return None
    if lower in {"remote", "remote only", "worldwide"}:
        return "Remote"
    if lower in {"any india", "india", "anywhere in india"}:
        return "India"
    if lower in {"bangalore", "bengaluru"}:
        return "Bengaluru, India"
    if lower in {"delhi/ncr", "delhi ncr", "ncr"}:
        return "Delhi NCR, India"
    if "," not in value and lower in {"hyderabad", "mumbai", "pune", "chennai"}:
        return f"{value}, India"
    return value


def build_query_plan(
    roles: list[str] | None,
    locations: list[str] | None = None,
    default_location: str = "India",
    max_queries: int = 6,
) -> list[SearchRequest]:
    queries = expand_role_queries(roles, max_queries=max_queries)
    lanes: list[str] = []
    for value in locations or [default_location]:
        lane = _normalize_location_lane(value)
        if lane and lane.casefold() not in {item.casefold() for item in lanes}:
            lanes.append(lane)
    if not lanes:
        lanes.append(default_location)

    return [
        SearchRequest(query=query, location=lanes[index % len(lanes)])
        for index, query in enumerate(queries)
    ]


def scrape_jobspy_jobs(
    plan: list[SearchRequest],
    sleep_fn: Callable[[float], None] = time_module.sleep,
    max_attempts: int = JOBSPY_MAX_ATTEMPTS,
) -> tuple[list[dict], list[SourceReport]]:
    rows: list[dict] = []
    reports: list[SourceReport] = []
    indeed_requests = 0
    for request in plan:
        for site in ("indeed", "linkedin"):
            if site == "indeed" and indeed_requests:
                sleep_fn(JOBSPY_INTER_QUERY_DELAY)
            if site == "indeed":
                indeed_requests += 1
            started = perf_counter()
            found: list[dict] = []
            error = None
            for attempt in range(max(1, max_attempts)):
                try:
                    frame = scrape_jobs(
                        site_name=[site],
                        search_term=request.query,
                        location=request.location,
                        country_indeed="India",
                        results_wanted=50,
                        hours_old=24 * 30,
                    )
                    normalized = [
                        normalize_jobspy_job(job) for job in frame.to_dict("records")
                    ]
                    found = [job for job in normalized if job]
                    error = None
                    break
                except Exception as exc:
                    error = str(exc)[:500]
                    if attempt + 1 < max_attempts:
                        sleep_fn(JOBSPY_RETRY_BACKOFF * (attempt + 1))
                    else:
                        logger.exception(
                            "JobSpy %s query failed after %d attempts: %s",
                            site,
                            max_attempts,
                            request.query,
                        )
            rows.extend(found)
            status = "success" if found else ("error" if error else "empty")
            reports.append(
                SourceReport(
                    source=site,
                    query=request.query,
                    location=request.location,
                    status=status,
                    jobs_found=len(found),
                    duration_ms=round((perf_counter() - started) * 1000),
                    error_summary=error,
                )
            )
    return rows, reports


async def _fetch_api(
    client: httpx.AsyncClient,
    source: str,
    url: str,
    params: dict,
    query: str | None,
    normalizer: Callable[[dict], dict | None],
) -> tuple[list[dict], SourceReport]:
    started = perf_counter()
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        raw_jobs = payload.get("jobs", [])
        rows = [normalizer(job) for job in raw_jobs]
        found = [row for row in rows if row]
        status = "success" if found else "empty"
        error = None
    except Exception as exc:
        logger.exception("%s refresh failed for query %r", source, query)
        found = []
        status = "error"
        error = str(exc)[:500]
    return found, SourceReport(
        source=source,
        query=query,
        location="Remote",
        status=status,
        jobs_found=len(found),
        duration_ms=round((perf_counter() - started) * 1000),
        error_summary=error,
    )


async def _fetch_free_sources(
    queries: list[str],
) -> tuple[list[dict], list[SourceReport]]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        tasks: list[Awaitable[tuple[list[dict], SourceReport]]] = [
            _fetch_api(
                client,
                "remotive",
                REMOTIVE_URL,
                {"category": "software-dev", "limit": 200},
                None,
                normalize_remotive_job,
            )
        ]
        for query in queries[:3]:
            tasks.extend(
                (
                    _fetch_api(
                        client,
                        "himalayas",
                        HIMALAYAS_URL,
                        {"q": query, "limit": 50, "offset": 0},
                        query,
                        normalize_himalayas_job,
                    ),
                    _fetch_api(
                        client,
                        "jobicy",
                        JOBICY_URL,
                        {"count": 50, "tag": query},
                        query,
                        normalize_jobicy_job,
                    ),
                )
            )
        results = await asyncio.gather(*tasks)
    rows = [row for result_rows, _ in results for row in result_rows]
    reports = [report for _, report in results]
    return rows, reports


async def refresh_job_catalog(
    db: AsyncSession,
    roles: list[str] | None = None,
    locations: list[str] | None = None,
    location: str = "India",
    max_queries: int = 6,
) -> IngestResult:
    plan = build_query_plan(
        roles,
        locations=locations,
        default_location=location,
        max_queries=max_queries,
    )
    free_result, jobspy_result = await asyncio.gather(
        _fetch_free_sources([request.query for request in plan]),
        asyncio.to_thread(scrape_jobspy_jobs, plan),
    )
    free_rows, free_reports = free_result
    jobspy_rows, jobspy_reports = jobspy_result
    all_rows = [_fit_storage_fields(row) for row in free_rows + jobspy_rows]
    rows = list({row["job_url"]: row for row in all_rows}.values())
    reports = tuple(free_reports + jobspy_reports)
    if not rows:
        return IngestResult(jobs_discovered=0, jobs_persisted=0, reports=reports)

    statement = insert(JobRaw).values(rows)
    update_values = {
        "title": statement.excluded.title,
        "company": statement.excluded.company,
        "description": statement.excluded.description,
        "location": statement.excluded.location,
        "site": statement.excluded.site,
        "date_posted": statement.excluded.date_posted,
    }
    if hasattr(JobRaw, "last_seen"):
        update_values.update(
            last_seen=func.now(),
            last_verified=func.now(),
            active=True,
        )
    statement = statement.on_conflict_do_update(
        index_elements=[JobRaw.job_url],
        set_=update_values,
    )
    await db.execute(statement)
    await db.commit()
    return IngestResult(
        jobs_discovered=len(all_rows),
        jobs_persisted=len(rows),
        reports=reports,
    )

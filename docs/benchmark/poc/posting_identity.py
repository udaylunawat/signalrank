"""Read-only POC: conservative posting identity for June SignalRank.

No application imports, database access, requests, or side effects. Exact
ATS requisition keys and verified canonical employer URLs can auto-group.
Company/title/description *alone* are not evidence of the same opening.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "fbclid", "gclid", "msclkid", "gh_src", "lever_source", "ref",
    "refsrc", "trk", "trackingid", "source", "src", "from",
}
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_WORKDAY_REQ = re.compile(r"_([a-z][a-z0-9-]*\d[a-z0-9-]*)$", re.I)
_SYNTHETIC_REQ = re.compile(r"^TEST-REQ-\d{4,}$", re.I)


def _host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _parse(url: object):
    if not isinstance(url, str) or not url:
        return None
    try:
        parsed = urlsplit(url.strip())
        # Untrusted or incomplete URLs are *never* turned into posting IDs.
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        _ = parsed.port  # triggers ValueError for a malformed port
        return parsed
    except (ValueError, TypeError):
        return None


def _first_param(parsed, key: str) -> str | None:
    for k, v in parse_qsl(parsed.query, keep_blank_values=False):
        if k.lower() == key and v:
            return v.strip() or None
    return None


def canonical_url(url: object) -> str | None:
    """Comparison-only URL; original clickable URL must remain unchanged.

    Do not strip opaque query parameters on unknown hosts, change the path
    case, or strip Indeed's jk / LinkedIn's currentJobId identity keys.
    """
    parsed = _parse(url)
    if parsed is None:
        return None
    host = parsed.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    netloc = host + (f":{parsed.port}" if parsed.port else "")
    path = parsed.path.rstrip("/") or "/"
    items = sorted(
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING and not k.lower().startswith("utm_")
    )
    return urlunsplit(("https", netloc, path, urlencode(items), ""))


def ats_key(url: object) -> str | None:
    """Recognize *known provider* posting IDs. Unknown forms return None."""
    parsed = _parse(url)
    if parsed is None:
        return None
    host = parsed.hostname.lower().removeprefix("www.")
    segments = [s for s in parsed.path.split("/") if s]
    lower = [s.lower() for s in segments]

    # Synthetic-only fixture readers, never match ordinary production hosts.
    if host == "jobs.example.invalid" and len(segments) == 2:
        if segments[0].startswith("synthetic_") and _SYNTHETIC_REQ.fullmatch(segments[1]):
            return f"synthetic:{segments[1].upper()}"
    if host == "boards.example.invalid" and len(segments) == 2:
        if segments[0] == "listings" and _SYNTHETIC_REQ.fullmatch(segments[1]):
            return f"synthetic:{segments[1].upper()}"

    if _host_is(host, "greenhouse.io"):
        gh_id = _first_param(parsed, "gh_jid")
        if gh_id and gh_id.isdigit():
            return f"greenhouse:{gh_id}"
        token = _first_param(parsed, "token")
        if "job_app" in lower and token and token.isdigit():
            return f"greenhouse:{token}"
        if "jobs" in lower:
            i = lower.index("jobs")
            if i + 1 < len(segments) and segments[i + 1].isdigit():
                return f"greenhouse:{segments[i + 1]}"
    # Never take ATS IDs from query parameters on an unverified third-party
    # host. A trusted adapter must supply verified_canonical_url instead.

    if _host_is(host, "lever.co") and len(segments) >= 2 and _UUID.fullmatch(segments[1]):
        return f"lever:{segments[1].lower()}"

    if _host_is(host, "ashbyhq.com"):
        for segment in segments[1:]:
            if _UUID.fullmatch(segment):
                return f"ashby:{segment.lower()}"
        ashby_id = _first_param(parsed, "ashby_jid")
        if ashby_id and _UUID.fullmatch(ashby_id):
            return f"ashby:{ashby_id.lower()}"

    if _host_is(host, "myworkdayjobs.com") and "job" in lower and segments:
        tenant = host.split(".")[0].split("-")[0]
        match = _WORKDAY_REQ.search(segments[-1])
        if match:
            return f"workday:{tenant}:{match.group(1).upper()}"
    if _host_is(host, "myworkdaysite.com") and "recruiting" in lower and "job" in lower:
        index = lower.index("recruiting")
        if index + 1 < len(segments):
            match = _WORKDAY_REQ.search(segments[-1])
            if match:
                return f"workday:{segments[index + 1].lower()}:{match.group(1).upper()}"

    if _host_is(host, "indeed.com"):
        job_id = _first_param(parsed, "jk") or _first_param(parsed, "vjk")
        if job_id and re.fullmatch(r"[a-zA-Z0-9_-]{6,64}", job_id):
            return f"indeed:{job_id.lower()}"
    if _host_is(host, "linkedin.com"):
        match = re.search(r"/jobs/view/(\d+)(?:/|$)", parsed.path, re.I)
        if match:
            return f"linkedin:{match.group(1)}"
        job_id = _first_param(parsed, "currentjobid")
        if job_id and job_id.isdigit() and parsed.path.lower().startswith("/jobs/"):
            return f"linkedin:{job_id}"
    return None


@dataclass(frozen=True)
class Identity:
    key: str
    evidence: str
    confidence: str


def identity_for(job: Mapping[str, Any]) -> Identity:
    """Group only when source evidence, not title proximity, supports it.

    verified_canonical_url is accepted ONLY when supplied by a trusted scraper
    that actually verified a redirect/employer link. It is not extracted from
    untrusted page text or LLM output.
    """
    raw = job.get("job_url")
    key = ats_key(raw)
    if key:
        return Identity(key, "ats_posting_key", "high")
    canonical = job.get("verified_canonical_url")
    if job.get("canonical_url_verified") is True:
        key = ats_key(canonical)
        if key:
            return Identity(key, "verified_employer_url", "high")
    url = canonical_url(raw)
    if url:
        return Identity(f"url:{url}", "normalized_url", "medium")
    # A missing URL is *not* proof that same-company/same-title records are one.
    job_id = job.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Unidentified posting requires a stable job_id")
    return Identity(f"unidentified:{job_id}", "missing_url_unique", "low")


def group_postings(jobs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Non-destructive groups retaining every member, URL and source."""
    groups: dict[str, dict[str, Any]] = {}
    for job in jobs:
        identity = identity_for(job)
        group = groups.setdefault(identity.key, {
            "identity_key": identity.key,
            "identity_evidence": identity.evidence,
            "confidence": identity.confidence,
            "job_ids": [],
            "source_urls": [],
            "sources": [],
        })
        group["job_ids"].append(job.get("job_id"))
        if job.get("job_url") not in group["source_urls"]:
            group["source_urls"].append(job.get("job_url"))
        if job.get("source") not in group["sources"]:
            group["sources"].append(job.get("source"))
    return list(groups.values())

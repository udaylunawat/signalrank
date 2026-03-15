# scrapers/recruiter_finder.py
"""
RecruiterFinder — Find HR/recruiter contacts for jobs.

Strategy stack (in order, primary → fallback):
  1. Clearbit Autocomplete (free) → domain resolution
  2a. Email extraction from job descriptions (free)
  2b. DuckDuckGo Search → site:linkedin.com/in (free, primary)
  2c. SerpAPI Google → site:linkedin.com/in (fallback, uses quota)
  3.  Email pattern generation from domain + LinkedIn name
      (generates likely work emails: first@domain, first.last@domain, etc.)

No Hunter.io. No RapidAPI people-search. Works out of the box.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

TIMEOUT = 15
CLEARBIT_AUTOCOMPLETE = "https://autocomplete.clearbit.com/v1/companies/suggest"
SERPAPI_SEARCH        = "https://serpapi.com/search"
DDG_DELAY             = 2.0   # seconds between DDG calls (politeness)
SERP_DELAY            = 1.5   # seconds between SerpAPI calls
MAX_RESULTS           = 7

_NOISE_EMAIL_SIGNALS = [
    "example", "noreply", "no-reply", "pixel", "sentry", "@email", "@mail.com",
    "privacy", "legal", "support@", "help@", "info@", "abuse@", "security@",
    "unsubscribe", "donotreply", "do-not-reply", "feedback", "notifications@",
    "alerts@", "press@", "media@", "marketing@",
]
_RECRUITER_TITLE_SIGNALS = [
    "recruiter", "talent acquisition", "talent partner", "hr manager",
    "human resources", "people partner", "hiring", "sourcer", "recruiting",
    "talent management", "people ops", "workforce", "staffing", "hr generalist",
    "talent lead", "campus recruit",
]
_EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')


# ─────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────

@dataclass
class RecruiterContact:
    company:      str
    name:         Optional[str]  = None
    title:        Optional[str]  = None
    email:        Optional[str]  = None
    linkedin_url: Optional[str]  = None
    domain:       Optional[str]  = None
    source:       str            = "unknown"
    confidence:   str            = "medium"
    job_url:      Optional[str]  = None
    job_title:    Optional[str]  = None
    job_score:    Optional[str]  = None
    guessed_emails: List[str]    = field(default_factory=list)

    def display(self) -> str:
        parts = []
        if self.name:
            parts.append(self.name)
        if self.title:
            parts.append(f"({self.title})")
        if self.email:
            parts.append(f"<{self.email}>")
        if self.guessed_emails:
            parts.append(f"[guessed: {', '.join(self.guessed_emails)}]")
        if self.linkedin_url:
            parts.append(self.linkedin_url)
        parts.append(f"[{self.source}, {self.confidence}]")
        return "  ".join(parts)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Flatten guessed_emails to pipe-separated string for CSV
        d["guessed_emails"] = "|".join(self.guessed_emails) if self.guessed_emails else ""
        return d

    def uid(self) -> str:
        key = (self.linkedin_url or "") + (self.email or "") + self.company
        return hashlib.sha256(key.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────
# Strategy 1: Clearbit domain resolution
# ─────────────────────────────────────────────────────────────

def resolve_domain(company: str) -> Optional[str]:
    """Clearbit free autocomplete → domain. Falls back to slug."""
    try:
        resp = requests.get(
            CLEARBIT_AUTOCOMPLETE,
            params={"query": company},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            results = resp.json()
            if results and results[0].get("domain"):
                return results[0]["domain"]
    except Exception as e:
        logger.debug("[RECRUITER] Clearbit failed for %r: %s", company, e)

    slug = re.sub(r"[^a-z0-9]", "", re.sub(
        r"\b(limited|ltd|pvt|inc|corp|llc|co|group|solutions|technologies|"
        r"services|private|ventures)\b",
        "", company.lower()
    ).replace(" ", ""))
    return f"{slug}.com" if slug else None


# ─────────────────────────────────────────────────────────────
# Strategy 2a: Email extraction from description
# ─────────────────────────────────────────────────────────────

def _is_noise_email(email: str) -> bool:
    return any(s in email.lower() for s in _NOISE_EMAIL_SIGNALS)

def _is_recruiter_local(local: str) -> bool:
    signals = ["recruit", "talent", "hiring", "hr", "people", "careers",
               "jobs", "staffing", "workforce", "apply", "campus"]
    return any(s in local.lower() for s in signals)

def extract_emails_from_description(
    description: str, emails_col: str, company: str,
    job_url: str, job_title: str, job_score: str, domain: Optional[str],
) -> List[RecruiterContact]:
    raw = f"{description or ''} {emails_col or ''}"
    found = {e for e in _EMAIL_RE.findall(raw) if not _is_noise_email(e)}
    contacts = []
    for email in found:
        local = email.split("@")[0]
        if _is_recruiter_local(local):
            conf = "high"
        elif domain and email.lower().endswith(f"@{domain.lower()}"):
            conf = "medium"
        else:
            conf = "low"
        contacts.append(RecruiterContact(
            company=company, email=email, domain=domain,
            source="description_email", confidence=conf,
            job_url=job_url, job_title=job_title, job_score=job_score,
        ))
    return contacts


# ─────────────────────────────────────────────────────────────
# Strategy 3: Email pattern generation from name + domain
# ─────────────────────────────────────────────────────────────

def generate_email_patterns(name: str, domain: str) -> List[str]:
    """
    Given a recruiter's name and company domain, generate likely work emails.
    e.g. "Aarushi Jain" @ "adobe.com" → aarushi@adobe.com, aarushi.jain@adobe.com, etc.
    """
    if not name or not domain:
        return []
    parts = re.sub(r"[^a-zA-Z\s]", "", name).lower().split()
    if not parts:
        return []

    patterns = []
    first = parts[0]
    if len(parts) >= 2:
        last = parts[-1]
        patterns = [
            f"{first}@{domain}",
            f"{first}.{last}@{domain}",
            f"{first[0]}{last}@{domain}",
            f"{first}{last[0]}@{domain}",
            f"{first}_{last}@{domain}",
            f"{last}.{first}@{domain}",
        ]
    else:
        patterns = [f"{first}@{domain}"]

    return patterns[:5]  # cap at 5 guesses


# ─────────────────────────────────────────────────────────────
# Strategy 2b: DuckDuckGo → LinkedIn profiles (primary, free)
# ─────────────────────────────────────────────────────────────

def _is_recruiter_title(text: str) -> bool:
    return any(s in text.lower() for s in _RECRUITER_TITLE_SIGNALS)

def _parse_li_title(raw: str) -> Tuple[str, str]:
    m = re.match(r'^(.+?)\s*[-–|]\s*(.+)$', raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return raw.strip(), ""

def _clean_title(raw: str | None) -> str:
    """Truncate DDG multi-person snippet noise to the first segment.

    Splits on: newline, pipe (|), or ' - ' (spaced dash only).
    Caps result at 120 chars. Does NOT split on bare hyphens (e.g. 'Recruiter-Cognizant').
    Applied before _parse_li_title so it receives a single-person string.
    """
    if not raw:
        return ""
    for sep in ("\n", "|", " - "):
        idx = raw.find(sep)
        if idx > 0:
            raw = raw[:idx]
            break  # take only the earliest-found separator
    return raw.strip()[:120]


_FUNCTION_KEYWORDS: dict[str, list[str]] = {
    "engineering": ["engineer", "software", "backend", "frontend", "platform",
                    "infrastructure", "devops", "sre", "fullstack"],
    "ml":          ["machine learning", " ml ", "artificial intelligence", " ai ",
                    "data science", "nlp", "llm", "deep learning"],
    "product":     ["product manager", "product management", "program manager",
                    "product hiring", "product"],   # bare "product" needed for title overlap
    "data":        ["data engineer", "data analyst", "analytics", " bi "],
    "security":    ["security engineer", "infosec", "cybersecurity"],
}
_TECHNICAL_TERMS = ["technical", "tech recruiter", "engineering recruiter", "software recruiter"]


def score_recruiter(recruiter_title: str | None, job_title: str | None) -> float:
    """Return 0.0-1.0 relevance score for a recruiter contact given a job title.

    Uses _RECRUITER_TITLE_SIGNALS to confirm the person is a recruiter.
    Uses _FUNCTION_KEYWORDS to score domain relevance.

    0.0  = not a recruiter (no signal in title)
    0.3  = confirmed recruiter, no function overlap with job title
    0.5  = "technical" recruiter for an eng/ML job (generic technical affinity)
    0.7  = recruiter with specific function keyword match
    """
    if not recruiter_title:
        return 0.0
    rt = recruiter_title.lower()
    jt = (" " + (job_title or "").lower() + " ")  # pad for word-boundary matching

    if not any(s in rt for s in _RECRUITER_TITLE_SIGNALS):
        return 0.0  # not a recruiter — hard zero

    score = 0.3  # baseline: confirmed recruiter

    # Function keyword overlap
    for keywords in _FUNCTION_KEYWORDS.values():
        if any(k in jt for k in keywords) and any(k in rt for k in keywords):
            score += 0.4
            break

    # Technical affinity bonus: generic "technical recruiter" for eng/ML jobs
    if score < 0.7 and any(t in rt for t in _TECHNICAL_TERMS):
        eng_ml = _FUNCTION_KEYWORDS["engineering"] + _FUNCTION_KEYWORDS["ml"]
        if any(k in jt for k in eng_ml):
            score = max(score, 0.5)

    return min(score, 1.0)


_CONF_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2, "none": 3}


def dedup_top_n(contacts: list["RecruiterContact"], n: int = 2) -> list["RecruiterContact"]:
    """Keep the top-n most relevant recruiter contacts per job_url.

    - Groups by job_url (None/empty → '__no_url__' bucket)
    - Scores each with score_recruiter(_clean_title(title), job_title)
    - Sorts: score DESC, then _CONF_RANK ASC (lower = better confidence)
    - Excludes score == 0.0 (not a recruiter)
    - Fallback: if ALL contacts in a group score 0.0, returns top-1 by confidence
    """
    from collections import defaultdict

    by_job: dict[str, list] = defaultdict(list)
    for c in contacts:
        key = (c.job_url or "").strip() or "__no_url__"
        s = score_recruiter(_clean_title(c.title), c.job_title)
        by_job[key].append((s, _CONF_RANK.get(c.confidence, 3), c))

    result: list = []
    for entries in by_job.values():
        entries.sort(key=lambda x: (-x[0], x[1]))  # score DESC, conf_rank ASC
        qualified = [c for s, _, c in entries if s > 0.0]
        if qualified:
            result.extend(qualified[:n])
        else:
            # Fallback: best confidence when no recruiter titles found
            result.append(entries[0][2])

    return result


def search_linkedin_ddg(
    company: str, domain: Optional[str],
    job_url: str, job_title: str, job_score: str,
    location: str = "india",
) -> List[RecruiterContact]:
    """DuckDuckGo text search for LinkedIn recruiter profiles — free, no quota."""
    try:
        try:
            from ddgs import DDGS          # new package name (ddgs>=9)
        except ImportError:
            from duckduckgo_search import DDGS  # legacy fallback
    except ImportError:
        logger.warning("[RECRUITER] ddgs/duckduckgo_search not installed, skipping DDG")
        return []

    query = (
        f'site:linkedin.com/in '
        f'(recruiter OR "talent acquisition" OR "hr manager" OR "people partner") '
        f'"{company}" {location}'
    )

    contacts = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=MAX_RESULTS))

        for item in results:
            url  = item.get("href", "")
            if "linkedin.com/in/" not in url:
                continue
            title   = item.get("title", "")
            snippet = item.get("body", "")
            name, role = _parse_li_title(title)
            combined = f"{role} {snippet}"

            if not _is_recruiter_title(combined):
                continue

            guessed = generate_email_patterns(name, domain) if domain else []
            contacts.append(RecruiterContact(
                company=company, name=name,
                title=role or None,
                linkedin_url=url,
                domain=domain,
                guessed_emails=guessed,
                source="ddg_linkedin",
                confidence="high" if _is_recruiter_title(role) else "medium",
                job_url=job_url, job_title=job_title, job_score=job_score,
            ))

        logger.info("[RECRUITER] DDG: %d profiles for %r", len(contacts), company)
    except Exception as e:
        logger.warning("[RECRUITER] DDG failed for %r: %s", company, e)

    return contacts


# ─────────────────────────────────────────────────────────────
# Strategy 2c: SerpAPI → LinkedIn profiles (fallback)
# ─────────────────────────────────────────────────────────────

def search_linkedin_serpapi(
    company: str, serpapi_key: str, domain: Optional[str],
    job_url: str, job_title: str, job_score: str,
    location: str = "india",
) -> List[RecruiterContact]:
    """SerpAPI fallback when DDG returns 0 results."""
    if not serpapi_key:
        return []

    query = (
        f'site:linkedin.com/in '
        f'(recruiter OR "talent acquisition" OR "hr manager" OR "people partner") '
        f'"{company}" {location}'
    )
    try:
        resp = requests.get(
            SERPAPI_SEARCH,
            params={"engine": "google", "q": query, "api_key": serpapi_key,
                    "num": MAX_RESULTS, "hl": "en"},
            timeout=TIMEOUT,
        )
        if resp.status_code in (401, 403, 429):
            logger.warning("[RECRUITER] SerpAPI error %d", resp.status_code)
            return []
        if resp.status_code != 200:
            return []

        contacts = []
        for item in resp.json().get("organic_results", []):
            url = item.get("link", "")
            if "linkedin.com/in/" not in url:
                continue
            title   = item.get("title", "")
            snippet = item.get("snippet", "")
            name, role = _parse_li_title(title)
            combined = f"{role} {snippet}"
            if not _is_recruiter_title(combined):
                continue
            guessed = generate_email_patterns(name, domain) if domain else []
            contacts.append(RecruiterContact(
                company=company, name=name,
                title=role or None,
                linkedin_url=url,
                domain=domain,
                guessed_emails=guessed,
                source="serpapi_linkedin",
                confidence="high" if _is_recruiter_title(role) else "medium",
                job_url=job_url, job_title=job_title, job_score=job_score,
            ))

        logger.info("[RECRUITER] SerpAPI: %d profiles for %r", len(contacts), company)
        return contacts
    except Exception as e:
        logger.warning("[RECRUITER] SerpAPI failed for %r: %s", company, e)
        return []


# ─────────────────────────────────────────────────────────────
# DuckDB persistence
# ─────────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS recruiters (
    id             TEXT PRIMARY KEY,
    company        TEXT,
    name           TEXT,
    title          TEXT,
    email          TEXT,
    guessed_emails TEXT,
    linkedin_url   TEXT,
    domain         TEXT,
    source         TEXT,
    confidence     TEXT,
    job_url        TEXT,
    job_title      TEXT,
    job_score      DOUBLE,
    found_at       TIMESTAMP
)
"""

def persist_to_duckdb(contacts: List[RecruiterContact], db_path: str) -> int:
    """Upsert contacts into DuckDB. Returns count inserted/updated."""
    if not contacts:
        return 0
    try:
        import duckdb
        con = duckdb.connect(db_path)
        con.execute(_CREATE_TABLE)
        now = datetime.utcnow()
        n = 0
        for c in contacts:
            uid = c.uid()
            score = None
            try:
                score = float(c.job_score) if c.job_score else None
            except (ValueError, TypeError):
                pass
            con.execute("""
                INSERT INTO recruiters
                    (id, company, name, title, email, guessed_emails,
                     linkedin_url, domain, source, confidence,
                     job_url, job_title, job_score, found_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, title=EXCLUDED.title,
                    email=EXCLUDED.email,
                    guessed_emails=EXCLUDED.guessed_emails,
                    linkedin_url=EXCLUDED.linkedin_url,
                    domain=EXCLUDED.domain,
                    source=EXCLUDED.source,
                    confidence=EXCLUDED.confidence,
                    found_at=EXCLUDED.found_at
            """, [uid, c.company, c.name, c.title, c.email,
                  "|".join(c.guessed_emails),
                  c.linkedin_url, c.domain, c.source, c.confidence,
                  c.job_url, c.job_title, score, now])
            n += 1
        con.close()
        logger.info("[RECRUITER] Persisted %d contacts to DuckDB", n)
        return n
    except Exception as e:
        logger.warning("[RECRUITER] DuckDB persist failed: %s", e)
        return 0


# ─────────────────────────────────────────────────────────────
# Main engine
# ─────────────────────────────────────────────────────────────

class RecruiterFinder:
    def __init__(self, logger_=None, db_path: Optional[str] = None):
        self.log         = logger_ or logger
        self.serpapi_key = os.getenv("SERPAPI_KEY", "")
        self.db_path     = db_path
        self._last_ddg   = 0.0
        self._last_serp  = 0.0

    def _ddg_throttle(self):
        elapsed = time.time() - self._last_ddg
        if elapsed < DDG_DELAY:
            time.sleep(DDG_DELAY - elapsed)
        self._last_ddg = time.time()

    def _serp_throttle(self):
        elapsed = time.time() - self._last_serp
        if elapsed < SERP_DELAY:
            time.sleep(SERP_DELAY - elapsed)
        self._last_serp = time.time()

    def find(
        self,
        company: str,
        job_url: str = "",
        job_title: str = "",
        job_score: str = "",
        description: str = "",
        emails_col: str = "",
        location: str = "india",
        max_results: int = 10,
    ) -> List[RecruiterContact]:
        domain = resolve_domain(company)

        all_contacts: List[RecruiterContact] = []

        # S2a: description emails
        all_contacts.extend(extract_emails_from_description(
            description=description, emails_col=emails_col,
            company=company, job_url=job_url, job_title=job_title,
            job_score=job_score, domain=domain,
        ))

        # S2b: DDG (primary, free)
        self._ddg_throttle()
        ddg_results = search_linkedin_ddg(
            company=company, domain=domain,
            job_url=job_url, job_title=job_title, job_score=job_score,
            location=location,
        )
        all_contacts.extend(ddg_results)

        # S2c: SerpAPI (fallback — only if DDG found 0)
        if not ddg_results and self.serpapi_key:
            self.log.info("[RECRUITER] DDG empty for %r — falling back to SerpAPI", company)
            self._serp_throttle()
            all_contacts.extend(search_linkedin_serpapi(
                company=company, serpapi_key=self.serpapi_key,
                domain=domain, job_url=job_url, job_title=job_title,
                job_score=job_score, location=location,
            ))

        # Dedup
        seen_li: set = set()
        seen_em: set = set()
        unique = []
        for c in all_contacts:
            kl = (c.linkedin_url or "").lower().strip()
            ke = (c.email or "").lower().strip()
            if kl and kl in seen_li:
                continue
            if ke and ke in seen_em:
                continue
            if kl:
                seen_li.add(kl)
            if ke:
                seen_em.add(ke)
            # Clean noisy DDG snippet titles before scoring
            c.title = _clean_title(c.title)
            unique.append(c)

        # Score + dedup to top-2 per job_url (replaces raw max_results slice)
        result = dedup_top_n(unique, n=2)

        # Persist to DuckDB if configured
        if self.db_path:
            persist_to_duckdb(result, self.db_path)

        return result

    def find_from_csv(
        self,
        csv_path: str,
        top: int = 15,
        location: str = "india",
        output_csv: Optional[str] = None,
        db_path: Optional[str] = None,
    ) -> Tuple[List[dict], str]:
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError(f"CSV is empty: {csv_path}")

        if "final_score" in rows[0]:
            rows.sort(key=lambda r: float(r.get("final_score") or 0), reverse=True)

        seen: dict[str, dict] = {}
        for row in rows:
            company = (row.get("company") or "").strip()
            if not company or company.lower() in seen:
                continue
            seen[company.lower()] = row
            if len(seen) >= top:
                break

        _db = db_path or self.db_path
        self.log.info("[RECRUITER] Processing %d companies from %s", len(seen), path.name)

        all_results: List[dict] = []
        all_contacts_for_db: List[RecruiterContact] = []

        for i, (_, row) in enumerate(seen.items()):
            company   = (row.get("company") or "").strip()
            job_url   = row.get("job_url", "")
            job_title = row.get("title", "")
            job_score = row.get("final_score", "")
            description = row.get("description", "")
            emails_col  = row.get("emails", "")

            self.log.info("[RECRUITER] [%d/%d] %r", i+1, len(seen), company)

            contacts = self.find(
                company=company, job_url=job_url, job_title=job_title,
                job_score=job_score, description=description,
                emails_col=emails_col, location=location,
                max_results=10,
            )
            all_contacts_for_db.extend(contacts)

            if contacts:
                for c in contacts:
                    all_results.append(c.to_dict())
                self.log.info("[RECRUITER]  → %d contact(s)", len(contacts))
            else:
                all_results.append({
                    "company": company, "name": None, "title": None,
                    "email": None, "guessed_emails": "",
                    "linkedin_url": None, "domain": resolve_domain(company),
                    "source": "not_found", "confidence": "none",
                    "job_url": job_url, "job_title": job_title, "job_score": job_score,
                })
                self.log.info("[RECRUITER]  → no contacts found")

        # Bulk persist to DuckDB
        if _db:
            persist_to_duckdb(all_contacts_for_db, _db)

        if not output_csv:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_csv = str(path.parent / f"recruiter_contacts_{ts}.csv")

        if all_results:
            fieldnames = list(all_results[0].keys())
            with open(output_csv, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(all_results)
            self.log.info("[RECRUITER] Saved %d rows → %s", len(all_results), output_csv)

        return all_results, output_csv

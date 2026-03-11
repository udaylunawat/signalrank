"""
gmail_alerts.py — Read-only Gmail Job Alerts scraper via IMAP.

Reads Google Job Alert emails from a Gmail label and extracts
structured job listings (title, company, location, URL, description).

Security:
- IMAP connection is READ-ONLY (imaplib.IMAP4_SSL with EXAMINE, not SELECT)
- Never modifies, deletes, or marks emails
- Only reads the configured label — nothing else

Setup:
1. Enable IMAP: Gmail → Settings → Forwarding and POP/IMAP → Enable IMAP
2. Create App Password: https://myaccount.google.com/apppasswords
3. Add to .env:
       GMAIL_USER=you@gmail.com
       GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
       GMAIL_LABEL=Job Alerts/Google Alerts
"""
from __future__ import annotations

import email
import imaplib
import logging
import os
import re
from datetime import datetime, timedelta
from email.header import decode_header
from html.parser import HTMLParser
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
SENDER_FILTER = "notify-noreply@google.com"


# ─────────────────────────────────────────────
# HTML parser — extracts job cards from alert emails
# ─────────────────────────────────────────────

def _parse_jobs_from_html(html: str) -> list[dict]:
    """
    Parse Google Job Alert email HTML.

    Email structure (actual):
      <a href="https://notifications.googleapis.com/email/redirect?...">
        ...
        <td data-f=XXXXXXX>
          <div>
            <span style="cursor: pointer; color: #212121...">Job Title</span>
            <div style="color: black...">Company Name</div>
            <div style="color: #8A8A8A...">Location, Country</div>
            <div style="color: #8A8A8A...">via Source</div>
            <div>...<span>Date posted</span>...</div>
          </div>
        </td>
      </a>
    """
    jobs = []

    # Split on job card links (notifications.googleapis.com redirect links)
    card_split = re.split(
        r'<a[^>]+href="(https://notifications\.googleapis\.com/email/redirect[^"]+)"',
        html
    )

    # card_split: [pre, url1, chunk1, url2, chunk2, ...]
    for i in range(1, len(card_split), 2):
        redirect_url = card_split[i]
        chunk = card_split[i + 1] if i + 1 < len(card_split) else ""

        # Only process chunks that have job card content (data-f attribute)
        if 'data-f=' not in chunk:
            continue

        # Strip all tags to get text content in order
        # Extract in sequence: title, company, location, via, date
        texts = re.findall(r'>([^<]{2,})<', chunk)
        texts = [t.strip() for t in texts if t.strip() and not t.strip().startswith('http')]

        # Filter out noise (single chars, numbers, icons alt text)
        texts = [t for t in texts if len(t) > 2 and not re.match(r'^[\d\s]+$', t)
                 and t not in ("Time icon", "Work icon", "W", "G", "M", "A")]

        if not texts:
            continue

        title = texts[0] if len(texts) > 0 else ""
        company = texts[1] if len(texts) > 1 else ""
        location = texts[2] if len(texts) > 2 else ""

        # date: find "N Mar" / "N Feb" pattern
        date_match = re.search(r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\b', chunk)
        date_posted = date_match.group(1) if date_match else ""

        if title and company:
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": "",
                "job_url": redirect_url,  # Google redirect URL (resolves to actual job)
                "date_posted": date_posted,
            })

    return jobs


# ─────────────────────────────────────────────
# Core scraper
# ─────────────────────────────────────────────

class GmailAlertsScraper:
    """
    Read-only IMAP scraper for Google Job Alert emails.

    Uses EXAMINE (not SELECT) — guaranteed read-only, no side effects.
    """

    def __init__(
        self,
        user: Optional[str] = None,
        app_password: Optional[str] = None,
        label: Optional[str] = None,
    ):
        self.user = user or os.getenv("GMAIL_USER", "")
        self.app_password = (app_password or os.getenv("GMAIL_APP_PASSWORD", "")).replace(" ", "")
        self.label = label or os.getenv("GMAIL_LABEL", "Job Alerts/Google Alerts")

    def scrape(self, days_back: int = 7, max_emails: int = 20) -> list[dict]:
        """
        Fetch job listings from Gmail Job Alert emails.

        Args:
            days_back:   How many days of emails to look back (default 7)
            max_emails:  Max number of alert emails to read (default 20)

        Returns:
            List of job dicts: title, company, location, description, job_url, source, date_seen
        """
        if not self.user or not self.app_password:
            logger.warning(
                "[GMAIL] GMAIL_USER or GMAIL_APP_PASSWORD not set — skipping. "
                "See job_ranker/.env copy for setup instructions."
            )
            return []

        try:
            conn = self._connect()
        except Exception as e:
            logger.error("[GMAIL] Connection failed: %s", e)
            return []

        try:
            return self._fetch_jobs(conn, days_back=days_back, max_emails=max_emails)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    # ─────────────────────────────────────
    # Internal
    # ─────────────────────────────────────

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Connect and authenticate. Raises on failure."""
        logger.info("[GMAIL] Connecting to %s as %s", GMAIL_IMAP_HOST, self.user)
        conn = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
        conn.login(self.user, self.app_password)
        logger.info("[GMAIL] Authenticated ✓")
        return conn

    def _fetch_jobs(
        self,
        conn: imaplib.IMAP4_SSL,
        days_back: int,
        max_emails: int,
    ) -> list[dict]:
        """Open label read-only, search, parse jobs."""

        # EXAMINE = read-only (vs SELECT which could mark as read)
        label_imap = self._encode_label(self.label)
        status, _ = conn.select(f'"{label_imap}"', readonly=True)

        if status != "OK":
            # Try without quotes
            status, _ = conn.select(label_imap, readonly=True)
            if status != "OK":
                logger.error("[GMAIL] Could not open label %r — check GMAIL_LABEL in .env", self.label)
                return []

        logger.info("[GMAIL] Opened label %r (read-only)", self.label)

        # Search for job alert emails within days_back
        since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
        status, msg_ids = conn.search(
            None,
            f'(FROM "{SENDER_FILTER}" SINCE {since_date})',
        )

        if status != "OK" or not msg_ids[0]:
            logger.info("[GMAIL] No job alert emails found in last %d days", days_back)
            return []

        ids = msg_ids[0].split()
        # Most recent first
        ids = list(reversed(ids))[:max_emails]
        logger.info("[GMAIL] Found %d alert emails (reading up to %d)", len(msg_ids[0].split()), len(ids))

        all_jobs: list[dict] = []
        seen_urls: set[str] = set()

        for msg_id in ids:
            try:
                jobs = self._parse_email(conn, msg_id)
                for job in jobs:
                    url = job.get("job_url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_jobs.append(job)
            except Exception as e:
                logger.warning("[GMAIL] Failed to parse email id=%s: %s", msg_id, e)
                continue

        logger.info("[GMAIL] Extracted %d unique jobs from %d emails", len(all_jobs), len(ids))
        return all_jobs

    def _parse_email(self, conn: imaplib.IMAP4_SSL, msg_id: bytes) -> list[dict]:
        """Fetch and parse a single email."""
        status, data = conn.fetch(msg_id, "(RFC822)")
        if status != "OK":
            return []

        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        # Get email date
        date_str = msg.get("Date", "")
        try:
            from email.utils import parsedate_to_datetime
            date_seen = parsedate_to_datetime(date_str).date().isoformat()
        except Exception:
            date_seen = datetime.now().date().isoformat()

        # Get subject (for logging)
        subject_raw = msg.get("Subject", "")
        subject, enc = decode_header(subject_raw)[0]
        if isinstance(subject, bytes):
            subject = subject.decode(enc or "utf-8", errors="replace")
        logger.debug("[GMAIL] Parsing: %s", subject)

        # Extract HTML body
        html_body = ""
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                charset = part.get_content_charset() or "utf-8"
                html_body = part.get_payload(decode=True).decode(charset, errors="replace")
                break

        if not html_body:
            return []

        # Parse job cards
        jobs = []
        for job in _parse_jobs_from_html(html_body):
            if job.get("title") and job.get("job_url"):
                job["source"] = "google_alerts"
                if not job.get("date_posted"):
                    job["date_posted"] = date_seen
                jobs.append(job)

        return jobs

    @staticmethod
    def _encode_label(label: str) -> str:
        """Convert label path to IMAP format (Gmail uses / as separator)."""
        # Gmail IMAP uses UTF-7 for non-ASCII but labels like "Job Alerts/Google Alerts" work as-is
        return label


# ─────────────────────────────────────────────
# Convenience function for scraper.py
# ─────────────────────────────────────────────

def scrape_gmail_alerts(days_back: int = 7, max_emails: int = 20) -> list[dict]:
    """Drop-in function for use in job_ranker scraping pipeline."""
    return GmailAlertsScraper().scrape(days_back=days_back, max_emails=max_emails)

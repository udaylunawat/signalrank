"""
Test script for Gmail Job Alerts IMAP scraper.
Run this on your laptop (NOT in Docker — needs outbound imap.gmail.com:993).

Usage:
    cd ~/Projects/job_ranker
    uv run python job_ranker/tests/test_gmail_alerts.py

Prerequisites:
    1. Gmail → Settings → Forwarding and POP/IMAP → Enable IMAP
    2. https://myaccount.google.com/apppasswords → create App Password
    3. Add to job_ranker/.env:
           GMAIL_USER=examplecandidate@gmail.com
           GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
           GMAIL_LABEL=Job Alerts/Google Alerts
"""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv
load_dotenv()

from job_ranker.scrapers.gmail_alerts import GmailAlertsScraper


def main():
    user = os.getenv("GMAIL_USER", "")
    pwd = os.getenv("GMAIL_APP_PASSWORD", "")
    label = os.getenv("GMAIL_LABEL", "Job Alerts/Google Alerts")

    if not user or not pwd:
        print("\n❌ GMAIL_USER or GMAIL_APP_PASSWORD not set in .env")
        print("   See job_ranker/.env copy for setup instructions.")
        sys.exit(1)

    print(f"\n🔌 Connecting to Gmail as {user}")
    print(f"   Label: {label}")
    print(f"   Days back: 14, Max emails: 10\n")

    scraper = GmailAlertsScraper(user=user, app_password=pwd, label=label)
    jobs = scraper.scrape(days_back=14, max_emails=10)

    if not jobs:
        print("\n⚠️  No jobs found. Possible reasons:")
        print("   - No job alert emails in the last 14 days in that label")
        print("   - Wrong label name (check GMAIL_LABEL in .env)")
        print("   - IMAP not enabled in Gmail settings")
        return

    print(f"\n✅ Found {len(jobs)} jobs:\n")
    for i, job in enumerate(jobs[:10], 1):
        print(f"  {i:2}. {job['title']}")
        print(f"      {job['company']} | {job['location']}")
        print(f"      {job['job_url'][:80]}...")
        print()


if __name__ == "__main__":
    main()

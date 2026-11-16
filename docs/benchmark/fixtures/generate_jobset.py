#!/usr/bin/env python3
"""Generate *synthetic*, fully offline adversarial job-ranking/identity fixtures.

No real employers, jobs, links, resumes, accounts, or web calls are used.
This checks contract/invariant behavior, NOT real-world ranking accuracy.
Run: python3 docs/benchmark/fixtures/generate_jobset.py
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
SNAPSHOT = date(2026, 11, 17)
COMPANIES = (
    "Acme Data Lab", "Northwind Labs", "Contoso Tech", "Fabrikam Systems",
    "Blue Willow Analytics", "Exampleworks", "Mockridge", "Sample Dynamics",
)

# (title, description, location, relevance 0..3, special exclusion)
# The first two scenarios intentionally have the SAME title for each company
# but different requisitions/duties: merging them is a false positive.
SCENARIOS = (
    ("Senior Data Engineer", "Own batch and streaming data pipelines in Python, Spark, Airflow and SQL. Build reliable analytics platforms and production ETL.", "Pune, India", 3, ""),
    ("Senior Data Engineer", "Design warehouses and governed marts using dbt, BigQuery and SQL. Own ingestion quality, lineage and data modeling.", "Pune, India", 3, ""),
    ("Data Platform Engineer", "Build cloud data infrastructure on GCP, orchestration and streaming ingestion using Python and Kafka.", "Remote - India", 3, ""),
    ("MLOps Engineer", "Operate model serving, deployment and feature pipelines using Python, Kubernetes and GCP.", "Bengaluru, India", 2, ""),
    ("AI Platform Engineer", "Develop LLM evaluation and retrieval infrastructure, Python APIs and distributed workloads.", "Mumbai, India", 2, ""),
    ("Backend Engineer", "Develop Python backend APIs with event-driven services and several core ETL pipelines.", "Pune, India", 2, ""),
    ("Data Scientist", "Conduct experimentation, statistics and product analysis with Python and SQL; no pipeline ownership.", "Remote - India", 1, ""),
    ("Data Analyst", "Build KPI dashboards, reporting queries and business analysis in SQL and Power BI.", "Mumbai, India", 1, ""),
    ("Junior Data Engineer", "Entry-level training role building simple Python data scripts and SQL queries. No production ownership.", "Pune, India", 1, "junior"),
    ("Principal Data Engineer", "Lead architecture across a 30-person organization. Requires 14+ years and principal-level leadership.", "Remote - India", 1, "seniority"),
    ("Frontend Engineer", "Build browser interfaces with React, Next.js, CSS and accessibility tooling.", "Pune, India", 0, "role"),
    ("QA Automation Engineer", "Build UI automation with Selenium and Playwright. Python is only used in small tests.", "Bengaluru, India", 0, "role"),
    ("Product Manager", "Define product roadmaps, stakeholder priorities and user research, no engineering implementation.", "Mumbai, India", 0, "role"),
    ("Senior Data Engineer", "Build production Spark and Python pipelines in a five-day on-site office role in California only.", "San Francisco, USA (on-site)", 0, "geography"),
    ("Senior Data Engineer (contract)", "Six-month part-time contract developing Python ETL jobs, SQL models and orchestration.", "Remote - India", 1, "contract"),
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    profile = {
        "profile_id": "synthetic-data-platform-5yoe",
        "synthetic": True,
        "snapshot_date": SNAPSHOT.isoformat(),
        "target_roles": ["Data Engineer", "Data Platform Engineer", "AI Platform Engineer"],
        "preferred_locations": ["Pune, India", "Mumbai, India", "Bengaluru, India", "Remote - India"],
        "skills": ["Python", "SQL", "Spark", "Airflow", "dbt", "GCP", "Docker", "Kafka"],
        "experience_years": 5,
        "exclude": ["internships", "pure people management", "non-India-only on-site", "short contract"],
        "resume_text": "Synthetic candidate: 5 years building data platforms with Python, SQL, Spark, Airflow, dbt and GCP. No identity or contact details.",
    }
    public: list[dict] = []
    gold: list[dict] = []
    originals: list[tuple[dict, dict]] = []

    # 15 hand-authored scenario types x 8 fictional companies = 120 distinct
    # openings. The grade is defined independently of generated descriptions.
    for scenario_i, (title, description, location, grade, exclusion) in enumerate(SCENARIOS):
        for company_i, company in enumerate(COMPANIES):
            i = scenario_i * len(COMPANIES) + company_i
            posting_key = f"TEST-REQ-{i + 1:04d}"
            posted_date = (SNAPSHOT - timedelta(days=(i * 13) % 151)).isoformat()
            active = i % 17 != 0
            simulated_link_status = (
                "mock_410" if not active
                else "mock_429" if i % 23 == 0
                else "mock_200"
            )
            source = ("synthetic_greenhouse", "synthetic_lever", "synthetic_ashby")[i % 3]
            record = {
                "job_id": f"J{i + 1:04d}",
                "source": source,
                "job_url": f"https://jobs.example.invalid/{source}/{posting_key}",
                "title": title,
                "company": company,
                "location": location,
                "description": f"{description} Test employer: {company}. Reference: {posting_key}.",
                "posted_date": posted_date,
            }
            truth = {
                "job_id": record["job_id"],
                "duplicate_group": posting_key,
                "relevance_grade": grade,
                "eligible": not exclusion in {"geography", "contract"} and active,
                "source_is_synthetic": True,
                "is_active_label": active,
                "simulated_link_status": simulated_link_status,
                "exclusion_reason": exclusion or None,
                "snapshot_date": SNAPSHOT.isoformat(),
            }
            originals.append((record, truth))
            public.append(record)
            gold.append(truth)

    # 30 cross-source copies of known requisitions, preserving original truth.
    # They must be grouped by opening despite the second URL; do not remove
    # either original source URL from job-source provenance.
    for i in range(30):
        original, label = originals[i]
        copy = {
            **original,
            "job_id": f"X{i + 1:04d}",
            "source": "synthetic_aggregator",
            "job_url": f"https://boards.example.invalid/listings/{label['duplicate_group']}?src=aggregator",
            "description": original["description"] + " Cross-listed through a synthetic job board.",
        }
        public.append(copy)
        gold.append({**label, "job_id": copy["job_id"]})

    assert len(public) == 150 and len(gold) == 150
    (OUT / "profile.json").write_text(
        json.dumps(profile, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_jsonl(OUT / "jobs-public.jsonl", public)
    write_jsonl(OUT / "gold.jsonl", gold)
    print(f"Generated {len(public)} synthetic postings, {len(originals)} identity groups")
    print("Do not make HTTP requests to example.invalid; simulated link labels are mock-only.")


if __name__ == "__main__":
    main()

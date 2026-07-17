import argparse
import asyncio
import hashlib
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.database import _build_engine, initialize_database
from api.models import JobRaw
from batch.ingest import SourceReport, refresh_job_catalog
from batch.ranker import score_jobs_for_user
from llm.resume_parser import _heuristic_parse


@dataclass(frozen=True)
class Category:
    slug: str
    label: str
    target_roles: tuple[str, ...]
    search_terms: tuple[str, ...]
    skills: tuple[str, ...]
    relevance_terms: tuple[str, ...]


CATEGORIES = (
    Category(
        "data_science",
        "Data science",
        ("Data Scientist", "Data Analyst"),
        (
            "Data Scientist",
            "Data Analyst",
            "Analytics Engineer",
            "Data Engineer",
            "ML Scientist",
            "BI Analyst",
        ),
        ("Python", "SQL", "Pandas", "scikit-learn", "statistics", "Tableau"),
        ("data scientist", "data analyst", "analytics engineer", "data engineer"),
    ),
    Category(
        "ai",
        "AI",
        ("AI Engineer", "ML Engineer"),
        (
            "AI Engineer",
            "ML Engineer",
            "LLM Engineer",
            "MLOps Engineer",
            "Applied Scientist",
            "NLP Engineer",
        ),
        ("Python", "PyTorch", "TensorFlow", "NLP", "LLM", "MLOps"),
        (
            "ai engineer",
            "ml engineer",
            "machine learning",
            "llm engineer",
            "mlops",
            "applied scientist",
        ),
    ),
    Category(
        "fde",
        "Forward-deployed engineering",
        ("Forward Deployed Engineer", "Solutions Engineer"),
        (
            "Forward Deployed Engineer",
            "Solutions Engineer",
            "Customer Engineer",
            "Implementation Engineer",
            "Technical Consultant",
            "Deployment Engineer",
        ),
        ("Python", "TypeScript", "SQL", "REST", "Docker", "Kubernetes"),
        (
            "forward deployed",
            "solutions engineer",
            "customer engineer",
            "implementation engineer",
            "technical consultant",
        ),
    ),
    Category(
        "sap",
        "SAP",
        ("SAP Consultant", "SAP S/4HANA Consultant"),
        (
            "SAP Consultant",
            "SAP S/4HANA Consultant",
            "SAP FICO",
            "SAP ABAP",
            "SAP Fiori",
            "SAP Basis",
        ),
        ("SAP S/4HANA", "SAP FI/CO", "SAP MM", "ABAP", "Fiori", "SAP BW"),
        ("sap", "s/4hana", "abap", "fiori", "fico"),
    ),
    Category(
        "innovation",
        "Innovation",
        ("Innovation Manager", "Digital Transformation Manager"),
        (
            "Innovation Manager",
            "Digital Transformation Manager",
            "Innovation Strategist",
            "Product Innovation Manager",
            "Venture Builder",
            "R&D Manager",
        ),
        (
            "innovation strategy",
            "product discovery",
            "design thinking",
            "roadmapping",
            "agile",
            "stakeholder management",
        ),
        (
            "innovation",
            "digital transformation",
            "innovation strategist",
            "product innovation",
            "venture builder",
            "r&d",
        ),
    ),
    Category(
        "testing",
        "Testing",
        ("QA Automation Engineer", "SDET"),
        (
            "QA Automation Engineer",
            "SDET",
            "Test Automation Engineer",
            "QA Engineer",
            "Software Engineer in Test",
            "API Test Engineer",
        ),
        ("Selenium", "Playwright", "Python", "API testing", "Cypress", "CI/CD"),
        (
            "qa",
            "quality",
            "sdet",
            "test automation",
            "engineer in test",
            "software tester",
        ),
    ),
    Category(
        "frontend",
        "Frontend",
        ("Frontend Developer", "React Developer"),
        (
            "Frontend Developer",
            "Front-End Engineer",
            "React Developer",
            "UI Engineer",
            "JavaScript Developer",
            "TypeScript Developer",
        ),
        ("JavaScript", "TypeScript", "React", "Next.js", "HTML", "CSS"),
        (
            "frontend",
            "front-end",
            "react developer",
            "ui engineer",
            "javascript developer",
            "typescript developer",
        ),
    ),
)


def default_report_dir() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "benchmarks"
        / "2026-07-15-primary-lane"
    )


def candidate_text(category: Category, number: int) -> str:
    years = number + 2
    skills = ", ".join(category.skills)
    role = category.target_roles[number % len(category.target_roles)]
    return f"""Benchmark Candidate {category.slug.upper()} {number:02d}

Professional Summary
{role} with {years} years of experience delivering measurable outcomes across distributed teams.

Technical Skills
{skills}

Professional Experience
{role} | Benchmark Organization | India | 20{14 + number % 10}-Present
- Delivered product and customer outcomes using {category.skills[0]} and {category.skills[1]}.
- Partnered with stakeholders to ship reliable production workflows and improve adoption.
- Improved quality, delivery speed, and operational visibility through iterative experiments.

Education
Bachelor of Technology, Computer Science
"""


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    values = [[cell(value) for value in row] for row in rows]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in values)
    return "\n".join(lines)


def write_markdown(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")


def title_is_relevant(title: object, category: Category) -> bool:
    value = str(title or "").casefold()
    return any(term in value for term in category.relevance_terms)


def lane_metrics(ranked: pd.DataFrame, category: Category) -> dict[str, float | int]:
    top = ranked.head(10)
    lanes = top.get("match_lane", pd.Series(dtype=str)).tolist()
    primary_positions = [
        index for index, lane in enumerate(ranked.get("match_lane", []), start=1) if lane == "primary"
    ]
    broader_positions = [
        index for index, lane in enumerate(ranked.get("match_lane", []), start=1) if lane == "broader"
    ]
    has_primary = bool(primary_positions)
    violation = bool(
        has_primary
        and broader_positions
        and min(broader_positions) < max(primary_positions)
    )
    relevant = sum(title_is_relevant(row.title, category) for row in top.itertuples())
    top_count = len(top)
    return {
        "primary_available": int(has_primary),
        "primary_top10_share": sum(lane == "primary" for lane in lanes) / top_count
        if top_count
        else 0.0,
        "primary_first": int(bool(lanes and lanes[0] == "primary")),
        "ordering_violation": int(violation),
        "first_primary_rank": min(primary_positions) if primary_positions else 0,
        "precision_at_10_proxy": relevant / top_count if top_count else 0.0,
        "ranked_job_count": len(ranked),
    }


def aggregate_metrics(rows: list[dict]) -> dict[str, float | int]:
    count = len(rows)
    primary_eligible = [row for row in rows if row["primary_available"]]
    return {
        "candidates": count,
        "primary_eligible": len(primary_eligible),
        "primary_top10_share": sum(row["primary_top10_share"] for row in rows) / count,
        "primary_first_rate": sum(row["primary_first"] for row in primary_eligible)
        / len(primary_eligible)
        if primary_eligible
        else 0.0,
        "ordering_violations": sum(row["ordering_violation"] for row in rows),
        "mean_first_primary_rank": sum(
            row["first_primary_rank"] for row in primary_eligible
        )
        / len(primary_eligible)
        if primary_eligible
        else 0.0,
        "precision_at_10_proxy": sum(row["precision_at_10_proxy"] for row in rows)
        / count,
        "mean_ranked_job_count": sum(row["ranked_job_count"] for row in rows) / count,
    }


def metric_row(label: str, metrics: dict[str, float | int]) -> list[object]:
    return [
        label,
        metrics["candidates"],
        metrics["primary_eligible"],
        f"{float(metrics['primary_top10_share']):.1%}",
        f"{float(metrics['primary_first_rate']):.1%}",
        metrics["ordering_violations"],
        f"{float(metrics['mean_first_primary_rank']):.2f}",
        f"{float(metrics['precision_at_10_proxy']):.1%}",
        f"{float(metrics['mean_ranked_job_count']):.1f}",
    ]


async def collect_catalog(
    factory: async_sessionmaker,
) -> tuple[list[tuple[Category, SourceReport]], dict[str, int]]:
    reports: list[tuple[Category, SourceReport]] = []
    async with factory() as db:
        for category in CATEGORIES:
            result = await refresh_job_catalog(
                db,
                roles=list(category.search_terms),
                locations=["India"],
            )
            reports.extend((category, report) for report in result.reports)
        source_counts = dict(
            (
                str(site or "unknown"),
                count,
            )
            for site, count in (
                await db.execute(
                    select(JobRaw.site, func.count()).group_by(JobRaw.site)
                )
            ).all()
        )
    return reports, source_counts


async def score_candidates(
    factory: async_sessionmaker, embedding_device: str
) -> dict[str, dict[str, list[dict]]]:
    results = {"pre_fix": {}, "post_fix": {}}
    for category in CATEGORIES:
        pre_rows: list[dict] = []
        post_rows: list[dict] = []
        async with factory() as db:
            for number in range(1, 11):
                candidate_id = f"{category.slug}-{number:02d}"
                resume = candidate_text(category, number)
                parsed = _heuristic_parse(resume)
                config = {
                    "embeddings": {"device": embedding_device},
                    "profile_intent": {"roles": list(category.target_roles)},
                    "location_scoring": {
                        "preferred_locations": ["India"],
                        "preferred_weight": 1.4,
                    },
                    "company_preferences": {"filter_mode": "all", "tiers": ["any"]},
                }
                kwargs = {
                    "db": db,
                    "user_id": candidate_id,
                    "resume_text": resume,
                    "distilled_text": (
                        "Recent roles: "
                        + ", ".join(parsed.recent_titles)
                        + "\nSkills: "
                        + ", ".join(parsed.skills)
                    ),
                    "resume_skills": parsed.skills,
                    "config_overrides": config,
                }
                pre = await score_jobs_for_user(
                    **kwargs,
                    prioritize_primary_lane=False,
                )
                post = await score_jobs_for_user(
                    **kwargs,
                    prioritize_primary_lane=True,
                )
                pre_metric = lane_metrics(pre, category)
                post_metric = lane_metrics(post, category)
                base = {
                    "candidate_id": candidate_id,
                    "parse_status": parsed.status,
                    "parse_confidence": parsed.confidence,
                    "extracted_skills": len(parsed.skills),
                }
                pre_rows.append(
                    {**base, **pre_metric, "top_titles": pre["title"].head(5).tolist()}
                )
                post_rows.append(
                    {**base, **post_metric, "top_titles": post["title"].head(5).tolist()}
                )
            await db.commit()
        results["pre_fix"][category.slug] = pre_rows
        results["post_fix"][category.slug] = post_rows
    return results


def phase_two_markdown(
    reports: list[tuple[Category, SourceReport]], source_counts: dict[str, int]
) -> str:
    status_counts = Counter(report.status for _, report in reports)
    rows = [
        [
            category.label,
            report.source,
            report.query or "—",
            report.location or "—",
            report.status,
            report.jobs_found,
            report.jobs_persisted,
            report.duration_ms,
            report.error_summary or "—",
        ]
        for category, report in reports
    ]
    return f"""# Phase 2 — Frozen catalog collection

Collected at {datetime.now(timezone.utc).isoformat()}.

## Summary

- Frozen catalog size: **{sum(source_counts.values())}** active jobs.
- Source totals: {", ".join(f"{source}: {count}" for source, count in sorted(source_counts.items())) or "none"}.
- Source terminal statuses: {", ".join(f"{status}: {count}" for status, count in sorted(status_counts.items())) or "none"}.
- JobSpy used its bounded request and refresh budgets. An `error` or `empty` report is valid telemetry and does not invalidate the frozen catalog.

## Source telemetry

{markdown_table(["Category", "Source", "Query", "Location", "Status", "Found", "Persisted", "ms", "Error"], rows)}
"""


def phase_three_markdown(
    results: dict[str, dict[str, list[dict]]], embedding_device: str
) -> str:
    rows = []
    top_samples = []
    for category in CATEGORIES:
        pre = aggregate_metrics(results["pre_fix"][category.slug])
        post = aggregate_metrics(results["post_fix"][category.slug])
        rows.extend(
            [
                [category.label, *metric_row("Pre-fix", pre)],
                [category.label, *metric_row("Post-fix", post)],
            ]
        )
        sample = results["post_fix"][category.slug][0]
        top_samples.append(
            [
                category.label,
                "<br>".join(str(title) for title in sample["top_titles"]),
            ]
        )
    overall_pre = aggregate_metrics(
        [row for rows_by_category in results["pre_fix"].values() for row in rows_by_category]
    )
    overall_post = aggregate_metrics(
        [row for rows_by_category in results["post_fix"].values() for row in rows_by_category]
    )
    rows.extend(
        [
            ["Overall", *metric_row("Pre-fix", overall_pre)],
            ["Overall", *metric_row("Post-fix", overall_post)],
        ]
    )
    return f"""# Phase 3 — Pre-fix versus post-fix ranking

Both variants use the same frozen catalog, 70 PII-free resumes, extracted skills, target roles, locations, embeddings, and score weights. The only difference is final ordering: score-only pre-fix versus primary-lane-first post-fix. Embeddings were computed locally on `{embedding_device}`.

## A/B metrics

{markdown_table(["Category", "Variant", "Candidates", "Primary eligible", "Primary top-10 share", "Primary-first rate", "Violations", "Mean first primary rank", "P@10 proxy", "Mean ranked jobs"], rows)}

An ordering violation means a broader result appears above a primary result when primary results exist.

## Post-fix top-five samples

{markdown_table(["Category", "Candidate 01 top five titles"], top_samples)}
"""


def phase_four_markdown(results: dict[str, dict[str, list[dict]]]) -> str:
    pre_rows = [
        row for rows_by_category in results["pre_fix"].values() for row in rows_by_category
    ]
    post_rows = [
        row for rows_by_category in results["post_fix"].values() for row in rows_by_category
    ]
    pre = aggregate_metrics(pre_rows)
    post = aggregate_metrics(post_rows)
    passed = int(post["ordering_violations"] == 0)
    return f"""# Phase 4 — Assessment

## Outcome

- Primary/broader ordering gate: **{"passed" if passed else "failed"}**.
- Pre-fix ordering violations: **{pre["ordering_violations"]}**.
- Post-fix ordering violations: **{post["ordering_violations"]}**.
- Primary top-10 share: **{float(pre["primary_top10_share"]):.1%} → {float(post["primary_top10_share"]):.1%}**.
- Primary-first rate among primary-eligible candidates: **{float(pre["primary_first_rate"]):.1%} → {float(post["primary_first_rate"]):.1%}**.
- Automated title-family Precision@10 proxy: **{float(pre["precision_at_10_proxy"]):.1%} → {float(post["precision_at_10_proxy"]):.1%}**.

## Interpretation

The ordering A/B is causal for the lane fix because it replays the same candidate/job score frames. It does not establish absolute ranking quality: the title-family precision metric is an automated proxy, not a recruiter label.

## Next assessment gate

Label the top 20 post-fix jobs for one canonical resume in each category as relevant, adjacent, or irrelevant. Feed relevant labels to `scripts/evaluate_rankings.py` and require Precision@10, Recall@20, and NDCG@10/20 to remain stable or improve before changing score weights.
"""


async def run(
    report_dir: Path,
    scratch_dir: Path,
    reset: bool,
    reuse_catalog: bool,
    embedding_device: str,
) -> None:
    if scratch_dir.exists() and any(scratch_dir.iterdir()):
        if reset:
            shutil.rmtree(scratch_dir)
        elif not reuse_catalog:
            raise RuntimeError(
                f"Scratch directory is not empty: {scratch_dir}. Pass --reset to replace it."
            )
    scratch_dir.mkdir(parents=True, exist_ok=True)
    database_path = scratch_dir / "signalrank-primary-lane.db"
    if reuse_catalog and not database_path.exists():
        raise RuntimeError(f"Frozen catalog does not exist: {database_path}")
    engine = _build_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    if not reuse_catalog:
        await initialize_database(engine)
        reports, source_counts = await collect_catalog(factory)
        write_markdown(
            report_dir / "phase-2-catalog-collection.md",
            phase_two_markdown(reports, source_counts),
        )
    results = await score_candidates(factory, embedding_device)
    write_markdown(
        report_dir / "phase-3-ranking-ab.md",
        phase_three_markdown(results, embedding_device),
    )
    write_markdown(report_dir / "phase-4-assessment.md", phase_four_markdown(results))
    digest = hashlib.sha256(database_path.read_bytes()).hexdigest()
    write_markdown(
        report_dir / "phase-4-assessment.md",
        (report_dir / "phase-4-assessment.md").read_text(encoding="utf-8")
        + f"\n## Reproducibility\n\nFrozen catalog SHA-256: `{digest}`.\n",
    )
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path, default=default_report_dir())
    parser.add_argument(
        "--scratch-dir",
        type=Path,
        default=Path(__file__).resolve().parents[3]
        / ".benchmark"
        / "primary-lane",
    )
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--reuse-catalog", action="store_true")
    parser.add_argument("--embedding-device", choices=("cpu", "mps"), default="cpu")
    args = parser.parse_args()
    asyncio.run(
        run(
            args.report_dir,
            args.scratch_dir,
            args.reset,
            args.reuse_catalog,
            args.embedding_device,
        )
    )


if __name__ == "__main__":
    main()

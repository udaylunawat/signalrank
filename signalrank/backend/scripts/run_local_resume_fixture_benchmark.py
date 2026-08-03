import argparse
import asyncio
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.database import _build_engine, initialize_database
from batch.ingest import (
    IngestResult,
    SearchRequest,
    build_query_plan,
    refresh_job_catalog,
)
from batch.ranker import score_jobs_for_user
from llm.resume_parser import _heuristic_parse

_FIXTURE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    sha256: str
    canonical_id: str
    is_canonical: bool
    target_roles: tuple[str, ...]
    preferred_locations: tuple[str, ...]
    max_yoe: int | None


@dataclass(frozen=True)
class FixtureAudit:
    fixture_id: str
    canonical_id: str
    is_canonical: bool
    extracted_text: bool
    has_skills: bool
    has_titles: bool
    has_yoe: bool
    has_skill_evidence: bool
    has_experiences: bool
    has_declared_yoe: bool
    has_computed_yoe: bool
    ranking_attempted: bool
    ranked_job_count: int
    primary_available: bool
    primary_top10_share: float


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_resume_dir() -> Path:
    return project_root() / "test_resumes"


def default_catalog_path() -> Path:
    return project_root() / ".benchmark" / "primary-lane" / "signalrank-primary-lane.db"


def default_output_dir() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return project_root() / ".benchmark" / "private-resumes" / timestamp


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        item.strip() for item in value if isinstance(item, str) and item.strip()
    )


def load_manifest(path: Path) -> list[Fixture]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("fixtures") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a non-empty fixtures list")

    fixtures: list[Fixture] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each fixture manifest entry must be an object")
        fixture_id = str(entry.get("id", "")).strip()
        canonical_id = str(entry.get("canonical_id", "")).strip()
        digest = str(entry.get("sha256", "")).strip().casefold()
        if not _FIXTURE_ID.fullmatch(fixture_id):
            raise ValueError("Fixture IDs must be opaque lowercase identifiers")
        if not _FIXTURE_ID.fullmatch(canonical_id):
            raise ValueError("Canonical IDs must be opaque lowercase identifiers")
        if not _SHA256.fullmatch(digest):
            raise ValueError("Fixture SHA-256 values must be lowercase hex digests")
        max_yoe = entry.get("max_yoe")
        if max_yoe is not None and (
            not isinstance(max_yoe, int) or not 0 < max_yoe < 60
        ):
            raise ValueError("max_yoe must be an integer from 1 through 59")
        fixtures.append(
            Fixture(
                fixture_id=fixture_id,
                sha256=digest,
                canonical_id=canonical_id,
                is_canonical=bool(entry.get("is_canonical")),
                target_roles=_string_list(entry.get("target_roles")),
                preferred_locations=_string_list(entry.get("preferred_locations")),
                max_yoe=max_yoe,
            )
        )

    if len({fixture.fixture_id for fixture in fixtures}) != len(fixtures):
        raise ValueError("Fixture IDs must be unique")
    if len({fixture.sha256 for fixture in fixtures}) != len(fixtures):
        raise ValueError("Fixture SHA-256 values must be unique")
    canonical_counts: dict[str, int] = {}
    for fixture in fixtures:
        canonical_counts[fixture.canonical_id] = canonical_counts.get(
            fixture.canonical_id, 0
        ) + int(fixture.is_canonical)
    invalid = [key for key, value in canonical_counts.items() if value != 1]
    if invalid:
        raise ValueError("Each canonical candidate must have one canonical fixture")
    return fixtures


def find_registered_pdfs(resume_dir: Path, fixtures: list[Fixture]) -> dict[str, Path]:
    discovered = {sha256_file(path): path for path in resume_dir.glob("*.pdf")}
    expected = {fixture.sha256 for fixture in fixtures}
    if len(discovered) != len(list(resume_dir.glob("*.pdf"))):
        raise ValueError("PDF byte hashes must be unique")
    if set(discovered) != expected:
        raise ValueError("Manifest and local PDF corpus must contain the same files")
    return discovered


def extract_pdf_text(path: Path) -> str:
    import pypdf

    reader = pypdf.PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def copy_sqlite_catalog(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Frozen catalog is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)


def _ranking_config(fixture: Fixture) -> dict:
    config: dict = {
        "profile_intent": {"roles": list(fixture.target_roles)},
        "location_scoring": {
            "preferred_locations": list(fixture.preferred_locations),
            "preferred_weight": 1.4,
        },
        "company_preferences": {"filter_mode": "all", "tiers": ["any"]},
    }
    if fixture.max_yoe is not None:
        config["experience"] = {"max_yoe": fixture.max_yoe}
    return config


def ranking_metrics(ranked: pd.DataFrame) -> tuple[int, bool, float]:
    lanes = ranked.head(10).get("match_lane", pd.Series(dtype=str)).tolist()
    top_count = len(lanes)
    return (
        len(ranked),
        bool((ranked.get("match_lane", pd.Series(dtype=str)) == "primary").any()),
        sum(lane == "primary" for lane in lanes) / top_count if top_count else 0.0,
    )


def verified_profile_source_inputs(
    fixtures: list[Fixture],
) -> tuple[list[str], list[str]]:
    roles: list[str] = []
    locations: list[str] = []
    for fixture in fixtures:
        if not fixture.is_canonical:
            continue
        for value, values in (
            (fixture.target_roles, roles),
            (fixture.preferred_locations, locations),
        ):
            for item in value:
                if item.casefold() not in {existing.casefold() for existing in values}:
                    values.append(item)
    if not roles:
        raise ValueError("Fresh collection requires verified target roles")
    return roles, locations or ["India"]


def verified_profile_query_plan(fixtures: list[Fixture]) -> list[SearchRequest]:
    requests: list[SearchRequest] = []
    seen: set[tuple[str, str]] = set()
    for fixture in fixtures:
        if not fixture.is_canonical:
            continue
        locations = fixture.preferred_locations or ("India",)
        for role in fixture.target_roles:
            for location in locations:
                request = build_query_plan([role], locations=[location], max_queries=1)[
                    0
                ]
                key = (request.query.casefold(), request.location.casefold())
                if key not in seen:
                    requests.append(request)
                    seen.add(key)
    if not requests:
        raise ValueError("Fresh collection requires verified target roles")
    return requests


async def collect_verified_profile_catalog(
    fixtures: list[Fixture],
    catalog_path: Path,
    max_queries: int,
    max_query_batches: int,
) -> tuple[dict[str, object], list[dict]]:
    unbounded_plan = verified_profile_query_plan(fixtures)
    batches = [
        unbounded_plan[index : index + max_queries]
        for index in range(0, len(unbounded_plan), max_queries)
    ]
    if len(batches) > max_query_batches:
        raise ValueError(
            "Verified profile queries exceed the configured bounded query batches"
        )
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    engine = _build_engine(f"sqlite+aiosqlite:///{catalog_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await initialize_database(engine)
        async with factory() as db:
            results = [
                await refresh_job_catalog(db, query_plan=batch) for batch in batches
            ]
        statuses: dict[str, int] = {}
        for result in results:
            for report in result.reports:
                statuses[report.status] = statuses.get(report.status, 0) + 1
        provenance = source_provenance_rows(results)
        return {
            "query_count": len(unbounded_plan),
            "batch_count": len(batches),
            "jobs_discovered": sum(result.jobs_discovered for result in results),
            "jobs_persisted": sum(result.jobs_persisted for result in results),
            "report_statuses": statuses,
            "provenance_rows": len(provenance),
        }, provenance
    finally:
        await engine.dispose()


def source_provenance_rows(results: list[IngestResult]) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for result in results:
        for report in result.reports:
            for job_url in report.job_urls:
                key = (
                    report.source,
                    report.query or "",
                    report.location or "",
                    job_url,
                )
                if key in seen:
                    continue
                rows.append(
                    {
                        "source": report.source,
                        "query": report.query,
                        "location": report.location,
                        "job_url": job_url,
                    }
                )
                seen.add(key)
    return rows


def ranking_rows(
    fixture: Fixture, ranked: pd.DataFrame, label_depth: int
) -> tuple[list[dict], list[dict]]:
    ranking: list[dict] = []
    labels: list[dict] = []
    for rank, row in enumerate(ranked.head(label_depth).itertuples(), start=1):
        job_id = str(row.id)
        ranking.append(
            {
                "fixture_id": fixture.fixture_id,
                "job_id": job_id,
                "rank": rank,
                "match_lane": str(row.match_lane),
            }
        )
        labels.append(
            {
                "fixture_id": fixture.fixture_id,
                "job_id": job_id,
                "rank": rank,
                "match_lane": str(row.match_lane),
                "title": str(row.title or ""),
                "company": str(row.company or ""),
                "location": str(row.location or ""),
                "job_url": str(row.job_url or ""),
                "relevance_grade": None,
                "error_tags": [],
                "reason": "",
            }
        )
    return ranking, labels


async def audit_fixtures(
    fixtures: list[Fixture],
    pdfs: dict[str, Path],
    catalog_path: Path,
    embedding_device: str,
    label_depth: int,
) -> tuple[list[FixtureAudit], list[dict], list[dict]]:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    engine = _build_engine(f"sqlite+aiosqlite:///{catalog_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    audits: list[FixtureAudit] = []
    ranked_rows: list[dict] = []
    label_rows: list[dict] = []
    try:
        # The frozen catalog predates optional cached enrichment. Create only
        # missing tables in its private copy so unassessed listings stay neutral.
        await initialize_database(engine)
        async with factory() as db:
            for fixture in fixtures:
                text = extract_pdf_text(pdfs[fixture.sha256])
                parsed = _heuristic_parse(text)
                ranked = pd.DataFrame()
                ranking_attempted = bool(
                    fixture.is_canonical and fixture.target_roles and text.strip()
                )
                if ranking_attempted:
                    distilled = "\n".join(
                        filter(
                            None,
                            [
                                (
                                    "Recent roles: " + ", ".join(parsed.recent_titles)
                                    if parsed.recent_titles
                                    else ""
                                ),
                                (
                                    "Skills: " + ", ".join(parsed.skills)
                                    if parsed.skills
                                    else ""
                                ),
                            ],
                        )
                    )
                    ranked = await score_jobs_for_user(
                        db=db,
                        user_id=fixture.fixture_id,
                        resume_text=text,
                        distilled_text=distilled,
                        resume_skills=parsed.skills,
                        config_overrides={
                            **_ranking_config(fixture),
                            "embeddings": {"device": embedding_device},
                        },
                    )
                    fixture_ranking_rows, fixture_label_rows = ranking_rows(
                        fixture, ranked, label_depth
                    )
                    ranked_rows.extend(fixture_ranking_rows)
                    label_rows.extend(fixture_label_rows)
                ranked_count, primary_available, primary_share = ranking_metrics(ranked)
                audits.append(
                    FixtureAudit(
                        fixture_id=fixture.fixture_id,
                        canonical_id=fixture.canonical_id,
                        is_canonical=fixture.is_canonical,
                        extracted_text=bool(text.strip()),
                        has_skills=bool(parsed.skills),
                        has_titles=bool(parsed.recent_titles),
                        has_yoe=parsed.years_of_experience is not None,
                        has_skill_evidence=bool(parsed.skill_evidence),
                        has_experiences=bool(parsed.experiences),
                        has_declared_yoe=(
                            parsed.declared_years_of_experience is not None
                        ),
                        has_computed_yoe=(
                            parsed.computed_years_of_experience is not None
                        ),
                        ranking_attempted=ranking_attempted,
                        ranked_job_count=ranked_count,
                        primary_available=primary_available,
                        primary_top10_share=primary_share,
                    )
                )
            await db.commit()
    finally:
        await engine.dispose()
    return audits, ranked_rows, label_rows


def render_report(
    audits: list[FixtureAudit],
    catalog_sha256: str,
    label_row_count: int,
    source_collection: dict[str, object] | None = None,
) -> str:
    fixture_count = len(audits)
    canonical_count = len({audit.canonical_id for audit in audits})
    canonical_audits = {
        audit.canonical_id: audit for audit in audits if audit.is_canonical
    }
    rankable = [audit for audit in canonical_audits.values() if audit.ranking_attempted]
    primary_eligible = [audit for audit in rankable if audit.primary_available]
    source_section = "- Source collection: reused frozen catalog."
    if source_collection:
        statuses = source_collection["report_statuses"]
        status_summary = (
            ", ".join(
                f"{status}: {count}" for status, count in sorted(statuses.items())
            )
            or "none"
        )
        source_section = (
            "- Source collection: bounded refresh from verified profile inputs only; "
            f"{source_collection['query_count']} queries in "
            f"{source_collection['batch_count']} batches, "
            f"{source_collection['jobs_discovered']} discovered, "
            f"{source_collection['jobs_persisted']} persisted, "
            f"{source_collection['provenance_rows']} provenance records, "
            f"reports {status_summary}."
        )
    return f"""# Phase 2 - Private local resume ranking and label queue

## Privacy contract

- PDF names, content, parsed fields, candidate/job samples, and labels are not written here.
- Parsing uses the deterministic heuristic only; this runner cannot call an external LLM.
- The frozen job catalog is copied before ranking so the source snapshot is unchanged.
- The private JSONL label queue contains opaque fixture IDs and job metadata, never resume data.

## Corpus and parser coverage

- PDF fixtures: **{fixture_count}**.
- Distinct canonical candidates: **{canonical_count}**.
- Text extraction success: **{sum(audit.extracted_text for audit in audits)}/{fixture_count}**.
- Non-empty skills: **{sum(audit.has_skills for audit in audits)}/{fixture_count}**.
- Non-empty titles: **{sum(audit.has_titles for audit in audits)}/{fixture_count}**.
- Explicit years of experience found: **{sum(audit.has_yoe for audit in audits)}/{fixture_count}**.
- Grounded skill evidence: **{sum(audit.has_skill_evidence for audit in audits)}/{fixture_count}**.
- Grounded work experiences: **{sum(audit.has_experiences for audit in audits)}/{fixture_count}**.
- Explicitly declared experience: **{sum(audit.has_declared_yoe for audit in audits)}/{fixture_count}**.
- Date-computed experience: **{sum(audit.has_computed_yoe for audit in audits)}/{fixture_count}**.

## Ranking coverage

{source_section}
- Canonical fixtures ranked with verified target roles: **{len(rankable)}/{canonical_count}**.
- Primary-eligible ranked fixtures: **{len(primary_eligible)}/{len(rankable)}**.
- Mean primary top-10 share: **{sum(audit.primary_top10_share for audit in primary_eligible) / len(primary_eligible) if primary_eligible else 0.0:.1%}**.

## Relevance-label queue

- Top-ranked job records queued for review: **{label_row_count}**.
- Review decisions are deliberately blank in `relevance-labels.jsonl`. Set
  `relevance_grade` to 0 (irrelevant), 1 (adjacent), 2 (good), or 3 (strong),
  then use generic `error_tags` only for grades 0 or 1. These judgements come
  from the candidate's verified target profile, not from the runner's
  primary/broader lane.

## Reproducibility

Frozen catalog SHA-256: `{catalog_sha256}`.
"""


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as destination:
        for row in rows:
            destination.write(json.dumps(row, sort_keys=True) + "\n")


async def run(
    *,
    resume_dir: Path,
    manifest_path: Path,
    catalog_path: Path,
    output_dir: Path,
    embedding_device: str,
    label_depth: int,
    refresh_catalog: bool = False,
    max_queries: int = 6,
    max_query_batches: int = 1,
) -> Path:
    fixtures = load_manifest(manifest_path)
    pdfs = find_registered_pdfs(resume_dir, fixtures)
    copied_catalog = output_dir / "catalog.db"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_collection = None
    provenance_rows: list[dict] = []
    if refresh_catalog:
        source_collection, provenance_rows = await collect_verified_profile_catalog(
            fixtures, copied_catalog, max_queries, max_query_batches
        )
    else:
        catalog_sha256 = sha256_file(catalog_path)
        copy_sqlite_catalog(catalog_path, copied_catalog)
    catalog_sha256 = sha256_file(copied_catalog)
    audits, ranked_rows, label_rows = await audit_fixtures(
        fixtures, pdfs, copied_catalog, embedding_device, label_depth
    )
    write_jsonl(output_dir / "ranking.jsonl", ranked_rows)
    write_jsonl(output_dir / "relevance-labels.jsonl", label_rows)
    if refresh_catalog:
        write_jsonl(output_dir / "source-provenance.jsonl", provenance_rows)
    report_path = output_dir / "phase-2-ranking-and-label-queue.md"
    report_path.write_text(
        render_report(audits, catalog_sha256, len(label_rows), source_collection),
        encoding="utf-8",
    )
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-dir", type=Path, default=default_resume_dir())
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--catalog-db", type=Path, default=default_catalog_path())
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--embedding-device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--label-depth", type=int, default=20)
    parser.add_argument("--refresh-catalog", action="store_true")
    parser.add_argument("--max-queries", type=int, default=6)
    parser.add_argument("--max-query-batches", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.label_depth <= 100:
        parser.error("--label-depth must be between 1 and 100")
    if not 1 <= args.max_queries <= 6:
        parser.error("--max-queries must be between 1 and 6")
    if not 1 <= args.max_query_batches <= 6:
        parser.error("--max-query-batches must be between 1 and 6")
    manifest = args.manifest or args.resume_dir / "manifest.local.yaml"
    report = asyncio.run(
        run(
            resume_dir=args.resume_dir,
            manifest_path=manifest,
            catalog_path=args.catalog_db,
            output_dir=args.output_dir,
            embedding_device=args.embedding_device,
            label_depth=args.label_depth,
            refresh_catalog=args.refresh_catalog,
            max_queries=args.max_queries,
            max_query_batches=args.max_query_batches,
        )
    )
    print(f"Private fixture report written: {report}")


if __name__ == "__main__":
    main()

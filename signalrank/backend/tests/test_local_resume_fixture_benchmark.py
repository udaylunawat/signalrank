import sqlite3

import pandas as pd
import pytest

from scripts.run_local_resume_fixture_benchmark import (
    FixtureAudit,
    copy_sqlite_catalog,
    load_manifest,
    ranking_rows,
    render_report,
)


def write_manifest(path, fixtures):
    path.write_text("fixtures:\n" + "\n".join(fixtures), encoding="utf-8")


def fixture_entry(*, fixture_id, digest, canonical_id, is_canonical):
    return "\n".join(
        [
            f"  - id: {fixture_id}",
            f"    sha256: {digest}",
            f"    canonical_id: {canonical_id}",
            f"    is_canonical: {str(is_canonical).lower()}",
            "    target_roles: []",
            "    preferred_locations: [India]",
        ]
    )


def test_manifest_requires_exactly_one_canonical_fixture(tmp_path):
    manifest = tmp_path / "manifest.local.yaml"
    write_manifest(
        manifest,
        [
            fixture_entry(
                fixture_id="candidate-01",
                digest="a" * 64,
                canonical_id="candidate-01",
                is_canonical=False,
            )
        ],
    )

    with pytest.raises(ValueError, match="one canonical fixture"):
        load_manifest(manifest)


def test_manifest_rejects_non_opaque_fixture_ids(tmp_path):
    manifest = tmp_path / "manifest.local.yaml"
    write_manifest(
        manifest,
        [
            fixture_entry(
                fixture_id="Jane-Doe",
                digest="a" * 64,
                canonical_id="candidate-01",
                is_canonical=True,
            )
        ],
    )

    with pytest.raises(ValueError, match="opaque"):
        load_manifest(manifest)


def test_report_contains_aggregate_metrics_only():
    report = render_report(
        [
            FixtureAudit(
                fixture_id="candidate-01",
                canonical_id="candidate-01",
                is_canonical=True,
                extracted_text=True,
                has_skills=True,
                has_titles=False,
                has_yoe=True,
                ranking_attempted=False,
                ranked_job_count=0,
                primary_available=False,
                primary_top10_share=0.0,
            )
        ],
        "a" * 64,
        0,
    )

    assert "PDF names, content, parsed fields" in report
    assert "candidate-01" not in report
    assert "private resume text" not in report


def test_ranking_rows_keep_resume_data_out_of_label_queue(tmp_path):
    fixture = load_manifest_fixture(tmp_path)
    ranked = pd.DataFrame(
        [
            {
                "id": "job-01",
                "match_lane": "primary",
                "title": "Sample job",
                "company": "Example company",
                "location": "Pune",
                "job_url": "https://example.test/jobs/01",
            }
        ]
    )

    ranking, labels = ranking_rows(fixture, ranked, label_depth=20)

    assert ranking == [
        {
            "fixture_id": "candidate-01",
            "job_id": "job-01",
            "rank": 1,
            "match_lane": "primary",
        }
    ]
    assert labels[0]["relevant"] is None
    assert "resume_text" not in labels[0]
    assert "skills" not in labels[0]


def load_manifest_fixture(tmp_path):
    manifest = """fixtures:
  - id: candidate-01
    sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    canonical_id: candidate-01
    is_canonical: true
    target_roles: [QA Automation Engineer]
    preferred_locations: [Pune]
"""
    path = tmp_path / "manifest.local.yaml"
    path.write_text(manifest, encoding="utf-8")
    return load_manifest(path)[0]


def test_catalog_copy_preserves_source_database(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "destination.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE jobs (title TEXT)")
        connection.execute("INSERT INTO jobs VALUES ('private source job')")

    copy_sqlite_catalog(source, destination)

    with sqlite3.connect(destination) as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone() == (1,)
    with sqlite3.connect(source) as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone() == (1,)

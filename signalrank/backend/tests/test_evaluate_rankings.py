import pytest

from scripts.compare_ranking_evaluations import compare_evaluations
from scripts.evaluate_rankings import evaluate_label_files
from scripts.migrate_relevance_labels import migrate_legacy_labels


def test_evaluate_label_files_reports_macro_metrics_and_generic_error_counts():
    result = evaluate_label_files(
        [
            {"fixture_id": "candidate-01", "job_id": "job-01", "rank": 1},
            {"fixture_id": "candidate-01", "job_id": "job-02", "rank": 2},
            {"fixture_id": "candidate-02", "job_id": "job-01", "rank": 1},
        ],
        [
            {
                "fixture_id": "candidate-01",
                "job_id": "job-01",
                "relevance_grade": 3,
                "error_tags": [],
            },
            {
                "fixture_id": "candidate-01",
                "job_id": "job-02",
                "relevance_grade": 0,
                "error_tags": ["location_or_work_mode"],
            },
            {
                "fixture_id": "candidate-02",
                "job_id": "job-01",
                "relevance_grade": None,
                "error_tags": [],
            },
        ],
        (1, 2),
    )

    assert result["fixtures"] == 2
    assert result["reviewed_jobs"] == 2
    assert result["grade_counts"] == {"0": 1, "1": 0, "2": 0, "3": 1}
    assert result["error_tag_counts"] == {"location_or_work_mode": 1}
    assert result["macro_metrics"]["review_coverage_at_1"] == 0.5


def test_evaluate_label_files_rejects_unreviewed_error_tags():
    with pytest.raises(ValueError, match="only valid"):
        evaluate_label_files(
            [{"fixture_id": "candidate-01", "job_id": "job-01", "rank": 1}],
            [
                {
                    "fixture_id": "candidate-01",
                    "job_id": "job-01",
                    "relevance_grade": None,
                    "error_tags": ["other"],
                }
            ],
            (1,),
        )


def test_legacy_labels_migrate_without_assuming_error_tags():
    migrated = migrate_legacy_labels(
        [
            {"fixture_id": "candidate-01", "job_id": "job-01", "relevant": True},
            {"fixture_id": "candidate-01", "job_id": "job-02", "relevant": False},
            {"fixture_id": "candidate-01", "job_id": "job-03", "relevant": None},
        ]
    )

    assert [row["relevance_grade"] for row in migrated] == [2, 0, None]
    assert all(row["error_tags"] == [] for row in migrated)
    assert all("relevant" not in row for row in migrated)


def test_comparison_gate_rejects_primary_lane_and_quality_regression():
    baseline_ranking = [
        {
            "fixture_id": "candidate-01",
            "job_id": "job-01",
            "rank": 1,
            "match_lane": "primary",
        },
        {
            "fixture_id": "candidate-01",
            "job_id": "job-02",
            "rank": 2,
            "match_lane": "primary",
        },
        {
            "fixture_id": "candidate-01",
            "job_id": "job-03",
            "rank": 3,
            "match_lane": "primary",
        },
        {
            "fixture_id": "candidate-01",
            "job_id": "job-04",
            "rank": 4,
            "match_lane": "primary",
        },
        {
            "fixture_id": "candidate-01",
            "job_id": "job-05",
            "rank": 5,
            "match_lane": "primary",
        },
        {
            "fixture_id": "candidate-01",
            "job_id": "job-06",
            "rank": 6,
            "match_lane": "primary",
        },
        {
            "fixture_id": "candidate-01",
            "job_id": "job-07",
            "rank": 7,
            "match_lane": "primary",
        },
        {
            "fixture_id": "candidate-01",
            "job_id": "job-08",
            "rank": 8,
            "match_lane": "primary",
        },
        {
            "fixture_id": "candidate-01",
            "job_id": "job-09",
            "rank": 9,
            "match_lane": "primary",
        },
        {
            "fixture_id": "candidate-01",
            "job_id": "job-10",
            "rank": 10,
            "match_lane": "primary",
        },
    ]
    labels = [
        {
            "fixture_id": "candidate-01",
            "job_id": row["job_id"],
            "relevance_grade": 2 if row["rank"] <= 5 else 0,
            "error_tags": [],
        }
        for row in baseline_ranking
    ]
    candidate_ranking = [dict(row, match_lane="broader") for row in baseline_ranking]
    candidate_ranking[0], candidate_ranking[-1] = (
        candidate_ranking[-1],
        candidate_ranking[0],
    )
    candidate_ranking[0]["rank"] = 1
    candidate_ranking[-1]["rank"] = 10

    result = compare_evaluations(baseline_ranking, labels, candidate_ranking, labels)

    assert not result["passed"]
    assert not result["gates"]["primary_top10_share"]
    assert not result["gates"]["judged_precision_at_5"]

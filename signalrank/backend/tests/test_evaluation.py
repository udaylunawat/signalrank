from domain.evaluation import evaluate_graded_ranking, evaluate_ranking


def test_evaluate_ranking_reports_precision_recall_and_ndcg():
    metrics = evaluate_ranking(
        ["good-first", "noise", "good-third"],
        ["good-first", "good-third", "missed"],
        cutoffs=(2, 3),
    )

    assert metrics["precision_at_2"] == 0.5
    assert metrics["recall_at_3"] == 2 / 3
    assert 0 < metrics["ndcg_at_3"] < 1


def test_graded_evaluation_keeps_unreviewed_jobs_separate_from_negative_labels():
    metrics = evaluate_graded_ranking(
        ["strong", "unreviewed", "adjacent", "irrelevant"],
        {"strong": 3, "adjacent": 1, "irrelevant": 0},
        cutoffs=(2, 4),
    )

    assert metrics["reviewed_count"] == 3
    assert metrics["unreviewed_count"] == 1
    assert metrics["review_coverage_at_2"] == 0.5
    assert metrics["judged_precision_at_4"] == 1 / 3
    assert 0 < metrics["graded_ndcg_at_4"] < 1

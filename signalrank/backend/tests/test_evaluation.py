from domain.evaluation import evaluate_ranking


def test_evaluate_ranking_reports_precision_recall_and_ndcg():
    metrics = evaluate_ranking(
        ["good-first", "noise", "good-third"],
        ["good-first", "good-third", "missed"],
        cutoffs=(2, 3),
    )

    assert metrics["precision_at_2"] == 0.5
    assert metrics["recall_at_3"] == 2 / 3
    assert 0 < metrics["ndcg_at_3"] < 1

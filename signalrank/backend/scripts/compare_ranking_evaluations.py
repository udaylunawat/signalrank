import argparse
import json
from pathlib import Path

from scripts.evaluate_rankings import _read_jsonl, evaluate_label_files

_GATED_METRICS = (
    "judged_precision_at_5",
    "judged_precision_at_10",
    "graded_ndcg_at_10",
)


def _primary_share(ranking_rows: list[dict]) -> tuple[int, float]:
    lanes_by_fixture: dict[str, list[tuple[int, str]]] = {}
    for row in ranking_rows:
        fixture_id = row.get("fixture_id")
        job_id = row.get("job_id")
        rank = row.get("rank")
        lane = row.get("match_lane")
        if (
            not isinstance(fixture_id, str)
            or not isinstance(job_id, str)
            or type(rank) is not int
            or rank < 1
            or not isinstance(lane, str)
        ):
            raise ValueError(
                "Ranking rows must include fixture_id, job_id, rank, and match_lane"
            )
        lanes_by_fixture.setdefault(fixture_id, []).append((rank, lane))
    shares = []
    for rows in lanes_by_fixture.values():
        top = sorted(rows)[:10]
        shares.append(
            sum(lane == "primary" for _, lane in top) / len(top) if top else 0.0
        )
    return len(shares), sum(shares) / len(shares) if shares else 0.0


def compare_evaluations(
    baseline_ranking: list[dict],
    baseline_labels: list[dict],
    candidate_ranking: list[dict],
    candidate_labels: list[dict],
) -> dict:
    baseline = evaluate_label_files(baseline_ranking, baseline_labels, (5, 10, 20))
    candidate = evaluate_label_files(candidate_ranking, candidate_labels, (5, 10, 20))
    baseline_fixtures, baseline_primary = _primary_share(baseline_ranking)
    candidate_fixtures, candidate_primary = _primary_share(candidate_ranking)
    if baseline_fixtures != candidate_fixtures:
        raise ValueError(
            "Baseline and candidate must cover the same number of fixtures"
        )
    if (
        baseline["macro_metrics"]["review_coverage_at_10"] < 1
        or candidate["macro_metrics"]["review_coverage_at_10"] < 1
    ):
        raise ValueError(
            "Both comparisons require complete review coverage through rank 10"
        )

    deltas = {
        metric: candidate["macro_metrics"][metric] - baseline["macro_metrics"][metric]
        for metric in _GATED_METRICS
    }
    deltas["primary_top10_share"] = candidate_primary - baseline_primary
    gates = {metric: delta >= 0 for metric, delta in deltas.items()}
    return {
        "fixtures": baseline_fixtures,
        "baseline": {
            "primary_top10_share": baseline_primary,
            "macro_metrics": {
                metric: baseline["macro_metrics"][metric] for metric in _GATED_METRICS
            },
        },
        "candidate": {
            "primary_top10_share": candidate_primary,
            "macro_metrics": {
                metric: candidate["macro_metrics"][metric] for metric in _GATED_METRICS
            },
        },
        "deltas": deltas,
        "gates": gates,
        "passed": all(gates.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ranking", type=Path, required=True)
    parser.add_argument("--baseline-labels", type=Path, required=True)
    parser.add_argument("--candidate-ranking", type=Path, required=True)
    parser.add_argument("--candidate-labels", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare_evaluations(
        _read_jsonl(args.baseline_ranking),
        _read_jsonl(args.baseline_labels),
        _read_jsonl(args.candidate_ranking),
        _read_jsonl(args.candidate_labels),
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

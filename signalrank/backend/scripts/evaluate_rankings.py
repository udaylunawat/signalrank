import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from domain.evaluation import ERROR_TAGS, RELEVANCE_GRADES, evaluate_graded_ranking


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _key(row: dict) -> tuple[str, str]:
    fixture_id = row.get("fixture_id")
    job_id = row.get("job_id")
    if not isinstance(fixture_id, str) or not fixture_id:
        raise ValueError("Each row must contain a non-empty fixture_id")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Each row must contain a non-empty job_id")
    return fixture_id, job_id


def _label_grade(row: dict) -> int | None:
    grade = row.get("relevance_grade")
    if grade is None:
        return None
    if type(grade) is not int or grade not in RELEVANCE_GRADES:
        raise ValueError("relevance_grade must be 0, 1, 2, 3, or null")
    return grade


def _label_tags(row: dict, grade: int | None) -> list[str]:
    tags = row.get("error_tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("error_tags must be a list of strings")
    if len(tags) != len(set(tags)) or any(tag not in ERROR_TAGS for tag in tags):
        raise ValueError("error_tags contains an unknown or duplicate value")
    if tags and (grade is None or grade >= 2):
        raise ValueError("error_tags are only valid for reviewed grades 0 or 1")
    return tags


def _cutoffs(value: str) -> tuple[int, ...]:
    try:
        cutoffs = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Cutoffs must be comma-separated integers"
        ) from error
    if not cutoffs or any(cutoff <= 0 for cutoff in cutoffs):
        raise argparse.ArgumentTypeError("Cutoffs must be positive integers")
    return cutoffs


def evaluate_label_files(
    ranking_rows: list[dict], label_rows: list[dict], cutoffs: tuple[int, ...]
) -> dict:
    rankings: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for row in ranking_rows:
        fixture_id, job_id = _key(row)
        rank = row.get("rank")
        if type(rank) is not int or rank < 1:
            raise ValueError("Ranking rows must contain a positive integer rank")
        rankings[fixture_id].append((rank, job_id))

    labels: dict[tuple[str, str], tuple[int | None, list[str]]] = {}
    for row in label_rows:
        key = _key(row)
        if key in labels:
            raise ValueError("Label rows must be unique per fixture and job")
        grade = _label_grade(row)
        labels[key] = (grade, _label_tags(row, grade))

    error_counts: Counter[str] = Counter()
    grade_counts: Counter[int] = Counter()
    fixture_metrics: list[dict[str, float]] = []
    total_ranked = 0
    for fixture_id, rows in rankings.items():
        rows.sort()
        ranked = [job_id for _, job_id in rows]
        if len(ranked) != len(set(ranked)):
            raise ValueError("Ranking rows must be unique per fixture and job")
        grades: dict[str, int | None] = {}
        for job_id in ranked:
            grade, tags = labels.get((fixture_id, job_id), (None, []))
            grades[job_id] = grade
            if grade is not None:
                grade_counts[grade] += 1
            error_counts.update(tags)
        fixture_metrics.append(evaluate_graded_ranking(ranked, grades, cutoffs))
        total_ranked += len(ranked)

    unknown_labels = set(labels) - {
        (fixture_id, job_id)
        for fixture_id, rows in rankings.items()
        for _, job_id in rows
    }
    if unknown_labels:
        raise ValueError("Every label must correspond to a ranking row")

    reviewed = sum(metric["reviewed_count"] for metric in fixture_metrics)
    metrics = (
        {
            key: sum(metric[key] for metric in fixture_metrics) / len(fixture_metrics)
            for key in fixture_metrics[0]
        }
        if fixture_metrics
        else {}
    )
    return {
        "fixtures": len(fixture_metrics),
        "ranked_jobs": total_ranked,
        "reviewed_jobs": int(reviewed),
        "unreviewed_jobs": int(total_ranked - reviewed),
        "fixtures_with_reviews": sum(
            metric["reviewed_count"] > 0 for metric in fixture_metrics
        ),
        "grade_counts": {
            str(grade): grade_counts[grade] for grade in sorted(RELEVANCE_GRADES)
        },
        "error_tag_counts": dict(sorted(error_counts.items())),
        "macro_metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--ranking", type=Path, required=True)
    parser.add_argument("--cutoffs", type=_cutoffs, default=(5, 10, 20))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    labels = _read_jsonl(args.labels)
    ranking = _read_jsonl(args.ranking)
    result = evaluate_label_files(ranking, labels, args.cutoffs)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

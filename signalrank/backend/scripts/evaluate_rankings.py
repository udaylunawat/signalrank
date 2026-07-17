import argparse
import json
from pathlib import Path

from domain.evaluation import evaluate_ranking


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--ranking", type=Path, required=True)
    args = parser.parse_args()
    labels = _read_jsonl(args.labels)
    ranking = _read_jsonl(args.ranking)
    relevant = [row["job_id"] for row in labels if row.get("relevant")]
    ranked = [row["job_id"] for row in ranking]
    print(json.dumps(evaluate_ranking(ranked, relevant), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

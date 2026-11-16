#!/usr/bin/env python3
"""Evaluate offline JSONL ranking predictions against synthetic fixture gold.

This is a contract test for fixture behavior, NOT a live product accuracy test.

Usage:
  python3 docs/benchmark/fixtures/evaluate_predictions.py \
    --pred path/to/predictions.jsonl

Each prediction: {"job_id":"J0001","score":0.85,"rank":1}
If rank is absent, file order is used. Unknown IDs and duplicate IDs are errors.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent
K = 10


def rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def dcg(grades: list[int]) -> float:
    return sum((2 ** grade - 1) / math.log2(pos + 2) for pos, grade in enumerate(grades))


def grade_of(label: dict) -> int:
    return int(label["relevance_grade"]) if label["eligible"] else 0


def evaluate(predictions: list[dict], jobs: list[dict], gold: list[dict]) -> dict:
    truth = {r["job_id"]: r for r in gold}
    posting = {r["job_id"]: r for r in jobs}
    if len(truth) != len(gold) or len(posting) != len(jobs):
        raise ValueError("Fixture job IDs must be unique")

    ids: list[str] = []
    for record in predictions:
        job_id = record.get("job_id")
        if not isinstance(job_id, str) or job_id not in truth:
            raise ValueError(f"Unknown/invalid job ID: {job_id!r}")
        ids.append(job_id)
    if len(ids) != len(set(ids)):
        raise ValueError("Prediction repeats one job_id")

    ordered = sorted(enumerate(predictions), key=lambda pair: (
        pair[1].get("rank", pair[0] + 1), pair[0]
    ))
    top = [record["job_id"] for _, record in ordered[:K]]
    grades = [grade_of(truth[jid]) for jid in top]
    groups = [truth[jid]["duplicate_group"] for jid in top]
    seen: set[str] = set()
    effective_grades: list[int] = []
    for group, grade in zip(groups, grades):
        effective_grades.append(grade if group not in seen else 0)
        seen.add(group)

    # Ideal ranking is over unique opening identities, not over 2 URLs
    # of the same job (duplicates must not inflate ideal relevance).
    best: dict[str, int] = {}
    for label in gold:
        group = label["duplicate_group"]
        best[group] = max(best.get(group, 0), grade_of(label))
    ideal = sorted(best.values(), reverse=True)[:K]
    if len(ideal) < K:
        ideal += [0] * (K - len(ideal))
    norm = dcg(ideal)

    snapshot = date.fromisoformat(gold[0]["snapshot_date"])
    stale = sum(
        (snapshot - date.fromisoformat(posting[jid]["posted_date"])).days > 30
        for jid in top
    )
    mock_dead = sum(
        truth[jid]["simulated_link_status"] == "mock_410"
        for jid in top
    )
    return {
        "dataset": "synthetic-contract-fixture",
        "profile": "synthetic-data-platform-5yoe",
        "k": K,
        "predicted_count": len(predictions),
        "precision_at_10": round(sum(g >= 2 for g in effective_grades) / K, 4),
        "ndcg_at_10": round(dcg(effective_grades) / norm, 4) if norm else None,
        "duplicate_exposures_at_10": len(groups) - len(set(groups)),
        "stale_exposures_at_10": stale,
        "mock_expired_exposures_at_10": mock_dead,
        "notes": "Only synthetic fixture results; not evidence of real-world relevance, freshness, link availability, or UX.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pred", required=True, type=Path)
    args = parser.parse_args()
    output = evaluate(
        rows(args.pred),
        rows(FIXTURES / "jobs-public.jsonl"),
        rows(FIXTURES / "gold.jsonl"),
    )
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

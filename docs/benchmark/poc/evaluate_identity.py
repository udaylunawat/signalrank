#!/usr/bin/env python3
"""Offline identity benchmark: source-code-inspired baselines vs POC.

Uses fictional URLs, opening IDs, employers and candidate data exclusively.
The legacy baselines approximate *specific key forms* in June SignalRank;
they do not execute or claim to measure its live backend. Outputs are not
cross-application performance results.

Run: python3 docs/benchmark/poc/evaluate_identity.py
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path
import re
from typing import Callable

from posting_identity import canonical_url, identity_for

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().casefold())


def url_key(job: dict) -> str:
    """Approximate existing URL-first ingestion upsert key."""
    return normalize(job["job_url"])


def title_company_key(job: dict) -> str:
    """Exact company/title match from June ranker's final display reduction."""
    return normalize(job["company"]) + "|" + normalize(job["title"])


def title_company_location_key(job: dict) -> str:
    """Approximate June pre-embedding candidate selection key."""
    return title_company_key(job) + "|" + normalize(job["location"])


def conservative_identity_key(job: dict) -> str:
    return identity_for(job).key


def same_group_pairs(groups: dict[str, list[str]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for ids in groups.values():
        for a, b in combinations(sorted(ids), 2):
            pairs.add((a, b))
    return pairs


def benchmark(
    jobs: list[dict], gold: list[dict], key_fn: Callable[[dict], str]
) -> dict:
    if len({row["job_id"] for row in jobs}) != len(jobs):
        raise ValueError("Duplicate job IDs in input")
    truth = {row["job_id"]: row["duplicate_group"] for row in gold}
    if set(truth) != {row["job_id"] for row in jobs}:
        raise ValueError("Every input job must have a truth label")

    expected_groups: dict[str, list[str]] = defaultdict(list)
    predicted_groups: dict[str, list[str]] = defaultdict(list)
    for job in jobs:
        job_id = job["job_id"]
        expected_groups[truth[job_id]].append(job_id)
        predicted_groups[key_fn(job)].append(job_id)

    expected = same_group_pairs(expected_groups)
    predicted = same_group_pairs(predicted_groups)
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else 0.0
    return {
        "input_listings": len(jobs),
        "real_openings_in_synthetic_gold": len(expected_groups),
        "predicted_groups": len(predicted_groups),
        "gold_duplicate_pairs": len(expected),
        "predicted_duplicate_pairs": len(predicted),
        "correct_pairs": tp,
        "false_merges": fp,
        "missed_duplicate_pairs": fn,
        "pair_precision": round(precision, 4) if precision is not None else None,
        "pair_recall": round(recall, 4) if recall is not None else None,
        "pair_f1": round(f1, 4),
    }


def main() -> None:
    jobs = load_jsonl(FIXTURES / "jobs-public.jsonl")
    gold = load_jsonl(FIXTURES / "gold.jsonl")
    baselines = {
        "URL-only (approx June ingest)": url_key,
        "Company+title (approx June final matches)": title_company_key,
        "Company+title+location (approx June pre-embed)": title_company_location_key,
        "ATS-aware identity (new isolated POC)": conservative_identity_key,
    }
    results = {name: benchmark(jobs, gold, fn) for name, fn in baselines.items()}
    print(json.dumps({
        "dataset": "synthetic-adversarial-identity-fixture",
        "evidence": "Offline POC; legacy key functions approximated from source, not an executed SignalRank backend.",
        "results": results,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

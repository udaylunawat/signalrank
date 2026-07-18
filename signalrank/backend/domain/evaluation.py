from __future__ import annotations

from math import log2
from typing import Iterable

RELEVANCE_GRADES = frozenset(range(4))
ERROR_TAGS = frozenset(
    {
        "role_scope",
        "skills_or_domain",
        "seniority",
        "location_or_work_mode",
        "employment_terms",
        "listing_quality",
        "other",
    }
)


def evaluate_ranking(
    ranked_job_ids: Iterable[str],
    relevant_job_ids: Iterable[str],
    cutoffs: tuple[int, ...] = (20, 100),
) -> dict[str, float]:
    ranked = list(dict.fromkeys(str(job_id) for job_id in ranked_job_ids))
    relevant = {str(job_id) for job_id in relevant_job_ids}
    metrics: dict[str, float] = {}
    for cutoff in cutoffs:
        top = ranked[:cutoff]
        hits = sum(job_id in relevant for job_id in top)
        metrics[f"precision_at_{cutoff}"] = hits / cutoff if cutoff else 0.0
        metrics[f"recall_at_{cutoff}"] = hits / len(relevant) if relevant else 0.0
        dcg = sum(
            1 / log2(index + 2)
            for index, job_id in enumerate(top)
            if job_id in relevant
        )
        ideal_hits = min(len(relevant), cutoff)
        ideal_dcg = sum(1 / log2(index + 2) for index in range(ideal_hits))
        metrics[f"ndcg_at_{cutoff}"] = dcg / ideal_dcg if ideal_dcg else 0.0
    return metrics


def evaluate_graded_ranking(
    ranked_job_ids: Iterable[str],
    relevance_grades: dict[str, int | None],
    cutoffs: tuple[int, ...] = (5, 10, 20),
) -> dict[str, float]:
    """Evaluate a ranking without treating unreviewed jobs as irrelevant."""
    ranked = list(dict.fromkeys(str(job_id) for job_id in ranked_job_ids))
    grades = {str(job_id): grade for job_id, grade in relevance_grades.items()}
    invalid = {
        job_id: grade
        for job_id, grade in grades.items()
        if grade is not None
        and (type(grade) is not int or grade not in RELEVANCE_GRADES)
    }
    if invalid:
        raise ValueError("Relevance grades must be integers from 0 through 3 or None")
    if any(cutoff <= 0 for cutoff in cutoffs):
        raise ValueError("Evaluation cutoffs must be positive")

    reviewed = [job_id for job_id in ranked if grades.get(job_id) is not None]
    positive = [job_id for job_id in reviewed if grades[job_id] >= 2]
    metrics: dict[str, float] = {
        "reviewed_count": float(len(reviewed)),
        "unreviewed_count": float(len(ranked) - len(reviewed)),
        "review_coverage": len(reviewed) / len(ranked) if ranked else 0.0,
        "positive_review_rate": len(positive) / len(reviewed) if reviewed else 0.0,
    }
    all_gains = sorted(((2 ** grades[job_id]) - 1 for job_id in reviewed), reverse=True)
    for cutoff in cutoffs:
        top = ranked[:cutoff]
        reviewed_top = [job_id for job_id in top if grades.get(job_id) is not None]
        positive_top = sum(grades[job_id] >= 2 for job_id in reviewed_top)
        metrics[f"review_coverage_at_{cutoff}"] = (
            len(reviewed_top) / len(top) if top else 0.0
        )
        metrics[f"judged_precision_at_{cutoff}"] = (
            positive_top / len(reviewed_top) if reviewed_top else 0.0
        )
        dcg = sum(
            ((2 ** (grades.get(job_id) or 0)) - 1) / log2(index + 2)
            for index, job_id in enumerate(top)
        )
        ideal_dcg = sum(
            gain / log2(index + 2) for index, gain in enumerate(all_gains[:cutoff])
        )
        metrics[f"graded_ndcg_at_{cutoff}"] = dcg / ideal_dcg if ideal_dcg else 0.0
    return metrics

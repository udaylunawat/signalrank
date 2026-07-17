from __future__ import annotations

from math import log2
from typing import Iterable


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

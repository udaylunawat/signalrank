# job_ranker/llm/config_advisor.py
"""
Post-batch AI Config Advisor.

Samples top-20 + random-20-from-rank-21-200 jobs, sends them with the
resume to an OpenRouter free model, and writes a markdown config
suggestions report to <reports_dir>/config_suggestions_<run_id>.md.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from job_ranker.llm.client import llm_text

logger = logging.getLogger(__name__)

# Model IDs validated against OpenRouter /api/v1/models on 2026-03-15.
# All confirmed free (pricing.prompt="0", pricing.completion="0").
# hunter-alpha: 1M context, 1T param frontier model
# healer-alpha: 262K context, multimodal
# nemotron-3-super: 262K context, 120B params
# step-3.5-flash: 256K context, fast fallback
ADVISOR_MODEL_POOL = [
    "openrouter/hunter-alpha",
    "openrouter/healer-alpha",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "stepfun/step-3.5-flash:free",
    "google/gemma-3-27b-it:free",
]

SYSTEM_PROMPT = """You are a job search optimization assistant.
Analyze the user's resume and a sample of ranked job listings.
Respond with ONLY the four sections below — no preamble, no JSON.

## 1. Skills Gap
List 3-6 specific skills or keywords prominent in top jobs but underrepresented in the resume or skills-boost config. Be specific (e.g. "PyTorch", "Kubernetes", "A/B testing").

## 2. Ranking Calibration
Identify 2-4 jobs that appear misscored relative to the resume. For each, note the job title, company, current score, and a brief reason (e.g. "score too low — strong NLP match"). Suggest which config weight to adjust.

## 3. Blocklist / Veto Tuning
Identify 2-4 recurring patterns in the job sample that seem off-target. Suggest specific terms or patterns to add to the veto/blocklist (e.g. "exclude 'staffing agency'", "exclude 'sales engineer'").

## 4. Company Tier Suggestions
List up to 4 companies appearing frequently in top results that are not yet in the tier config. Suggest which tier (tier1/tier2/tier3) each belongs to."""


def sample_jobs(ranked_df: pd.DataFrame, run_id: str) -> pd.DataFrame:
    """Top-20 + random-20 from rank 21-200. Seed derived from run_id for reproducibility."""
    top20 = ranked_df.head(20)
    pool = ranked_df.iloc[20:200]
    seed = int(hashlib.md5(run_id.encode()).hexdigest()[:8], 16) % (2**31)
    rand20 = pool.sample(min(20, len(pool)), random_state=seed)
    return pd.concat([top20, rand20], ignore_index=True)


def build_user_message(
    sample: pd.DataFrame,
    resume_text: str,
    config: dict,
) -> str:
    """Build the user message: resume excerpt + job summaries + config summary."""
    resume_excerpt = (resume_text or "")[:2000]

    jobs_summary = []
    for _, row in sample.iterrows():
        jobs_summary.append({
            "title": str(row.get("title", ""))[:80],
            "company": str(row.get("company", ""))[:50],
            "score": round(float(row.get("final_score", 0)), 1),
            "description": str(row.get("description", ""))[:300],
        })

    config_summary = {
        "skills_boost": config.get("skills_boost", [])[:30],
        "blocklist": config.get("blocklist", [])[:20],
        "company_tiers": list(config.get("company_tiers", {}).keys())[:5],
        "weights": config.get("weights", {}),
    }

    return (
        f"## Resume (excerpt)\n{resume_excerpt}\n\n"
        f"## Job Sample ({len(jobs_summary)} jobs)\n"
        f"{json.dumps(jobs_summary, indent=2)}\n\n"
        f"## Current Config Summary\n"
        f"{json.dumps(config_summary, indent=2)}"
    )


def run_advisor(
    *,
    ranked_df: pd.DataFrame,
    resume_text: str,
    run_id: str,
    config: dict,
    reports_dir: Path,
) -> Path | None:
    """
    Run the advisor and write the report. Returns report path or None on skip.
    Never raises — errors are written into the report.
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"config_suggestions_{run_id}.md"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if not os.getenv("OPENROUTER_API_KEY"):
        logger.warning("[ADVISOR] OPENROUTER_API_KEY not set — skipping advisor (no report written)")
        return None

    try:
        if ranked_df.empty:
            logger.warning("[ADVISOR] No ranked results, skipping advisor")
            return None

        sample = sample_jobs(ranked_df, run_id)
        user_msg = build_user_message(sample, resume_text, config)

        logger.info("[ADVISOR] Calling LLM with %d job sample", len(sample))

        # Try models in priority order so we know exactly which one succeeded
        model_used = None
        response = ""
        for model in ADVISOR_MODEL_POOL:
            response = llm_text(
                SYSTEM_PROMPT,
                user_msg,
                model_pool=[model],  # single model per call for accurate attribution
                max_tokens=2048,
                timeout=60,
            )
            if response:
                model_used = model
                break

        if response and model_used:
            content = (
                f"# Config Suggestions — Run {run_id} — {now}\n\n"
                f"> Generated by {model_used} | {now}\n\n"
                f"{response}\n"
            )
        else:
            content = (
                f"# Config Suggestions — Run {run_id} — {now}\n\n"
                f"> ⚠️ LLM unavailable — all models exhausted or API key missing.\n\n"
                f"Run the advisor manually once OPENROUTER_API_KEY is set.\n"
            )

        report_path.write_text(content, encoding="utf-8")
        logger.info("[ADVISOR] Report written: %s", report_path)
        return report_path

    except Exception as e:
        logger.error("[ADVISOR] Unexpected error: %s", e)
        report_path.write_text(
            f"# Config Suggestions — Run {run_id} — {now}\n\n"
            f"> ⚠️ Advisor error: {e}\n",
            encoding="utf-8",
        )
        return report_path

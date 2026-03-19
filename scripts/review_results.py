#!/usr/bin/env python3
"""
Review job ranker results: extract top N + random sample, output score breakdowns.

Usage:
    uv run python scripts/review_results.py
    uv run python scripts/review_results.py --top-n 10 --sample-n 15 --output review.md
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parents[1] / "job_ranker" / "duckdb"

WEIGHTS = {
    "skills_match": 0.40,
    "company_fit": 0.20,
    "seniority": 0.15,
    "location": 0.15,
    "recency": 0.10,
}


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


def load_results(con: duckdb.DuckDBPyConnection, user: str, use_case: str) -> pd.DataFrame:
    row = con.execute(
        """
        SELECT run_id, finished_at
        FROM runs
        WHERE user = ? AND use_case = ? AND status = 'success'
        ORDER BY finished_at DESC
        LIMIT 1
        """,
        [user, use_case],
    ).fetchone()

    if not row:
        print("No successful runs found.", file=sys.stderr)
        sys.exit(1)

    run_id, finished_at = row
    print(f"Run: {run_id}  finished: {finished_at}", file=sys.stderr)

    rows = con.execute(
        "SELECT payload FROM run_results WHERE run_id = ? ORDER BY final_score DESC",
        [run_id],
    ).df()

    records = [json.loads(p) for p in rows["payload"]]
    df = pd.DataFrame(records)

    # Dedup by title+company (case-insensitive), keep highest score
    df["_dedup_key"] = (
        df["title"].str.strip().str.lower() + "|" + df["company"].str.strip().str.lower()
    )
    df = df.sort_values("final_score", ascending=False).drop_duplicates(
        subset="_dedup_key", keep="first"
    ).reset_index(drop=True)
    df = df.drop(columns=["_dedup_key"])

    print(f"Total results (after dedup): {len(df)}", file=sys.stderr)
    return df


def select_sample(df: pd.DataFrame, top_n: int, sample_n: int, seed: int) -> pd.DataFrame:
    top = df.head(top_n)

    pool = df.iloc[top_n:200]
    rng = random.Random(seed)
    sample_indices = rng.sample(range(len(pool)), min(sample_n, len(pool)))
    sampled = pool.iloc[sample_indices]

    result = pd.concat([top, sampled]).reset_index(drop=True)
    # Carry original rank
    result["_orig_rank"] = list(range(1, top_n + 1)) + [top_n + 1 + i for i in sample_indices]
    return result


def format_job(row: pd.Series) -> str:
    rank = row["_orig_rank"]
    title = row.get("title", "?")
    company = row.get("company", "?")
    score = row.get("final_score", 0)
    location = row.get("location", "?")
    role = row.get("functional_role", "?")
    date = row.get("date_posted")
    url = row.get("job_url", "")

    # Dimension scores
    skills = row.get("skills_score", 0)
    company_s = row.get("company_score", 0)
    seniority = row.get("seniority_score_dim", 0)
    location_s = row.get("location_score", 0)
    recency = row.get("recency_score", 0)

    # Raw values
    semantic = row.get("semantic_score", 0)
    overlap = row.get("skill_overlap", 0)
    role_skill = row.get("role_skill_score", 0)
    tier = row.get("company_tier", "?")
    sen_mult = row.get("seniority_score", 0)
    loc_wt = row.get("location_weight", 0)
    func_penalty = row.get("functional_role_penalty", 1.0)
    skills_list = row.get("canonical_skills", [])

    # Contributions
    sk_c = skills * WEIGHTS["skills_match"]
    co_c = company_s * WEIGHTS["company_fit"]
    se_c = seniority * WEIGHTS["seniority"]
    lo_c = location_s * WEIGHTS["location"]
    re_c = recency * WEIGHTS["recency"]
    total_c = sk_c + co_c + se_c + lo_c + re_c

    date_str = str(date) if date and str(date) != "None" and str(date) != "NaT" else "unknown"

    lines = [
        f"### Rank #{rank}: {title} @ {company}  (Score: {score:.1f})",
        "",
        f"**Location:** {location} | **Date:** {date_str} | **Role:** {role}",
        "",
        "| Dimension | Raw | Score | Weight | Contrib |",
        "|-----------|-----|-------|--------|---------|",
        f"| Skills | sem={semantic:.3f} ovl={overlap} role_skill={role_skill:.2f} penalty={func_penalty:.2f} | {skills:.0f} | {WEIGHTS['skills_match']:.2f} | {sk_c:.1f} |",
        f"| Company | {tier} ({company}) | {company_s:.0f} | {WEIGHTS['company_fit']:.2f} | {co_c:.1f} |",
        f"| Seniority | mult={sen_mult:.2f} | {seniority:.0f} | {WEIGHTS['seniority']:.2f} | {se_c:.1f} |",
        f"| Location | weight={loc_wt:.2f} | {location_s:.0f} | {WEIGHTS['location']:.2f} | {lo_c:.1f} |",
        f"| Recency | {date_str} | {recency:.0f} | {WEIGHTS['recency']:.2f} | {re_c:.1f} |",
        f"| **TOTAL** | | | | **{total_c:.1f}** |",
        "",
        f"**Skills:** {', '.join(skills_list[:15]) if isinstance(skills_list, list) else skills_list}",
        f"**URL:** {url}",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def pattern_analysis(df: pd.DataFrame) -> str:
    lines = ["## Pattern Analysis", ""]

    # 1. Duplicates in top 50
    top50 = df.head(50)
    keys = (
        top50["title"].str.strip().str.lower() + "|" + top50["company"].str.strip().str.lower()
    )
    dupes = {k: v for k, v in Counter(keys).items() if v > 1}
    lines.append("### Duplicates in Top 50 (before dedup)")
    if dupes:
        for k, v in sorted(dupes.items(), key=lambda x: -x[1]):
            lines.append(f"- {v}x: {k}")
    else:
        lines.append("- None (dedup already applied)")
    lines.append("")

    # 2. Unknown date prevalence
    lines.append("### Unknown Date (recency_score=50) Prevalence")
    for bracket, lo, hi in [("Top 20", 0, 20), ("Rank 21-50", 20, 50), ("Rank 51-100", 50, 100), ("Rank 101-200", 100, 200)]:
        subset = df.iloc[lo:min(hi, len(df))]
        if subset.empty:
            continue
        unk = (subset["recency_score"] == 50.0).sum()
        lines.append(f"- {bracket}: {unk}/{len(subset)} ({100*unk/len(subset):.0f}%)")
    lines.append("")

    # 3. Company dominance
    lines.append("### Company Score Dominance (top 50)")
    lines.append("Jobs where company contributes >30% of final score AND skills_score < 70:")
    flagged = 0
    for _, row in df.head(50).iterrows():
        fs = row.get("final_score", 1)
        co_contrib = row.get("company_score", 0) * WEIGHTS["company_fit"]
        sk = row.get("skills_score", 0)
        if fs > 0 and (co_contrib / fs) > 0.30 and sk < 70:
            lines.append(
                f"- #{_ + 1} {row['title']} @ {row['company']}: "
                f"company_contrib={co_contrib:.1f}/{fs:.1f} ({100*co_contrib/fs:.0f}%), skills={sk:.0f}"
            )
            flagged += 1
    if not flagged:
        lines.append("- None found")
    lines.append("")

    # 4. Functional role distribution
    lines.append("### Functional Role Distribution")
    lines.append("**Top 50:**")
    top50_roles = Counter(df.head(50)["functional_role"])
    for role, cnt in top50_roles.most_common():
        lines.append(f"- {role}: {cnt}")
    lines.append("")
    lines.append("**Full corpus:**")
    all_roles = Counter(df["functional_role"])
    for role, cnt in all_roles.most_common():
        lines.append(f"- {role}: {cnt} ({100*cnt/len(df):.1f}%)")
    lines.append("")

    # 5. Score distribution by dimension
    lines.append("### Score Distribution (full corpus)")
    lines.append("| Dimension | Min | P25 | Median | P75 | Max |")
    lines.append("|-----------|-----|-----|--------|-----|-----|")
    for name, col in [
        ("Skills", "skills_score"),
        ("Company", "company_score"),
        ("Seniority", "seniority_score_dim"),
        ("Location", "location_score"),
        ("Recency", "recency_score"),
        ("Final", "final_score"),
    ]:
        if col in df.columns:
            s = df[col]
            lines.append(
                f"| {name} | {s.min():.0f} | {s.quantile(0.25):.0f} | "
                f"{s.median():.0f} | {s.quantile(0.75):.0f} | {s.max():.0f} |"
            )
    lines.append("")

    # 6. Misclassification candidates in top 20
    lines.append("### Potential Misclassifications (top 20)")
    lines.append("Jobs with customer/architect/field/outcome in title but classified as engineering role:")
    suspect_terms = ["architect", "field", "customer", "outcome", "consultant", "advisory", "solutions"]
    for i, row in df.head(20).iterrows():
        title_lower = str(row.get("title", "")).lower()
        role = row.get("functional_role", "")
        if any(t in title_lower for t in suspect_terms) and role not in ("customer_facing", "architecture_strategy"):
            lines.append(f"- #{i + 1} [{role}] {row['title']} @ {row['company']} (score={row['final_score']:.1f})")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Review job ranker results")
    parser.add_argument("--user", default="example")
    parser.add_argument("--use-case", default="default")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--sample-n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, help="Output file path (default: stdout)")
    args = parser.parse_args()

    con = connect()
    df = load_results(con, args.user, args.use_case)

    sample = select_sample(df, args.top_n, args.sample_n, args.seed)

    out_lines = [
        "# Job Ranker Results Review",
        "",
        f"**User:** {args.user} | **Use case:** {args.use_case}",
        f"**Top {args.top_n} + {len(sample) - args.top_n} random from rank {args.top_n + 1}-200**",
        f"**Total jobs (after dedup):** {len(df)}",
        "",
        "---",
        "",
        "## Top Jobs",
        "",
    ]

    for _, row in sample.head(args.top_n).iterrows():
        out_lines.append(format_job(row))

    out_lines.extend(["## Random Sample (rank 6-200)", ""])

    for _, row in sample.iloc[args.top_n:].iterrows():
        out_lines.append(format_job(row))

    out_lines.append(pattern_analysis(df))

    output = "\n".join(out_lines)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()

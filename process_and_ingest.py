#!/usr/bin/env python3
# ================================
# FILE: process_and_ingest.py
# ================================
import argparse
import pandas as pd
import subprocess
from pathlib import Path

from config_loader import settings
from user_context import resolve_user_context


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--use-case", help="Use case (optional)")
    parser.add_argument("--include-eda", action="store_true")
    args = parser.parse_args()

    ctx = resolve_user_context(
        user=args.user,
        use_case_override=args.use_case,
        require_resume=False,
    )

    input_path = ctx.outputs_dir / settings.outputs.ranked_jobs_file
    output_path = ctx.outputs_dir / settings.outputs.preview_file
    preview_cfg = settings.outputs.preview

    if not input_path.exists():
        raise FileNotFoundError(f"{input_path} not found")

    df = pd.read_csv(input_path)

    # ---------------------------------
    # Drop heavy / sensitive columns
    # ---------------------------------
    drop_cols = set(preview_cfg.drop_columns)
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    # ---------------------------------
    # Write preview (INGEST-SAFE)
    # ---------------------------------
    preview_df = df.head(preview_cfg.rows).copy()

    # HARD DROP: description must never enter gitingest
    if "description" in preview_df.columns:
        preview_df.drop(columns=["description"], inplace=True)

    preview_df.to_csv(output_path, index=False)
    print(f"[INGEST] Preview written → {output_path}")

    # ---------------------------------
    # Optional EDA
    # ---------------------------------
    if args.include_eda:
        subprocess.run(
            ["python3", "eda.py", "--user", ctx.user, "--use-case", ctx.use_case],
            check=False,
        )
    # ---------------------------------
    # CURATED CODEBASE INGEST (FAST)
    # ---------------------------------
    import shutil

    ingest_dir = ctx.outputs_dir / "_ingest_tmp"
    if ingest_dir.exists():
        shutil.rmtree(ingest_dir)
    ingest_dir.mkdir(parents=True)

    PROJECT_ROOT = Path(__file__).resolve().parent

    # 1. Copy codebase (selectively)
    EXCLUDE_DIRS = {
        "cache",
        "users",
        "corpus",
        "outputs",
        "embeddings",
        "__pycache__",
        ".git",
        ".venv",
    }

    for item in PROJECT_ROOT.iterdir():
        if item.name in EXCLUDE_DIRS:
            continue
        if item.is_dir():
            shutil.copytree(item, ingest_dir / item.name)
        else:
            shutil.copy2(item, ingest_dir / item.name)

    # 2. Inject preview CSV ONLY
    preview_target = ingest_dir / output_path.name
    preview_target.write_bytes(output_path.read_bytes())

    print(f"[INGEST] Curated ingest directory → {ingest_dir}")

    # 3. Run gitingest on curated tree
    subprocess.run(
        ["gitingest", str(ingest_dir)],
        check=False,
    )


if __name__ == "__main__":
    main()
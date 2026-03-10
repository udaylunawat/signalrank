#!/usr/bin/env bash
set -euo pipefail

ARCHIVE_DIR="archive/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$ARCHIVE_DIR"

move_if_exists() {
  local src="$1"
  if [ -e "$src" ]; then
    echo "Archiving $src"
    mv "$src" "$ARCHIVE_DIR/" 2>/dev/null || {
      echo "⚠️  Skipped (could not move): $src"
    }
  fi
}

# ---------- legacy scripts ----------
move_if_exists build_corpus.py
move_if_exists cache_loader.py
move_if_exists rank_corpus.py
move_if_exists eda.py
move_if_exists eda_recency.py
move_if_exists fast_heuristics.py
move_if_exists get_free_models.py
move_if_exists test_db.py
move_if_exists test_linkedin_api.py
move_if_exists ranked_jobs_head.csv

# ---------- folders ----------
move_if_exists _ingest_tmp
move_if_exists config/legacy

echo
echo "✅ Archive complete → $ARCHIVE_DIR"
echo "Nothing deleted. Safe to revert."
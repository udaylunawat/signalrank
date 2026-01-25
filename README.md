# Calm-First Job Ranker

A **batch-first, deterministic job discovery and ranking system** designed for senior IC roles in AI, MLOps, and platform engineering.

This project deliberately separates **data collection and ranking (CLI + cron)** from **presentation (Streamlit viewer)** to achieve:

- Stability on macOS (no OpenMP / multiprocessing crashes)
- Reproducible daily runs
- Low cognitive and operational complexity
- Clear ownership of side effects (scraping, caching, embeddings)

---

## High-Level Architecture



**CRON / MANUAL CLI** │  
▼  
**jobs fetch / jobs run** │  
▼  
**cache/** (query CSVs + metadata)  
│  
▼  
**jobs rank** │  
▼  
**outputs/ranked_jobs.csv** │  
▼  
**Streamlit (read-only viewer)**

**Key principle:** Streamlit never scrapes, embeds, or calls LLMs. It only reads a CSV.

---

## Core Concepts

### Batch-First
All expensive and failure-prone work (scraping, LLM calls, embeddings, FAISS) happens in the CLI.  
The UI is a thin, safe consumer.

### Deterministic
- Cached queries
- Cached role classification
- Cached embeddings
- Bounded cache eviction

You can re-run the pipeline and understand *why* results changed.

### macOS-Safe
- No multiprocessing in Streamlit
- Controlled multiprocessing in CLI only
- OpenMP hard-limited via `sitecustomize.py`

---

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

```

Set your OpenRouter key (for optional LLM features):

```bash
export OPENROUTER_API_KEY=your_key_here

```

---

## CLI Usage (Primary Interface)

All commands are exposed via `cli.py` under the jobs program.

### 1. Fetch jobs only

Scrapes and caches jobs. No ranking.

```bash
python cli.py fetch \
  --search "mlops engineer|genai engineer|llmops engineer" \
  --country India \
  --profile senior_ic

```

**Output:** `cache/query_*.csv`, `cache/query_*.json`

### 2. Rank cached jobs

Ranks only from cache for a given resume.

```bash
python cli.py rank \
  --resume path/to/resume.pdf \
  --user uday \
  --profile senior_ic

```

**Output:** `outputs/ranked_jobs.csv`

### 3. One-shot run (recommended)

Fetch + rank in a single command.

```bash
python cli.py run \
  --resume path/to/resume.pdf \
  --search "mlops engineer|genai engineer|llmops engineer" \
  --user uday \
  --profile senior_ic \
  --country India

```

---

## Daily Automation (Cron)

The project is designed to be run daily via `run_daily.sh`. This script:

* Sets all safety environment variables
* Enables JobSpy multiprocessing (CLI only)
* Writes a fresh `outputs/ranked_jobs.csv`

**Add to crontab (example: 7 AM daily):**

```cron
0 7 * * * /absolute/path/to/run_daily.sh >> ~/job_ranker.log 2>&1

```

---

## Streamlit UI (Read-Only)

The Streamlit app is intentionally minimal:

```bash
streamlit run app.py

```

* **What it does:** Reads `outputs/ranked_jobs.csv` and displays a sortable table.
* **What it does NOT do:** Scraping, Embedding, FAISS, or LLM calls.

---

## Cache Strategy

### What is cached

* Scraped job results (per query)
* Role classification results
* LLM outputs
* FAISS embeddings

### Automatic pruning

Implemented in `cache_loader.py`:

* **Max age:** 72 hours
* **Max query files:** 50
* Old or excess entries are removed automatically.

---

## Profiles

Profiles live in `profiles.py` and define role filters (junior / manager), keyword exclusions, preferred companies, and LLM usage toggles. The `senior_ic` profile is the default optimization.

---

## LLM Usage Philosophy

LLMs are used surgically, never as a primary dependency:

* Search query planning (guarded + normalized)
* Resume distillation (cached)
* Role classification (heuristic first, cached fallback)
* Explanations for top matches only

---

## Repository Structure (Intentional)

* `cli.py`: Single source of truth (batch)
* `run_daily.sh`: Cron entrypoint
* `app.py`: Read-only Streamlit viewer
* `scrape_jobs.py`: Scraping + caching
* `match_engine.py`: Ranking logic
* `cache_loader.py`: Bounded cache management
* `embeddings/`: FAISS + embedding cache
* `llm/`: Guarded LLM utilities
* `profiles.py`: Role profiles
* `sitecustomization.py`: macOS / OpenMP safety

---

## Operating Principles

* Batch first
* Cache aggressively, prune deterministically
* Heuristics before LLMs
* UI reads data, never produces it
* Fewer moving parts beat clever abstractions


# Calm-First Job Ranker

A **calm-first, senior IC–oriented job discovery tool** that surfaces
high-signal enterprise AI/ML roles instead of overwhelming you with noise.

This project combines:
- Deterministic quality filters
- Semantic matching
- Company-tier intelligence
- Minimal, well-bounded LLM usage
- A clean Streamlit decision interface

The goal is not to find *more* jobs.
The goal is to find **fewer, better jobs**.

---

## ✨ Key Features

### 1. Calm-First Ranking Philosophy
Jobs are ranked based on:
- Enterprise stability
- Senior IC suitability
- Predictable work cadence
- Platform / infrastructure focus
- Clear role ownership

Delivery-heavy, chaotic, or low-signal roles are aggressively filtered out.

### 2. Deterministic-First Architecture
The system is intentionally designed so that:

- **Deterministic filters do 70–80% of the work**
- **Company tiers do most of the remaining work**
- **Embeddings resolve ambiguity**
- **LLMs never decide ranking**

LLMs are used only for:
- Skill normalization
- Resume distillation
- Human-readable explanations

If an LLM fails, the system **degrades gracefully**.

### 3. Enterprise-Aware Company Scoring

Companies are scored via a YAML-driven tier system:

- `enterprise_calm` – stable, long-lifecycle organizations
- `enterprise_saas_finance` – strong product / finance firms
- `big_tech_controlled` – high upside, team-dependent calm
- `delivery_ai_services` – client-driven, lower calm
- `legacy_it_services` – low leverage, deprioritized

Company names are normalized to ensure robust matching.

### 4. Strong Quality Gates (By Design)

Before ranking, jobs must pass:
- Minimum description length (default ≥ 500 chars)
- Role classification (no junior / no manager for Senior IC profile)
- Keyword exclusions
- Deduplication
- Semantic similarity floor
- Experience mismatch penalties (e.g. 12+ years roles)

This is why result sets are small — **selectivity is intentional**.

### 5. Streamlit Decision UI

The Streamlit app is built as a **decision cockpit**, not a dashboard.

You get:
- Clear sidebar controls
- Result limit and minimum score sliders
- Apply-ready table with:
  - Clickable job links
  - Visual score bars
  - Company + location clarity
- Expandable job detail sections
- CSV export

The UI is calm, minimal, and optimized for shortlisting.

---

## 🗂 Project Structure

```text
scrape_jobs/
├── app.py                 # Streamlit UI
├── config.py              # Centralized tunable defaults
├── match_engine.py        # Ranking logic
├── scrape_jobs.py         # Scraping + filtering
├── company_scoring.py     # Company tier logic
├── profiles.py            # Role profiles
├── cache_loader.py        # Cached job loading
├── resume_parser.py       # Resume parsing
├── logger.py              # Unified logging
├── skill_normalizer.py    # Deterministic skill normalization
├── llm/
│   ├── client.py
│   ├── distill_resume.py
│   ├── normalize_skills.py
│   ├── explain_match.py
│   ├── classify_role.py
│   └── plan_search.py
├── config/
│   └── company_tiers.yaml
└── workspaces/



⚙️ Configuration
All system-wide tunables live in config.py:
Semantic thresholds
Penalty weights
LLM usage toggles
Scraping limits
Defaults for CLI and UI
CLI arguments and Streamlit controls override config defaults
when explicitly set.
This keeps behavior centralized and predictable.

🚀 How to Run
1. Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Set environment variables
```bash
export OPENROUTER_API_KEY=your_key_here
```

3. Run Streamlit app
```bash
python -m streamlit run app.py
```


# 🧠 Design Principles
- Calm > Compensation: Prioritize peace of mind over raw salary maximization.
- Signal > Volume: Better to see 3 perfect jobs than 300 "okay" ones.
- Determinism > Cleverness: Use regex and logic before reaching for an LLM.
- Transparency: Always explain why a job was ranked high or low.
- Fewer knobs, stronger defaults.
- If the tool returns only 2–5 jobs, that’s a success, not a failure.

# 📌 Known Tradeoffs
- This tool intentionally filters out many “okay” roles.
- Startup / hustle environments are deprioritized by default.
- Big Tech roles are treated as team-dependent, not universally calm.
- LLM usage is constrained to avoid instability and cost blowups.

# 🧾 License
Internal / personal tooling.
Use, fork, or adapt freely.


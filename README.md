# 🧘 Calm-First Job Ranker

A career-quality–first job ranking tool for senior AI / ML engineers.

This project ranks jobs not just by resume similarity, but by:
- **Company quality:** Filtering for stability and prestige.
- **Long-term calm:** Prioritizing enterprise signal over startup noise.
- **Precision:** Using semantic matching rather than just keyword stuffing.

---

## ✨ Key Features

* 🔍 **Semantic Matching:** Resume-to-job matching via Sentence Transformers.
* 🏢 **Company Tiering:** Simple UI-based weighting (no YAML wrestling required).
* 🌍 **Flexible Filters:** Country, remote-only, and job freshness (hours) controls.
* 📊 **Observability:** Live scraping logs and progress bars in both CLI and Streamlit.
* ♻️ **Smart Caching:** Avoids redundant scraping to keep runs fast and reproducible.
* 🧾 **Deterministic Outputs:** All results are timestamped and tied to specific resume hashes.

---

## 📁 Project Structure

```text
jobs_scraper/
├── app.py                  # Streamlit UI entry point
├── match_jobs.py           # CLI entry point
├── scrape_jobs.py          # Job scraping + cache management
├── match_engine.py         # Ranking & semantic logic
├── company_scoring.py      # Company tier weighting
├── resume_parser.py        # PDF and LaTeX parsing
├── requirements.txt        # Project dependencies
├── config/
│   └── company_tiers.yaml  # Default tiering data (optional)
├── users/
│   └── <username>/         # User-specific resumes
├── cache/                  # Auto-generated scrape cache
└── outputs/                # Auto-generated ranked results



⚙️ Setup
Create and activate virtual environment:
Bash
python3 -m venv .venv
source .venv/bin/activate




Install dependencies:
Bash
pip install -r requirements.txt





▶️ Streamlit App Usage (Recommended)
Start the interactive dashboard:
Bash
python -m streamlit run app.py


In the UI, you can:
Upload your resume (PDF or .tex).
Toggle filters: Country, Remote Only, and Freshness.
Modify search terms dynamically (e.g., adding "Staff" or "Platform" roles).
Select priority companies via a multi-select dropdown.
Download the final ranked CSV.
Outputs are saved to: outputs/<username>/resume_<hash>/runs/<timestamp>/

▶️ CLI Usage
The CLI is ideal for fast iteration or scripting.
Example Run:
Bash
python match_jobs.py \
  --resume users/Example_Candidate/resume.tex \
  --search '"machine learning engineer" OR "mlops engineer"' \
  --country India \
  --hours-old 48


What happens:
Parses the provided resume.
Scrapes jobs matching the search string.
Applies company weights and semantic scoring.
Saves ranked_jobs.csv and prints the top matches to your terminal.

♻️ Caching & Data
Caching Behavior
Scrapes are cached based on a combination of country, freshness, remote, and search terms.
Default TTL: 6 hours.
Manual Override: Force a fresh scrape via the Streamlit sidebar or CLI flags.
Large CSVs
To preview or manage large raw data files:
Bash
head -n 20 jobs_raw.csv > jobs_raw_head.csv
gitingest -e "jobs_raw.csv" -e "ranked_jobs.csv" -e "cache/*"



🧠 Philosophy
This tool is built for Senior Engineers who value calm-first career decisions. It prioritizes enterprise stability over venture-capital hype and focuses on long-term growth rather than the typical 18-month "churn and burn" cycle.

🚀 Future Extensions
[ ] Profile Presets: "Calm" vs. "High Growth" vs. "Big Tech" filters.
[ ] Ranking Explainability: "Why this job?" descriptions for top matches.
[ ] Persistence: SQLite backend instead of CSV caching.
[ ] Containerization: Docker support for easy deployment.

Would you like me to help you draft the `match_engine.py` logic for that semantic matching, or perhaps refine the company scoring weights?




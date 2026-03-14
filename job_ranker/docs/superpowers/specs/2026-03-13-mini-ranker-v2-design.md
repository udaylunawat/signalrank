# Mini Ranker v2 — Design Spec

## Problem

`mini_ranker.py` works but is hardcoded to one person's profile. A new user must edit Python source to change their resume, companies, locations, and blocklists. The terminal output is a raw pandas table. Skill matching relies solely on embedding similarity with no explicit skill extraction.

## Goals

1. **Anyone can use it** — config file + setup wizard, no code edits
2. **Smarter ranking** — skill extraction, resume file loading, embedding cache
3. **Rich terminal UX** — colored tables, score breakdowns, progress bars, clickable URLs

## Constraints

- Single file (`mini_ranker.py`), ~1000-1100 lines max
- New deps: `rich`, `PyPDF2`, `pyyaml` (all lightweight, widely used)
- Existing deps stay: `pandas`, `jobspy`, `sentence-transformers`, `numpy`
- No database, no web server, no multi-user infrastructure

---

## 1. Config System

### 1.1 Config file: `config.yaml`

Minimal, human-friendly, ~20 lines for a typical user:

```yaml
resume: |
  AI Platform Engineer with 7 years experience.
  MLOps, LLM systems, Kubernetes, Terraform, CI/CD.

# OR load from file (takes precedence over inline resume):
# resume_file: ~/resume.pdf

search_queries:
  - ai platform engineer
  - mlops

country: India
hours_old: 240
preferred_locations: [pune, remote, maharashtra]

top_companies: [databricks, openai, nvidia, anthropic]
good_companies: [intuit, walmart, visa, atlassian]
avoid_companies: [wipro, infosys, tcs, cognizant]

title_blocklist: [trainee, manager, sales, junior, director, qa engineer]
max_yoe: 10
```

### 1.2 Internal tier mapping

The engine maps user-facing config to internal tiers:

| Config key | Internal tier | Score |
|---|---|---|
| `top_companies` | tier_s | 100 |
| `good_companies` | tier_a | 85 |
| `avoid_companies` | tier_d | 15 |
| everything else | default | 40 (hidden gem eligible) |

The full 5-tier system (S/A/B/C/D) remains in the code as smart defaults. Users who want finer control can add an `advanced:` section (parsed but not validated beyond type checks in v2):

```yaml
advanced:
  okay_companies: [optum, siemens, philips]     # tier_b -> 65
  meh_companies: [ge vernova, bosch, birlasoft]  # tier_c -> 45
  company_aliases: {wandb: weights and biases}
  scoring_weights: {skills: 0.45, company: 0.15, seniority: 0.15, location: 0.15, recency: 0.10}
  semantic_floor: 0.50
  contract_penalty: 0.9
```

### 1.3 Config loading & merging

Priority order (first found wins for file selection):
1. CLI `--config path/to/config.yaml`
2. `./config.yaml` in current directory
3. Built-in defaults only (current hardcoded CONFIG)

**Merging semantics:** User config is **deep-merged over built-in defaults**. A partial config.yaml with only `resume:` and `search_queries:` still gets all default company tiers, thresholds, etc. Each key in the user config overrides the corresponding default key.

**Resume precedence:** If both `resume_file` and `resume` are present, `resume_file` takes priority. If the file cannot be loaded (not found or extraction fails), fall back to inline `resume:` with a warning.

**Error handling:** If config.yaml has invalid YAML syntax, catch `yaml.YAMLError`, print a clear error message with context, and exit. If `search_queries` is empty or missing, warn and exit.

### 1.4 Setup wizard

Triggered by `python mini_ranker.py --setup` OR automatically on first run if no config.yaml exists.

**TTY guard:** If `not sys.stdin.isatty()`, skip the wizard and print: "No config.yaml found. Run with --setup interactively or create config.yaml manually. See config.example.yaml."

Interactive prompts (6 questions):

1. "Path to your resume (PDF/TXT/TEX):" (validates file exists)
2. "What job titles are you searching for? (comma-separated):"
3. "What country?" (default: India)
4. "Companies you'd love to work at? (comma-separated):"
5. "Companies to avoid? (comma-separated):"
6. "Preferred locations? (comma-separated):"

Writes `config.yaml` and prints: "Config saved to config.yaml — edit anytime."

---

## 2. Smarter Ranking

### 2.1 Resume file loading

If config has `resume_file:`, load it:
- `.pdf` -> PyPDF2 text extraction
- `.txt` / `.tex` / anything else -> read as UTF-8 text
- Falls back to inline `resume:` text if file not found **or extraction fails** (with warning)

### 2.2 Skill extraction (lightweight)

Inline skill groups (no separate file), ~30 groups covering common tech:

```python
SKILL_GROUPS = {
    "kubernetes": ["kubernetes", "k8s", "kubectl", "helm"],
    "terraform": ["terraform", "terragrunt", "hcl"],
    "mlops": ["mlops", "mlflow", "kubeflow", "ml pipeline"],
    "llm": ["llm", "large language model", "gpt", "claude", "gemini"],
    "rag": ["rag", "retrieval augmented", "vector search"],
    ...
}
```

For each job, extract which skill groups appear in the description. Compare against skill groups found in the resume text.

**Integration with skills_score:** The overlap bonus is added to the base score inside `skills_score()`, after `semantic * 100` and before the role penalty adjustment:

```python
def skills_score(semantic, role, consulting_damp, skill_overlap):
    base = semantic * 100.0
    base += min(skill_overlap * 2, 8)        # <-- NEW: +2 per matching group, capped at +8
    penalty = ROLE_PENALTIES.get(role, 1.0)
    base += max(-8, min((penalty - 1.0) * 50, 10))
    if consulting_damp < 1.0:
        base -= 10
    return max(0.0, min(base, 100.0))
```

This modifies the skills dimension of the existing 5D model. It does NOT add a 6th dimension.

### 2.3 Embedding disk cache

**Format:** numpy `.npz` file + JSON sidecar (no pickle — avoids arbitrary code execution risk).
- Cache dir: `.mini_ranker_cache/` (gitignored)
  - `vectors.npz` — numpy array of embeddings
  - `keys.json` — list of SHA256 hashes mapping to vector indices
- On startup: load cache if exists
- On embed: check cache first, only compute missing texts
- On exit: save updated cache
- CLI: `--no-cache` skips cache, `--clear-cache` deletes it

**Progress integration:** The embed function returns a `(vectors, cache_hits, cache_misses)` tuple. Progress bar shows total items with a note like `(327 cached)`. The progress bar advances per-batch at the `embed()` caller level, not inside `model.encode()`.

Speeds up repeat runs significantly (embedding is the slowest step).

### 2.4 Better role classification

Title gets 3x weight in keyword counting (matching the full system's heuristic). Already implemented in current mini_ranker — confirming this stays.

---

## 3. Rich Terminal Output

### 3.1 Dependencies

`rich` library — handles colors, tables, progress bars, panels, hyperlinks.

### 3.2 Progress indicators

```
[SCRAPE] ━━━━━━━━━━━━━━━━━━━━ 7/9 queries  "ai infrastructure"
[EMBED]  ━━━━━━━━━━━━━━━━━━━━ 842/842 jobs  (327 cached)
```

### 3.3 Results table

```
 TOP 20 RANKED JOBS                                842 -> 267 -> 20

 #  Score  Title                          Company          Loc     Role
 1   67.0  Sr ML Platform Engineer        Databricks [S]   Pune    mlops
 2   61.7  AI Infrastructure Engineer     OpenAI [S]       Remote  agentic
 3   54.5  GenAI Engineer                 Persistent [B]   Pune    agentic
 4   48.6  Contract MLOps Engineer        Unknown Startup  Remote  mlops  CONTRACT
 ...
```

- Tier badges color-coded: `[S]` green, `[A]` cyan, `[B]` yellow, `[D]` red
- Contract flags in red
- Score column color gradient (high=green, low=dim)
- Job URLs as clickable terminal hyperlinks on title (rich supports this)

### 3.4 Summary panel

```
 Summary
 Scraped: 842 jobs from 9 queries
 After filters: 267 (blocklist: -198, semantic: -312, dedup: -65)
 Top companies: Databricks, OpenAI, Netflix, Anthropic
 Roles: 45% mlops, 30% agentic, 20% platform, 5% software
 Cached embeddings: 327 reused, 515 new
 Saved: outputs/mini_ranked_20260313_120000.csv
```

### 3.5 Score breakdown (--verbose flag)

With `--verbose`, show per-dimension scores and skill matches:

```
 #1  67.0  Sr ML Platform Engineer @ Databricks [S]
     skills=79  company=100  seniority=92  location=100  recency=100
     skills: kubernetes, terraform, mlops, llm (4/6 match)
```

### 3.6 Graceful degradation

If `rich` is not installed, fall back to current plain-text output. Import with try/except. All rich usage goes through a thin wrapper so the fallback is a single code path.

---

## 4. CLI Interface

```
python mini_ranker.py                    # scrape + rank (uses config.yaml)
python mini_ranker.py --setup            # interactive wizard
python mini_ranker.py --csv jobs.csv     # rank pre-scraped CSV
python mini_ranker.py --hours-old 72     # override freshness
python mini_ranker.py --config my.yaml   # custom config path
python mini_ranker.py --top 50           # show more results
python mini_ranker.py --verbose          # show score breakdowns
python mini_ranker.py --no-cache         # skip embedding cache
python mini_ranker.py --clear-cache      # delete embedding cache
```

`--setup` and `--csv` are mutually exclusive (argparse group).

---

## 5. File structure

Still one file: `mini_ranker.py` (~1000-1100 lines)

Supporting files (generated, not code):
- `config.yaml` — user profile (generated by wizard or copied from example)
- `config.example.yaml` — shipped sample (current Example profile as reference)
- `.mini_ranker_cache/` — embedding cache dir (auto-generated, gitignored)
- `outputs/mini_ranked_*.csv` — ranked results

---

## 6. What stays the same

Everything in the current mini_ranker.py's ranking engine is preserved:
- 5D additive scoring model (skills dimension enhanced with skill overlap bonus)
- Semantic gates (non-IC, role-aware thresholds)
- Description quality multiplier
- Contract detection + penalty
- Consulting dampener
- Seniority scoring
- Role-intent caps
- 3-layer deduplication

---

## 7. Verification

1. `python mini_ranker.py --setup` -> generates config.yaml from wizard
2. `python mini_ranker.py` -> scrapes, ranks, shows rich table
3. `python mini_ranker.py --csv` -> ranks existing data with rich output
4. Delete config.yaml -> wizard triggers automatically (TTY) or prints help (non-TTY)
5. `pip install` without `rich` -> falls back to plain text gracefully
6. Second run with same data -> embedding cache hits (faster, reported in summary)
7. Top 10 results are all IC AI/ML/platform roles at tiered companies, consistent with current quality bar
8. Invalid config.yaml -> clear error message with context, clean exit

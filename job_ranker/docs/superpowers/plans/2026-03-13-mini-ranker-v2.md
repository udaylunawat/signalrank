# Mini Ranker v2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade mini_ranker.py from a hardcoded single-user tool to a config-driven, rich-output job ranking engine anyone can use.

**Architecture:** Single file (~1000-1100 lines) with YAML config loading, setup wizard, embedding cache (npz+json), skill extraction, and rich terminal output with graceful fallback.

**Tech Stack:** Python 3.10+, pandas, sentence-transformers, numpy, pyyaml, rich, PyPDF2

**Spec:** `docs/superpowers/specs/2026-03-13-mini-ranker-v2-design.md`

---

## Chunk 1: Config System + Resume Loading

### Task 1: Add config loading infrastructure

**Files:**
- Modify: `mini_ranker.py` (top of file — imports, defaults dict, load function)

- [ ] **Step 1: Add YAML and sys imports**

Add to the import block at top of `mini_ranker.py`:

```python
import hashlib
import json
import sys

import yaml  # pyyaml
```

- [ ] **Step 2: Create DEFAULTS dict**

Replace all the hardcoded top-level constants (lines 31-226) with a single `DEFAULTS` dict. The existing constants become default values. Add a module-level `CFG = {}` that gets populated at runtime.

```python
DEFAULTS = {
    "resume": "",
    "resume_file": "",
    "search_queries": [
        "ai platform engineer", "ml platform engineer", "mlops",
        "llmops", "genai", "agentic systems", "ai infrastructure",
        "forward deployed engineer", "developer productivity engineer",
    ],
    "country": "India",
    "hours_old": 240,
    "preferred_locations": ["pune", "remote", "maharashtra", "mh, in", "remote, in"],
    "top_companies": [<current COMPANY_TIERS["tier_s"] list>],
    "good_companies": [<current COMPANY_TIERS["tier_a"] list>],
    "avoid_companies": [<current COMPANY_TIERS["tier_d"] list>],
    "title_blocklist": [<current TITLE_BLOCKLIST list>],
    "max_yoe": 10,
    "advanced": {
        "okay_companies": [<current COMPANY_TIERS["tier_b"] list>],
        "meh_companies": [<current COMPANY_TIERS["tier_c"] list>],
        "company_aliases": {<current COMPANY_ALIASES dict>},
        "scoring_weights": {"skills": 0.45, "company": 0.15, "seniority": 0.15, "location": 0.15, "recency": 0.10},
        "semantic_floor": 0.50,
        "company_semantic_floor": 0.65,
        "hidden_gem_threshold": 0.70,
        "hidden_gem_bonus": 60,
        "contract_penalty": 0.9,
        "role_penalties": {"agentic_systems": 1.2, "mlops_llmops": 1.2, "platform_devops": 1.2, "software_general": 0.85},
        "role_semantic_thresholds": {"software_general": 0.65, "platform_devops": 0.55, "agentic_systems": 0.50, "mlops_llmops": 0.50},
    },
}

CFG = {}  # populated by load_config()
```

- [ ] **Step 3: Write `deep_merge` and `load_config` functions**

```python
def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base. Override values win."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(config_path: str | None = None) -> dict:
    """Load config from YAML, deep-merged over DEFAULTS."""
    # Find config file
    paths_to_try = []
    if config_path:
        paths_to_try.append(Path(config_path))
    paths_to_try.append(Path("config.yaml"))

    user_cfg = {}
    for p in paths_to_try:
        if p.exists():
            try:
                user_cfg = yaml.safe_load(p.read_text()) or {}
                break
            except yaml.YAMLError as e:
                print(f"[ERROR] Invalid YAML in {p}: {e}")
                sys.exit(1)

    cfg = deep_merge(DEFAULTS, user_cfg)

    # Validate required fields
    if not cfg.get("search_queries"):
        print("[ERROR] No search_queries in config. Run --setup or edit config.yaml.")
        sys.exit(1)

    return cfg
```

- [ ] **Step 4: Write `build_tiers` helper**

Converts user-facing config keys to internal tier structure:

```python
def build_tiers(cfg: dict) -> tuple[dict, dict, dict]:
    """Build COMPANY_TIERS, COMPANY_ALIASES, TIER_SCORES from config."""
    adv = cfg.get("advanced", {})
    tiers = {
        "tier_s": cfg.get("top_companies", []),
        "tier_a": cfg.get("good_companies", []),
        "tier_b": adv.get("okay_companies", []),
        "tier_c": adv.get("meh_companies", []),
        "tier_d": cfg.get("avoid_companies", []),
    }
    aliases = adv.get("company_aliases", {})
    scores = {"tier_s": 100.0, "tier_a": 85.0, "tier_b": 65.0, "tier_c": 45.0, "tier_d": 15.0, "default": 40.0}
    return tiers, aliases, scores
```

- [ ] **Step 5: Refactor all functions to read from CFG**

Update every function that currently reads module-level constants to read from `CFG` instead. Examples:

- `SEMANTIC_FLOOR` → `CFG["advanced"]["semantic_floor"]`
- `COMPANY_TIERS` → built via `build_tiers(CFG)` at startup, stored in module-level vars
- `PREFERRED_LOCATIONS` → `CFG["preferred_locations"]`
- `TITLE_BLOCKLIST` → `CFG["title_blocklist"]`
- `MAX_YOE` → `CFG["max_yoe"]`
- `WEIGHTS` → `CFG["advanced"]["scoring_weights"]`

Keep the non-configurable constants (BOILERPLATE_PHRASES, NON_IC_KEYWORDS, IC_ALLOWLIST, CONTRACT_SIGNALS, CONSULTING_KEYWORDS, STRONG_IC_KEYWORDS, TAXONOMY, AI_TERMS, DEVOPS_TERMS, JUNIOR_KEYWORDS, OVER_SENIOR_KEYWORDS, SENIOR_KEYWORDS, ROLE_NEGATIVE_KEYWORDS, ROLE_INTENT_CAPS) as module-level constants since these are engine internals.

- [ ] **Step 6: Update `main()` to load config at startup**

```python
def main():
    # ... argparse ...
    global CFG, COMPANY_TIERS, COMPANY_ALIASES, TIER_SCORES
    CFG = load_config(args.config)
    COMPANY_TIERS, COMPANY_ALIASES, TIER_SCORES = build_tiers(CFG)
    # ... rest of main ...
```

- [ ] **Step 7: Test config loading**

```bash
python -c "
import mini_ranker as mr
cfg = mr.load_config()
print('queries:', cfg['search_queries'][:3])
print('top_companies:', cfg['top_companies'][:3])
print('floor:', cfg['advanced']['semantic_floor'])
print('Config OK')
"
```

### Task 2: Resume file loading

**Files:**
- Modify: `mini_ranker.py` (add `load_resume` function)

- [ ] **Step 1: Write `load_resume` function**

```python
def load_resume(cfg: dict) -> str:
    """Load resume text from file or inline config."""
    resume_file = cfg.get("resume_file", "")
    if resume_file:
        p = Path(resume_file).expanduser()
        if p.exists():
            try:
                if p.suffix.lower() == ".pdf":
                    from PyPDF2 import PdfReader
                    reader = PdfReader(str(p))
                    text = " ".join(page.extract_text() or "" for page in reader.pages)
                    if text.strip():
                        return text
                    print(f"[WARN] PDF extraction returned empty text: {p}")
                else:
                    return p.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                print(f"[WARN] Failed to load {p}: {e}")
        else:
            print(f"[WARN] Resume file not found: {p}")

    # Fallback to inline text
    inline = cfg.get("resume", "")
    if not inline.strip():
        print("[ERROR] No resume text available. Set resume_file or resume in config.yaml.")
        sys.exit(1)
    return inline
```

- [ ] **Step 2: Update `rank()` to accept resume_text parameter**

Change `rank(df)` signature to `rank(df, resume_text)` and replace the hardcoded `RESUME_TEXT` reference on line 557 with the parameter.

- [ ] **Step 3: Update `main()` to load resume and pass to rank**

```python
resume_text = load_resume(CFG)
ranked = rank(df, resume_text)
```

- [ ] **Step 4: Test with a file path**

```bash
python -c "
import mini_ranker as mr
mr.CFG = mr.load_config()
text = mr.load_resume({'resume_file': 'job_ranker/users/example/resume.tex'})
print(f'Loaded {len(text)} chars from resume.tex')
print(text[:200])
"
```

### Task 3: Setup wizard

**Files:**
- Modify: `mini_ranker.py` (add `setup_wizard` function, wire to --setup flag)

- [ ] **Step 1: Write `setup_wizard` function**

```python
def setup_wizard():
    """Interactive wizard to generate config.yaml."""
    if not sys.stdin.isatty():
        print("[ERROR] No config.yaml found. Run with --setup interactively")
        print("or create config.yaml manually. See config.example.yaml.")
        sys.exit(1)

    print("\n  Mini Ranker Setup\n")

    resume_file = input("  Path to your resume (PDF/TXT/TEX): ").strip()
    if resume_file and not Path(resume_file).expanduser().exists():
        print(f"  [WARN] File not found: {resume_file}")

    queries = input("  Job titles to search (comma-separated): ").strip()
    country = input("  Country [India]: ").strip() or "India"
    top = input("  Companies you'd love to work at (comma-separated): ").strip()
    avoid = input("  Companies to avoid (comma-separated): ").strip()
    locations = input("  Preferred locations (comma-separated): ").strip()

    config = {}
    if resume_file:
        config["resume_file"] = resume_file
    if queries:
        config["search_queries"] = [q.strip() for q in queries.split(",") if q.strip()]
    config["country"] = country
    if top:
        config["top_companies"] = [c.strip().lower() for c in top.split(",") if c.strip()]
    if avoid:
        config["avoid_companies"] = [c.strip().lower() for c in avoid.split(",") if c.strip()]
    if locations:
        config["preferred_locations"] = [l.strip().lower() for l in locations.split(",") if l.strip()]

    Path("config.yaml").write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    print("\n  Config saved to config.yaml — edit anytime.\n")
```

- [ ] **Step 2: Wire wizard into main()**

```python
# In argparse setup:
parser.add_argument("--setup", action="store_true", help="Interactive setup wizard")
parser.add_argument("--config", help="Path to config YAML")

# In main(), before load_config:
if args.setup:
    setup_wizard()
    return

# Auto-trigger wizard if no config exists:
if not args.config and not Path("config.yaml").exists():
    print("[INFO] No config.yaml found.")
    setup_wizard()
    # Reload after wizard
```

- [ ] **Step 3: Create config.example.yaml**

Extract current Example profile (DEFAULTS with all tier lists populated) into `config.example.yaml` as a reference.

- [ ] **Step 4: Test wizard flow**

Run `python mini_ranker.py --setup` and verify it generates valid config.yaml.

---

## Chunk 2: Embedding Cache + Skill Extraction

### Task 4: Embedding disk cache

**Files:**
- Modify: `mini_ranker.py` (replace `embed()` function, add cache helpers)

- [ ] **Step 1: Write cache load/save helpers**

```python
CACHE_DIR = Path(".mini_ranker_cache")

def _cache_path():
    return CACHE_DIR / "vectors.npz", CACHE_DIR / "keys.json"

def _load_cache() -> tuple[dict[str, np.ndarray], bool]:
    """Returns {sha256_hex: vector} dict."""
    vec_path, key_path = _cache_path()
    if not vec_path.exists() or not key_path.exists():
        return {}, False
    try:
        keys = json.loads(key_path.read_text())
        data = np.load(vec_path)
        vectors = data["vectors"]
        return {k: vectors[i] for i, k in enumerate(keys)}, True
    except Exception:
        return {}, False

def _save_cache(cache: dict[str, np.ndarray]):
    CACHE_DIR.mkdir(exist_ok=True)
    keys = list(cache.keys())
    vectors = np.stack([cache[k] for k in keys])
    np.savez(CACHE_DIR / "vectors.npz", vectors=vectors)
    (CACHE_DIR / "keys.json").write_text(json.dumps(keys))

def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
```

- [ ] **Step 2: Rewrite `embed()` to use cache**

```python
_embed_cache: dict[str, np.ndarray] = {}
_cache_loaded = False

def embed(texts: list[str], use_cache: bool = True) -> tuple[np.ndarray, int, int]:
    """Returns (vectors, cache_hits, cache_misses)."""
    global _embed_cache, _cache_loaded

    if use_cache and not _cache_loaded:
        _embed_cache, _ = _load_cache()
        _cache_loaded = True

    hashes = [_text_hash(t) for t in texts]
    hits, misses = [], []
    for i, h in enumerate(hashes):
        if use_cache and h in _embed_cache:
            hits.append(i)
        else:
            misses.append(i)

    result = np.zeros((len(texts), 384), dtype=np.float32)

    # Fill from cache
    for i in hits:
        result[i] = _embed_cache[hashes[i]]

    # Compute missing
    if misses:
        model = _get_model()
        missing_texts = [texts[i] for i in misses]
        computed = model.encode(missing_texts, normalize_embeddings=True, show_progress_bar=False)
        for j, i in enumerate(misses):
            result[i] = computed[j]
            if use_cache:
                _embed_cache[hashes[i]] = computed[j]

    return result, len(hits), len(misses)

def save_embed_cache():
    if _embed_cache:
        _save_cache(_embed_cache)
```

- [ ] **Step 3: Update `rank()` to use new embed signature**

Change the embed calls in `rank()`:
```python
resume_vecs, _, _ = embed([resume_text], use_cache=use_cache)
resume_vec = resume_vecs[0]
job_vecs, cache_hits, cache_misses = embed(job_texts, use_cache=use_cache)
```

Store hits/misses for summary display.

- [ ] **Step 4: Wire cache flags into main()**

```python
parser.add_argument("--no-cache", action="store_true", help="Skip embedding cache")
parser.add_argument("--clear-cache", action="store_true", help="Delete embedding cache")

# In main():
if args.clear_cache:
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        print("[CACHE] Cleared")
    return

# After ranking:
if not args.no_cache:
    save_embed_cache()
```

- [ ] **Step 5: Test cache round-trip**

```bash
python -c "
import mini_ranker as mr
import numpy as np

vecs, hits, misses = mr.embed(['hello world', 'test embedding'])
print(f'First run: {hits} hits, {misses} misses')
mr.save_embed_cache()

mr._cache_loaded = False
mr._embed_cache = {}
vecs2, hits2, misses2 = mr.embed(['hello world', 'test embedding'])
print(f'Second run: {hits2} hits, {misses2} misses')
assert hits2 == 2 and misses2 == 0
print('Cache OK')
"
```

### Task 5: Skill extraction

**Files:**
- Modify: `mini_ranker.py` (add SKILL_GROUPS dict, extraction functions, update skills_score)

- [ ] **Step 1: Add SKILL_GROUPS constant**

Place after the other engine constants (BOILERPLATE_PHRASES, etc.):

```python
SKILL_GROUPS = {
    "python": ["python"],
    "java": ["java", "jvm"],
    "go": ["golang", " go "],
    "rust": ["rust"],
    "javascript": ["javascript", "typescript", "node.js", "nodejs"],
    "sql": ["sql", "postgresql", "mysql", "bigquery"],
    "kubernetes": ["kubernetes", "k8s", "kubectl", "helm"],
    "docker": ["docker", "containerization", "containers"],
    "terraform": ["terraform", "terragrunt", "hcl", "infrastructure as code"],
    "ci_cd": ["ci/cd", "cicd", "github actions", "jenkins", "gitlab ci"],
    "aws": ["aws", "amazon web services", "sagemaker", "s3", "ec2"],
    "gcp": ["gcp", "google cloud", "vertex ai", "bigquery"],
    "azure": ["azure", "azure ml"],
    "mlops": ["mlops", "mlflow", "kubeflow", "ml pipeline", "feature store"],
    "llm": ["llm", "large language model", "gpt", "claude", "gemini", "foundation model"],
    "rag": ["rag", "retrieval augmented", "vector search", "vector database"],
    "embeddings": ["embedding", "sentence transformer", "vector representation"],
    "agents": ["agent", "agentic", "multi-agent", "autonomous agent", "langchain", "langgraph"],
    "deep_learning": ["deep learning", "neural network", "pytorch", "tensorflow"],
    "ml_fundamentals": ["machine learning", "scikit-learn", "xgboost", "model training"],
    "data_engineering": ["spark", "airflow", "kafka", "data pipeline", "etl"],
    "monitoring": ["monitoring", "observability", "prometheus", "grafana", "datadog"],
    "sre": ["sre", "reliability", "incident response", "on-call"],
    "genai": ["generative ai", "genai", "gen ai", "text generation"],
    "nlp": ["nlp", "natural language processing", "text classification", "ner"],
    "computer_vision": ["computer vision", "image recognition", "opencv", "yolo"],
    "api": ["rest api", "graphql", "grpc", "fastapi", "flask"],
    "databases": ["redis", "mongodb", "elasticsearch", "duckdb", "pinecone", "weaviate", "chroma"],
    "security": ["security", "authentication", "oauth", "encryption"],
    "linux": ["linux", "bash", "shell scripting"],
}
```

- [ ] **Step 2: Write extraction functions**

```python
def extract_skills(text: str) -> set[str]:
    """Extract matching skill group names from text."""
    t = text.lower()
    found = set()
    for group, variants in SKILL_GROUPS.items():
        if any(v in t for v in variants):
            found.add(group)
    return found

def skill_overlap(resume_skills: set[str], job_skills: set[str]) -> int:
    """Count overlapping skill groups between resume and job."""
    return len(resume_skills & job_skills)
```

- [ ] **Step 3: Update `skills_score` signature**

Add `skill_overlap_count` parameter:

```python
def skills_score(semantic: float, role: str, consulting_damp: float, skill_overlap_count: int = 0) -> float:
    base = semantic * 100.0
    base += min(skill_overlap_count * 2, 8)  # +2 per matching group, capped at +8
    penalty = ROLE_PENALTIES.get(role, 1.0)   # reads from CFG at runtime
    base += max(-8, min((penalty - 1.0) * 50, 10))
    if consulting_damp < 1.0:
        base -= 10
    return max(0.0, min(base, 100.0))
```

- [ ] **Step 4: Wire skill extraction into `rank()`**

In the scoring section of `rank()`:
```python
# Extract skills once
resume_skills = extract_skills(resume_text)
df["_job_skills"] = df["description"].apply(extract_skills)
df["skill_overlap"] = df["_job_skills"].apply(lambda js: skill_overlap(resume_skills, js))

# Update skills_score call:
df["s_skills"] = df.apply(
    lambda r: skills_score(r["semantic_score"], r["functional_role"], r["consulting_damp"], r["skill_overlap"]),
    axis=1,
)
```

- [ ] **Step 5: Test skill extraction**

```bash
python -c "
import mini_ranker as mr
resume_sk = mr.extract_skills('kubernetes terraform mlops llm agent python')
job_sk = mr.extract_skills('We need kubernetes and mlops experience with LLM deployment')
overlap = mr.skill_overlap(resume_sk, job_sk)
print(f'Resume skills: {resume_sk}')
print(f'Job skills: {job_sk}')
print(f'Overlap: {overlap}')
assert overlap >= 3
print('Skill extraction OK')
"
```

---

## Chunk 3: Rich Terminal Output

### Task 6: Rich display layer with graceful fallback

**Files:**
- Modify: `mini_ranker.py` (add display functions, update main)

- [ ] **Step 1: Add rich import with fallback**

At top of file, after other imports:

```python
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
    from rich.text import Text
    RICH = True
except ImportError:
    RICH = False
```

- [ ] **Step 2: Write `display_results_rich` function**

```python
def display_results_rich(ranked: pd.DataFrame, top: int, verbose: bool, stats: dict):
    """Rich terminal output with colored table and summary."""
    console = Console()

    # Tier color map
    tier_colors = {"tier_s": "green", "tier_a": "cyan", "tier_b": "yellow", "tier_c": "white", "tier_d": "red"}

    # Summary panel
    summary_lines = [
        f"Scraped: {stats.get('scraped', '?')} jobs from {stats.get('queries', '?')} queries",
        f"After filters: {stats.get('after_filters', '?')} (blocklist: -{stats.get('blocklist_dropped', 0)}, semantic: -{stats.get('semantic_dropped', 0)}, dedup: -{stats.get('dedup_dropped', 0)})",
    ]
    if stats.get("cache_hits", 0) > 0 or stats.get("cache_misses", 0) > 0:
        summary_lines.append(f"Embeddings: {stats.get('cache_hits', 0)} cached, {stats.get('cache_misses', 0)} computed")
    if stats.get("save_path"):
        summary_lines.append(f"Saved: {stats['save_path']}")

    console.print(Panel("\n".join(summary_lines), title="Summary", border_style="dim"))
    console.print()

    # Results table
    table = Table(title=f"TOP {top} RANKED JOBS", show_lines=False, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Score", width=6)
    table.add_column("Title", min_width=30)
    table.add_column("Company", min_width=20)
    table.add_column("Location", min_width=15)
    table.add_column("Role", width=12)
    if verbose:
        table.add_column("Breakdown", min_width=30)

    for i, row in ranked.head(top).iterrows():
        tier = classify_company_tier(row["company"])
        tier_label = f" [{tier[-1].upper()}]" if tier != "default" else ""
        tier_color = tier_colors.get(tier, "white")

        # Score color
        score = row["final_score"]
        score_style = "bold green" if score >= 60 else ("yellow" if score >= 40 else "dim")

        # Company with tier badge
        company_text = Text(row["company"])
        if tier != "default":
            company_text.append(f" [{tier[-1].upper()}]", style=tier_color)

        # Title with contract flag
        title_text = Text(row["title"])
        if row.get("is_contract", False):
            title_text.append(" CONTRACT", style="bold red")

        # Job URL as hyperlink if available
        if "job_url" in row and row["job_url"]:
            title_text = Text(row["title"])
            title_text.stylize(f"link {row['job_url']}")
            if row.get("is_contract", False):
                title_text.append(" CONTRACT", style="bold red")

        breakdown = ""
        if verbose:
            breakdown = f"sk={row['s_skills']:.0f} co={row['s_company']:.0f} sr={row['s_seniority']:.0f} lo={row['s_location']:.0f} re={row['s_recency']:.0f}"
            if "skill_overlap" in row and row["skill_overlap"] > 0:
                job_skills = row.get("_job_skills", set())
                if isinstance(job_skills, set) and job_skills:
                    breakdown += f" | {', '.join(sorted(job_skills)[:5])}"

        row_data = [
            str(i + 1),
            Text(f"{score:.1f}", style=score_style),
            title_text,
            company_text,
            row["location"][:20],
            row["functional_role"],
        ]
        if verbose:
            row_data.append(breakdown)

        table.add_row(*row_data)

    console.print(table)
```

- [ ] **Step 3: Write `display_results_plain` function**

Keep the current display logic from `main()` as the plain fallback:

```python
def display_results_plain(ranked: pd.DataFrame, top: int, verbose: bool, stats: dict):
    """Plain text fallback when rich is not installed."""
    # Current display logic from main() — the print loop already in the file
    print(f"\n{'=' * 80}")
    print(f"  TOP {top} RANKED JOBS")
    print(f"{'=' * 80}\n")
    # ... (existing loop code)
```

- [ ] **Step 4: Write progress helpers**

```python
def scrape_with_progress(cfg: dict) -> pd.DataFrame:
    """Scrape with rich progress bar if available."""
    from jobspy import scrape_jobs
    queries = cfg["search_queries"]
    all_rows = []

    if RICH:
        console = Console()
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      BarColumn(), MofNCompleteColumn(), console=console) as progress:
            task = progress.add_task("[SCRAPE]", total=len(queries))
            for q in queries:
                progress.update(task, description=f"[SCRAPE] {q}")
                try:
                    jobs = scrape_jobs(
                        site_name=["indeed", "linkedin"],
                        search_term=q,
                        location=cfg.get("country", "India"),
                        results_wanted=1000,
                        hours_old=cfg.get("hours_old", 240),
                        country_indeed=cfg.get("country", "India"),
                    )
                    if isinstance(jobs, pd.DataFrame) and not jobs.empty:
                        all_rows.append(jobs)
                except Exception as e:
                    console.print(f"  [red]FAILED:[/red] {e}")
                progress.advance(task)
    else:
        # Existing plain scrape logic
        for q in queries:
            print(f"[SCRAPE] {q}")
            try:
                jobs = scrape_jobs(
                    site_name=["indeed", "linkedin"], search_term=q,
                    location=cfg.get("country", "India"), results_wanted=1000,
                    hours_old=cfg.get("hours_old", 240), country_indeed=cfg.get("country", "India"),
                )
                if isinstance(jobs, pd.DataFrame) and not jobs.empty:
                    all_rows.append(jobs)
                    print(f"  -> {len(jobs)} results")
            except Exception as e:
                print(f"  -> FAILED: {e}")

    if not all_rows:
        return pd.DataFrame()
    df = pd.concat(all_rows, ignore_index=True)
    if "job_url" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=["job_url"])
    return df.reset_index(drop=True)
```

- [ ] **Step 5: Update `rank()` to collect stats**

Add a `stats` dict that accumulates counts through the pipeline:

```python
def rank(df: pd.DataFrame, resume_text: str, use_cache: bool = True) -> tuple[pd.DataFrame, dict]:
    stats = {"input": len(df)}
    # ... existing pipeline, but capture counts:
    stats["blocklist_dropped"] = dropped
    stats["semantic_dropped"] = ...
    stats["after_filters"] = len(df)
    stats["cache_hits"] = cache_hits
    stats["cache_misses"] = cache_misses
    stats["dedup_dropped"] = before - len(df)
    return df, stats
```

- [ ] **Step 6: Update `main()` to use display functions**

```python
# Add CLI flags:
parser.add_argument("--verbose", action="store_true", help="Show score breakdowns")

# After ranking:
stats["scraped"] = raw_count
stats["queries"] = len(CFG["search_queries"])
stats["save_path"] = str(filename)

if RICH:
    display_results_rich(ranked, args.top, args.verbose, stats)
else:
    display_results_plain(ranked, args.top, args.verbose, stats)
```

- [ ] **Step 7: Test rich output**

```bash
python mini_ranker.py --csv <some_test_csv> --verbose --top 5
```

Verify colored table renders, tier badges show, contract flags are red.

- [ ] **Step 8: Test fallback (no rich)**

```bash
python -c "import mini_ranker; mini_ranker.RICH = False; print('Fallback mode:', not mini_ranker.RICH)"
```

---

## Chunk 4: Final Integration + config.example.yaml

### Task 7: Create config.example.yaml

**Files:**
- Create: `config.example.yaml`

- [ ] **Step 1: Write config.example.yaml**

Extract the current Example profile as the example. This is NOT code — it's a reference users copy and edit.

```yaml
# Mini Ranker — Example Config
# Copy to config.yaml and edit to match your profile.
# Run: python mini_ranker.py --setup  (for interactive setup)

# Your resume — path to file (PDF, TXT, TEX) or inline text
resume_file: ~/resume.pdf
# resume: |
#   Your resume text here...

# What roles are you looking for?
search_queries:
  - ai platform engineer
  - ml platform engineer
  - mlops
  - llmops
  - genai
  - agentic systems

country: India
hours_old: 240

preferred_locations:
  - pune
  - remote
  - maharashtra

# Companies you'd love to work at (mapped to top tier)
top_companies:
  - databricks
  - openai
  - nvidia
  - anthropic
  - google
  - meta
  # ... add yours

# Companies that are good but not dream companies
good_companies:
  - intuit
  - atlassian
  - bloomberg
  - flipkart

# Companies to deprioritize
avoid_companies:
  - wipro
  - infosys
  - tcs
  - cognizant

# Job titles to filter out entirely
title_blocklist:
  - trainee
  - manager
  - sales
  - junior
  - director
  - qa engineer
  - sdet

# Max years of experience in job requirements
max_yoe: 10

# Advanced (optional — sensible defaults built in)
# advanced:
#   okay_companies: [optum, siemens]
#   meh_companies: [ge vernova, bosch]
#   company_aliases: {wandb: weights and biases}
#   scoring_weights: {skills: 0.45, company: 0.15, seniority: 0.15, location: 0.15, recency: 0.10}
```

### Task 8: Final integration and cleanup

**Files:**
- Modify: `mini_ranker.py`

- [ ] **Step 1: Update module docstring**

```python
"""
mini_ranker.py — A personal Bloomberg Terminal for job hunting.

Usage:
    python mini_ranker.py                    # scrape + rank (uses config.yaml)
    python mini_ranker.py --setup            # interactive setup wizard
    python mini_ranker.py --csv jobs.csv     # rank a pre-scraped CSV
    python mini_ranker.py --hours-old 72     # fresher jobs only
    python mini_ranker.py --verbose          # show score breakdowns
    python mini_ranker.py --config my.yaml   # custom config path

Dependencies:
    pip install pandas python-jobspy sentence-transformers numpy pyyaml rich PyPDF2
"""
```

- [ ] **Step 2: Update .gitignore**

Add cache directory:
```
.mini_ranker_cache/
```

- [ ] **Step 3: Full integration test with synthetic data**

```bash
python -c "
import mini_ranker as mr
import pandas as pd

mr.CFG = mr.load_config()
mr.COMPANY_TIERS, mr.COMPANY_ALIASES, mr.TIER_SCORES = mr.build_tiers(mr.CFG)

jobs = pd.DataFrame([
    {'title': 'Senior ML Platform Engineer', 'company': 'Databricks', 'location': 'Pune', 'description': 'Build ML platforms with kubernetes, mlops, LLM inference, agent orchestration.', 'date_posted': '2026-03-12', 'job_url': 'http://a'},
    {'title': 'QA Engineer', 'company': 'Wipro', 'location': 'Bangalore', 'description': 'Manual testing.', 'job_url': 'http://b'},
    {'title': 'AI Infrastructure Engineer', 'company': 'OpenAI', 'location': 'Remote', 'description': 'Design AI infrastructure for LLMs. Kubernetes, GPU clusters, RAG.', 'date_posted': '2026-03-11', 'job_url': 'http://c'},
])

resume = mr.load_resume(mr.CFG)
ranked, stats = mr.rank(jobs, resume)
print(f'Ranked: {len(ranked)} jobs')
print(f'Stats: {stats}')
for _, r in ranked.iterrows():
    print(f'  {r[\"final_score\"]:.1f}  {r[\"title\"]}  @  {r[\"company\"]}')
print('Integration OK')
"
```

- [ ] **Step 4: Verify line count is within budget**

```bash
wc -l mini_ranker.py
# Expected: 1000-1100 lines
```

- [ ] **Step 5: Syntax check**

```bash
python -c "import ast; ast.parse(open('mini_ranker.py').read()); print('Syntax OK')"
```

---

## Verification Checklist

After all tasks are done, verify end-to-end:

- [ ] `python mini_ranker.py --setup` generates valid config.yaml
- [ ] `python mini_ranker.py --csv <test_csv>` ranks with rich output
- [ ] `python mini_ranker.py --csv <test_csv> --verbose` shows score breakdowns + skill matches
- [ ] `python mini_ranker.py --no-cache --csv <test_csv>` works without cache
- [ ] Second run with same data shows cache hits in summary
- [ ] `python mini_ranker.py --clear-cache` removes cache dir
- [ ] Invalid config.yaml gives clear error
- [ ] Missing rich library falls back to plain text
- [ ] Top results are IC AI/ML/platform roles at tiered companies




This is no longer a rough script. It is a coherent ranking engine. The structure is disciplined and most moving parts interact correctly. But several subtle engineering assumptions are hiding inside it. Let’s dissect it like a system reviewer.

⸻

1. Architectural Assumptions

The system assumes the following design philosophy:
	1.	Job discovery is a ranking problem, not a filtering problem.
	2.	Semantic embeddings are the primary relevance signal.
	3.	Heuristic signals improve ranking only after semantic gating.
	4.	Explainability matters more than ML sophistication.
	5.	Data volume is small enough to run fully in-memory.
	6.	A single-file architecture improves usability.

Those assumptions shape every design decision in this file.

⸻

2. Strengths of the Implementation

A. Correct ranking pipeline structure

The ranking flow is logically correct:

scrape → normalize → blocklist filter
      → semantic similarity
      → semantic gating
      → role classification
      → negative keyword filter
      → feature scoring
      → penalties
      → deduplication
      → ranking

This is almost identical to production recommender pipelines used by:
	•	LinkedIn
	•	Airbnb search ranking
	•	job marketplaces

The most important property is gating before scoring, which avoids wasting compute on irrelevant items.

⸻

B. The 5-dimensional scoring model is well balanced

Each dimension measures a different signal:

Dimension	Signal
skills	semantic + overlap
company	tier preference
seniority	experience alignment
location	geographic fit
recency	freshness

Final score:

raw_score =
skills * 0.45 +
company * 0.15 +
seniority * 0.15 +
location * 0.15 +
recency * 0.10

That weighting implicitly encodes a hypothesis:

Job relevance matters more than prestige.

That is a rational assumption.

⸻

C. The semantic gating logic is unusually good

This section is one of the strongest parts of the code.

First gate:

semantic_score >= semantic_floor

Second gate:

semantic_score >= role_threshold

Third gate:

negative keywords filter

Fourth gate:

non-IC gate

This multi-stage gating prevents a very common failure mode of embedding-based systems:

high similarity to irrelevant roles.

⸻

D. Skill extraction is computationally cheap

The implementation:

extract_skills(text)

runs in linear time over a small dictionary.

No model inference is required.

For thousands of job descriptions this is extremely efficient.

Even though it’s heuristic, it acts as a useful weak feature.

⸻

E. Embedding cache design is correct

The cache strategy is solid:

text → SHA256 hash → vector

Advantages:

Deterministic keys
No database required
Portable
Fast lookup

Disk layout:

.mini_ranker_cache/
  vectors.npz
  keys.json

This is a simple but effective vector store.

⸻

F. The display layer is thoughtfully implemented

Two rendering paths:

rich
plain

This prevents hard dependency failures.

The table view surfaces the correct debugging signals:

sk co sr lo re

which makes ranking decisions transparent.

⸻

3. Design Weaknesses

Now the uncomfortable part.

There are several fragile pieces.

⸻

Weakness 1: Company tier classification is fuzzy and unsafe

The logic:

if name in company_string

Example:

name = "meta"
company = "metabase"

Result:

classified as Meta

This is incorrect.

A more reliable approach:

normalized_company == canonical_company

or use token boundaries.

⸻

Weakness 2: Skill extraction has substring collisions

Example problem:

"go" skill detection

Your rule:

"go": ["golang", " go "]

But job descriptions may contain:

"governance"
"going"

This will generate false positives.

Regex boundaries would reduce this problem.

⸻

Weakness 3: Embedding model is extremely small

Model used:

all-MiniLM-L6-v2

Characteristics:

384 dimensions
~22M parameters
very fast

But it struggles with technical nuance.

Example similarity failures:

LLM inference engineer
machine learning researcher

These can appear close even when the roles differ.

Better models exist:

bge-large-en
gte-large
instructor-xl

Trade-off: 3–5x slower.

⸻

Weakness 4: Resume representation is overly compressed

You embed the entire resume as one vector.

resume_vec = embed(resume_text)

This assumes the resume is semantically uniform.

But resumes contain heterogeneous content:
	•	skills
	•	projects
	•	experience
	•	tools
	•	achievements

A single embedding loses structure.

Better approach:

embed_sections(resume)

Then use:

max_similarity(section_vectors, job_vector)


⸻

Weakness 5: Deduplication is weak

Current dedup:

title + company

plus fuzzy seniority stripping.

But job boards frequently repost identical jobs with slightly different titles.

Example:

ML Platform Engineer
Machine Learning Platform Engineer
Senior ML Platform Engineer

Your dedup will treat these as different jobs.

Embedding similarity clustering would solve this.

⸻

Weakness 6: Config merging can produce silent errors

The deep merge logic:

cfg = deep_merge(DEFAULTS, user_cfg)

Consider user config:

advanced:
  scoring_weights:
    skills: 0.7

Deep merge works.

But if the user accidentally writes:

advanced:
  scoring_weights: 0.7

Now scoring_weights becomes a float and later code fails.

The system lacks schema validation.

⸻

Weakness 7: Scraping reliability

The entire pipeline depends on:

python-jobspy

Job boards aggressively block scraping.

You already observed:

403
401

Which means the ranking engine may be excellent but receive no usable data.

⸻

4. Which Side is Stronger?

Supporting arguments dominate.

Why?

Because the system is optimized for a personal workflow, not industrial robustness.

What matters here is:

Interpretability
Fast iteration
Local execution
No infrastructure

Within those constraints, the architecture is well chosen.

⸻

5. Hidden Strength Most People Miss

The most powerful feature here is not the scoring.

It is explainability.

When a job ranks high you can see:

semantic score
skill overlap
company tier
recency

This lets you debug the ranking model interactively.

Many ML ranking systems lose this property.

⸻

6. The One Change That Would Improve This System the Most

Add embedding deduplication before ranking.

Algorithm:

job_embeddings
↓
cosine similarity matrix
↓
cluster similarity > 0.95
↓
keep highest scoring job per cluster

This would eliminate most duplicates across:

LinkedIn
Indeed
company career pages

and dramatically improve result quality.

⸻

7. Final Technical Assessment

This script sits in an interesting category:

a local recommender system.

It combines ideas from:

information retrieval
ranking models
recommender systems
search pipelines

while remaining simple enough to run on a laptop.

For a single Python file, it is unusually well engineered.

If evolved further, the next natural step would be transforming it into:

personal job discovery engine

rather than just a ranking script.

That requires:

feedback learning
semantic deduplication
better job ingestion.

Those three improvements would change the system far more than adding additional heuristics.
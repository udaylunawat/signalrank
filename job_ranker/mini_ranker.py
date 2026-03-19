"""
mini_ranker.py — A personal Bloomberg Terminal for job hunting.

Single-file job ranking engine: 5D additive scoring, company tiers,
semantic gates, seniority logic, contract detection, skill extraction,
embedding cache, and rich terminal output.

Usage:
    python mini_ranker.py                    # scrape + rank (uses config.yaml)
    python mini_ranker.py --setup            # interactive setup wizard
    python mini_ranker.py --csv jobs.csv     # rank a pre-scraped CSV
    python mini_ranker.py --hours-old 72     # fresher jobs only
    python mini_ranker.py --verbose          # show score breakdowns
    python mini_ranker.py --config my.yaml   # custom config path
    python mini_ranker.py --no-cache         # skip embedding cache
    python mini_ranker.py --clear-cache      # delete embedding cache

Dependencies:
    pip install pandas python-jobspy sentence-transformers numpy pyyaml rich PyPDF2
"""

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
    )
    from rich.table import Table
    from rich.text import Text

    RICH = True
except ImportError:
    RICH = False


# ════════════════════════════════════════════════════════════════
# DEFAULTS — Built-in config, overridden by config.yaml
# ════════════════════════════════════════════════════════════════

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
    "top_companies": [
        "databricks", "snowflake", "nvidia", "openai", "anthropic",
        "microsoft", "google", "meta", "apple", "cohere", "mistral ai",
        "adept", "perplexity", "together ai", "scale ai", "glean", "harvey",
        "weights and biases", "arize ai", "hugging face", "langchain",
        "anyscale", "modal", "prefect", "temporal", "astronomer",
        "pinecone", "weaviate", "chroma", "replit", "cognition",
        "adobe", "salesforce", "palantir", "netflix", "stripe",
    ],
    "good_companies": [
        "intuit", "walmart", "visa", "mastercard", "capital one",
        "servicenow", "atlassian", "workday", "bloomberg", "airbnb",
        "spotify", "shopify", "jpmorgan chase", "goldman sachs",
        "blackrock", "palo alto networks", "crowdstrike",
        "samsung research", "qualcomm", "oracle", "barclays", "citi",
        "autodesk", "zendesk", "priceline", "vodafone", "nielseniq",
        "razorpay", "phonepe", "swiggy", "flipkart",
    ],
    "avoid_companies": [
        "wipro", "infosys", "tcs", "tata consultancy services", "hcl",
        "tech mahindra", "cognizant", "capgemini", "ibm", "epam",
        "globallogic", "nagarro", "fractal", "genpact", "accenture",
        "deloitte", "ey", "ntt data",
    ],
    "title_blocklist": [
        "trainee", "manager", "sales", "trainer", "junior",
        "director", "head of",
        "automation engineer", "qa engineer", "test engineer",
        "quality engineer", "sdet",
    ],
    "max_yoe": 10,
    "advanced": {
        "okay_companies": [
            "optum", "unitedhealth", "msci", "siemens healthineers",
            "siemens", "ge healthcare", "pfizer", "roche", "eli lilly",
            "abbvie", "merck", "philips", "ubs", "wolters kluwer",
            "pubmatic", "husqvarna", "persistent systems", "luxoft",
            "fluke", "mahindra",
        ],
        "meh_companies": [
            "ge vernova", "ge", "general electric", "john deere", "bosch",
            "nxp semiconductors", "webengage", "birlasoft", "ltimindtree",
            "expleo", "bridgeai",
        ],
        "company_aliases": {
            "uhg": "unitedhealth", "united health group": "unitedhealth",
            "lilly": "eli lilly", "ge healthineers": "ge healthcare",
            "goldman": "goldman sachs", "capitalone": "capital one",
            "wnb": "weights and biases", "wandb": "weights and biases",
            "huggingface": "hugging face", "jp morgan": "jpmorgan chase",
            "jpmc": "jpmorgan chase", "citibank": "citi", "citigroup": "citi",
        },
        "scoring_weights": {
            "skills": 0.45, "company": 0.15, "seniority": 0.15,
            "location": 0.15, "recency": 0.10,
        },
        "semantic_floor": 0.50,
        "company_semantic_floor": 0.65,
        "hidden_gem_threshold": 0.70,
        "hidden_gem_bonus": 60,
        "contract_penalty": 0.9,
        "role_penalties": {
            "agentic_systems": 1.2, "mlops_llmops": 1.2,
            "platform_devops": 1.2, "software_general": 0.85,
        },
        "role_semantic_thresholds": {
            "software_general": 0.65, "platform_devops": 0.55,
            "agentic_systems": 0.50, "mlops_llmops": 0.50,
        },
    },
}

# Module-level state (populated by main → load_config / build_tiers)
CFG: dict = {}
COMPANY_TIERS: dict = {}
COMPANY_ALIASES: dict = {}
TIER_SCORES: dict = {"tier_s": 100.0, "tier_a": 85.0, "tier_b": 65.0, "tier_c": 45.0, "tier_d": 15.0, "default": 40.0}


# ════════════════════════════════════════════════════════════════
# ENGINE CONSTANTS (not user-configurable)
# ════════════════════════════════════════════════════════════════

BOILERPLATE_PHRASES = [
    "fast paced environment", "dynamic environment",
    "cross functional teams", "stakeholders", "self starter",
    "good communication skills", "work independently",
    "work collaboratively", "various ad hoc", "as assigned",
]

NON_IC_KEYWORDS = {"analyst", "executive", "operations", "process", "hr", "human resource", "trainer", "talent", "sourcing", "business systems"}
IC_ALLOWLIST = {"engineer", "developer", "architect", "systems"}

CONTRACT_SIGNALS = [
    "contract", "part-time", "part time", "freelance",
    "hours per day", "hrs/day", "hours/day", "hrs per day",
    "hr/day", "hr per day", "temporary", "temp position",
    "fixed-term", "fixed term",
]

CONSULTING_KEYWORDS = {"consultant", "consulting", "engagement", "advisory", "client", "manager", "director"}
STRONG_IC_KEYWORDS = {"engineer", "developer", "architect", "platform", "systems", "backend", "ml", "ai"}

TAXONOMY = {
    "architecture_strategy": [
        "enterprise architect", "platform architect", "solution architect",
        "solutions architect", "field solutions architect",
    ],
    "customer_facing": [
        "solutions engineer", "pre-sales", "sales engineer",
        "customer engineer", "field solutions", "forward deployed engineer",
        "forward deployed",
    ],
}

AI_TERMS = ["llm", "agent", "rag", "embedding", "inference", "orchestration"]
DEVOPS_TERMS = ["kubernetes", "terraform", "ci/cd", "pipeline", "monitoring", "sre"]

JUNIOR_KEYWORDS = ["intern", "junior", "entry"]
OVER_SENIOR_KEYWORDS = ["director", "head of", "chief"]
SENIOR_KEYWORDS = ["senior", "lead", "staff", "principal"]

ROLE_NEGATIVE_KEYWORDS = {
    "software_general": ["qa", "tester", "manual testing", "support engineer", "helpdesk", "customer support", "wordpress", "shopify developer"],
    "platform_devops": ["qa", "tester", "frontend", "react", "angular", "ui developer", "wordpress", "shopify developer"],
    "agentic_systems": ["qa", "tester", "data analyst", "business analyst", "power bi", "tableau", "excel heavy", "reporting", "dashboard", "wordpress", "shopify developer"],
}

ROLE_INTENT_CAPS = {"customer_facing": 60, "architecture_strategy": 75}

SKILL_GROUPS = {
    "python": ["python"],
    "java": ["java", "jvm"],
    "go": ["golang", r"\bgo\b"],
    "rust": ["rust"],
    "javascript": ["javascript", "typescript", "node.js", "nodejs"],
    "sql": ["sql", "postgresql", "mysql", "bigquery"],
    "kubernetes": ["kubernetes", "k8s", "kubectl", "helm"],
    "docker": ["docker", "containerization", "containers"],
    "terraform": ["terraform", "terragrunt", "hcl", "infrastructure as code"],
    "ci_cd": ["ci/cd", "cicd", "github actions", "jenkins", "gitlab ci"],
    "aws": ["aws", "amazon web services", "sagemaker", "s3", "ec2"],
    "gcp": ["gcp", "google cloud", "vertex ai"],
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


# ════════════════════════════════════════════════════════════════
# CONFIG SYSTEM
# ════════════════════════════════════════════════════════════════

def _clean_text(text: str) -> str:
    """Strip LaTeX/markup commands from text for better embeddings."""
    # Remove LaTeX comments
    text = re.sub(r"%.*$", "", text, flags=re.MULTILINE)
    # Remove \begin{...} and \end{...} blocks for environments
    text = re.sub(r"\\(?:begin|end)\{[^}]*\}", " ", text)
    # Remove \command[options]{content} → content
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", text)
    # Remove standalone \commands and \command[options]
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    # Remove standalone [...] option blocks (LaTeX document setup)
    text = re.sub(r"\[[^\]]*(?:pt|cm|em|true|false|itemize|enumerate)[^\]]*\]", " ", text)
    # Remove remaining braces, backslashes, and special chars
    text = re.sub(r"[{}\\~^&$#_]", " ", text)
    # Remove lines that are just LaTeX package names or single tokens
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        # Keep lines with meaningful content (multiple words or substantial length)
        if len(line.split()) >= 3 or (len(line) > 30 and any(c.isalpha() for c in line)):
            lines.append(line)
        elif line and not re.match(r"^[a-z-]+$", line):  # skip bare package names
            lines.append(line)
    text = " ".join(lines)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(config_path: str | None = None) -> dict:
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
    if not cfg.get("search_queries"):
        print("[ERROR] No search_queries in config. Run --setup or edit config.yaml.")
        sys.exit(1)
    return cfg


def build_tiers(cfg: dict) -> tuple[dict, dict, dict]:
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


def load_resume(cfg: dict) -> str:
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
                        return _clean_text(text)
                    print(f"[WARN] PDF extraction returned empty text: {p}")
                else:
                    return _clean_text(p.read_text(encoding="utf-8", errors="ignore"))
            except Exception as e:
                print(f"[WARN] Failed to load {p}: {e}")
        else:
            print(f"[WARN] Resume file not found: {p}")

    inline = cfg.get("resume", "")
    if not inline.strip():
        print("[ERROR] No resume text. Set resume_file or resume in config.yaml.")
        sys.exit(1)
    return _clean_text(inline)


def setup_wizard():
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

    config: dict = {}
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
        config["preferred_locations"] = [loc.strip().lower() for loc in locations.split(",") if loc.strip()]

    Path("config.yaml").write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    print("\n  Config saved to config.yaml — edit anytime.\n")


# ════════════════════════════════════════════════════════════════
# SCRAPING
# ════════════════════════════════════════════════════════════════

def scrape_jobs_all(cfg: dict) -> pd.DataFrame:
    from jobspy import scrape_jobs

    queries = cfg["search_queries"]
    country = cfg.get("country", "India")
    hours_old = cfg.get("hours_old", 240)
    all_rows: list[pd.DataFrame] = []

    if RICH:
        console = Console()
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      BarColumn(), MofNCompleteColumn(), console=console) as progress:
            task = progress.add_task("[SCRAPE]", total=len(queries))
            for q in queries:
                progress.update(task, description=f"[SCRAPE] {q}")
                try:
                    jobs = scrape_jobs(
                        site_name=["indeed", "linkedin"], search_term=q,
                        location=country, results_wanted=1000,
                        hours_old=hours_old, country_indeed=country,
                    )
                    if isinstance(jobs, pd.DataFrame) and not jobs.empty:
                        all_rows.append(jobs)
                except Exception as e:
                    console.print(f"  [red]FAILED:[/red] {e}")
                progress.advance(task)
    else:
        for q in queries:
            print(f"[SCRAPE] {q}")
            try:
                jobs = scrape_jobs(
                    site_name=["indeed", "linkedin"], search_term=q,
                    location=country, results_wanted=1000,
                    hours_old=hours_old, country_indeed=country,
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
        df = df.drop_duplicates(subset=["job_url"])
    return df.reset_index(drop=True)


# ════════════════════════════════════════════════════════════════
# EMBEDDING CACHE
# ════════════════════════════════════════════════════════════════

CACHE_DIR = Path(".mini_ranker_cache")

_embed_cache: dict[str, np.ndarray] = {}
_cache_loaded = False
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _load_cache() -> dict[str, np.ndarray]:
    vec_path = CACHE_DIR / "vectors.npz"
    key_path = CACHE_DIR / "keys.json"
    if not vec_path.exists() or not key_path.exists():
        return {}
    try:
        keys = json.loads(key_path.read_text())
        vectors = np.load(vec_path)["vectors"]
        return {k: vectors[i] for i, k in enumerate(keys)}
    except Exception:
        return {}


def _save_cache(cache: dict[str, np.ndarray]):
    if not cache:
        return
    CACHE_DIR.mkdir(exist_ok=True)
    keys = list(cache.keys())
    vectors = np.stack([cache[k] for k in keys])
    np.savez(CACHE_DIR / "vectors.npz", vectors=vectors)
    (CACHE_DIR / "keys.json").write_text(json.dumps(keys))


def embed(texts: list[str], use_cache: bool = True) -> tuple[np.ndarray, int, int]:
    global _embed_cache, _cache_loaded

    if use_cache and not _cache_loaded:
        _embed_cache = _load_cache()
        _cache_loaded = True

    hashes = [_text_hash(t) for t in texts]
    hits, misses = [], []
    for i, h in enumerate(hashes):
        (hits if (use_cache and h in _embed_cache) else misses).append(i)

    result = np.zeros((len(texts), 384), dtype=np.float32)
    for i in hits:
        result[i] = _embed_cache[hashes[i]]

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


def cosine_sim(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    q = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
    m = matrix / norms
    return m @ q


# ════════════════════════════════════════════════════════════════
# SKILL EXTRACTION
# ════════════════════════════════════════════════════════════════

def extract_skills(text: str) -> set[str]:
    t = text.lower()
    found = set()
    for group, variants in SKILL_GROUPS.items():
        for v in variants:
            if v.startswith(r"\b"):
                if re.search(v, t):
                    found.add(group)
                    break
            elif v in t:
                found.add(group)
                break
    return found


def skill_overlap_count(resume_skills: set[str], job_skills: set[str]) -> int:
    return len(resume_skills & job_skills)


# ════════════════════════════════════════════════════════════════
# SCORING DIMENSIONS (each returns 0-100)
# ════════════════════════════════════════════════════════════════

def skills_score(semantic: float, role: str, consulting_damp: float, overlap: int = 0) -> float:
    base = semantic * 100.0
    base += min(overlap * 2, 8)
    penalties = CFG.get("advanced", {}).get("role_penalties", {})
    penalty = penalties.get(role, 1.0)
    base += max(-8, min((penalty - 1.0) * 50, 10))
    if consulting_damp < 1.0:
        base -= 10
    return max(0.0, min(base, 100.0))


def company_score(company: str, semantic: float) -> float:
    adv = CFG.get("advanced", {})
    tier = classify_company_tier(company)
    base = TIER_SCORES.get(tier, TIER_SCORES["default"])

    floor = adv.get("company_semantic_floor", 0.65)
    if tier != "default" and semantic < floor:
        base *= semantic / floor

    gem_thresh = adv.get("hidden_gem_threshold", 0.70)
    gem_bonus = adv.get("hidden_gem_bonus", 60)
    if tier == "default" and semantic >= gem_thresh:
        base = gem_bonus

    return max(0.0, min(base, 100.0))


def seniority_score(title: str, description: str) -> float:
    multiplier = _seniority_multiplier(title, description)
    score = ((multiplier - 0.4) / 0.75) * 90.0 + 10.0
    return max(0.0, min(score, 100.0))


def location_score(location: str) -> float:
    if not location:
        return 30.0
    loc = location.lower()
    for p in CFG.get("preferred_locations", []):
        if p in loc:
            return 100.0
    return 30.0


def recency_score(date_posted) -> float:
    if not date_posted or pd.isna(date_posted):
        return 50.0
    try:
        posted = pd.to_datetime(date_posted, utc=True)
        age_days = (datetime.now(timezone.utc) - posted).days
    except Exception:
        return 50.0

    breakpoints = [(0, 100), (7, 80), (14, 60), (30, 30), (60, 10)]
    if age_days <= 0:
        return 100.0
    if age_days >= 60:
        return 10.0
    for i in range(len(breakpoints) - 1):
        d0, s0 = breakpoints[i]
        d1, s1 = breakpoints[i + 1]
        if d0 <= age_days <= d1:
            frac = (age_days - d0) / (d1 - d0)
            return s0 + frac * (s1 - s0)
    return 10.0


# ════════════════════════════════════════════════════════════════
# HELPERS — Classification, gating, quality
# ════════════════════════════════════════════════════════════════

def normalize_company(name: str) -> str:
    n = re.sub(r"[^\w\s]", " ", name.lower()).strip()
    n = re.sub(r"\s+", " ", n)
    return COMPANY_ALIASES.get(n, n)


def classify_company_tier(company: str) -> str:
    c = normalize_company(company)
    # Exact match first
    for tier in ["tier_s", "tier_a", "tier_b", "tier_c", "tier_d"]:
        if c in COMPANY_TIERS.get(tier, []):
            return tier
    # Word-boundary match to avoid "meta" matching "metabase"
    for tier in ["tier_s", "tier_a", "tier_b", "tier_c", "tier_d"]:
        for name in COMPANY_TIERS.get(tier, []):
            if re.search(r"\b" + re.escape(name) + r"\b", c):
                return tier
    return "default"


def classify_functional_role(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    for role_name, keywords in TAXONOMY.items():
        if any(kw in text for kw in keywords):
            return role_name

    t, d = title.lower(), description.lower()
    ai_score = sum(3 for k in AI_TERMS if k in t) + sum(1 for k in AI_TERMS if k in d)
    devops_score = sum(3 for k in DEVOPS_TERMS if k in t) + sum(1 for k in DEVOPS_TERMS if k in d)

    if ai_score >= 3 and devops_score >= 1:
        return "mlops_llmops"
    if ai_score >= 3:
        return "agentic_systems"
    if devops_score >= 2:
        return "platform_devops"
    return "software_general"


def _seniority_multiplier(title: str, description: str) -> float:
    t = (title or "").lower()
    d = (description or "").lower()

    if any(k in t for k in JUNIOR_KEYWORDS):
        return 0.4
    if any(x in d for x in ["0-2 years", "1-2 years", "2-3 years"]):
        return 0.5
    if any(k in t for k in OVER_SENIOR_KEYWORDS):
        return 0.7

    boost = 1.0
    if any(k in t for k in SENIOR_KEYWORDS):
        boost *= 1.08

    req_yoe = extract_max_yoe(d)
    if req_yoe is not None and req_yoe > CFG.get("max_yoe", 10):
        boost *= 0.9

    return min(boost, 1.15)


def extract_max_yoe(text: str) -> int | None:
    if not isinstance(text, str):
        return None
    found = []
    for m in re.findall(r"(\d+)\s*\+?\s*years", text.lower()):
        if m.isdigit():
            found.append(int(m))
    for m in re.findall(r"(\d+)\s*-\s*(\d+)\s*years", text.lower()):
        found.extend(int(x) for x in m if x.isdigit())
    return max(found) if found else None


def consulting_dampener(title: str) -> float:
    t = title.lower()
    if any(k in t for k in CONSULTING_KEYWORDS) and not any(k in t for k in STRONG_IC_KEYWORDS):
        return 0.8
    return 1.0


def description_quality(description: str) -> float:
    if not isinstance(description, str):
        return 0.70
    text = description.lower()
    length = len(text)

    lp = 0.75 if length < 200 else (0.85 if length < 400 else 1.0)
    hits = sum(1 for p in BOILERPLATE_PHRASES if p in text)
    bp = max(0.85, 1.0 - 0.05 * hits)
    tokens = set(re.findall(r"\b[a-zA-Z_]{4,}\b", text))
    density = len(tokens) / max(length / 1000.0, 1.0)
    tp = 0.85 if density < 8 else (0.92 if density < 12 else 1.0)

    return round(lp * bp * tp, 3)


def is_non_ic(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in NON_IC_KEYWORDS) and not any(k in t for k in IC_ALLOWLIST)


def is_contract(title: str, description: str) -> bool:
    text = (title + " " + (description or "")[:200]).lower().replace("\\", "")
    return any(s in text for s in CONTRACT_SIGNALS)


def passes_title_blocklist(title: str) -> bool:
    t = title.lower()
    for blocked in CFG.get("title_blocklist", []):
        if re.search(r"\b" + re.escape(blocked) + r"\b", t):
            return False
    return True


def violates_negative_keywords(text: str, role: str) -> bool:
    negatives = ROLE_NEGATIVE_KEYWORDS.get(role, [])
    t = text.lower()
    return any(kw in t for kw in negatives)


# ════════════════════════════════════════════════════════════════
# DEDUPLICATION
# ════════════════════════════════════════════════════════════════

def _strip_seniority(title: str) -> str:
    t = re.sub(r"\b(senior|sr\.?|junior|jr\.?|lead|staff|principal|ii|iii|iv)\b", "", title.lower())
    return re.sub(r"\s+", " ", t).strip()


def dedup(df: pd.DataFrame) -> pd.DataFrame:
    if "job_url" in df.columns:
        df = df.drop_duplicates(subset=["job_url"], keep="first")
    df = df.drop_duplicates(subset=["title", "company"], keep="first")
    df["_fuzzy_key"] = df.apply(
        lambda r: _strip_seniority(str(r["title"])) + "|" + str(r["company"]).lower(), axis=1,
    )
    df = df.drop_duplicates(subset=["_fuzzy_key"], keep="first")
    df = df.drop(columns=["_fuzzy_key"])
    return df.reset_index(drop=True)


# ════════════════════════════════════════════════════════════════
# RANKING PIPELINE
# ════════════════════════════════════════════════════════════════

def rank(df: pd.DataFrame, resume_text: str, use_cache: bool = True) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    adv = CFG.get("advanced", {})
    weights = adv.get("scoring_weights", DEFAULTS["advanced"]["scoring_weights"])
    semantic_floor = adv.get("semantic_floor", 0.50)
    role_thresholds = adv.get("role_semantic_thresholds", {})
    contract_penalty = adv.get("contract_penalty", 0.9)

    stats: dict = {"input": len(df), "blocklist_dropped": 0, "semantic_dropped": 0, "cache_hits": 0, "cache_misses": 0, "dedup_dropped": 0, "after_filters": 0}

    # Normalize columns
    df["title"] = df["title"].fillna("").astype(str)
    df["company"] = df["company"].fillna("").astype(str)
    df["location"] = df["location"].fillna("").astype(str)
    df["description"] = df["description"].fillna("").astype(str)

    # 1. Filter: title blocklist
    mask = df["title"].apply(passes_title_blocklist)
    stats["blocklist_dropped"] = (~mask).sum()
    df = df[mask].reset_index(drop=True)

    if df.empty:
        return df, stats

    # 2. Embed
    job_texts = ("ROLE: " + df["title"] + "\nRESPONSIBILITIES: " + df["description"].str[:5000]).tolist()
    resume_vecs, _, _ = embed([resume_text], use_cache=use_cache)
    resume_vec = resume_vecs[0]
    job_vecs, cache_hits, cache_misses = embed(job_texts, use_cache=use_cache)
    df["semantic_score"] = cosine_sim(resume_vec, job_vecs)
    stats["cache_hits"] = cache_hits
    stats["cache_misses"] = cache_misses

    # 3. Gate: semantic floors
    before_sem = len(df)
    df = df[df["semantic_score"] >= semantic_floor].reset_index(drop=True)

    if df.empty:
        stats["semantic_dropped"] = before_sem
        return df, stats

    df["functional_role"] = df.apply(lambda r: classify_functional_role(r["title"], r["description"]), axis=1)

    # Non-IC gate
    non_ic_mask = df["title"].apply(is_non_ic)
    non_ic_fail = non_ic_mask & (df["semantic_score"] < 0.75)
    df = df[~non_ic_fail].reset_index(drop=True)

    # Role-aware thresholds
    df = df[df.apply(
        lambda r: r["semantic_score"] >= role_thresholds.get(r["functional_role"], semantic_floor), axis=1
    )].reset_index(drop=True)

    # Negative keyword gate
    df = df[df.apply(
        lambda r: not violates_negative_keywords(f"{r['title']} {r['description']}", r["functional_role"]), axis=1
    )].reset_index(drop=True)

    stats["semantic_dropped"] = before_sem - len(df)

    if df.empty:
        return df, stats

    # 4. Score: 5D additive model
    resume_skills = extract_skills(resume_text)
    df["_job_skills"] = df["description"].apply(extract_skills)
    df["skill_overlap"] = df["_job_skills"].apply(lambda js: skill_overlap_count(resume_skills, js))
    df["consulting_damp"] = df["title"].apply(consulting_dampener)

    df["s_skills"] = df.apply(
        lambda r: skills_score(r["semantic_score"], r["functional_role"], r["consulting_damp"], r["skill_overlap"]),
        axis=1,
    )
    df["s_company"] = df.apply(lambda r: company_score(r["company"], r["semantic_score"]), axis=1)
    df["s_seniority"] = df.apply(lambda r: seniority_score(r["title"], r["description"]), axis=1)
    df["s_location"] = df["location"].apply(location_score)
    df["s_recency"] = df["date_posted"].apply(recency_score) if "date_posted" in df.columns else 50.0

    df["raw_score"] = (
        df["s_skills"]    * weights["skills"]
        + df["s_company"]   * weights["company"]
        + df["s_seniority"] * weights["seniority"]
        + df["s_location"]  * weights["location"]
        + df["s_recency"]   * weights["recency"]
    )

    # 5. Penalize
    df["is_contract"] = df.apply(lambda r: is_contract(r["title"], r["description"]), axis=1)
    df["desc_quality"] = df["description"].apply(description_quality)
    df["final_score"] = df["raw_score"] * df["desc_quality"]
    df.loc[df["is_contract"], "final_score"] *= contract_penalty

    # 6. Cap
    for role_name, cap in ROLE_INTENT_CAPS.items():
        m = df["functional_role"] == role_name
        df.loc[m, "final_score"] = df.loc[m, "final_score"].clip(upper=cap)

    # 7. Dedup
    df = df.sort_values("final_score", ascending=False).reset_index(drop=True)
    before_dedup = len(df)
    df = dedup(df)
    stats["dedup_dropped"] = before_dedup - len(df)
    stats["after_filters"] = len(df)

    df = df.sort_values("final_score", ascending=False).reset_index(drop=True)
    return df, stats


# ════════════════════════════════════════════════════════════════
# DISPLAY
# ════════════════════════════════════════════════════════════════

def display_results_rich(ranked: pd.DataFrame, top: int, verbose: bool, stats: dict):
    console = Console()
    tier_colors = {"tier_s": "green", "tier_a": "cyan", "tier_b": "yellow", "tier_c": "white", "tier_d": "red"}

    # Summary
    lines = [
        f"Scraped: {stats.get('scraped', '?')} jobs from {stats.get('queries', '?')} queries",
        f"After filters: {stats.get('after_filters', '?')} "
        f"(blocklist: -{stats.get('blocklist_dropped', 0)}, "
        f"semantic: -{stats.get('semantic_dropped', 0)}, "
        f"dedup: -{stats.get('dedup_dropped', 0)})",
    ]
    if stats.get("cache_hits", 0) or stats.get("cache_misses", 0):
        lines.append(f"Embeddings: {stats.get('cache_hits', 0)} cached, {stats.get('cache_misses', 0)} computed")
    if stats.get("save_path"):
        lines.append(f"Saved: {stats['save_path']}")
    console.print(Panel("\n".join(lines), title="Summary", border_style="dim"))
    console.print()

    # Table
    table = Table(title=f"TOP {min(top, len(ranked))} RANKED JOBS", show_lines=False, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Score", width=6)
    table.add_column("Title", min_width=30)
    table.add_column("Company", min_width=20)
    table.add_column("Location", min_width=12)
    table.add_column("Role", width=14)
    if verbose:
        table.add_column("Breakdown", min_width=35)

    for idx, (_, row) in enumerate(ranked.head(top).iterrows()):
        tier = classify_company_tier(row["company"])
        tier_color = tier_colors.get(tier, "white")
        score = row["final_score"]
        score_style = "bold green" if score >= 60 else ("yellow" if score >= 40 else "dim")

        # Title (hyperlinked if URL available)
        title_text = Text(row["title"])
        if "job_url" in row.index and pd.notna(row.get("job_url")):
            title_text.stylize(f"link {row['job_url']}")
        if row.get("is_contract", False):
            title_text.append(" CONTRACT", style="bold red")

        # Company with tier badge
        company_text = Text(row["company"])
        if tier != "default":
            company_text.append(f" [{tier[-1].upper()}]", style=f"bold {tier_color}")

        breakdown = ""
        if verbose:
            breakdown = f"sk={row['s_skills']:.0f} co={row['s_company']:.0f} sr={row['s_seniority']:.0f} lo={row['s_location']:.0f} re={row['s_recency']:.0f}"
            if row.get("skill_overlap", 0) > 0:
                js = row.get("_job_skills", set())
                if isinstance(js, set) and js:
                    breakdown += f" | {', '.join(sorted(js)[:5])}"

        row_data = [
            str(idx + 1),
            Text(f"{score:.1f}", style=score_style),
            title_text,
            company_text,
            (row["location"] or "")[:20],
            row["functional_role"],
        ]
        if verbose:
            row_data.append(breakdown)
        table.add_row(*row_data)

    console.print(table)


def display_results_plain(ranked: pd.DataFrame, top: int, verbose: bool, stats: dict):
    print(f"\n{'=' * 80}")
    print(f"  TOP {min(top, len(ranked))} RANKED JOBS")
    print(f"{'=' * 80}")
    if stats:
        print(f"  Scraped: {stats.get('scraped', '?')} | Filtered: {stats.get('after_filters', '?')} | "
              f"Cache: {stats.get('cache_hits', 0)} hit / {stats.get('cache_misses', 0)} miss")
    print()

    for idx, (_, row) in enumerate(ranked.head(top).iterrows()):
        tier = classify_company_tier(row["company"])
        tier_label = f" [{tier.upper()}]" if tier != "default" else ""
        contract_label = " [CONTRACT]" if row.get("is_contract", False) else ""

        print(f"  #{idx+1:>2}  {row['final_score']:5.1f}  {row['title']}")
        print(f"        {row['company']}{tier_label}{contract_label}")
        print(f"        {row['location']}  |  {row['functional_role']}")
        if verbose:
            print(f"        sk={row['s_skills']:.0f}  co={row['s_company']:.0f}  sr={row['s_seniority']:.0f}  lo={row['s_location']:.0f}  re={row['s_recency']:.0f}", end="")
            if row.get("skill_overlap", 0) > 0:
                js = row.get("_job_skills", set())
                if isinstance(js, set):
                    print(f"  | {', '.join(sorted(js)[:5])}", end="")
            print()
        print()

    if stats.get("save_path"):
        print(f"  [SAVED] {stats['save_path']}")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Mini Job Ranker — your personal Bloomberg Terminal for jobs")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--setup", action="store_true", help="Interactive setup wizard")
    group.add_argument("--csv", help="Path to pre-scraped CSV (skip scraping)")
    parser.add_argument("--config", help="Path to config YAML")
    parser.add_argument("--hours-old", type=int, help="Max job age in hours")
    parser.add_argument("--top", type=int, default=20, help="Number of top results to display")
    parser.add_argument("--verbose", action="store_true", help="Show score breakdowns")
    parser.add_argument("--no-cache", action="store_true", help="Skip embedding cache")
    parser.add_argument("--clear-cache", action="store_true", help="Delete embedding cache")
    args = parser.parse_args()

    # Clear cache
    if args.clear_cache:
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
            print("[CACHE] Cleared")
        else:
            print("[CACHE] Nothing to clear")
        return

    # Setup wizard
    if args.setup:
        setup_wizard()
        return

    # Auto-trigger wizard if no config
    if not args.config and not Path("config.yaml").exists():
        print("[INFO] No config.yaml found.")
        setup_wizard()

    # Load config
    global CFG, COMPANY_TIERS, COMPANY_ALIASES, TIER_SCORES
    CFG = load_config(args.config)
    COMPANY_TIERS, COMPANY_ALIASES, TIER_SCORES = build_tiers(CFG)

    # CLI overrides
    if args.hours_old is not None:
        CFG["hours_old"] = args.hours_old

    # Load resume
    resume_text = load_resume(CFG)

    # Load jobs
    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        df = scrape_jobs_all(CFG)

    if df.empty:
        print("No jobs found.")
        return

    raw_count = len(df)

    # Rank
    ranked, stats = rank(df, resume_text, use_cache=not args.no_cache)
    stats["scraped"] = raw_count
    stats["queries"] = len(CFG["search_queries"])

    if ranked.empty:
        print("No jobs survived ranking filters.")
        return

    # Save
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = outputs_dir / f"mini_ranked_{timestamp}.csv"

    # Drop set columns before saving
    save_cols = [c for c in ranked.columns if c != "_job_skills"]
    ranked[save_cols].to_csv(filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
    stats["save_path"] = str(filename)

    # Save cache
    if not args.no_cache:
        save_embed_cache()

    # Display
    if RICH:
        display_results_rich(ranked, args.top, args.verbose, stats)
    else:
        display_results_plain(ranked, args.top, args.verbose, stats)


if __name__ == "__main__":
    main()

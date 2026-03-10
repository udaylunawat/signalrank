# ================================
# FILE: config_schema.py (v2)
# ================================
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ==================================================
# PATHS
# ==================================================
class PathsConfig(BaseModel):
    project_root: str
    cache_dir: str
    corpus_dir: str
    outputs_dir: str
    workspaces_dir: str
    users_dir: str


# ==================================================
# RESUME / WORKSPACE
# ==================================================
class ResumePDFConfig(BaseModel):
    max_pages: int


class ResumeLaTeXConfig(BaseModel):
    strip_comments: bool
    collapse_whitespace: bool


class ResumeEmbeddingConfig(BaseModel):
    mode: str = Field(..., description="prefix_only | skills_only | prefix_plus_skills")
    separator: str


class ResumeConfig(BaseModel):
    default_path: str
    allowed_formats: List[str]
    pdf: ResumePDFConfig
    latex: ResumeLaTeXConfig
    embedding_prefix: str
    embedding: ResumeEmbeddingConfig
    embedding_prefix_by_use_case: Dict[str, str] = {}


class WorkspacePersistConfig(BaseModel):
    distilled_resume: bool
    resume_embedding: bool


class WorkspaceConfig(BaseModel):
    template: str
    persist: WorkspacePersistConfig


# ==================================================
# RANKING
# ==================================================
class SkillOverlapConfig(BaseModel):
    enabled: bool
    alpha: float
    min_overlap: int
    cap_multiplier: float
    debug: bool = False


class LLMVetoConfig(BaseModel):
    enabled: bool
    top_n: int
    model_max_tokens: int
    hard_fail_on_error: bool = False
    penalty_multiplier: float


class SeniorityPenaltyConfig(BaseModel):
    junior_multiplier: float
    low_yoe_multiplier: float
    title_keywords: Dict[str, List[str]]


class RankingConfig(BaseModel):
    # semantic
    min_semantic_score: float
    semantic_company_floor: float

    # experience
    max_yoe_cap: int
    yoe_penalty_threshold: int
    yoe_mismatch_penalty: float
    seniority_penalty: SeniorityPenaltyConfig

    # recency
    enable_recency_decay: bool
    recency_half_life_days: int

    # functional role penalties
    functional_role_penalties: Dict[str, float]

    # skill overlap
    skill_overlap: SkillOverlapConfig

    # hard filters
    hard_title_blocklist: List[str]

    # llm veto
    llm_veto: LLMVetoConfig

    # optional allowlist
    allowed_functional_roles: List[str] = []


# ==================================================
# FUNCTIONAL ROLE VOCABULARY
# ==================================================
class FunctionalRoleTermsConfig(BaseModel):
    ai: List[str]
    devops: List[str]
    security: List[str]


# ==================================================
# COMPANY SCORING
# ==================================================
class CompanyScoringConfig(BaseModel):
    tiers_file: str
    default_weight: float
    preferred_companies: List[str] = []
    aliases: Dict[str, str] = {}


# ==================================================
# PROFILES
# ==================================================
class ProfileLLMConfig(BaseModel):
    use_search_expansion: bool
    use_skill_normalization: bool
    use_match_explanations: bool


class ProfileConfig(BaseModel):
    description: str
    skip_junior_roles: bool
    skip_manager_roles: bool
    exclude_keywords: List[str]
    deprioritized_companies: List[str] = []
    llm: ProfileLLMConfig


# ==================================================
# EMBEDDINGS
# ==================================================
class EmbeddingsTextConfig(BaseModel):
    max_chars: int
    normalize_embeddings: bool


class EmbeddingsConfig(BaseModel):
    model_name: str
    embedding_dim: int
    device: str
    text: EmbeddingsTextConfig


# ==================================================
# LLM
# ==================================================
class LLMCacheConfig(BaseModel):
    enabled: bool
    ttl_seconds: int


class LLMRateLimitConfig(BaseModel):
    max_concurrency: int
    call_cooldown_seconds: float


class LLMConfig(BaseModel):
    provider: str
    api_key_env: str
    model_pool: List[str]
    cache: LLMCacheConfig
    rate_limits: LLMRateLimitConfig


# ==================================================
# SCRAPING
# ==================================================
class ScrapingVolumeConfig(BaseModel):
    max_jobs_per_query: int
    max_pages: int


class ScrapingLinkedInAPIConfig(BaseModel):
    enabled: bool
    max_requests_per_minute: int
    page_limit: int
    timeout_seconds: int
    max_results_per_query: int
    sources: List[str]


class ScrapingSitesConfig(BaseModel):
    enabled: List[str]


class QueryClusterConfig(BaseModel):
    match: List[str]


class ScrapingConfig(BaseModel):
    min_description_length: int
    use_multiprocessing: bool
    volume: ScrapingVolumeConfig
    sites: Dict[str, ScrapingSitesConfig]
    linkedin_api: ScrapingLinkedInAPIConfig
    query_clusters: Dict[str, QueryClusterConfig]


# ==================================================
# CACHE
# ==================================================
class CacheQueryConfig(BaseModel):
    max_files: int
    max_age_hours: int


class CacheRoleConfig(BaseModel):
    ttl_days: int


class CacheConfig(BaseModel):
    queries: CacheQueryConfig
    role_classification: CacheRoleConfig


# ==================================================
# OUTPUTS
# ==================================================
class PreviewConfig(BaseModel):
    enabled: bool
    rows: int
    drop_columns: List[str]


class OutputsConfig(BaseModel):
    ranked_jobs_file: str
    ranked_corpus_file: str
    preview_file: str
    overwrite: bool
    retain_previous_runs: bool
    preview: PreviewConfig


# ==================================================
# SCHEDULER / LOGGING / ENV
# ==================================================
class SchedulerConfig(BaseModel):
    enabled: bool
    check_interval_seconds: int
    stale_after_hours: int
    auto_start_streamlit: bool
    lockfile: str


class LoggingConfig(BaseModel):
    level: str
    format: str
    log_to_file: bool
    log_file: str


class EnvironmentConfig(BaseModel):
    omp_num_threads: int
    mkl_num_threads: int
    openblas_num_threads: int
    veclib_maximum_threads: int
    numexpr_num_threads: int
    torch_num_threads: int
    tokenizers_parallelism: bool


# ==================================================
# SEARCH
# ==================================================
class PersonaOverrideConfig(BaseModel):
    extra_queries: List[str]


class LiteralQueryRulesConfig(BaseModel):
    forbid_tokens: List[str]
    min_words: int


class SearchConfig(BaseModel):
    prompt: str
    min_query_length: int
    anchors: List[str]
    invalid_tokens: List[str]
    normalization: Dict[str, str]
    persona_overrides: Dict[str, PersonaOverrideConfig] = {}

    # NEW (required by plan_search.py)
    literal_query_rules: LiteralQueryRulesConfig


# ==================================================
# USERS
# ==================================================
class UserUseCaseConfig(BaseModel):
    profile: str
    resume_path: str
    description: Optional[str] = None


class UserConfig(BaseModel):
    default_profile: str
    default_use_case: str
    resume_path: str
    use_cases: Dict[str, UserUseCaseConfig]


# ==================================================
# ROOT SETTINGS (v2)
# ==================================================
class Settings(BaseModel):
    version: int

    paths: PathsConfig
    resume: ResumeConfig
    workspace: WorkspaceConfig

    ranking: RankingConfig
    functional_role_terms: FunctionalRoleTermsConfig
    company_scoring: CompanyScoringConfig
    profiles: Dict[str, ProfileConfig]

    embeddings: EmbeddingsConfig
    llm: LLMConfig
    scraping: ScrapingConfig
    cache: CacheConfig
    outputs: OutputsConfig
    scheduler: SchedulerConfig
    logging: LoggingConfig
    environment: EnvironmentConfig

    search: SearchConfig
    skills: Dict[str, Any]

    users: Dict[str, UserConfig]

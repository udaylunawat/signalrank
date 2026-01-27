# ================================
# FILE: config_schema.py
# ================================
from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class PathsConfig(BaseModel):
    project_root: str
    cache_dir: str
    corpus_dir: str
    outputs_dir: str
    # embeddings_dir: str
    workspaces_dir: str
    users_dir: str


class RankingConfig(BaseModel):
    min_semantic_score: float
    max_yoe_cap: int
    yoe_penalty_threshold: int
    yoe_mismatch_penalty: float
    enable_recency_decay: bool
    recency_half_life_days: int


class CompanyScoringConfig(BaseModel):
    tiers_file: str
    default_weight: float
    preferred_companies: List[str] = []
    aliases: Dict[str, str] = {}


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


class EmbeddingsTextConfig(BaseModel):
    max_chars: int
    normalize_embeddings: bool


class EmbeddingsConfig(BaseModel):
    model_name: str
    embedding_dim: int
    device: str
    text: EmbeddingsTextConfig


class CacheQueryConfig(BaseModel):
    max_files: int
    max_age_hours: int


class CacheConfig(BaseModel):
    queries: CacheQueryConfig


class SchedulerConfig(BaseModel):
    enabled: bool
    check_interval_seconds: int
    stale_after_hours: int
    auto_start_streamlit: bool


class LoggingConfig(BaseModel):
    level: str
    format: str
    log_to_file: bool
    log_file: str


class Settings(BaseModel):
    version: int
    paths: PathsConfig
    ranking: RankingConfig
    company_scoring: CompanyScoringConfig
    profiles: Dict[str, ProfileConfig]
    embeddings: EmbeddingsConfig
    cache: CacheConfig
    scheduler: SchedulerConfig
    logging: LoggingConfig
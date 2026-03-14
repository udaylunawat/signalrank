# batch/context.py
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# --------------------------------------------------
# Package paths
# --------------------------------------------------
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PACKAGE_ROOT / "config"
USERS_DIR = PACKAGE_ROOT / "users"


# --------------------------------------------------
# Context
# --------------------------------------------------
@dataclass(frozen=True)
class Context:
    user: str
    use_case: str
    config: dict
    config_fp: str
    resume_text: str
    db_path: Path


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def _fingerprint(obj: dict) -> str:
    return hashlib.md5(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_resume_text(user: str) -> str:
    """
    Load resume from:
      job_ranker/users/<user>/resume.(pdf|tex)
    """

    user_dir = USERS_DIR / user
    if not user_dir.exists():
        raise FileNotFoundError(f"User directory not found: {user_dir}")

    candidates = list(user_dir.glob("resume.pdf")) + list(user_dir.glob("resume.tex"))

    if not candidates:
        raise FileNotFoundError(
            f"No resume found under {user_dir} " "(expected resume.pdf or resume.tex)"
        )

    p = candidates[0]

    if p.suffix.lower() == ".pdf":
        from PyPDF2 import PdfReader

        reader = PdfReader(str(p))
        return " ".join(page.extract_text() or "" for page in reader.pages)

    return p.read_text(encoding="utf-8", errors="ignore")


# --------------------------------------------------
# Main resolver
# --------------------------------------------------
def resolve_context(user: str, use_case: str | None) -> Context:
    if "streamlit" in sys.modules:
        raise RuntimeError("resolve_context() must not be called from Streamlit UI")
    if not user:
        raise ValueError("user is required")

    use_case = use_case or "default"

    # --------------------------------------------------
    # Load base config
    # --------------------------------------------------
    base_cfg = yaml.safe_load((CONFIG_DIR / "base.yaml").read_text())
    skills_cfg = yaml.safe_load((CONFIG_DIR / "skills.yaml").read_text())

    cfg = deep_merge(base_cfg, skills_cfg)

    # --------------------------------------------------
    # Optional per-user override (DEEP MERGE)
    # --------------------------------------------------
    override_path = CONFIG_DIR / "overrides" / f"{user}.yaml"
    if override_path.exists():
        override_cfg = yaml.safe_load(override_path.read_text())
        cfg = deep_merge(cfg, override_cfg)

        from job_ranker.batch.logging_utils import log_config_override

        log_config_override(user, override_cfg)

    # --------------------------------------------------
    # Validate required engine keys
    # --------------------------------------------------
    required = [
        "functional_role_taxonomy",
        "functional_role_terms",
        "functional_role_thresholds",
        "ranking",
    ]
    for k in required:
        if k not in cfg:
            raise ValueError(f"Missing required config key: {k}")
    if "role_semantic_thresholds" not in cfg["ranking"]:
        raise ValueError("ranking.role_semantic_thresholds must be defined")

    if "caps" not in cfg["ranking"]:
        raise ValueError("ranking.caps must be defined")
    if "min_semantic_score" not in cfg["ranking"]:
        raise ValueError("ranking.min_semantic_score must be defined")

    cfg_fp = _fingerprint(cfg)

    # --------------------------------------------------
    # Resume
    # --------------------------------------------------
    resume_text = _load_resume_text(user)

    # --------------------------------------------------
    # Storage
    # --------------------------------------------------
    db_path = (PACKAGE_ROOT / cfg["paths"]["db_path"]).resolve()

    return Context(
        user=user,
        use_case=use_case,
        config=cfg,
        config_fp=cfg_fp,
        resume_text=resume_text,
        db_path=db_path,
    )


def resolve_ui_context(user: str, use_case: str):
    if not user:
        raise ValueError("user is required")

    use_case = use_case or "default"

    base_cfg = yaml.safe_load((CONFIG_DIR / "base.yaml").read_text())
    skills_cfg = yaml.safe_load((CONFIG_DIR / "skills.yaml").read_text())

    cfg = deep_merge(base_cfg, skills_cfg)

    override_path = CONFIG_DIR / "overrides" / f"{user}.yaml"
    if override_path.exists():
        override_cfg = yaml.safe_load(override_path.read_text())
        cfg = deep_merge(cfg, override_cfg)

    if "min_semantic_score" not in cfg.get("ranking", {}):
        raise ValueError("ranking.min_semantic_score must be defined")

    resume_text = _load_resume_text(user)
    cfg_fp = _fingerprint(cfg)
    db_path = (PACKAGE_ROOT / cfg["paths"]["db_path"]).resolve()

    return Context(
        user=user,
        use_case=use_case,
        config=cfg,
        config_fp=cfg_fp,
        resume_text=resume_text,
        db_path=db_path,
    )

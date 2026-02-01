# batch/context.py
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from job_ranker.storage.store import Store

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
    store: Store


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def _fingerprint(obj: dict) -> str:
    return hashlib.md5(json.dumps(obj, sort_keys=True).encode()).hexdigest()


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

    # default use case (pure label)
    use_case = use_case or "default"

    # --------------------------------------------------
    # Load base config (global only)
    # --------------------------------------------------
    base_cfg = yaml.safe_load((CONFIG_DIR / "base.yaml").read_text())
    skills_cfg = yaml.safe_load((CONFIG_DIR / "skills.yaml").read_text())
    base_cfg = {**base_cfg, **skills_cfg}
    # Optional per-user override
    required = [
        "functional_role_taxonomy",
        "functional_role_terms",
        "functional_role_thresholds",
    ]
    for k in required:
        if k not in base_cfg:
            raise ValueError(f"Missing required config key: {k}")
    override_path = CONFIG_DIR / "overrides" / f"{user}.yaml"
    if override_path.exists():
        override_cfg = yaml.safe_load(override_path.read_text())
        base_cfg = {**base_cfg, **override_cfg}

        from job_ranker.batch.logging_utils import log_config_override

        if override_path.exists():
            override_cfg = yaml.safe_load(override_path.read_text())
            base_cfg = {**base_cfg, **override_cfg}
            log_config_override(user, override_cfg)

    cfg_fp = _fingerprint(base_cfg)

    # --------------------------------------------------
    # Resume
    # --------------------------------------------------
    resume_text = _load_resume_text(user)

    # --------------------------------------------------
    # Storage
    # --------------------------------------------------
    db_path = (PACKAGE_ROOT / base_cfg["paths"]["db_path"]).resolve()
    try:
        store = Store(db_path)
    except Exception as e:
        raise RuntimeError(f"""
    ❌ Failed to acquire DuckDB write lock.

    Another process is holding the database.

    Most common causes:
    - Streamlit UI is running
    - Another batch job is active

    Fix:
    - Stop Streamlit before running batch
    - OR run UI in read-only mode

    Original error:
    {e}
    """) from e

    return Context(
        user=user,
        use_case=use_case,
        config=base_cfg,
        config_fp=cfg_fp,
        resume_text=resume_text,
        db_path=db_path,
        store=store,
    )


# batch/context.py


def resolve_ui_context(user: str, use_case: str):
    """
    UI-safe context:
    - NO Store
    - NO write DB connection
    - config + resume only
    """

    if not user:
        raise ValueError("user is required")

    use_case = use_case or "default"

    base_cfg = yaml.safe_load((CONFIG_DIR / "base.yaml").read_text())
    skills_cfg = yaml.safe_load((CONFIG_DIR / "skills.yaml").read_text())
    base_cfg = {**base_cfg, **skills_cfg}

    override_path = CONFIG_DIR / "overrides" / f"{user}.yaml"
    if override_path.exists():
        override_cfg = yaml.safe_load(override_path.read_text())
        base_cfg = {**base_cfg, **override_cfg}

    resume_text = _load_resume_text(user)
    cfg_fp = _fingerprint(base_cfg)
    db_path = (PACKAGE_ROOT / base_cfg["paths"]["db_path"]).resolve()

    return Context(
        user=user,
        use_case=use_case,
        config=base_cfg,
        config_fp=cfg_fp,
        resume_text=resume_text,
        db_path=db_path,
        store=None,  # 🚨 explicitly no Store
    )

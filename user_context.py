# ================================
# FILE: user_context.py
# ================================
from dataclasses import dataclass
from pathlib import Path
from config_loader import settings


@dataclass(frozen=True)
class UserContext:
    user: str
    use_case: str
    base_dir: Path
    outputs_dir: Path
    corpus_dir: Path
    cache_dir: Path
    resume_path: Path | None


def resolve_user_context(
    *,
    user: str,
    use_case_override: str | None = None,
    require_resume: bool = False,
) -> UserContext:
    """
    Resolve user/use-case paths.

    - require_resume=False → safe for Dashboard / Logs
    - require_resume=True  → enforced for execution paths
    """
    use_case = use_case_override or "default"

    base_dir = Path(settings.paths.users_dir) / user / use_case
    base_dir.mkdir(parents=True, exist_ok=True)

    outputs_dir = base_dir / "outputs"
    corpus_dir = base_dir / "corpus"
    cache_dir = base_dir / "cache"

    outputs_dir.mkdir(exist_ok=True)
    corpus_dir.mkdir(exist_ok=True)
    cache_dir.mkdir(exist_ok=True)

    resume_dir = base_dir / "resume"
    resume_path = None

    if resume_dir.exists():
        candidates = list(resume_dir.glob("*.pdf")) + list(resume_dir.glob("*.tex"))
        if candidates:
            resume_path = candidates[0]

    if require_resume and resume_path is None:
        raise ValueError(
            f"User '{user}' / use_case '{use_case}' requires a resume, "
            "but none was found under:\n"
            f"{resume_dir}"
        )

    return UserContext(
        user=user,
        use_case=use_case,
        base_dir=base_dir,
        outputs_dir=outputs_dir,
        corpus_dir=corpus_dir,
        cache_dir=cache_dir,
        resume_path=resume_path,
    )

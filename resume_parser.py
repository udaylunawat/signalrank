# ================================
# FILE: resume_parser.py
# ================================
import re
from pathlib import Path
from PyPDF2 import PdfReader

from config_loader import settings


def latex_to_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def pdf_to_text(path: Path) -> str:
    reader = PdfReader(path)
    max_pages = settings.resume.pdf.max_pages
    pages = reader.pages[:max_pages]
    return " ".join(page.extract_text() or "" for page in pages)


def load_resume(path: str) -> str:
    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(f"Resume not found: {p}")

    ext = p.suffix.lower().lstrip(".")
    allowed = settings.resume.allowed_formats

    if ext not in allowed:
        raise ValueError(
            f"Unsupported resume format: .{ext}. "
            f"Allowed: {allowed}"
        )

    if ext == "pdf":
        return pdf_to_text(p)

    if ext == "tex":
        return latex_to_text(p)

    # Defensive (should never hit)
    raise ValueError(f"Unhandled resume format: .{ext}")
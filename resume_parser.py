import re
from pathlib import Path
from PyPDF2 import PdfReader


def latex_to_text(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def pdf_to_text(path: str) -> str:
    reader = PdfReader(path)
    return " ".join(page.extract_text() or "" for page in reader.pages)


def load_resume(path: str) -> str:
    if path.endswith(".pdf"):
        return pdf_to_text(path)
    if path.endswith(".tex"):
        return latex_to_text(path)
    raise ValueError("Resume must be PDF or LaTeX")
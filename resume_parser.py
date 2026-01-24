import re
from pathlib import Path

def latex_to_text(latex_path: str) -> str:
    text = Path(latex_path).read_text(encoding="utf-8")

    # Remove LaTeX commands
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)

    # Remove comments
    text = re.sub(r"%.*", "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


if __name__ == "__main__":
    resume_text = latex_to_text("resume.tex")
    print(resume_text[:1000])
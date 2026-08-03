import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from fpdf import FPDF

SYSTEM_PROMPT = """You are a resume optimization expert.
Given a candidate's resume and a job description, rewrite the resume to maximize relevance to this specific role.

Rules:
- Keep every claim truthful. Rephrase and reorder, but never fabricate skills, employers, dates, education, or metrics.
- Preserve the candidate's identity and contact details exactly as supplied.
- Mirror relevant job-description language naturally without changing the candidate's profession or seniority.
- Prioritize quantified achievements that are present in the source resume.
- Keep the result concise enough for a one- or two-page resume.
- Return JSON only with exactly these keys:
  name (str), email (str), phone (str), location (str), homepage (str), linkedin (str), github (str),
  position (str), summary (str), skills (list of str),
  experiences (list of {title, company, location, dates, tech, bullets[]}),
  projects (list of {name, url, description}),
  education (list of {degree, institution, year}).
"""

VALID_TEMPLATES = {"classic", "modern", "minimal"}

RESUME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "name",
        "email",
        "phone",
        "location",
        "homepage",
        "linkedin",
        "github",
        "position",
        "summary",
        "skills",
        "experiences",
        "projects",
        "education",
    ],
    "properties": {
        **{
            key: {"type": "string"}
            for key in (
                "name",
                "email",
                "phone",
                "location",
                "homepage",
                "linkedin",
                "github",
                "position",
                "summary",
            )
        },
        "skills": {"type": "array", "items": {"type": "string"}},
        "experiences": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "title",
                    "company",
                    "location",
                    "dates",
                    "tech",
                    "bullets",
                ],
                "properties": {
                    **{
                        key: {"type": "string"}
                        for key in ("title", "company", "location", "dates", "tech")
                    },
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "url", "description"],
                "properties": {
                    key: {"type": "string"} for key in ("name", "url", "description")
                },
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["degree", "institution", "year"],
                "properties": {
                    key: {"type": "string"} for key in ("degree", "institution", "year")
                },
            },
        },
    },
}


class ResumeTailorError(RuntimeError):
    pass


class ResumeRenderError(RuntimeError):
    pass


@dataclass
class TailoredContent:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    homepage: str = ""
    linkedin: str = ""
    github: str = ""
    position: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    experiences: list[dict] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _object_list(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _parse_content(raw: dict) -> TailoredContent:
    return TailoredContent(
        name=_string(raw.get("name")),
        email=_string(raw.get("email")),
        phone=_string(raw.get("phone")),
        location=_string(raw.get("location")),
        homepage=_string(raw.get("homepage")),
        linkedin=_string(raw.get("linkedin")),
        github=_string(raw.get("github")),
        position=_string(raw.get("position")),
        summary=_string(raw.get("summary")),
        skills=_string_list(raw.get("skills")),
        experiences=_object_list(raw.get("experiences")),
        projects=_object_list(raw.get("projects")),
        education=_object_list(raw.get("education")),
    )


async def tailor_resume(
    resume_text: str,
    job_title: str,
    job_description: str,
    llm: OpenRouterClient,
) -> TailoredContent:
    user_msg = (
        f"RESUME:\n{resume_text[:12000]}\n\n"
        f"JOB TITLE: {job_title}\n\n"
        f"JOB DESCRIPTION:\n{job_description[:5000]}"
    )
    raw = await llm.llm_json(
        system=SYSTEM_PROMPT,
        user=user_msg,
        max_tokens=3200,
        response_schema=RESUME_SCHEMA,
    )
    if raw.get("_error"):
        raise ResumeTailorError(
            str(raw.get("_details") or "OpenRouter returned no usable resume")
        )

    content = _parse_content(raw)
    if not content.name or not (
        content.summary or content.experiences or content.projects
    ):
        raise ResumeTailorError("OpenRouter returned an incomplete tailored resume")
    return content


def _pdf_text(value: Any) -> str:
    text = " ".join(str(value or "").split())
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _palette(template: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if template == "modern":
        return (67, 56, 202), (53, 53, 70)
    if template == "minimal":
        return (55, 65, 81), (75, 85, 99)
    return (20, 25, 35), (65, 70, 80)


def _section_title(pdf: "FPDF", title: str, accent: tuple[int, int, int]) -> None:
    from fpdf.enums import XPos, YPos

    if pdf.get_y() > 270:
        pdf.add_page()
    pdf.ln(2)
    pdf.set_text_color(*accent)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(
        0,
        5,
        _pdf_text(title).upper(),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_draw_color(*accent)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1.5)


def _write_paragraph(pdf: "FPDF", text: Any, *, bold: bool = False) -> None:
    from fpdf.enums import XPos, YPos

    clean = _pdf_text(text)
    if not clean:
        return
    pdf.set_font("Helvetica", "B" if bold else "", 8.6)
    pdf.multi_cell(0, 4.1, clean, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def compile_pdf(content: TailoredContent, template: str = "classic") -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    if template not in VALID_TEMPLATES:
        raise ResumeRenderError(f"Unknown resume template: {template}")

    accent, body = _palette(template)
    try:
        pdf = FPDF(format="A4", unit="mm")
        pdf.set_margins(14, 12, 14)
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.set_title(_pdf_text(f"{content.name} resume"))
        pdf.set_author(_pdf_text(content.name))
        pdf.add_page()
        pdf.set_text_color(*accent)
        pdf.set_font("Helvetica", "B", 18 if template != "minimal" else 16)
        pdf.multi_cell(
            0,
            7,
            _pdf_text(content.name),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        if content.position:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*body)
            pdf.multi_cell(
                0,
                5,
                _pdf_text(content.position),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

        contact = [
            content.email,
            content.phone,
            content.location,
            content.linkedin,
            content.github,
            content.homepage,
        ]
        contact_line = " | ".join(_pdf_text(value) for value in contact if value)
        if contact_line:
            pdf.set_font("Helvetica", "", 7.8)
            pdf.set_text_color(*body)
            pdf.multi_cell(
                0,
                4,
                contact_line,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

        pdf.set_text_color(*body)
        if content.summary:
            _section_title(pdf, "Profile", accent)
            _write_paragraph(pdf, content.summary)

        if content.skills:
            _section_title(pdf, "Skills", accent)
            _write_paragraph(pdf, " | ".join(content.skills))

        if content.experiences:
            _section_title(pdf, "Experience", accent)
            for experience in content.experiences:
                heading = " - ".join(
                    part
                    for part in [
                        _pdf_text(experience.get("title")),
                        _pdf_text(experience.get("company")),
                    ]
                    if part
                )
                _write_paragraph(pdf, heading, bold=True)
                meta = " | ".join(
                    part
                    for part in [
                        _pdf_text(experience.get("dates")),
                        _pdf_text(experience.get("location")),
                        _pdf_text(experience.get("tech")),
                    ]
                    if part
                )
                if meta:
                    pdf.set_text_color(95, 100, 110)
                    _write_paragraph(pdf, meta)
                    pdf.set_text_color(*body)
                for bullet in _string_list(experience.get("bullets")):
                    _write_paragraph(pdf, f"- {bullet}")
                pdf.ln(1)

        if content.projects:
            _section_title(pdf, "Projects", accent)
            for project in content.projects:
                heading = _pdf_text(project.get("name"))
                url = _pdf_text(project.get("url"))
                _write_paragraph(
                    pdf, f"{heading} | {url}" if url else heading, bold=True
                )
                _write_paragraph(pdf, project.get("description"))

        if content.education:
            _section_title(pdf, "Education", accent)
            for item in content.education:
                line = " | ".join(
                    part
                    for part in [
                        _pdf_text(item.get("degree")),
                        _pdf_text(item.get("institution")),
                        _pdf_text(item.get("year")),
                    ]
                    if part
                )
                _write_paragraph(pdf, line)

        output = bytes(pdf.output())
    except Exception as error:
        raise ResumeRenderError(
            f"Unable to render the tailored resume: {error}"
        ) from error

    if not output.startswith(b"%PDF"):
        raise ResumeRenderError("The resume renderer returned an invalid PDF")
    return output

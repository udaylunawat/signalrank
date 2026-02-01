#!/usr/bin/env python3
"""
Interactive user onboarding for Job Ranker v2 (Resume-first).

Flow:
1. Ask for resume (.pdf / .tex)
2. Ask for free-text role intent
3. Use LLM to derive persona (optional, advisory)
4. Normalize locations
5. Show diff
6. Write explicit override YAML

LLMs are advisory only.
"""

import argparse
import copy
import shutil
import sys
import textwrap
from pathlib import Path

import yaml
from PyPDF2 import PdfReader

# Optional LLM
llm_json = None
try:
    from job_ranker.llm.client import llm_json as _llm_json

    if _llm_json:
        llm_json = _llm_json
except Exception as e:
    print(f"[LLM] Disabled due to import error: {e}")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OVERRIDES_DIR = PROJECT_ROOT / "config" / "overrides"
USERS_DIR = PROJECT_ROOT / "users"

# --------------------------------------------------
# Persona schema for LLM output validation
# --------------------------------------------------
PERSONA_SCHEMA = {
    "type": "object",
    "required": [
        "persona_label",
        "resume_embedding_prefix",
        "functional_role_penalties",
        "title_blocklist",
    ],
    "additionalProperties": False,
    "properties": {
        "persona_label": {
            "type": "string",
            "minLength": 3,
            "maxLength": 60,
        },
        "resume_embedding_prefix": {
            "type": "string",
            "minLength": 20,
            "maxLength": 300,
        },
        "functional_role_penalties": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "agentic_systems": {"type": "number"},
                "mlops_llmops": {"type": "number"},
                "platform_devops": {"type": "number"},
                "software_general": {"type": "number"},
                "security": {"type": "number"},
                "hr": {"type": "number"},
                "consulting": {"type": "number"},
            },
        },
        "functional_role_terms": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 15,
            },
        },
        "title_blocklist": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 20,
        },
        "notes": {
            "type": "string",
            "maxLength": 500,
        },
    },
}
DEFAULT_PERSONA_ENGINE_MAP = {
    "Architecture": "platform_devops",
    "Technology": "agentic_systems",
    "Innovation": "agentic_systems",
    "Consulting": "software_general",
    "Management": "software_general",
    "Operations": "platform_devops",
}


def build_persona_block(persona: dict) -> dict:
    return {
        "label": persona["persona_label"],
        "themes": list(persona.get("functional_role_terms", {}).keys()),
        "notes": persona.get("notes", ""),
    }


def build_persona_engine_map(persona: dict) -> dict:
    out = {}
    for theme in persona.get("functional_role_terms", {}).keys():
        engine_role = DEFAULT_PERSONA_ENGINE_MAP.get(theme)
        if engine_role:
            out[theme] = {
                "maps_to": engine_role,
                "weight": 1.0,
            }
    return out


# --------------------------------------------------
# Location normalization (rule-based, deterministic)
# --------------------------------------------------
LOCATION_ALIASES = {
    "pune": ["pune", "mh, in"],
    "mumbai": ["mumbai", "mh, in"],
    "bangalore": ["bangalore", "bengaluru", "ka, in"],
    "bengaluru": ["bengaluru", "bangalore", "ka, in"],
    "hyderabad": ["hyderabad", "ts, in"],
    "chennai": ["chennai", "tn, in"],
    "remote": ["remote", "remote, in"],
}


def normalize_locations(raw: str) -> list[str]:
    out = set()
    for token in raw.split(","):
        t = token.strip().lower()
        if not t:
            continue
        if t in LOCATION_ALIASES:
            out.update(LOCATION_ALIASES[t])
        else:
            out.add(t)
    return sorted(out)


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def ask(prompt, default=None):
    if default:
        return input(f"{prompt} [{default}]: ").strip() or default
    return input(f"{prompt}: ").strip()


def ask_yes_no(prompt, default=False):
    d = "Y/n" if default else "y/N"
    resp = input(f"{prompt} ({d}): ").strip().lower()
    if not resp:
        return default
    return resp.startswith("y")


def load_resume_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return " ".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(errors="ignore")


def llm_available() -> bool:
    return llm_json is not None


def validate_penalty_values(penalties: dict) -> list[str]:
    errors = []
    for k, v in penalties.items():
        if not isinstance(v, (int, float)):
            errors.append(f"{k}: not a number")
            continue
        if v < 0.5 or v > 1.2:
            errors.append(f"{k}: {v} outside allowed range [0.5, 1.2]")
    return errors


# --------------------------------------------------
# LLM: derive persona from resume + intent
# --------------------------------------------------
def derive_persona_with_llm(*, resume_text: str, intent: str, yoe: int):
    if llm_json is None:
        return None

    prompt = f"""
You are helping onboard a user into a job ranking system.

Inputs:
- Resume text
- Free-text role intent
- Years of experience

Task:
Propose a job-search persona configuration.

Return JSON ONLY with these keys:
- persona_label (string)
- resume_embedding_prefix (string)
- functional_role_penalties (object: float values 0.5–1.2)
- functional_role_terms (object of keyword lists)
- title_blocklist (list of strings)
- notes (string)

DO NOT invent new sections.
DO NOT include explanations outside JSON.

Role intent:
{intent}

Years of experience:
{yoe}

Resume:
<<<
{resume_text[:5000]}
>>>
"""
    try:
        return llm_json(prompt, max_tokens=700)
    except Exception:
        return None


def semantic_sanity_checks(persona: dict) -> list[str]:
    errors = []

    penalties = persona.get("functional_role_penalties", {})

    # At least one role must be primary
    if not any(v >= 0.95 for v in penalties.values()):
        errors.append("No primary role (≥ 0.95) defined")

    # Prevent flat personas
    if len(set(penalties.values())) == 1:
        errors.append("All role penalties identical; persona is non-discriminative")

    # HR / Consulting sanity
    label = persona.get("persona_label", "").lower()
    if "hr" in label and penalties.get("software_general", 1.0) > 0.9:
        errors.append("HR persona should not strongly favor software_general")

    return errors


def validate_persona_output(data: dict) -> tuple[bool, list[str]]:
    errors = []

    if not isinstance(data, dict):
        return False, ["Persona output is not a JSON object"]

    # Required keys
    for k in PERSONA_SCHEMA["required"]:
        if k not in data:
            errors.append(f"Missing required key: {k}")

    # Unknown keys
    allowed = set(PERSONA_SCHEMA["properties"].keys())
    for k in data:
        if k not in allowed:
            errors.append(f"Unexpected key: {k}")

    # Type checks
    if "functional_role_penalties" in data:
        errors.extend(validate_penalty_values(data["functional_role_penalties"]))

    # Semantic checks
    errors.extend(semantic_sanity_checks(data))

    return len(errors) == 0, errors


def persona_diff(before: dict, after: dict) -> list[str]:
    diffs = []

    # Label
    if before.get("persona_label") != after.get("persona_label"):
        diffs.append(
            f"Persona label:\n"
            f"  before: {before.get('persona_label')}\n"
            f"  after:  {after.get('persona_label')}"
        )

    # Embedding intent
    if before.get("resume_embedding_prefix") != after.get("resume_embedding_prefix"):
        diffs.append("Embedding intent changed")

    # Role penalties
    b = before.get("functional_role_penalties", {})
    a = after.get("functional_role_penalties", {})
    for k in sorted(set(b) | set(a)):
        if b.get(k) != a.get(k):
            diffs.append(f"Role weight '{k}': {b.get(k)} → {a.get(k)}")

    # Title blocklist
    if set(before.get("title_blocklist", [])) != set(after.get("title_blocklist", [])):
        diffs.append(
            f"Title exclusions:\n"
            f"  before: {before.get('title_blocklist')}\n"
            f"  after:  {after.get('title_blocklist')}"
        )

    return diffs


def build_override_from_persona(
    persona: dict,
    *,
    base_override: dict,
) -> dict:
    candidate = copy.deepcopy(base_override)

    # Engine-safe changes only
    candidate["resume"]["embedding_prefix"] = persona["resume_embedding_prefix"].strip()

    candidate["ranking"]["functional_role_penalties"] = persona[
        "functional_role_penalties"
    ]

    candidate["title_blocklist"] = persona["title_blocklist"]

    # Persona metadata (NEW)
    candidate["persona"] = build_persona_block(persona)

    # Persona → engine mapping (NEW)
    persona_map = build_persona_engine_map(persona)
    if persona_map:
        candidate["persona_to_engine"] = persona_map

    return candidate


# --------------------------------------------------
# Main
# --------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    persona_label = None
    print("\n=== Job Ranker v2 — User Onboarding (Resume-first) ===\n")

    user = ask("User name")
    if not user:
        print("User name is required.")
        sys.exit(1)

    override_path = OVERRIDES_DIR / f"{user}.yaml"
    if override_path.exists() and not args.force:
        print(f"ERROR: {override_path} exists. Use --force to overwrite.")
        sys.exit(1)

    # --------------------------------------------------
    # Resume (mandatory)
    # --------------------------------------------------
    resume_path = Path(ask("Path to resume (.pdf or .tex)")).expanduser()
    if not resume_path.exists():
        print("Resume file not found.")
        sys.exit(1)

    user_dir = USERS_DIR / user
    user_dir.mkdir(parents=True, exist_ok=True)

    # Rename to resume.pdf or resume.tex based on extension
    if resume_path.suffix.lower() == ".pdf":
        dest_resume = user_dir / "resume.pdf"
    elif resume_path.suffix.lower() == ".tex":
        dest_resume = user_dir / "resume.tex"
    else:
        print("Unsupported resume file type. Use .pdf or .tex.")
        sys.exit(1)

    if resume_path.resolve() != dest_resume.resolve():
        shutil.copy(resume_path, dest_resume)

    resume_text = load_resume_text(dest_resume)

    # --------------------------------------------------
    # Intent
    # --------------------------------------------------
    intent = ask(
        "Describe the kind of roles you are targeting "
        "(e.g. HR, security engineer, innovation consulting, devops)"
    )

    yoe = int(ask("Years of experience"))

    raw_locations = ask(
        "Preferred locations (comma-separated, e.g. Pune, Bangalore, remote)"
    )
    locations = normalize_locations(raw_locations)

    raw_companies = ask("Preferred companies (comma-separated, optional)").lower()
    companies = [x.strip() for x in raw_companies.split(",") if x.strip()]

    # --------------------------------------------------
    # Base override (safe defaults)
    # --------------------------------------------------
    override = {
        "resume": {
            "embedding_prefix": "",
        },
        "ranking": {
            "functional_role_penalties": {
                "agentic_systems": 1.0,
                "mlops_llmops": 1.0,
                "platform_devops": 1.0,
                "software_general": 1.0,
            },
        },
        "functional_role_terms": {},
        "experience": {
            "max_yoe": yoe,
        },
        "location_scoring": {
            "preferred_weight": 1.2,
            "preferred_locations": locations,
        },
        "company_scoring": {
            "default_weight": 1.0,
            "preferred_weight": 1.25,
            "deprioritized_weight": 0.85,
            "preferred_companies": companies,
            "deprioritized_companies": [],
            "aliases": {},
        },
        "title_blocklist": ["trainee", "junior"],
    }

    # --------------------------------------------------
    # Persona derivation (LLM)
    # --------------------------------------------------
    if args.no_llm:
        print("\n[LLM] Skipped (--no-llm)")
    elif not llm_available():
        print("\n[LLM] Skipped (LLM unavailable or API key missing)")
    elif ask_yes_no("\nUse LLM to derive persona from resume?", True):
        llm_out = derive_persona_with_llm(
            resume_text=resume_text,
            intent=intent,
            yoe=yoe,
        )

        valid, errors = validate_persona_output(llm_out)
        if not valid:
            print("\nLLM persona rejected:")
            for e in errors:
                print(f"  - {e}")
        else:
            print("\nLLM persona proposal:")
            print(textwrap.indent(yaml.safe_dump(llm_out, sort_keys=False), "  "))

            current_override = copy.deepcopy(override)
            candidate_override = build_override_from_persona(
                llm_out,
                base_override=current_override,
            )

            diffs = persona_diff(current_override, llm_out)
            if diffs:
                print("\nProposed changes:")
                for d in diffs:
                    print(d)

            if llm_out.get("notes"):
                print("\nLLM notes:")
                print(textwrap.indent(llm_out["notes"], "  "))

            # -----------------------------
            # Allow user tweaks (IMPORTANT)
            # -----------------------------
            if ask_yes_no("\nWould you like to tweak any values manually?", False):
                new_prefix = ask(
                    "Edit resume embedding prefix",
                    candidate_override["resume"]["embedding_prefix"],
                )
                candidate_override["resume"]["embedding_prefix"] = new_prefix.strip()

                for k, v in candidate_override["ranking"][
                    "functional_role_penalties"
                ].items():
                    new_v = ask(
                        f"Penalty for {k}",
                        str(v),
                    )
                    try:
                        candidate_override["ranking"]["functional_role_penalties"][
                            k
                        ] = float(new_v)
                    except ValueError:
                        pass  # keep old
                # Edit title blocklist
                print("\nCurrent title blocklist:")
                print(", ".join(candidate_override["title_blocklist"]))

                if ask_yes_no("Edit title blocklist?", False):
                    new_blocklist = ask(
                        "Enter comma-separated title keywords to EXCLUDE",
                        ", ".join(candidate_override["title_blocklist"]),
                    )
                    candidate_override["title_blocklist"] = [
                        x.strip().lower() for x in new_blocklist.split(",") if x.strip()
                    ]

            if ask_yes_no("\nApply this persona?", True):
                override = candidate_override
                persona_label = llm_out.get("persona_label")
    # --------------------------------------------------
    # Write YAML
    # --------------------------------------------------
    OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
    yaml_body = yaml.safe_dump(override, sort_keys=False)

    comment = ""
    if persona_label:
        comment = f"# Persona: {persona_label}\n# Generated via onboarding\n\n"

    override_path.write_text(comment + yaml_body)

    print(f"\n✔ User `{user}` onboarded")
    print(f"  Override: {override_path}")
    print(f"  Resume: {dest_resume}")


if __name__ == "__main__":
    main()

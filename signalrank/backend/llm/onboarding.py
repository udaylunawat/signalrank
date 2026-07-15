from llm.resume_parser import ResumeParseResult

TIER_OPTIONS = [
    "S-tier (exceptional reputation)",
    "A-tier (strong reputation)",
    "B-tier (established reputation)",
    "C-tier (limited reputation evidence)",
    "Any company",
]

LOCATION_OPTIONS = [
    "Remote only",
    "Bangalore",
    "Hyderabad",
    "Mumbai",
    "Delhi/NCR",
    "Pune",
    "Any India",
    "Open to relocation",
]


def generate_onboarding_questions(profile: ResumeParseResult) -> list[dict]:
    questions = []

    yoe_str = (
        f"{profile.years_of_experience} years"
        if profile.years_of_experience
        else "your"
    )
    titles_str = (
        ", ".join(profile.recent_titles[:3])
        if profile.recent_titles
        else "your recent roles"
    )
    skills_str = ", ".join(profile.skills[:5]) if profile.skills else "your skills"

    role_suggestions = list(dict.fromkeys(profile.recent_titles))[:8]
    role_question = {
        "id": "target_roles",
        "text": f"I see {yoe_str} of experience with {skills_str} "
        f"(recent: {titles_str}). What roles are you targeting?",
        "type": "multiselect" if role_suggestions else "text",
    }
    if role_suggestions:
        role_question["options"] = role_suggestions
    questions.append(role_question)

    questions.append(
        {
            "id": "preferred_locations",
            "text": "Preferred locations? Open to remote?",
            "type": "multiselect",
            "options": LOCATION_OPTIONS,
        }
    )

    questions.append(
        {
            "id": "company_tiers",
            "text": "Which AI-assessed company reputation tiers should be eligible?",
            "type": "multiselect",
            "options": TIER_OPTIONS,
        }
    )

    questions.append(
        {
            "id": "preferred_companies",
            "text": "Any companies you especially want to see? Separate names with commas.",
            "type": "text",
        }
    )

    questions.append(
        {
            "id": "excluded_companies",
            "text": "Any companies to exclude? Separate names with commas.",
            "type": "text",
        }
    )

    questions.append(
        {
            "id": "excluded_titles",
            "text": "Any job titles to exclude? Separate titles with commas.",
            "type": "text",
        }
    )

    return questions

from llm.resume_parser import ResumeParseResult

ROLE_OPTIONS = [
    "AI/ML Engineer",
    "Data Scientist",
    "MLOps/Platform Engineer",
    "Backend Engineer",
    "Full-Stack Engineer",
    "DevOps/SRE",
    "Security Engineer",
]

TIER_OPTIONS = [
    "S-tier (FAANG, top startups)",
    "A-tier (strong tech companies)",
    "B-tier (good companies)",
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

    questions.append(
        {
            "id": "target_roles",
            "text": f"I see {yoe_str} of experience with {skills_str} "
            f"(recent: {titles_str}). What roles are you targeting?",
            "type": "multiselect",
            "options": ROLE_OPTIONS,
        }
    )

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
            "text": "Which company tiers should be eligible for matching?",
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
            "text": "Any job titles to exclude? (e.g., QA, manual testing, frontend)",
            "type": "text",
        }
    )

    return questions

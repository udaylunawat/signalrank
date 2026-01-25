# fast_heuristics.py
import re

AI_TERMS = {
    "llm", "agent", "agents", "rag", "embedding",
    "prompt", "inference", "evaluation", "orchestration",
    "langchain", "langgraph", "vector",
}

DEVOPS_TERMS = {
    "kubernetes", "terraform", "ci/cd", "pipeline",
    "monitoring", "grafana", "prometheus",
    "sre", "availability", "mttr",
}

SECURITY_TERMS = {
    "threat", "siem", "soc", "incident",
    "attack", "mitre", "edr", "forensics",
}

def classify_functional_role_fast(text: str) -> str:
    t = text.lower()

    ai = sum(1 for k in AI_TERMS if k in t)
    devops = sum(1 for k in DEVOPS_TERMS if k in t)
    sec = sum(1 for k in SECURITY_TERMS if k in t)

    if sec >= 2:
        return "security"
    if ai >= 3:
        return "agentic_systems"
    if ai >= 1 and devops >= 1:
        return "mlops_llmops"
    if devops >= 2:
        return "platform_devops"
    return "software_general"


def extract_skills_fast(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9\+\-\.]+", text.lower())
    seen = set()
    skills = []
    for t in tokens:
        if len(t) > 3 and t not in seen:
            seen.add(t)
            skills.append(t)
        if len(skills) >= 25:
            break
    return skills
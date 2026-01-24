from llm.client import llm_json

PROMPT = """
Generate job search queries from this role intent.

Rules:
- One role per query
- No OR operators
- Suitable for job boards
- Senior IC focused

Return JSON:
{ "queries": [...] }

ROLE:
<<<TEXT>>>
"""


def plan_search_queries(text: str) -> list[str]:
    data = llm_json(PROMPT.replace("<<<TEXT>>>", text))
    return data.get("queries", [])
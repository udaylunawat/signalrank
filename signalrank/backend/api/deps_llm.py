from llm.openrouter import OpenRouterClient

from api.config import settings

_client: OpenRouterClient | None = None


def get_llm_client() -> OpenRouterClient:
    global _client
    if _client is None:
        _client = OpenRouterClient(api_key=settings.openrouter_api_key)
    return _client

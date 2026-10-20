"""Provider chain Groq -> Gemini -> Ollama + cache (key = prompt_hash, model)."""
import hashlib
import json
from functools import lru_cache

from app.core.config import get_settings
from app.services.llm.llm_client import LLMError, LLMResponse, default_providers
from app.services.llm.prompt_builder import SYSTEM


def prompt_hash(prompt: str, system: str = SYSTEM) -> str:
    return hashlib.sha256((system + "\n" + prompt).encode()).hexdigest()


class _MemoryCache:
    def __init__(self) -> None:
        self._d: dict[str, str] = {}

    def get(self, k: str) -> str | None:
        return self._d.get(k)

    def set(self, k: str, v: str) -> None:
        self._d[k] = v


def _redis_cache():
    try:
        import redis

        r = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=0.5)
        r.ping()
        return r
    except Exception:
        return _MemoryCache()


class FallbackLLM:
    def __init__(self, providers: list | None = None, cache=None) -> None:
        self.providers = providers if providers is not None else default_providers()
        self.cache = cache if cache is not None else _redis_cache()

    def complete(self, prompt: str, system: str = SYSTEM, temperature: float | None = None) -> LLMResponse:
        temperature = get_settings().llm_temperature if temperature is None else temperature
        errors = []
        for p in self.providers:
            key = f"llm:{prompt_hash(prompt, system)}:{p.name}"
            cached = self.cache.get(key)
            if cached:
                return LLMResponse(**json.loads(cached))
            try:
                resp = p.complete(prompt, system, temperature)
            except Exception as e:  # rate limit / network / missing SDK -> next provider
                errors.append(f"{p.name}: {e.__class__.__name__}: {e}")
                continue
            self.cache.set(key, json.dumps(resp.__dict__))
            return resp
        raise LLMError("all LLM providers failed: " + " | ".join(errors))


@lru_cache
def get_llm() -> FallbackLLM:
    """FastAPI dependency (tests me `app.dependency_overrides` se fake LLM)."""
    return FallbackLLM()

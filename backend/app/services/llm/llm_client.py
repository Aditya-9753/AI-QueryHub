"""LLM providers: Groq / Gemini / Ollama. SDK imports lazy hain taaki missing key par app crash na ho."""
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


class LLMError(Exception):
    pass


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: float = 0.0


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key, self.model = api_key, model

    def complete(self, prompt: str, system: str, temperature: float) -> LLMResponse:
        from groq import Groq

        t0 = time.perf_counter()
        r = Groq(api_key=self.api_key).chat.completions.create(
            model=self.model, temperature=temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        return LLMResponse(r.choices[0].message.content or "", f"groq/{self.model}",
                           r.usage.prompt_tokens if r.usage else None,
                           r.usage.completion_tokens if r.usage else None,
                           (time.perf_counter() - t0) * 1000)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key, self.model = api_key, model

    def complete(self, prompt: str, system: str, temperature: float) -> LLMResponse:
        from google import genai

        t0 = time.perf_counter()
        client = genai.Client(api_key=self.api_key)
        r = client.models.generate_content(
            model=self.model, contents=prompt,
            config={"system_instruction": system, "temperature": temperature})
        usage = getattr(r, "usage_metadata", None)
        return LLMResponse(r.text or "", f"gemini/{self.model}",
                           getattr(usage, "prompt_token_count", None),
                           getattr(usage, "candidates_token_count", None),
                           (time.perf_counter() - t0) * 1000)


class OllamaProvider:
    name = "ollama"

    def __init__(self, url: str, model: str) -> None:
        self.url, self.model = url.rstrip("/"), model

    def complete(self, prompt: str, system: str, temperature: float) -> LLMResponse:
        t0 = time.perf_counter()
        r = httpx.post(f"{self.url}/api/generate", timeout=120, json={
            "model": self.model, "system": system, "prompt": prompt, "stream": False,
            "options": {"temperature": temperature}})
        r.raise_for_status()
        data = r.json()
        return LLMResponse(data.get("response", ""), f"ollama/{self.model}",
                           data.get("prompt_eval_count"), data.get("eval_count"),
                           (time.perf_counter() - t0) * 1000)


def default_providers() -> list:
    s = get_settings()
    providers: list = []
    if s.groq_api_key:
        providers.append(GroqProvider(s.groq_api_key, s.groq_model))
    if s.gemini_api_key:
        providers.append(GeminiProvider(s.gemini_api_key, s.gemini_model))
    providers.append(OllamaProvider(s.ollama_url, s.ollama_model))
    return providers

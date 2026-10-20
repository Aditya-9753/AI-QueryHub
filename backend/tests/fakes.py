from app.services.llm.llm_client import LLMError, LLMResponse


class FakeLLM:
    """Scripted LLM: har complete() call agla reply deta hai; replies khatam => LLMError."""

    def __init__(self, replies: list[str] | None = None) -> None:
        self.replies = list(replies or [])
        self.prompts: list[str] = []

    def complete(self, prompt: str, system: str = "", temperature: float | None = None) -> LLMResponse:
        self.prompts.append(prompt)
        if not self.replies:
            raise LLMError("fake: no reply left")
        return LLMResponse(self.replies.pop(0), "fake/model", 10, 5, 1.0)

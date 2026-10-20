"""LLM configuration status (Dashboard alert ke liye). Sirf config dekhta hai — koi API call / quota kharch nahi."""
from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import get_current_user

router = APIRouter(prefix="/llm", tags=["llm"], dependencies=[Depends(get_current_user)])


@router.get("/status")
def status():
    s = get_settings()
    providers = []
    if s.groq_api_key:
        providers.append(f"groq/{s.groq_model}")
    if s.gemini_api_key:
        providers.append(f"gemini/{s.gemini_model}")
    return {"configured": bool(providers), "providers": providers, "ollama_url": s.ollama_url}

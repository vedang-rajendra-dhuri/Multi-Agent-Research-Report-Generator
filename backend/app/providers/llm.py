from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import get_settings


def validate_llm_configuration() -> None:
    settings = get_settings()
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return
    if settings.llm_provider == "openai":
        raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
    if settings.llm_provider == "gemini":
        raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
    raise RuntimeError("Configure LLM_PROVIDER as 'openai' or 'gemini' to run research.")


def create_chat_model() -> BaseChatModel:
    settings = get_settings()
    validate_llm_configuration()
    if settings.llm_provider == "openai":
        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        return ChatOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.llm_model or "gpt-4o-mini",
            temperature=0,
            timeout=settings.provider_timeout_seconds,
            max_retries=1,
        )
    if settings.llm_provider == "gemini":
        if settings.gemini_api_key is None:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
        return ChatGoogleGenerativeAI(
            google_api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.llm_model or "gemini-3.6-flash",
            temperature=0,
            timeout=settings.provider_timeout_seconds,
            max_retries=1,
        )
    raise RuntimeError("Configure LLM_PROVIDER as 'openai' or 'gemini' to run research.")

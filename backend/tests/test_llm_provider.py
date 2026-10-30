from pydantic import SecretStr

from app.config import Settings
from app.providers import llm


def test_gemini_uses_supported_default_model_when_no_override_is_set(monkeypatch):
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        gemini_api_key=SecretStr("test-key"),
    )
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr(llm, "ChatGoogleGenerativeAI", lambda **kwargs: kwargs)

    model = llm.create_chat_model()

    assert model["model"] == "gemini-3.6-flash"

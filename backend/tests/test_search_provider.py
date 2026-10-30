import pytest
from pydantic import SecretStr

from app.config import Settings
from app.providers import search
from app.providers.search import SearchProviderError


class ResponseStub:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def test_search_results_come_from_provider_and_keep_source_metadata(monkeypatch):
    settings = Settings(
        search_provider="tavily",
        search_provider_api_key=SecretStr("provider-secret"),
    )
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return ResponseStub(
            {
                "results": [
                    {
                        "title": "Original title",
                        "url": "https://example.org/report",
                        "content": "  A retrieved evidence passage.  ",
                        "published_date": "2026-01-02",
                    }
                ]
            }
        )

    monkeypatch.setattr(search, "get_settings", lambda: settings)
    monkeypatch.setattr(search.httpx, "post", post)

    results = search.search_web("real search query", max_results=3)

    assert calls[0][0] == "https://api.tavily.com/search"
    assert calls[0][1]["json"]["query"] == "real search query"
    assert calls[0][1]["json"]["max_results"] == 3
    assert results[0].title == "Original title"
    assert results[0].url == "https://example.org/report"
    assert results[0].passage == "A retrieved evidence passage."
    assert results[0].published_date == "2026-01-02"
    assert "provider-secret" not in repr(results[0])


def test_search_provider_configuration_errors_are_explicit(monkeypatch):
    monkeypatch.setattr(
        search,
        "get_settings",
        lambda: Settings(_env_file=None, search_provider="tavily"),
    )

    with pytest.raises(RuntimeError, match="SEARCH_PROVIDER_API_KEY"):
        search.search_web("query")


def test_invalid_search_payload_is_not_replaced_with_mock_results(monkeypatch):
    settings = Settings(
        search_provider="tavily",
        search_provider_api_key=SecretStr("provider-secret"),
    )
    monkeypatch.setattr(search, "get_settings", lambda: settings)
    monkeypatch.setattr(search.httpx, "post", lambda *args, **kwargs: ResponseStub({"answer": "no results"}))

    with pytest.raises(SearchProviderError, match="invalid response"):
        search.search_web("query")

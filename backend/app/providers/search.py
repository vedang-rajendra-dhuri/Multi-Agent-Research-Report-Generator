from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx
import hashlib
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

from app.config import get_settings


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    content: str = Field(default="", max_length=20_000)
    published_date: str | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[SearchResult]


class SearchSource(BaseModel):
    source_id: str
    title: str
    url: str
    retrieved_at: datetime
    published_date: str | None
    passage: str
    publisher: str | None = None
    source_type: str = "web"
    locator: str | None = None


class SearchProviderError(RuntimeError):
    pass


def validate_search_configuration() -> None:
    settings = get_settings()
    if settings.search_provider != "tavily":
        raise RuntimeError("Configure SEARCH_PROVIDER=tavily to run web research.")
    if settings.search_provider_api_key is None:
        raise RuntimeError("SEARCH_PROVIDER_API_KEY is required when SEARCH_PROVIDER=tavily.")


def _validate_search_response(payload: Any) -> SearchResponse:
    try:
        return SearchResponse.model_validate(payload)
    except ValidationError as error:
        raise SearchProviderError("Search provider returned an invalid response.") from error


def search_web(query: str, max_results: int | None = None) -> list[SearchSource]:
    settings = get_settings()
    validate_search_configuration()

    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.search_provider_api_key.get_secret_value(),
                "query": query,
                "max_results": max_results or settings.max_search_results,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=settings.provider_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.TimeoutException as error:
        raise SearchProviderError("Search provider request timed out.") from error
    except httpx.HTTPStatusError as error:
        raise SearchProviderError(
            f"Search provider returned HTTP {error.response.status_code}."
        ) from error
    except httpx.RequestError as error:
        raise SearchProviderError("Search provider could not be reached.") from error

    try:
        payload = response.json()
    except ValueError as error:
        raise SearchProviderError("Search provider returned invalid JSON.") from error
    results = _validate_search_response(payload)
    retrieved_at = datetime.now(UTC)
    sources: list[SearchSource] = []
    for result in results.results:
        url = str(result.url)
        if urlsplit(url).scheme not in {"http", "https"}:
            continue
        source_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        sources.append(
            SearchSource(
                source_id=source_id,
                title=result.title,
                url=url,
                retrieved_at=retrieved_at,
                published_date=result.published_date,
                passage=result.content.strip(),
            )
        )
    return sources

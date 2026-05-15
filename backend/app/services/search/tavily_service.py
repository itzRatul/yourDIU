"""
Tavily Search Service
=====================
Primary web search. Daily limit: 900 (config).
Tracks usage in a simple in-memory counter (resets on restart).
When limit is hit, raises TavilyLimitError so search_router falls back to Brave.
"""

import logging
from dataclasses import dataclass, field

from tavily import AsyncTavilyClient

from app.core.config import settings

logger = logging.getLogger("yourDIU.tavily")


class TavilyLimitError(Exception):
    """Raised when daily Tavily limit is reached."""


@dataclass
class _TavilyState:
    count: int = 0

_state = _TavilyState()


def get_tavily_usage() -> dict:
    return {
        "used": _state.count,
        "limit": settings.tavily_daily_limit,
        "remaining": max(0, settings.tavily_daily_limit - _state.count),
    }


async def search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",   # "basic" or "advanced"
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[dict]:
    """
    Run a Tavily web search.
    Returns list of {title, url, content, score}.
    Raises TavilyLimitError if daily limit reached.
    """
    if _state.count >= settings.tavily_daily_limit:
        raise TavilyLimitError(f"Tavily daily limit ({settings.tavily_daily_limit}) reached.")

    if not settings.tavily_api_key:
        raise TavilyLimitError("Tavily API key not configured.")

    client = AsyncTavilyClient(api_key=settings.tavily_api_key)

    kwargs = {
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
    }
    if include_domains:
        kwargs["include_domains"] = include_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains

    try:
        response = await client.search(**kwargs)
        _state.count += 1
        logger.debug("Tavily search #%d: %s", _state.count, query)

        results = []
        for r in response.get("results", []):
            results.append({
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "content": r.get("content", ""),
                "score":   r.get("score"),
            })
        return results

    except TavilyLimitError:
        raise
    except Exception as e:
        logger.error("Tavily search failed: %s", e)
        raise

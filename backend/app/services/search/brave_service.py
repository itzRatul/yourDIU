"""
Brave Search Service
====================
Fallback web search when Tavily daily limit is hit.
Uses plain httpx — no dedicated SDK needed.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("yourDIU.brave")

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


async def search(
    query: str,
    max_results: int = 5,
    country: str = "BD",
) -> list[dict]:
    """
    Run a Brave web search.
    Returns list of {title, url, content, score}.
    """
    if not settings.brave_search_api_key:
        raise RuntimeError("Brave Search API key not configured.")

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.brave_search_api_key,
    }
    params = {
        "q": query,
        "count": max_results,
        "country": country,
        "search_lang": "en",
        "text_decorations": False,
        "extra_snippets": True,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(BRAVE_SEARCH_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("web", {}).get("results", []):
                # Combine description + extra snippets for richer content
                content_parts = [item.get("description", "")]
                for snippet in item.get("extra_snippets", []):
                    content_parts.append(snippet)
                content = " ".join(filter(None, content_parts))

                results.append({
                    "title":   item.get("title", ""),
                    "url":     item.get("url", ""),
                    "content": content,
                    "score":   None,
                })
            logger.debug("Brave search: %d results for '%s'", len(results), query)
            return results

        except httpx.HTTPStatusError as e:
            logger.error("Brave search HTTP error: %s", e)
            raise
        except Exception as e:
            logger.error("Brave search failed: %s", e)
            raise

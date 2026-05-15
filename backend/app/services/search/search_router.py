"""
Search Router
=============
Auto-fallback: Tavily (primary) → Brave Search (fallback).

Usage:
    from app.services.search.search_router import web_search

    results = await web_search("DIU admission 2026")
"""

import logging

from app.services.search.tavily_service import search as tavily_search, TavilyLimitError, get_tavily_usage
from app.services.search import brave_service

logger = logging.getLogger("yourDIU.search_router")


async def web_search(
    query: str,
    max_results: int = 5,
    prefer_diu: bool = False,
) -> tuple[list[dict], str]:
    """
    Search the web. Returns (results, provider_used).

    prefer_diu: if True, biases search toward diu.edu.bd results.
    """
    include_domains = ["diu.edu.bd", "daffodilvarsity.edu.bd"] if prefer_diu else None

    # ── Try Tavily first ─────────────────────────────────────────────────────
    try:
        results = await tavily_search(
            query,
            max_results=max_results,
            include_domains=include_domains,
        )
        usage = get_tavily_usage()
        logger.info(
            "Tavily search OK — %d/%d used today",
            usage["used"], usage["limit"]
        )
        return results, "tavily"

    except TavilyLimitError:
        logger.warning("Tavily limit reached — switching to Brave Search.")

    except Exception as e:
        logger.warning("Tavily failed (%s) — falling back to Brave.", e)

    # ── Fallback: Brave Search ───────────────────────────────────────────────
    try:
        results = await brave_service.search(query, max_results=max_results)
        return results, "brave"
    except Exception as e:
        logger.error("Brave Search also failed: %s", e)
        return [], "none"


def format_search_results(results: list[dict], max_chars: int = 3000) -> str:
    """Format search results into a string for LLM context injection."""
    if not results:
        return "No search results found."

    lines = ["Web search results:\n"]
    total = 0
    for i, r in enumerate(results, 1):
        block = f"[{i}] {r['title']}\nURL: {r['url']}\n{r['content']}\n"
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)

    return "\n".join(lines)

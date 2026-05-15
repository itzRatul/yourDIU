"""
Brain Service — Query Router
=============================
Decides HOW to answer a user query:

  MODE          WHEN
  ──────────────────────────────────────────────────────────────────────────
  routine       Query is about class schedule, routine, room number
  teacher       Query is about a teacher's availability/office hours
  rag           Query is about DIU info that is in our knowledge base
  search        Query needs fresh/current web info
  direct        General question; answer from LLM knowledge directly

Flow per mode:
  routine → query routine_slots/availability tables → inject into Groq prompt
  teacher → query teacher_info/availability → inject into Groq prompt
  rag     → retrieve from document_chunks (pgvector) → inject into Groq prompt
  search  → Tavily/Brave search → inject results into Groq prompt
  direct  → send directly to Groq, no extra context
"""

import asyncio
import logging
import re
from datetime import date, timedelta
from typing import Optional

from app.services.ai.groq_service import chat_completion, chat_completion_stream, quick_classify, DIU_SYSTEM_PROMPT
from app.services.search.search_router import web_search, format_search_results
from app.services.rag.retriever import RAGRetriever
from app.core.supabase import supabase_admin

logger = logging.getLogger("yourDIU.brain")

_retriever = RAGRetriever()


# ── Intent detection ─────────────────────────────────────────────────────────

ROUTINE_KEYWORDS = [
    "routine", "class", "schedule", "slot", "room", "section", "batch",
    "ক্লাস", "রুটিন", "ক্লাসরুম", "সময়সূচি",
]
TEACHER_KEYWORDS = [
    "teacher", "sir", "madam", "professor", "available", "office",
    "শিক্ষক", "স্যার", "ম্যাম", "অফিস", "পাওয়া যাবে", "আছেন",
]
SEARCH_KEYWORDS = [
    "latest", "news", "today", "recent", "current", "2026", "admission",
    "notice", "circular", "result", "আজকের", "সর্বশেষ", "নতুন",
]

def _detect_intent(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ROUTINE_KEYWORDS):
        return "routine"
    if any(k in q for k in TEACHER_KEYWORDS):
        return "teacher"
    if any(k in q for k in SEARCH_KEYWORDS):
        return "search"
    return "rag"


def _extract_initials(query: str) -> Optional[str]:
    """Try to extract teacher initials like MAK, SKR from the query."""
    matches = re.findall(r'\b[A-Z]{2,4}\b', query)
    if matches:
        return matches[0]
    return None


def _extract_date(query: str) -> date:
    """Extract a date from query text. Defaults to today."""
    q = query.lower()
    today = date.today()
    if "tomorrow" in q or "আগামীকাল" in q:
        return today + timedelta(days=1)
    if "yesterday" in q or "গতকাল" in q:
        return today - timedelta(days=1)
    # Try YYYY-MM-DD pattern
    m = re.search(r'\d{4}-\d{2}-\d{2}', query)
    if m:
        try:
            return date.fromisoformat(m.group())
        except ValueError:
            pass
    return today


# ── Context builders ─────────────────────────────────────────────────────────

def _build_routine_context(query: str) -> str:
    """Query routine_slots and return a formatted context string."""
    from app.services.routine.availability import get_teacher_schedule

    initials = _extract_initials(query)
    lines = []

    if initials:
        slots = get_teacher_schedule(initials)
        if slots:
            lines.append(f"Schedule for {initials}:")
            for s in slots:
                lines.append(
                    f"  {s['day']} {s['time_start'][:5]}-{s['time_end'][:5]} | "
                    f"Course: {s['course_code']} | Batch: {s['batch']} | "
                    f"Section: {s['section']} | Room: {s['room']}"
                )
        else:
            lines.append(f"No schedule found for initials: {initials}")
    else:
        lines.append("(No specific teacher initials detected in query.)")

    return "\n".join(lines) if lines else ""


def _build_teacher_context(query: str) -> str:
    """Query teacher availability and return a formatted context string."""
    from app.services.routine.availability import get_teacher_day_summary, format_availability_for_ai

    initials = _extract_initials(query)
    if not initials:
        return ""

    target_date = _extract_date(query)

    # Resolve initials → teacher_id
    resp = (
        supabase_admin.table("teacher_info")
        .select("id, initials, room_number, designation, office_hours")
        .eq("initials", initials)
        .single()
        .execute()
    )
    if not resp.data:
        return f"No teacher found with initials: {initials}"

    teacher_id = resp.data["id"]
    summary = get_teacher_day_summary(initials, teacher_id, target_date)
    return format_availability_for_ai(summary)


# ── Main brain entry point ───────────────────────────────────────────────────

async def get_answer(
    query: str,
    history: list[dict],
    stream: bool = False,
):
    """
    Route the query and produce an answer.

    Args:
        query:   The user's latest message
        history: List of {role, content} dicts (prior turns)
        stream:  If True, returns an AsyncIterator of text chunks

    Returns:
        If stream=False: (answer_str, mode, sources)
        If stream=True:  (async_generator, mode, sources)
    """
    intent = _detect_intent(query)
    logger.info("Query intent detected: %s | query: %.60s", intent, query)

    context_block = ""
    sources = []
    mode = intent

    # ── Build context based on intent ────────────────────────────────────────

    if intent == "routine":
        context_block = _build_routine_context(query)

    elif intent == "teacher":
        context_block = _build_teacher_context(query)

    elif intent == "search":
        results, provider = await web_search(query, max_results=5, prefer_diu=True)
        context_block = format_search_results(results)
        sources = results
        logger.info("Web search via %s — %d results", provider, len(results))

    elif intent == "rag":
        # Retriever is sync (CPU-bound embedding + blocking DB) — run in thread pool
        ctx_str, chunks = await asyncio.to_thread(_retriever.retrieve_and_format, query)
        context_block = ctx_str
        sources = [
            {"title": c.metadata.get("title", "DIU Knowledge"), "url": c.metadata.get("url", ""), "content": c.chunk_text[:300]}
            for c in chunks
        ]

    # ── Build prompt ─────────────────────────────────────────────────────────

    system = DIU_SYSTEM_PROMPT
    if context_block:
        system += f"\n\n--- Relevant Context ---\n{context_block}\n--- End Context ---"

    messages = history + [{"role": "user", "content": query}]

    # ── Call Groq (with Gemini fallback) ─────────────────────────────────────

    if stream:
        async def _stream_with_fallback():
            try:
                async for chunk in chat_completion_stream(messages, system_prompt=system):
                    yield chunk
            except Exception as e:
                logger.warning("Groq stream failed, falling back to Gemini: %s", e)
                from app.services.ai import gemini_service
                answer = await gemini_service.chat_completion(messages, system_prompt=system)
                yield answer

        return _stream_with_fallback(), mode, sources

    else:
        try:
            answer = await chat_completion(messages, system_prompt=system)
        except Exception as e:
            logger.warning("Groq failed, falling back to Gemini: %s", e)
            from app.services.ai import gemini_service
            answer = await gemini_service.chat_completion(messages, system_prompt=system)

        return answer, mode, sources

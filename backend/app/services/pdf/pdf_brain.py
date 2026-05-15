"""
PDF Brain Service
=================
Orchestrates AI chat for a single PDF session.

Design contract:
  - AI answers ONLY from the provided PDF content
  - Even if AI "knows" the answer from training data, it must NOT use it —
    it must answer only from what is written in the PDF
  - If PDF says "Bangladesh capital = New York", AI answers "New York" (follows PDF)
  - If content is NOT in PDF → tell user + ask permission to search web
  - Web search only happens with explicit per-query user approval
  - Chat history is client-side (passed in request body, not stored server-side)

Modes returned:
  pdf_rag          — answered from PDF chunks
  pdf_search       — PDF + web search (user explicitly approved)
  needs_permission — content not in PDF; frontend shows "Search web?" dialog
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

from app.services.ai.groq_service import chat_completion, chat_completion_stream
from app.services.search.search_router import web_search, format_search_results
from .pdf_retriever import retrieve_pdf_chunks, has_good_context, format_pdf_context

logger = logging.getLogger("yourDIU.pdf_brain")


# ── System prompts ────────────────────────────────────────────────────────────

# Core anti-hallucination prompt.
# Verbosely repeated constraints work better than single short instructions.
_PDF_ONLY_SYSTEM = """\
You are a PDF Research Assistant. Your ONLY knowledge source is the PDF content provided below.

CRITICAL RULES — follow without exception:

1. FORBIDDEN: Using ANY knowledge from your training data.
   - Even if you know the answer from training, you must NOT use it.
   - Example: If someone asks "What is the capital of Bangladesh?" and the PDF does NOT
     mention it, you must say the PDF does not contain this information.
   - Example: If the PDF says "Bangladesh capital = New York", you must answer "New York"
     because that is what the PDF says — even if you know it is wrong.

2. REQUIRED: Answer ONLY using information explicitly written in the PDF context below.
   - If the PDF contains it → answer with page reference: "According to the PDF (Page 3), ..."
   - If the PDF does NOT contain it → say: "This topic is not covered in the uploaded PDF."

3. FORBIDDEN: Guessing, inferring from outside knowledge, or supplementing with training data.

4. REQUIRED: Cite the page number for every fact you state: (Page 3) or (Pages 2–4).

5. REQUIRED: Answer in the same language the user writes in (Bangla or English).\
"""

_PDF_WITH_WEB_SYSTEM = """\
You are a PDF Research Assistant. The user has approved a web search to supplement the PDF.
Answer using the provided PDF content AND web search results below.

Rules:
1. Prioritize PDF content over web results.
2. Cite every fact inline: (PDF, Page 3) or (Web).
3. Answer in the same language the user writes in (Bangla or English).
4. Be accurate and concise.\
"""

# Shown when no relevant content found in PDF
_NEEDS_PERMISSION_MESSAGE = (
    "This topic is not covered in the uploaded PDF. "
    "Would you like me to search the web for this?"
)


# ── Main entry point ──────────────────────────────────────────────────────────

async def get_pdf_answer(
    session_id:       str,
    query:            str,
    history:          list[dict],
    allow_web_search: bool = False,
    stream:           bool = True,
):
    """
    Answer a query using the PDF session's chunks.

    Flow:
      1. Search PDF chunks (pgvector)
      2. Found relevant content → answer strictly from PDF (no training data)
      3. NOT found → return needs_permission (frontend asks user: "Search web?")
      4. User approves → re-sent with allow_web_search=True → web search injected

    Returns (stream=False): (answer: str, mode: str, search_query: str | None)
    Returns (stream=True):  (async_generator, mode, search_query | None)

    search_query is set when mode == "needs_permission" (for frontend display).
    """
    # Retrieve chunks (sync embedding + DB → thread pool)
    chunks = await asyncio.to_thread(
        retrieve_pdf_chunks, session_id, query, top_k=6, threshold=0.28
    )
    found_in_pdf = has_good_context(chunks)

    # ── Case 1: Nothing relevant in PDF ──────────────────────────────────────
    if not found_in_pdf:
        if not allow_web_search:
            # Ask user permission before doing any web search
            logger.info("PDF brain: no match in PDF, asking permission (session=%s)", session_id)
            if stream:
                async def _permission_stream():
                    yield _NEEDS_PERMISSION_MESSAGE
                return _permission_stream(), "needs_permission", query
            else:
                return _NEEDS_PERMISSION_MESSAGE, "needs_permission", query

        # User approved web search and PDF had nothing — search only from web
        logger.info("PDF brain: no PDF match, web search approved (session=%s)", session_id)
        web_results, provider = await web_search(query, max_results=5, prefer_diu=False)
        web_ctx = format_search_results(web_results, max_chars=3000)
        system  = _PDF_WITH_WEB_SYSTEM + (
            "\n\n--- PDF Content ---\n"
            "(No relevant sections found in the uploaded PDF)\n\n"
            f"--- Web Results ---\n{web_ctx}"
        )
        mode = "pdf_search"

    # ── Case 2: Found relevant PDF context ───────────────────────────────────
    else:
        pdf_ctx = format_pdf_context(chunks)
        system  = _PDF_ONLY_SYSTEM + f"\n\n--- PDF Content ---\n{pdf_ctx}"
        mode    = "pdf_rag"

        # User also approved web search to supplement the PDF answer
        if allow_web_search:
            web_results, _ = await web_search(query, max_results=3, prefer_diu=False)
            if web_results:
                web_ctx = format_search_results(web_results, max_chars=2000)
                system  = _PDF_WITH_WEB_SYSTEM + (
                    f"\n\n--- PDF Content ---\n{pdf_ctx}"
                    f"\n\n--- Web Results ---\n{web_ctx}"
                )
                mode = "pdf_search"

    messages = history + [{"role": "user", "content": query}]

    # ── Stream ────────────────────────────────────────────────────────────────
    if stream:
        async def _stream_with_fallback() -> AsyncIterator[str]:
            try:
                async for chunk in chat_completion_stream(
                    messages, system_prompt=system, max_tokens=1500
                ):
                    yield chunk
            except Exception as exc:
                logger.warning("Groq stream failed, falling back to Gemini: %s", exc)
                from app.services.ai import gemini_service
                answer = await gemini_service.chat_completion(
                    messages, system_prompt=system, max_tokens=1500
                )
                yield answer

        return _stream_with_fallback(), mode, None

    # ── Sync ──────────────────────────────────────────────────────────────────
    try:
        answer = await chat_completion(messages, system_prompt=system, max_tokens=1500)
    except Exception as exc:
        logger.warning("Groq failed, falling back to Gemini: %s", exc)
        from app.services.ai import gemini_service
        answer = await gemini_service.chat_completion(
            messages, system_prompt=system, max_tokens=1500
        )

    return answer, mode, None


# ── Summary generator ─────────────────────────────────────────────────────────

async def generate_pdf_summary(session_id: str) -> str:
    """
    Generate a structured summary of the entire PDF.
    Fetches all chunks ordered by position, capped at 14k chars.
    """
    from app.core.supabase import supabase_admin

    resp = (
        supabase_admin.table("pdf_session_chunks")
        .select("content, chunk_index, page_number")
        .eq("session_id", session_id)
        .order("chunk_index")
        .execute()
    )

    chunks = resp.data or []
    if not chunks:
        raise RuntimeError("No content found for this PDF session.")

    parts: list[str] = []
    total = 0
    max_chars = 14_000

    for chunk in chunks:
        block = f"[Page {chunk['page_number']}] {chunk['content']}"
        if total + len(block) > max_chars:
            parts.append("... [remaining content omitted for summary]")
            break
        parts.append(block)
        total += len(block)

    full_content = "\n\n".join(parts)

    prompt = (
        "Please provide a comprehensive, well-structured summary of this document.\n\n"
        "Format your response as:\n"
        "**Main Topic**\n"
        "What this document is about in 1-2 sentences.\n\n"
        "**Key Points**\n"
        "- bullet points of the most important information\n\n"
        "**Important Details**\n"
        "Notable data, findings, methods, or arguments.\n\n"
        "**Conclusion / Takeaway**\n"
        "What can be concluded or applied from this document.\n\n"
        f"Document Content:\n{full_content}\n\n"
        "Write the summary in the same language as the document."
    )

    summary_system = (
        "You are a document summarization expert. "
        "Create clear, structured, and accurate summaries from document content."
    )

    try:
        summary = await chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=summary_system,
            max_tokens=2000,
        )
    except Exception as exc:
        logger.warning("Groq summary failed, using Gemini: %s", exc)
        from app.services.ai import gemini_service
        summary = await gemini_service.chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=summary_system,
            max_tokens=2000,
        )

    return summary

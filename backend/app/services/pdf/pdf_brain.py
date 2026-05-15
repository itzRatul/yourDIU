"""
PDF Brain Service
=================
Orchestrates AI chat for a single PDF session.

Design contract (strict):
  - AI answers ONLY from the provided PDF content
  - Even if the AI "knows" the answer from training data, it must NOT answer
    unless that information is explicitly present in the PDF text
  - If no relevant content found in PDF → return "not_found" (not a web search prompt)
  - Web search is a SEPARATE explicit user action only (allow_web_search=True)
  - Chat history is client-side only (passed in request body, not stored server-side)

Modes returned:
  pdf_rag    — answered from PDF chunks
  pdf_search — PDF chunks + web search (user explicitly requested)
  not_found  — answer not in PDF (returned directly, no web search prompt)
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

from app.services.ai.groq_service import chat_completion, chat_completion_stream
from app.services.search.search_router import web_search, format_search_results
from .pdf_retriever import retrieve_pdf_chunks, has_good_context, format_pdf_context

logger = logging.getLogger("yourDIU.pdf_brain")


# ── System prompts ────────────────────────────────────────────────────────────

# This prompt is the core anti-hallucination contract.
# The wording is intentionally verbose and repetitive — LLMs respond better to
# explicit, repeated constraints than a single short instruction.
_PDF_ONLY_SYSTEM = """\
You are a PDF Research Assistant. Your ONLY knowledge source is the PDF content provided below.

CRITICAL RULES — you MUST follow these without exception:

1. FORBIDDEN: Using ANY knowledge from your training data, even if you are 100% sure of the answer.
   Example: If someone asks "What is the capital of Bangladesh?" and this is NOT in the PDF,
   you MUST say "This information is not in the uploaded PDF." — even though you know the answer is Dhaka.

2. REQUIRED: Answer ONLY using exact information found in the PDF context section below.
   If the PDF contains it → answer with page reference: "According to the PDF (Page 3), ..."
   If the PDF does NOT contain it → say exactly: "This information is not in the uploaded PDF."

3. FORBIDDEN: Guessing, inferring, extrapolating, or combining PDF content with outside knowledge.

4. REQUIRED: Cite the page number for every fact: write (Page 3) or (Pages 2–4) inline.

5. REQUIRED: Answer in the same language the user writes in (Bangla or English).

6. If you find partial information in the PDF, share what is there and state clearly what is missing.\
"""

_PDF_WITH_WEB_SYSTEM = """\
You are a PDF Research Assistant. The user has explicitly requested both PDF content and web search results.
Answer using the provided PDF content AND web search results below.

Rules:
1. Prioritize PDF content over web results.
2. Cite every fact: (PDF, Page 3) or (Web) inline.
3. Answer in the same language the user writes in (Bangla or English).
4. Be accurate and concise.\
"""

# Returned directly when PDF has no relevant content — no web search offer
_NOT_FOUND_MESSAGE = "This information is not in the uploaded PDF."


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

    allow_web_search=True means the user explicitly clicked "Search web" in the UI.
    This is NOT triggered automatically — it is always an explicit user action.

    Returns (stream=False): (answer: str, mode: str)
    Returns (stream=True):  (async_generator, mode)

    mode: "pdf_rag" | "pdf_search" | "not_found"
    """
    # Retrieve chunks (sync embedding + DB call → thread pool)
    chunks = await asyncio.to_thread(
        retrieve_pdf_chunks, session_id, query, top_k=6, threshold=0.28
    )
    found_in_pdf = has_good_context(chunks)

    # ── Case 1: No relevant content in PDF ───────────────────────────────────
    if not found_in_pdf:
        if not allow_web_search:
            # Just tell user it's not in the PDF — no automatic web search prompt
            logger.info("PDF brain: no match in PDF (session=%s) — returning not_found", session_id)
            if stream:
                async def _not_found_stream():
                    yield _NOT_FOUND_MESSAGE
                return _not_found_stream(), "not_found"
            else:
                return _NOT_FOUND_MESSAGE, "not_found"

        # User explicitly requested web search (and PDF had nothing)
        logger.info("PDF brain: no PDF match, web search explicitly requested (session=%s)", session_id)
        web_results, provider = await web_search(query, max_results=5, prefer_diu=False)
        web_ctx = format_search_results(web_results, max_chars=3000)
        system  = _PDF_WITH_WEB_SYSTEM + f"\n\n--- PDF Content ---\n(No relevant sections found in uploaded PDF)\n\n--- Web Results ---\n{web_ctx}"
        mode    = "pdf_search"

    # ── Case 2: Found relevant PDF context ───────────────────────────────────
    else:
        pdf_ctx = format_pdf_context(chunks)
        system  = _PDF_ONLY_SYSTEM + f"\n\n--- PDF Content ---\n{pdf_ctx}"
        mode    = "pdf_rag"

        # If user also requested web search, supplement (but PDF content takes priority)
        if allow_web_search:
            web_results, _ = await web_search(query, max_results=3, prefer_diu=False)
            if web_results:
                web_ctx = format_search_results(web_results, max_chars=2000)
                system  = _PDF_WITH_WEB_SYSTEM + f"\n\n--- PDF Content ---\n{pdf_ctx}\n\n--- Web Results ---\n{web_ctx}"
                mode    = "pdf_search"

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

        return _stream_with_fallback(), mode

    # ── Sync ──────────────────────────────────────────────────────────────────
    try:
        answer = await chat_completion(messages, system_prompt=system, max_tokens=1500)
    except Exception as exc:
        logger.warning("Groq failed, falling back to Gemini: %s", exc)
        from app.services.ai import gemini_service
        answer = await gemini_service.chat_completion(
            messages, system_prompt=system, max_tokens=1500
        )

    return answer, mode


# ── Summary generator ─────────────────────────────────────────────────────────

async def generate_pdf_summary(session_id: str) -> str:
    """
    Generate a structured summary of the entire PDF.
    Fetches all chunks ordered by position, builds content block (capped at 14k chars).
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

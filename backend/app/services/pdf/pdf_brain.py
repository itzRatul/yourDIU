"""
PDF Brain Service
=================
Orchestrates AI chat for a single PDF session.

Design contract:
  - AI answers ONLY from the provided PDF content (no hallucination from training data)
  - If no relevant content found → return "needs_permission" signal
  - Frontend shows "Search web for this?" dialog (per-query, not a global toggle)
  - If user approves → same query re-sent with allow_web_search=True → web search injected

Chat history is client-side only (passed in request body).
No server-side history stored — consistent with temporary session design.

Modes returned:
  pdf_rag        — answered from PDF chunks
  pdf_search     — PDF chunks + web search results combined
  needs_permission — no PDF match found, asking user to allow web search
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

from app.services.ai.groq_service import chat_completion, chat_completion_stream
from app.services.search.search_router import web_search, format_search_results
from .pdf_retriever import retrieve_pdf_chunks, has_good_context, format_pdf_context

logger = logging.getLogger("yourDIU.pdf_brain")


# ── System prompts ────────────────────────────────────────────────────────────

_PDF_ONLY_SYSTEM = """\
You are a PDF Research Assistant. Answer questions STRICTLY from the provided PDF content.

Rules — follow exactly:
1. Use ONLY information from the PDF context below. Do NOT use general knowledge or training data.
2. Cite page numbers where the answer comes from: write (Page 3) or (Pages 2–4) inline.
3. If the information is NOT in the provided PDF context, respond with this exact sentence:
   "I couldn't find this in the PDF."
   Do NOT guess, infer, or make up anything.
4. Quote short relevant excerpts from the PDF to support your answer when helpful.
5. Answer in the same language the user writes in (Bangla or English).
6. Be concise but complete.\
"""

_PDF_WITH_WEB_SYSTEM = """\
You are a PDF Research Assistant with web search access. Answer using BOTH the PDF content
and the web search results provided below.

Rules:
1. Prioritize PDF content. Use web results to supplement details not in the PDF.
2. Always cite sources inline: (PDF, Page 3) or (Web) for each fact.
3. Answer in the same language the user writes in (Bangla or English).
4. Be concise but complete.\
"""

_NO_RESULT_MESSAGE = (
    "I couldn't find this in the PDF. Would you like me to search the web for this?"
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

    Returns (when stream=False): (answer: str, mode: str, search_query: str | None)
    Returns (when stream=True):  (async_generator, mode, search_query | None)

    search_query is set only when mode == "needs_permission" — it's the query
    the frontend should surface to the user in the "Allow web search?" dialog.
    """
    # Retrieve chunks (sync embedding + DB call → thread pool)
    chunks = await asyncio.to_thread(
        retrieve_pdf_chunks, session_id, query, top_k=6, threshold=0.28
    )
    found_in_pdf = has_good_context(chunks)

    # ── Case 1: Nothing relevant in PDF ──────────────────────────────────────
    if not found_in_pdf:
        if not allow_web_search:
            # Signal frontend to ask permission
            if stream:
                async def _permission_stream():
                    yield _NO_RESULT_MESSAGE
                return _permission_stream(), "needs_permission", query
            else:
                return _NO_RESULT_MESSAGE, "needs_permission", query

        # User approved web search
        logger.info("PDF brain: no PDF match, searching web (session=%s)", session_id)
        web_results, provider = await web_search(query, max_results=5, prefer_diu=False)
        web_ctx = format_search_results(web_results, max_chars=3000)

        system  = _PDF_WITH_WEB_SYSTEM + f"\n\n--- PDF Content ---\n(No relevant sections found)\n\n--- Web Results ---\n{web_ctx}"
        mode    = "pdf_search"

    # ── Case 2: Found good PDF context ───────────────────────────────────────
    else:
        pdf_ctx = format_pdf_context(chunks)
        system  = _PDF_ONLY_SYSTEM + f"\n\n--- PDF Content ---\n{pdf_ctx}"
        mode    = "pdf_rag"

        # If user already granted permission, optionally supplement with web
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

    Fetches all chunks (ordered), builds a content block (capped at 14k chars
    to stay within LLM context), then asks for a structured summary.
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

    # Build representative content block
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

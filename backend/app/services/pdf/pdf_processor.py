"""
PDF Processor
=============
Handles the full pipeline for a user-uploaded PDF:
  1. Parse text per page with pdfplumber
  2. Gemini Vision fallback for image-heavy / scanned pages
  3. Hybrid chunk each page (reuses HybridChunker — same as DIU RAG)
  4. Embed all chunks (reuses EmbeddingService)
  5. Batch-insert into pdf_session_chunks
  6. Update session status → ready

This feature is research/study oriented — PDFs are temporary (7-day TTL).
The raw PDF bytes are NOT stored; only the chunked text + embeddings persist.
"""

import asyncio
import io
import logging
import uuid
from typing import Optional

from app.core.supabase import supabase_admin
from app.services.rag.chunking import HybridChunker
from app.services.rag.embeddings import EmbeddingService

logger = logging.getLogger("yourDIU.pdf_processor")

_BATCH_SIZE = 50       # chunks per Supabase insert call
_MIN_PAGE_CHARS = 30   # pages shorter than this are skipped (cover pages, blanks)


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def _extract_pages(file_bytes: bytes) -> tuple[list[tuple[int, str]], int]:
    """
    Extract text from each page with pdfplumber.
    Returns: ([(page_num, text), ...], total_pages)
    Pages with no extractable text are excluded from the list.
    """
    import pdfplumber

    pages: list[tuple[int, str]] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        total = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, 1):
            text = (page.extract_text() or "").strip()
            if len(text) >= _MIN_PAGE_CHARS:
                pages.append((page_num, text))

    return pages, total


async def _gemini_extract_page(file_bytes: bytes, page_num: int, total_pages: int) -> str:
    """
    Fallback: use Gemini Vision to extract text from a single PDF page image.
    Called when pdfplumber returns blank text for a page.
    """
    try:
        import pdfplumber
        from app.services.ai.gemini_service import analyze_image_bytes

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if page_num > len(pdf.pages):
                return ""
            page = pdf.pages[page_num - 1]
            pil_img = page.to_image(resolution=150).original

        img_buf = io.BytesIO()
        pil_img.save(img_buf, format="PNG")
        img_bytes = img_buf.getvalue()

        prompt = (
            "Extract ALL text from this document page. "
            "Preserve paragraph breaks. Return plain text only — no markdown, no explanation."
        )
        return await analyze_image_bytes(img_bytes, prompt, mime_type="image/png")

    except Exception as exc:
        logger.warning("Gemini Vision failed for page %d: %s", page_num, exc)
        return ""


# ---------------------------------------------------------------------------
# Main processing pipeline
# ---------------------------------------------------------------------------

async def process_pdf(
    file_bytes: bytes,
    filename:   str,
    session_id: str,
) -> dict:
    """
    Full pipeline: parse → chunk → embed → store.

    Runs CPU-heavy steps (encoding) in a thread pool via asyncio.to_thread()
    so it doesn't block the FastAPI event loop.

    Returns: {"page_count": int, "chunk_count": int, "status": "ready"}
    Raises RuntimeError on unrecoverable failure (also marks session as failed).
    """
    try:
        return await _run_pipeline(file_bytes, filename, session_id)
    except Exception as exc:
        logger.error("PDF processing failed for session %s: %s", session_id, exc)
        supabase_admin.table("pdf_sessions").update(
            {"status": "failed"}
        ).eq("id", session_id).execute()
        raise


async def _run_pipeline(file_bytes: bytes, filename: str, session_id: str) -> dict:
    # ── Step 1: Parse PDF pages ──────────────────────────────────────────────
    logger.info("PDF pipeline start: session=%s file=%s size=%d", session_id, filename, len(file_bytes))

    pages_text, total_pages = await asyncio.to_thread(_extract_pages, file_bytes)

    # For entirely image-based PDFs (scanned), fallback to Gemini Vision
    if not pages_text and total_pages > 0:
        logger.warning("No text from pdfplumber — trying Gemini Vision for %d pages", total_pages)
        for page_num in range(1, min(total_pages + 1, 21)):   # cap at 20 pages for Vision cost
            text = await _gemini_extract_page(file_bytes, page_num, total_pages)
            if len(text.strip()) >= _MIN_PAGE_CHARS:
                pages_text.append((page_num, text.strip()))

    if not pages_text:
        raise RuntimeError("Could not extract any text from this PDF. The file may be image-only or password-protected.")

    logger.info("Extracted text from %d / %d pages", len(pages_text), total_pages)

    # ── Step 2: Hybrid chunk each page ───────────────────────────────────────
    # Chunking is sync/CPU-bound → thread pool
    chunker = HybridChunker.get()

    def _chunk_all() -> list[tuple[int, str]]:
        result: list[tuple[int, str]] = []
        for page_num, text in pages_text:
            chunks = chunker.chunk(text=text, doc_id=session_id, doc_type="pdf_session")
            for chunk in chunks:
                result.append((page_num, chunk.text))
        return result

    chunks_with_pages: list[tuple[int, str]] = await asyncio.to_thread(_chunk_all)

    if not chunks_with_pages:
        raise RuntimeError("PDF was parsed but contained no usable text chunks after filtering.")

    logger.info("Chunked into %d chunks across %d pages", len(chunks_with_pages), len(pages_text))

    # ── Step 3: Embed all chunks ─────────────────────────────────────────────
    embedder = EmbeddingService.get()
    chunk_texts = [text for _, text in chunks_with_pages]

    embeddings: list[list[float]] = await asyncio.to_thread(
        embedder.embed, chunk_texts
    )

    # ── Step 4: Batch-insert into pdf_session_chunks ─────────────────────────
    rows = [
        {
            "id":          str(uuid.uuid4()),
            "session_id":  session_id,
            "content":     chunks_with_pages[i][1],
            "chunk_index": i,
            "page_number": chunks_with_pages[i][0],
            "embedding":   embeddings[i],
        }
        for i in range(len(chunks_with_pages))
    ]

    for start in range(0, len(rows), _BATCH_SIZE):
        batch = rows[start : start + _BATCH_SIZE]
        supabase_admin.table("pdf_session_chunks").insert(batch).execute()
        logger.debug("Inserted chunk batch %d-%d", start, start + len(batch) - 1)

    chunk_count = len(rows)

    # ── Step 5: Mark session as ready ────────────────────────────────────────
    supabase_admin.table("pdf_sessions").update({
        "page_count":  total_pages,
        "chunk_count": chunk_count,
        "status":      "ready",
    }).eq("id", session_id).execute()

    logger.info(
        "PDF pipeline done: session=%s pages=%d chunks=%d",
        session_id, total_pages, chunk_count,
    )
    return {
        "page_count":  total_pages,
        "chunk_count": chunk_count,
        "status":      "ready",
    }

"""
PDF Session Retriever
=====================
Semantic search over a specific PDF session's chunks via pgvector.

Uses the same EmbeddingService (all-MiniLM-L6-v2, 384-dim, L2-normalized)
as the main DIU RAG system — only the scope is different (single session).

Sync functions — wrap with asyncio.to_thread() in async callers.
"""

import logging
from dataclasses import dataclass

from app.core.supabase import supabase_admin
from app.services.rag.embeddings import EmbeddingService

logger = logging.getLogger("yourDIU.pdf_retriever")

_GOOD_SIMILARITY_THRESHOLD = 0.32   # above this = "found in PDF"


@dataclass
class PDFChunk:
    id:          str
    content:     str
    chunk_index: int
    page_number: int
    similarity:  float


def retrieve_pdf_chunks(
    session_id: str,
    query:      str,
    top_k:      int   = 6,
    threshold:  float = 0.28,
) -> list[PDFChunk]:
    """
    Find the most relevant chunks in a specific PDF session.
    Lower threshold (0.28) returns more candidates; caller judges quality
    by checking if top chunk similarity >= _GOOD_SIMILARITY_THRESHOLD.
    """
    if not query.strip():
        return []

    embedder        = EmbeddingService.get()
    query_embedding = embedder.embed_one(query)

    try:
        resp = supabase_admin.rpc(
            "match_pdf_session_chunks",
            {
                "p_session_id":    session_id,
                "query_embedding": query_embedding,
                "match_count":     top_k,
                "match_threshold": threshold,
            },
        ).execute()
    except Exception as exc:
        logger.error("PDF pgvector RPC failed (session=%s): %s", session_id, exc)
        return []

    rows   = resp.data or []
    chunks = [
        PDFChunk(
            id          = row["id"],
            content     = row["content"],
            chunk_index = row["chunk_index"],
            page_number = row.get("page_number", 0),
            similarity  = round(row["similarity"], 4),
        )
        for row in rows
    ]

    logger.info(
        "PDF retrieve: session=%s query=%.40s results=%d top_sim=%.3f",
        session_id, query, len(chunks),
        chunks[0].similarity if chunks else 0.0,
    )
    return chunks


def has_good_context(chunks: list[PDFChunk]) -> bool:
    """Returns True if the top chunk has meaningful similarity to the query."""
    return bool(chunks) and chunks[0].similarity >= _GOOD_SIMILARITY_THRESHOLD


def format_pdf_context(chunks: list[PDFChunk], max_chars: int = 7000) -> str:
    """
    Format retrieved chunks into LLM context with page references.
    Sorts by chunk_index so context reads in document order, not similarity order.
    """
    if not chunks:
        return ""

    # Re-sort by page/chunk order for better readability in the prompt
    ordered = sorted(chunks, key=lambda c: (c.page_number, c.chunk_index))

    parts  = []
    total  = 0

    for chunk in ordered:
        block = f"[Page {chunk.page_number}]\n{chunk.content}"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)

    return "\n\n---\n\n".join(parts)

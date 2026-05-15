"""
RAG Retriever
=============
Queries the pgvector index in Supabase using the match_document_chunks()
SQL function defined in schema.sql.

Flow:
  query string
    → embed with EmbeddingService
    → call match_document_chunks() RPC in Supabase
    → return ranked Chunk results with similarity scores
"""

import logging
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.core.supabase import supabase_admin
from .embeddings import EmbeddingService

logger = logging.getLogger("yourDIU.retriever")


@dataclass
class RetrievedChunk:
    id:         str
    doc_id:     str
    chunk_text: str
    metadata:   dict
    similarity: float


class RAGRetriever:
    _instance: Optional["RAGRetriever"] = None

    def __init__(self):
        self.embedder = EmbeddingService.get()

    @classmethod
    def get(cls) -> "RAGRetriever":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------

    def retrieve(
        self,
        query:      str,
        top_k:      int            = settings.rag_top_k,
        threshold:  float          = 0.45,
        doc_type:   Optional[str]  = None,
    ) -> list[RetrievedChunk]:
        """
        Retrieve the most semantically relevant chunks for a query.

        Args:
            query:     Natural language question or statement.
            top_k:     Max number of chunks to return.
            threshold: Minimum cosine similarity (0-1). Lower = more results.
            doc_type:  Optional filter — 'academic', 'department', 'faculty', etc.

        Returns:
            List of RetrievedChunk sorted by similarity (highest first).
        """
        if not query.strip():
            return []

        query_embedding = self.embedder.embed_one(query)

        try:
            resp = supabase_admin.rpc(
                "match_document_chunks",
                {
                    "query_embedding":  query_embedding,
                    "match_threshold":  threshold,
                    "match_count":      top_k,
                    "filter_doc_type":  doc_type,
                },
            ).execute()
        except Exception as exc:
            logger.error("pgvector RPC failed: %s", exc)
            return []

        rows = resp.data or []
        chunks = [
            RetrievedChunk(
                id=row["id"],
                doc_id=row["doc_id"],
                chunk_text=row["chunk_text"],
                metadata=row.get("metadata", {}),
                similarity=round(row["similarity"], 4),
            )
            for row in rows
        ]

        logger.info(
            "Retrieved %d chunks for query (top sim: %.3f)",
            len(chunks),
            chunks[0].similarity if chunks else 0,
        )
        return chunks

    def format_context(self, chunks: list[RetrievedChunk], max_tokens: int = 3000) -> str:
        """
        Join retrieved chunks into a single context string for the LLM prompt.
        Stops adding chunks once max_tokens (approximate chars) is reached.
        """
        parts:    list[str] = []
        total:    int       = 0
        approx_chars = max_tokens * 4  # ~4 chars per token

        for i, chunk in enumerate(chunks, 1):
            source = chunk.metadata.get("source_url", "DIU website")
            block  = f"[Source {i}: {source}]\n{chunk.chunk_text}"
            if total + len(block) > approx_chars:
                break
            parts.append(block)
            total += len(block)

        return "\n\n---\n\n".join(parts)

    def retrieve_and_format(
        self,
        query:     str,
        top_k:     int           = settings.rag_top_k,
        threshold: float         = 0.45,
        doc_type:  Optional[str] = None,
    ) -> tuple[str, list[RetrievedChunk]]:
        """Convenience: retrieve + format in one call. Returns (context_str, chunks)."""
        chunks  = self.retrieve(query, top_k, threshold, doc_type)
        context = self.format_context(chunks)
        return context, chunks

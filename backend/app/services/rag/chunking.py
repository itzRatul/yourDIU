"""
Hybrid Chunker
==============
Two-pass chunking strategy — much better than DAIC's fixed chunking:

Pass 1 — Semantic split
    Groups sentences together as long as adjacent sentences are semantically
    similar (cosine similarity >= threshold). When similarity drops, a new
    chunk begins. This keeps related ideas together and splits at real
    topic boundaries instead of arbitrary character counts.

Pass 2 — Recursive split
    Any semantic chunk that is still too large gets split further with
    RecursiveCharacterTextSplitter, preserving paragraph / sentence / word
    boundaries in that order.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger("yourDIU.chunker")


@dataclass
class Chunk:
    text:        str
    index:       int
    doc_id:      Optional[str]  = None
    source_url:  Optional[str]  = None
    doc_type:    str            = "general"
    metadata:    dict           = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# ---------------------------------------------------------------------------
# Sentence splitting (no heavy NLP dependency)
# ---------------------------------------------------------------------------

_SENT_PATTERN = re.compile(
    r"(?<=[।.!?])\s+"          # after Bangla danda or Latin sentence-enders
    r"|(?<=\n)\n+"              # blank lines between paragraphs
)


def _split_sentences(text: str) -> list[str]:
    raw = _SENT_PATTERN.split(text)
    return [s.strip() for s in raw if len(s.strip()) > 15]


# ---------------------------------------------------------------------------
# HybridChunker
# ---------------------------------------------------------------------------

class HybridChunker:
    """
    Singleton-friendly chunker.
    The SentenceTransformer model is loaded once and reused across calls.
    """

    _instance: Optional["HybridChunker"] = None

    def __init__(
        self,
        model_name: str  = settings.embedding_model,
        threshold:  float = settings.semantic_chunk_threshold,
        max_size:   int   = settings.max_chunk_size,
        overlap:    int   = settings.chunk_overlap,
    ):
        logger.info("Loading chunker model: %s", model_name)
        self.model     = SentenceTransformer(model_name)
        self.threshold = threshold
        self.max_size  = max_size
        self.recursive = RecursiveCharacterTextSplitter(
            chunk_size=max_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", "। ", ". ", " ", ""],
        )
        logger.info("HybridChunker ready (threshold=%.2f, max_size=%d)", threshold, max_size)

    @classmethod
    def get(cls) -> "HybridChunker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Internal: semantic pass
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / (denom + 1e-9))

    def _semantic_split(self, text: str) -> list[str]:
        sentences = _split_sentences(text)
        if len(sentences) <= 2:
            return [text]

        embeddings = self.model.encode(
            sentences,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=64,
        )

        groups: list[list[str]] = [[sentences[0]]]

        for i in range(1, len(sentences)):
            sim = self._cosine(embeddings[i - 1], embeddings[i])
            if sim < self.threshold:
                groups.append([sentences[i]])           # new semantic group
            else:
                groups[-1].append(sentences[i])         # continue current group

        return [" ".join(g) for g in groups if g]

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def chunk(
        self,
        text:      str,
        doc_id:    Optional[str] = None,
        source_url: Optional[str] = None,
        doc_type:  str           = "general",
        extra_meta: dict         = None,
    ) -> list[Chunk]:
        """
        Chunk a single document text.
        Returns a list of Chunk objects ready for embedding + storage.
        """
        text = text.strip()
        if not text:
            return []

        # Pass 1: semantic split
        semantic_chunks = self._semantic_split(text)

        # Pass 2: recursive split for oversized semantic chunks
        final_texts: list[str] = []
        for sc in semantic_chunks:
            if len(sc) > self.max_size:
                final_texts.extend(self.recursive.split_text(sc))
            else:
                final_texts.append(sc)

        # Filter noise & build Chunk objects
        base_meta = {
            "source_url": source_url,
            "doc_type":   doc_type,
            **(extra_meta or {}),
        }

        chunks = []
        for i, t in enumerate(final_texts):
            t = t.strip()
            if len(t) < 50:
                continue
            chunks.append(Chunk(
                text=t,
                index=i,
                doc_id=doc_id,
                source_url=source_url,
                doc_type=doc_type,
                metadata={**base_meta, "chunk_index": i, "char_count": len(t)},
            ))

        logger.debug(
            "Chunked doc %s → %d semantic → %d final chunks",
            doc_id or "?", len(semantic_chunks), len(chunks),
        )
        return chunks

    def chunk_many(self, documents: list[dict]) -> list[Chunk]:
        """
        documents: list of dicts with keys:
            text, doc_id, source_url, doc_type, metadata (optional)
        """
        all_chunks: list[Chunk] = []
        for doc in documents:
            chunks = self.chunk(
                text=doc.get("text", ""),
                doc_id=doc.get("doc_id"),
                source_url=doc.get("source_url"),
                doc_type=doc.get("doc_type", "general"),
                extra_meta=doc.get("metadata", {}),
            )
            all_chunks.extend(chunks)
        logger.info("chunk_many: %d docs → %d total chunks", len(documents), len(all_chunks))
        return all_chunks

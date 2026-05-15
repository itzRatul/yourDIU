"""
Embedding Service
=================
Singleton wrapper around SentenceTransformer.
Model is loaded once at first use and reused for all subsequent calls.
Handles both single-text and batch embedding.
"""

import logging
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger("yourDIU.embeddings")


class EmbeddingService:
    _instance: Optional["EmbeddingService"] = None
    _model:    Optional[SentenceTransformer] = None

    def __init__(self, model_name: str = settings.embedding_model):
        if EmbeddingService._model is None:
            logger.info("Loading embedding model: %s", model_name)
            EmbeddingService._model = SentenceTransformer(model_name)
            logger.info(
                "Embedding model ready — dim: %d",
                EmbeddingService._model.get_sentence_embedding_dimension(),
            )
        self.model = EmbeddingService._model

    @classmethod
    def get(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------

    def embed(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """Embed a list of texts. Returns list of float vectors."""
        if not texts:
            return []
        vectors: np.ndarray = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 50,
            normalize_embeddings=True,     # L2-normalize → cosine sim = dot product
        )
        return vectors.tolist()

    def embed_one(self, text: str) -> list[float]:
        """Embed a single string. Used for query embedding at inference time."""
        vector: np.ndarray = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vector.tolist()

    @property
    def dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()

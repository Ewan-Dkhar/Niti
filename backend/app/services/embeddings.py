"""Embedding providers for dense + sparse hybrid retrieval.

The default dense model is multilingual so Hindi, Tamil, Bengali, Telugu and
English clauses land in the same vector space. Sparse vectors come from BM25
in Qdrant's fastembed integration.
"""

from __future__ import annotations

from typing import Protocol

from qdrant_client import models


class EmbeddingProvider(Protocol):
    def embed_dense(self, texts: list[str]) -> list[list[float]]: ...

    def embed_sparse(self, texts: list[str]) -> list[models.SparseVector]: ...


class FastEmbedProvider:
    """Lazy wrapper around fastembed text and sparse models.

    Models are loaded on first use, not at import time, so API startup and
    tests stay fast.
    """

    def __init__(
        self,
        dense_model: str = "intfloat/multilingual-e5-large",
        sparse_model: str = "Qdrant/bm25",
    ) -> None:
        self.dense_model_name = dense_model
        self.sparse_model_name = sparse_model
        self._dense_model = None
        self._sparse_model = None

    def _load_dense(self):
        if self._dense_model is None:
            from fastembed import TextEmbedding

            self._dense_model = TextEmbedding(model_name=self.dense_model_name)
        return self._dense_model

    def _load_sparse(self):
        if self._sparse_model is None:
            from fastembed import SparseTextEmbedding

            self._sparse_model = SparseTextEmbedding(model_name=self.sparse_model_name)
        return self._sparse_model

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load_dense().embed(texts)
        return [vector.tolist() for vector in vectors]

    def embed_sparse(self, texts: list[str]) -> list[models.SparseVector]:
        embeddings = self._load_sparse().embed(texts)
        return [
            models.SparseVector(
                indices=embedding.indices.tolist(),
                values=embedding.values.tolist(),
            )
            for embedding in embeddings
        ]

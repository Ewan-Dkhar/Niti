"""Qdrant-backed hybrid retrieval over hierarchical policy chunks.

Dense and sparse (BM25) vectors are stored as named vectors on each point.
Queries use Qdrant's reciprocal rank fusion so semantic matches and exact
clause/currency terms both contribute to the ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.core.config import get_settings
from app.services.chunker import Chunk, chunk_markdown
from app.services.embeddings import EmbeddingProvider, FastEmbedProvider

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    text: str
    citation: str
    page: int
    score: float
    payload: dict


class HybridVectorStore:
    def __init__(
        self,
        client: QdrantClient,
        *,
        collection_name: str = "niti_chunks",
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.embeddings = embeddings or FastEmbedProvider()

    def ensure_collection(self, dense_dim: int) -> None:
        if self.client.collection_exists(self.collection_name):
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                DENSE_VECTOR: models.VectorParams(
                    size=dense_dim,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR: models.SparseVectorParams(),
            },
        )

    def index_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0

        texts = [chunk.embed_text for chunk in chunks]
        dense_vectors = self.embeddings.embed_dense(texts)
        sparse_vectors = self.embeddings.embed_sparse(texts)
        self.ensure_collection(len(dense_vectors[0]))

        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                vector={
                    DENSE_VECTOR: dense,
                    SPARSE_VECTOR: sparse,
                },
                payload=chunk.payload(),
            )
            for chunk, dense, sparse in zip(chunks, dense_vectors, sparse_vectors, strict=True)
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )
        return len(points)

    def index_document(self, markdown: str, *, document_id: str) -> int:
        chunks = chunk_markdown(markdown, document_id=document_id)
        return self.index_chunks(chunks)

    def _document_filter(self, document_id: str | None) -> models.Filter | None:
        if document_id is None:
            return None
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                )
            ]
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 8,
        prefetch_limit: int = 20,
        document_id: str | None = None,
    ) -> list[SearchHit]:
        dense_query = self.embeddings.embed_dense([query])[0]
        sparse_query = self.embeddings.embed_sparse([query])[0]
        query_filter = self._document_filter(document_id)

        if sparse_query.indices:
            result = self.client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    models.Prefetch(
                        query=dense_query,
                        using=DENSE_VECTOR,
                        limit=prefetch_limit,
                        filter=query_filter,
                    ),
                    models.Prefetch(
                        query=sparse_query,
                        using=SPARSE_VECTOR,
                        limit=prefetch_limit,
                        filter=query_filter,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=True,
                query_filter=query_filter,
            )
        else:
            result = self.client.query_points(
                collection_name=self.collection_name,
                query=dense_query,
                using=DENSE_VECTOR,
                limit=limit,
                with_payload=True,
                query_filter=query_filter,
            )

        hits: list[SearchHit] = []
        for point in result.points:
            payload = point.payload or {}
            hits.append(
                SearchHit(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    text=str(payload.get("text", "")),
                    citation=str(payload.get("citation", "")),
                    page=int(payload.get("page", 1)),
                    score=float(point.score),
                    payload=payload,
                )
            )
        return hits


def get_vector_store() -> HybridVectorStore:
    """Build a store from settings: remote Qdrant or local on-disk mode."""
    settings = get_settings()

    if settings.qdrant_url:
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    else:
        Path(settings.qdrant_path).mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=settings.qdrant_path)

    return HybridVectorStore(
        client,
        collection_name=settings.qdrant_collection,
        embeddings=FastEmbedProvider(
            dense_model=settings.dense_embedding_model,
            sparse_model=settings.sparse_embedding_model,
        ),
    )

"""
Vector search for KOFA decision text with hybrid FTS+embedding search.

Combines semantic vector search with PostgreSQL full-text search
for best results on both natural language and legal terminology.
"""

import logging
import math
import os
from dataclasses import dataclass
from functools import lru_cache

from kofa._supabase_utils import _rows, get_shared_client, with_retry

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 1536
DEFAULT_FTS_WEIGHT = 0.3  # Lower than lovdata (0.5) — short paragraphs have noisy FTS rank
TASK_TYPE_QUERY = "RETRIEVAL_QUERY"


@dataclass
class KofaSearchResult:
    """Result from hybrid vector search on KOFA decision text."""

    sak_nr: str
    paragraph_number: int
    section: str
    text: str
    similarity: float
    fts_rank: float
    combined_score: float
    innklaget: str | None
    sakstype: str | None
    avgjoerelse: str | None
    avsluttet: str | None


class KofaVectorSearch:
    """
    Hybrid vector search for KOFA decision text.

    Combines semantic vector search with PostgreSQL FTS for
    best results on both natural language and legal terminology.
    """

    def __init__(self):
        self.supabase = get_shared_client()
        self._genai_client = None

    def _get_genai_client(self):
        """Get or create Gemini API client lazily."""
        if self._genai_client is not None:
            return self._genai_client

        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set for vector search")
        self._genai_client = genai.Client(api_key=api_key)
        return self._genai_client

    @staticmethod
    def _normalize(embedding: list[float]) -> list[float]:
        """Normalize embedding to unit length."""
        norm = math.sqrt(sum(x * x for x in embedding))
        return [x / norm for x in embedding] if norm > 0 else embedding

    @lru_cache(maxsize=1000)
    def _generate_query_embedding(self, query: str) -> tuple[float, ...]:
        """Generate embedding for search query with caching."""
        from google.genai import types

        client = self._get_genai_client()
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query,
            config=types.EmbedContentConfig(
                task_type=TASK_TYPE_QUERY,
                output_dimensionality=EMBEDDING_DIM,
            ),
        )
        embedding = result.embeddings[0]  # type: ignore[index]
        normalized = self._normalize(list(embedding.values))  # type: ignore[arg-type]
        return tuple(normalized)

    @with_retry()
    def search(
        self,
        query: str,
        limit: int = 10,
        section: str | None = None,
        fts_weight: float = DEFAULT_FTS_WEIGHT,
        ivfflat_probes: int = 10,
    ) -> list[KofaSearchResult]:
        """
        Perform hybrid search with optional section filter.

        Falls back to pure FTS if embedding API fails.
        """
        try:
            query_embedding = list(self._generate_query_embedding(query))
        except Exception as e:
            logger.error(f"Embedding API error, falling back to FTS: {e}")
            return self._fallback_fts_search(query, limit, section)

        result = self.supabase.rpc(
            "search_kofa_decision_hybrid",
            {
                "query_text": query,
                "query_embedding": query_embedding,
                "section_filter": section,
                "match_count": limit,
                "fts_weight": fts_weight,
                "ivfflat_probes": ivfflat_probes,
            },
        ).execute()

        if not result.data:
            return []

        return [
            KofaSearchResult(
                sak_nr=row["sak_nr"],
                paragraph_number=row["paragraph_number"],
                section=row["section"],
                text=row["text"],
                similarity=row["similarity"],
                fts_rank=row["fts_rank"],
                combined_score=row["combined_score"],
                innklaget=row.get("innklaget"),
                sakstype=row.get("sakstype"),
                avgjoerelse=row.get("avgjoerelse"),
                avsluttet=row.get("avsluttet"),
            )
            for row in _rows(result.data)
        ]

    def _fallback_fts_search(
        self, query: str, limit: int, section: str | None = None
    ) -> list[KofaSearchResult]:
        """Fallback to pure FTS when embedding API fails."""
        logger.warning(f"Fallback to FTS for query: {query[:50]}...")

        result = self.supabase.rpc(
            "search_kofa_decision_text",
            {
                "search_query": query,
                "section_filter": section,
                "max_results": limit,
            },
        ).execute()

        if not result.data:
            return []

        return [
            KofaSearchResult(
                sak_nr=row["sak_nr"],
                paragraph_number=row["paragraph_number"],
                section=row["section"],
                text=row["text"],
                similarity=0.0,
                fts_rank=row.get("rank", 0.0),
                combined_score=row.get("rank", 0.0),
                innklaget=row.get("innklaget"),
                sakstype=row.get("sakstype"),
                avgjoerelse=row.get("avgjoerelse"),
                avsluttet=row.get("avsluttet"),
            )
            for row in _rows(result.data)
        ]

    def search_fts(
        self, query: str, limit: int = 20, section: str | None = None
    ) -> list[KofaSearchResult]:
        """Pure FTS search on decision text."""
        return self._fallback_fts_search(query, limit, section)

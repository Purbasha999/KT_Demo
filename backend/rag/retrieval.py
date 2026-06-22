import asyncio
import logging

from core.config import settings
from rag.embeddings import embed_query
from rag.sparse_embeddings import embed_sparse_query
from rag.vector_store import search, list_sources_for_firm

logger = logging.getLogger(__name__)


async def retrieve_relevant_chunks(
    query: str,
    firm_id: str,
    allowed_documents: list[str] | None = None,
) -> list[dict]:
    # Empty list means no document access at all — skip Qdrant entirely.
    if allowed_documents is not None and len(allowed_documents) == 0:
        return []

    try:
        if allowed_documents and allowed_documents != ["*"]:
            source_filters = allowed_documents
        else:
            source_filters = None

        dense_vector, sparse_vector = await asyncio.gather(
            embed_query(query),
            embed_sparse_query(query),
        )
        results = await search(
            dense_vector=dense_vector,
            sparse_vector=sparse_vector,
            firm_id=firm_id,
            top_k=settings.RAG_TOP_K,
            source_filters=source_filters,
        )

        chunks = [
            {
                "text":   r.payload.get("text",   ""),
                "source": r.payload.get("source", ""),
                "page":   r.payload.get("page",   0),
                "score":  r.score,
            }
            for r in results
            if r.payload
        ]

        if chunks:
            logger.info("RAG: retrieved %d chunks for firm_id=%s", len(chunks), firm_id)
        else:
            logger.info("RAG: no chunks above threshold for firm_id=%s", firm_id)

        return chunks

    except Exception as exc:
        logger.warning("RAG retrieval failed (firm_id=%s): %s", firm_id, exc)
        return []


async def get_ingested_sources(firm_id: str) -> list[str]:
    try:
        return await list_sources_for_firm(firm_id)
    except Exception as exc:
        logger.warning("Could not list RAG sources (firm_id=%s): %s", firm_id, exc)
        return []

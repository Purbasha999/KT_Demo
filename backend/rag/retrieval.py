import logging

from core.config import settings
from rag.embeddings import embed_query
from rag.vector_store import search, list_sources_for_firm

logger = logging.getLogger(__name__)


async def retrieve_relevant_chunks(
    query: str,
    firm_id: str,
    source_filter: str | None = None,
) -> list[dict]:
    """
    Embed the query, search Qdrant filtered to firm_id, return ranked chunks.
    Returns [] on any error so it never breaks the chat pipeline.
    """
    try:
        query_vector = await embed_query(query)
        results = await search(
            query_vector=query_vector,
            firm_id=firm_id,
            top_k=settings.RAG_TOP_K,
            score_threshold=settings.RAG_SCORE_THRESHOLD,
            source_filter=source_filter,
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

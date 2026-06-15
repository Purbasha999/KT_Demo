import logging
from functools import lru_cache

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
    ScoredPoint,
)
from core.config import settings

logger = logging.getLogger(__name__)


@lru_cache
def get_qdrant_client() -> AsyncQdrantClient:
    logger.info("Creating Qdrant client → %s", settings.QDRANT_URL)
    return AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )


async def ensure_collection() -> None:
    client = get_qdrant_client()
    exists = await client.collection_exists(settings.QDRANT_COLLECTION)

    if exists:
        info = await client.get_collection(settings.QDRANT_COLLECTION)
        current_dims = info.config.params.vectors.size
        if current_dims != settings.EMBEDDING_DIMENSIONS:
            logger.warning(
                "Recreating collection '%s' (dim mismatch: %d → %d).",
                settings.QDRANT_COLLECTION, current_dims, settings.EMBEDDING_DIMENSIONS,
            )
            await client.delete_collection(settings.QDRANT_COLLECTION)
            exists = False
        else:
            logger.info("Collection '%s' OK (dims=%d).", settings.QDRANT_COLLECTION, current_dims)

    if not exists:
        logger.info("Creating collection '%s' (dims=%d, metric=COSINE).",
                    settings.QDRANT_COLLECTION, settings.EMBEDDING_DIMENSIONS)
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
            ),
        )


async def upsert_points(points: list[PointStruct]) -> None:
    client = get_qdrant_client()
    logger.info("Upserting %d points into '%s'", len(points), settings.QDRANT_COLLECTION)
    await client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=points,
        wait=True,
    )


async def search(
    query_vector: list[float],
    firm_id: str,
    top_k: int,
    score_threshold: float,
    source_filter: str | None = None,
) -> list[ScoredPoint]:
    client = get_qdrant_client()

    must_conditions = [
        FieldCondition(key="firm_id", match=MatchValue(value=firm_id))
    ]
    if source_filter:
        must_conditions.append(
            FieldCondition(key="source", match=MatchValue(value=source_filter))
        )

    results = await client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
        query_filter=Filter(must=must_conditions),
        with_payload=True,
    )
    return results.points


async def delete_by_firm_and_source(firm_id: str, source: str) -> None:
    client = get_qdrant_client()
    logger.info("Deleting vectors for firm_id='%s' source='%s'", firm_id, source)
    await client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(key="firm_id", match=MatchValue(value=firm_id)),
                    FieldCondition(key="source",  match=MatchValue(value=source)),
                ]
            )
        ),
    )


async def list_sources_for_firm(firm_id: str) -> list[str]:
    client = get_qdrant_client()
    sources: set[str] = set()
    offset = None
    while True:
        result = await client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="firm_id", match=MatchValue(value=firm_id))]
            ),
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        records, offset = result
        for record in records:
            if record.payload and "source" in record.payload:
                sources.add(record.payload["source"])
        if offset is None:
            break
    return sorted(sources)

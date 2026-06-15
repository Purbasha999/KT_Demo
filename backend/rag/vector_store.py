import logging
from functools import lru_cache

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    SparseVector,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    FilterSelector,
    ScoredPoint,
    Prefetch,
    FusionQuery,
    Fusion,
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
        vectors_cfg = info.config.params.vectors

        if isinstance(vectors_cfg, dict):
            dense_cfg = vectors_cfg.get("dense")
            current_dims = dense_cfg.size if dense_cfg else 0
        else:
            current_dims = vectors_cfg.size if vectors_cfg else 0

        has_sparse = bool(getattr(info.config.params, "sparse_vectors_config", None))

        if current_dims != settings.EMBEDDING_DIMENSIONS or not has_sparse:
            logger.warning(
                "Recreating collection '%s' (dim mismatch or missing sparse index).",
                settings.QDRANT_COLLECTION,
            )
            await client.delete_collection(settings.QDRANT_COLLECTION)
            exists = False
        else:
            logger.info(
                "Collection '%s' OK (dense=%d dims, sparse=BM25).",
                settings.QDRANT_COLLECTION, current_dims,
            )

    if not exists:
        logger.info(
            "Creating collection '%s' (dense=%d dims + BM25 sparse).",
            settings.QDRANT_COLLECTION, settings.EMBEDDING_DIMENSIONS,
        )
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config={
                "dense": VectorParams(
                    size=settings.EMBEDDING_DIMENSIONS,
                    distance=Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=False)
                )
            },
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
    dense_vector: list[float],
    sparse_vector: SparseVector,
    firm_id: str,
    top_k: int,
    source_filters: list[str] | None = None,
) -> list[ScoredPoint]:
    client = get_qdrant_client()

    must_conditions = [
        FieldCondition(key="firm_id", match=MatchValue(value=firm_id))
    ]
    if source_filters:
        must_conditions.append(
            FieldCondition(key="source", match=MatchValue(value=source_filters[0]))
            if len(source_filters) == 1
            else FieldCondition(key="source", match=MatchAny(any=source_filters))
        )

    query_filter = Filter(must=must_conditions)

    results = await client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        prefetch=[
            Prefetch(query=dense_vector,  using="dense",  limit=top_k * 2, filter=query_filter),
            Prefetch(query=sparse_vector, using="sparse", limit=top_k * 2, filter=query_filter),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
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

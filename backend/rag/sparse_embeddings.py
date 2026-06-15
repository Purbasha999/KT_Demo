import asyncio
import logging
from functools import lru_cache

from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

logger = logging.getLogger(__name__)

_MODEL_NAME = "Qdrant/bm25"


@lru_cache
def _get_model() -> SparseTextEmbedding:
    logger.info("Loading BM25 sparse model '%s'…", _MODEL_NAME)
    return SparseTextEmbedding(model_name=_MODEL_NAME)


def _sparse_batch(texts: list[str]) -> list[SparseVector]:
    model = _get_model()
    return [
        SparseVector(indices=r.indices.tolist(), values=r.values.tolist())
        for r in model.embed(texts)
    ]


async def embed_sparse_texts(texts: list[str]) -> list[SparseVector]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sparse_batch, texts)


async def embed_sparse_query(text: str) -> SparseVector:
    results = await embed_sparse_texts([text])
    return results[0]

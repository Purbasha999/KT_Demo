import asyncio
import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer
from core.config import settings

logger = logging.getLogger(__name__)

_BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@lru_cache
def _get_model() -> SentenceTransformer:
    logger.info("Loading embedding model '%s'…", settings.EMBEDDING_MODEL)
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    logger.info("Embedding model loaded.")
    return model


def _is_bge(model_name: str) -> bool:
    return "bge" in model_name.lower()


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Encode document chunks — no query instruction prefix."""
    model = _get_model()
    loop = asyncio.get_event_loop()
    vectors = await loop.run_in_executor(
        None,
        lambda: model.encode(texts, normalize_embeddings=True).tolist(),
    )
    return vectors


async def embed_query(text: str) -> list[float]:
    """Encode a search query — prepends BGE instruction when using a BGE model."""
    if _is_bge(settings.EMBEDDING_MODEL):
        text = _BGE_QUERY_INSTRUCTION + text
    vectors = await embed_texts([text])
    return vectors[0]

import httpx
import logging

from core.config import settings

logger = logging.getLogger(__name__)

_HEADERS = {
    "Content-Type":  "application/json",
    "Authorization": f"Token {settings.EMBEDDING_API_TOKEN}",
}

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)


async def _embed_one(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            settings.EMBEDDING_API_URL,
            json={"text": text, "model": settings.EMBEDDING_MODEL},
            headers=_HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("embedding") or data.get("data", [data])[0].get("embedding", [])
    raise ValueError(f"Unexpected embedding response format: {type(data)}")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    results = []
    for text in texts:
        results.append(await _embed_one(text))
    return results


async def embed_query(text: str) -> list[float]:
    return await _embed_one(text)


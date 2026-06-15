from qdrant_client.models import PointStruct

from rag.pdf_parser import chunk_pdf, Chunk
from rag.embeddings import embed_texts
from rag.vector_store import ensure_collection, upsert_points, delete_by_firm_and_source

_EMBED_BATCH_SIZE = 64


async def _embed_in_batches(chunks: list[Chunk]) -> list[list[float]]:
    texts = [c.text for c in chunks]
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        vectors = await embed_texts(batch)
        all_vectors.extend(vectors)
    return all_vectors


async def ingest_pdf(
    file_bytes: bytes,
    filename: str,
    firm_id: str,
    replace: bool = True,
) -> dict:
    """
    Full ingestion pipeline for a single PDF.
    Returns summary dict: {source, chunks_ingested, status}.
    """
    await ensure_collection()

    chunk_pairs = chunk_pdf(file_bytes, source_name=filename, firm_id=firm_id)
    if not chunk_pairs:
        return {"source": filename, "chunks_ingested": 0, "status": "no_text_extracted"}

    if replace:
        await delete_by_firm_and_source(firm_id, filename)

    chunks    = [c for c, _ in chunk_pairs]
    chunk_ids = [cid for _, cid in chunk_pairs]
    vectors   = await _embed_in_batches(chunks)

    points = [
        PointStruct(
            id=chunk_id,
            vector=vector,
            payload={**chunk.metadata, "text": chunk.text},
        )
        for chunk, chunk_id, vector in zip(chunks, chunk_ids, vectors)
    ]

    await upsert_points(points)

    return {
        "source":          filename,
        "chunks_ingested": len(points),
        "status":          "success",
    }

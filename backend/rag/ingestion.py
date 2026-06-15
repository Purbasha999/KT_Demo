from qdrant_client.models import PointStruct

from rag.pdf_parser import chunk_pdf, Chunk
from rag.embeddings import embed_texts
from rag.sparse_embeddings import embed_sparse_texts
from rag.vector_store import ensure_collection, upsert_points, delete_by_firm_and_source

_EMBED_BATCH_SIZE = 64

async def _dense_in_batches(chunks: list[Chunk]) -> list[list[float]]:
    texts = [c.text for c in chunks]
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        all_vectors.extend(await embed_texts(texts[i : i + _EMBED_BATCH_SIZE]))
    return all_vectors


async def ingest_pdf(
    file_bytes: bytes,
    filename: str,
    firm_id: str,
    replace: bool = True,
) -> dict:
    await ensure_collection()

    chunk_pairs = chunk_pdf(file_bytes, source_name=filename, firm_id=firm_id)
    if not chunk_pairs:
        return {"source": filename, "chunks_ingested": 0, "status": "no_text_extracted"}

    if replace:
        await delete_by_firm_and_source(firm_id, filename)

    chunks    = [c for c, _ in chunk_pairs]
    chunk_ids = [cid for _, cid in chunk_pairs]

    dense_vecs  = await _dense_in_batches(chunks)
    sparse_vecs = await embed_sparse_texts([c.text for c in chunks])

    points = [
        PointStruct(
            id=chunk_id,
            vector={
                "dense":  dense_vec,
                "sparse": sparse_vec,
            },
            payload={**chunk.metadata, "text": chunk.text},
        )
        for chunk, chunk_id, dense_vec, sparse_vec in zip(chunks, chunk_ids, dense_vecs, sparse_vecs)
    ]

    await upsert_points(points)

    return {
        "source":          filename,
        "chunks_ingested": len(points),
        "status":          "success",
    }

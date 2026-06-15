import hashlib
import io
import uuid
from dataclasses import dataclass, field

from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.config import settings


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


def _make_chunk_id(firm_id: str, text: str) -> str:
    """Deterministic UUID scoped to firm so same text across firms doesn't collide."""
    content = f"{firm_id}:{text}"
    digest = hashlib.sha256(content.encode()).digest()[:16]
    return str(uuid.UUID(bytes=digest))


def _extract_text_from_pdf(file_bytes: bytes) -> list[tuple[int, str]]:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((i, text))
    return pages


def chunk_pdf(file_bytes: bytes, source_name: str, firm_id: str) -> list[tuple[Chunk, str]]:
    """
    Parse and chunk a PDF.
    Returns list of (Chunk, chunk_id) tuples.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    result: list[tuple[Chunk, str]] = []
    pages = _extract_text_from_pdf(file_bytes)

    for page_num, page_text in pages:
        splits = splitter.split_text(page_text)
        for split_index, text in enumerate(splits):
            chunk = Chunk(
                text=text,
                metadata={
                    "source":      source_name,
                    "page":        page_num,
                    "split_index": split_index,
                    "firm_id":     firm_id,
                },
            )
            chunk_id = _make_chunk_id(firm_id, text)
            result.append((chunk, chunk_id))

    return result

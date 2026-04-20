"""Document loading and chunking for RAG."""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import CSVLoader, PyPDFLoader, TextLoader

from asimplex.rag.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_RAW_DOCS_DIR

SUPPORTED_SUFFIXES = {".md", ".txt", ".csv", ".pdf"}


def _load_single_document(path: Path) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        loader = PyPDFLoader(str(path))
        return loader.load()
    if suffix == ".csv":
        loader = CSVLoader(str(path), encoding="utf-8")
        return loader.load()
    loader = TextLoader(str(path), encoding="utf-8")
    return loader.load()


def load_documents(raw_docs_dir: Path | None = None) -> list[Document]:
    root = (raw_docs_dir or RAG_RAW_DOCS_DIR).resolve()
    if not root.exists():
        return []
    docs: list[Document] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        loaded = _load_single_document(path)
        for d in loaded:
            d.metadata = {
                **(d.metadata or {}),
                "source_path": str(path),
                "doc_type": path.suffix.lower().lstrip("."),
                "source_name": path.name,
            }
        docs.extend(loaded)
    return docs


def chunk_documents(
    docs: list[Document],
    *,
    chunk_size: int = RAG_CHUNK_SIZE,
    chunk_overlap: int = RAG_CHUNK_OVERLAP,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    for idx, chunk in enumerate(chunks):
        chunk.metadata = {**(chunk.metadata or {}), "chunk_id": idx}
    return chunks

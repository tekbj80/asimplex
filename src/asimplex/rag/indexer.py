"""Build and refresh the local Chroma index for RAG."""

from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

from asimplex.rag.config import (
    RAG_CHROMA_DIR,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_COLLECTION_NAME,
)
from asimplex.rag.loader import chunk_documents, load_documents


def build_rag_index(
    *,
    raw_docs_dir: Path | None = None,
    chroma_dir: Path | None = None,
    collection_name: str = RAG_COLLECTION_NAME,
    chunk_size: int = RAG_CHUNK_SIZE,
    chunk_overlap: int = RAG_CHUNK_OVERLAP,
) -> dict[str, int]:
    docs = load_documents(raw_docs_dir=raw_docs_dir)
    chunks = chunk_documents(
        docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    target_dir = (chroma_dir or RAG_CHROMA_DIR).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(target_dir),
    )
    try:
        vector_store.delete_collection()
    except Exception:
        pass
    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(target_dir),
    )
    if chunks:
        vector_store.add_documents(chunks)
    vector_store.persist()
    return {"documents": len(docs), "chunks": len(chunks)}

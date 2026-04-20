"""Configuration for the local RAG index."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

RAG_RAW_DOCS_DIR = Path(
    os.getenv("ASIMPLEX_RAG_RAW_DOCS_DIR", str(PROJECT_ROOT / "knowledge_base" / "raw"))
).resolve()
RAG_CHROMA_DIR = Path(
    os.getenv("ASIMPLEX_RAG_CHROMA_DIR", str(PROJECT_ROOT / ".asimplex_rag_chroma"))
).resolve()
RAG_COLLECTION_NAME = os.getenv("ASIMPLEX_RAG_COLLECTION_NAME", "strategy")
RAG_COLLECTION_CONCEPTS = os.getenv("ASIMPLEX_RAG_COLLECTION_CONCEPTS", "asimplex_concepts")
RAG_COLLECTION_OPERATIONAL = os.getenv("ASIMPLEX_RAG_COLLECTION_OPERATIONAL", "asimplex_operational")

RAG_CHUNK_SIZE = int(os.getenv("ASIMPLEX_RAG_CHUNK_SIZE", "1000"))
RAG_CHUNK_OVERLAP = int(os.getenv("ASIMPLEX_RAG_CHUNK_OVERLAP", "150"))
RAG_TOP_K = int(os.getenv("ASIMPLEX_RAG_TOP_K", "4"))

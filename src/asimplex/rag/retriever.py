"""Context retrieval for chat prompts using local Chroma index."""

from __future__ import annotations

from typing import Any

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

from asimplex.rag.config import (
    RAG_CHROMA_DIR,
    RAG_COLLECTION_CONCEPTS,
    RAG_COLLECTION_NAME,
    RAG_COLLECTION_OPERATIONAL,
    RAG_TOP_K,
)


def _query_variants(query: str) -> list[str]:
    base = str(query or "").strip()
    if not base:
        return []
    variants = [base]
    ql = base.lower()
    if "evo" in ql:
        variants.append(base.replace("EVO", "evolutionary optimization").replace("evo", "evolutionary optimization"))
    if "peak" in ql:
        variants.append(base.replace("peak load", "peak demand").replace("peak", "maximum demand"))
    # de-duplicate while preserving order
    deduped: list[str] = []
    for item in variants:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _route_collection_names(user_query: str) -> list[str]:
    query = str(user_query or "").lower()
    concept_keywords = {
        "evo", "peak", "peak shaving", "strategy", "explain", "concept", "theory", "clarify",
        "tell", ""
        }
    operational_keywords = {
        "tariff",
        "price",
        "cost",
        "eur",
        "simulation",
        "grid limit",
        "threshold",
        "parameter",
        "battery",
    }
    concepts_match = any(k in query for k in concept_keywords)
    operational_match = any(k in query for k in operational_keywords)

    if concepts_match and not operational_match:
        return [RAG_COLLECTION_CONCEPTS]
    if operational_match and not concepts_match:
        return [RAG_COLLECTION_OPERATIONAL]
    # ambiguous or mixed query -> search both curated collections first
    return [RAG_COLLECTION_CONCEPTS, RAG_COLLECTION_OPERATIONAL, RAG_COLLECTION_NAME]


def retrieve_rag_context(user_query: str, *, top_k: int = RAG_TOP_K) -> list[dict[str, Any]]:
    if not RAG_CHROMA_DIR.exists():
        return []
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    hits: list[dict[str, Any]] = []
    seen = set()
    candidate_collections: list[str] = []
    for name in _route_collection_names(user_query):
        if name and name not in candidate_collections:
            candidate_collections.append(name)

    for collection_name in candidate_collections:
        try:
            vector_store = Chroma(
                collection_name=collection_name,
                embedding_function=embeddings,
                persist_directory=str(RAG_CHROMA_DIR),
            )
            for query in _query_variants(user_query):
                results = vector_store.similarity_search_with_relevance_scores(query=query, k=top_k)
                for doc, score in results:
                    key = (str(doc.metadata.get("source_path", "")), int(doc.metadata.get("chunk_id", -1)))
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append(
                        {
                            "score": float(score),
                            "collection_name": collection_name,
                            "source_name": str(doc.metadata.get("source_name", "")),
                            "source_path": str(doc.metadata.get("source_path", "")),
                            "doc_type": str(doc.metadata.get("doc_type", "")),
                            "chunk_id": int(doc.metadata.get("chunk_id", -1)),
                            "content": doc.page_content,
                        }
                    )
        except Exception:
            continue
    hits.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return hits[:top_k]

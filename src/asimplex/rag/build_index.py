"""CLI helper to build local RAG index from knowledge_base/raw."""

from __future__ import annotations

from asimplex.rag.indexer import build_rag_index


def main() -> None:
    stats = build_rag_index()
    print(f"Indexed {stats['documents']} documents into {stats['chunks']} chunks.")


if __name__ == "__main__":
    main()

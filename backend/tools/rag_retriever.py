"""
RAG retriever sobre los guidelines de apetito y pricing indexados en ChromaDB.
"""

from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

INDEX_DIR       = Path(__file__).parent.parent / "kb" / "index"
COLLECTION_NAME = "chubb_uw_guidelines"

_client     = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(INDEX_DIR))
        _collection = _client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=DefaultEmbeddingFunction(),
        )
    return _collection


def retrieve(query: str, n_results: int = 4, source_filter: str = None) -> list[dict]:
    """
    Recupera los chunks más relevantes para la query.
    source_filter: 'appetite_guidelines_property_casualty' | 'pricing_guidelines_property_casualty' | None
    Devuelve lista de {text, source, section_title, distance}.
    """
    collection = _get_collection()
    where = {"source": source_filter} if source_filter else None

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "source": meta.get("source", ""),
            "section_title": meta.get("section_title", ""),
            "distance": round(dist, 4),
        })
    return chunks


def format_context(chunks: list[dict]) -> str:
    """Formatea los chunks recuperados para insertar en el prompt."""
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[Fragmento {i} — {c['section_title']}]\n{c['text']}")
    return "\n\n---\n\n".join(parts)

# 04 — Tools y RAG

`backend/tools/` contiene una única herramienta: `rag_retriever.py`. No hay `pdf_parser`,
`field_extractor`, `appetite_checker`, `risk_scorer` ni `pricing_tool` como archivos
separados (aunque ARCHITECTURE.md los lista en el "catálogo de herramientas Fase 3+"). En la
práctica esas funciones están embebidas en los propios nodos vía LLM, y el pricing es un stub
dentro de `risk_node.py`.

---

## `backend/tools/rag_retriever.py` — 63 líneas

```python
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
```

> Nota técnica: usa `DefaultEmbeddingFunction()` de ChromaDB (all-MiniLM-L6-v2, local, sin
> coste de API). **No** usa `text-embedding-3-small` de OpenAI como sugiere ARCHITECTURE.md.
> El embedding es 100% local; solo el LLM de generación va contra Azure.

---

## `scripts/index_kb.py` — 94 líneas

```python
"""
Indexa los documentos RAG de backend/kb/raw/ en ChromaDB (backend/kb/index/).
Ejecutar desde la raíz una vez, o cuando cambien los documentos fuente:
  python scripts/index_kb.py
"""

import sys, os, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from pathlib import Path

RAW_DIR   = Path("backend/kb/raw")
INDEX_DIR = Path("backend/kb/index")
COLLECTION_NAME = "chubb_uw_guidelines"


def chunk_markdown(text: str, source: str) -> list[dict]:
    """
    Divide el documento por secciones (###). Cada chunk incluye:
    - el título de la sección como contexto
    - el cuerpo de la sección
    - metadatos: source, section_title, section_level
    """
    chunks = []
    # Dividir por encabezados ## o ###
    pattern = re.compile(r'^(#{2,3})\s+(.+)$', re.MULTILINE)
    matches = list(pattern.finditer(text))

    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        if len(body) < 50:  # ignorar secciones vacías o muy cortas
            continue

        chunks.append({
            "id": f"{source}::{i}::{title[:40]}",
            "text": f"## {title}\n\n{body}",
            "metadata": {
                "source": source,
                "section_title": title,
                "section_level": level,
            }
        })
    return chunks


def build_index():
    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    ef = DefaultEmbeddingFunction()

    # Recrear la colección limpia
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Colección existente eliminada.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    total_chunks = 0
    for md_file in RAW_DIR.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_markdown(text, md_file.stem)
        if not chunks:
            print(f"  {md_file.name}: sin chunks")
            continue

        collection.add(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )
        total_chunks += len(chunks)
        print(f"  {md_file.name}: {len(chunks)} chunks indexados")

    print(f"\nÍndice creado en {INDEX_DIR}")
    print(f"Total chunks: {total_chunks}")
    print(f"Colección: '{COLLECTION_NAME}'")
    return collection


if __name__ == "__main__":
    build_index()
```

---

## Estructura de `backend/kb/` (solo listado, sin contenido)

```
backend/kb/
├── raw/
│   ├── appetite_guidelines_property_casualty.md   (11.600 bytes, 154 líneas)  — fuente RAG apetito
│   └── pricing_guidelines_property_casualty.md    ( 7.972 bytes, 110 líneas)  — fuente RAG pricing
├── processed/                                       [VACÍA — index_kb.py indexa directo desde raw/]
└── index/                                           [ChromaDB PersistentClient]
    ├── chroma.sqlite3                              (483.328 bytes)
    └── 1ecc79ce-8e9f-40b6-802a-b81f5fd66285/        [colección "chubb_uw_guidelines", HNSW cosine]
        ├── data_level0.bin                         (167.600 bytes)
        ├── header.bin                              (100 bytes)
        ├── length.bin                              (400 bytes)
        └── link_lists.bin                          (0 bytes)
```

- Colección: `chubb_uw_guidelines`, distancia coseno, embeddings all-MiniLM-L6-v2 locales.
- Según SESSION_LOG, la indexación produjo **26 chunks** en total.
- Los mismos dos `.md` de guidelines están **duplicados** en `data/base/` (mismo tamaño).

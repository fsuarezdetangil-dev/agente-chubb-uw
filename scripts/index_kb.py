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

"""
Build a local Chroma vector store from the schema catalog, using a local
sentence-transformers embedding model (no external API needed for this part
-- only the SQL-generation/answer step will call the Anthropic API).

Usage:
    python llm_rag/src/build_vector_store.py
"""

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_PATH = PROJECT_ROOT / "llm_rag" / "schema_catalog.json"
CHROMA_DIR = PROJECT_ROOT / "llm_rag" / "chroma_db"
COLLECTION_NAME = "schema_catalog"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # small, fast, runs fine on CPU


def main() -> None:
    catalog = json.loads(CATALOG_PATH.read_text())

    print(f"Loading embedding model '{EMBEDDING_MODEL}' ...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # Fresh start each time this script runs, so re-running after schema
    # changes doesn't leave stale entries behind.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME)

    texts = [table["text_chunk"] for table in catalog]
    embeddings = model.encode(texts).tolist()

    collection.add(
        ids=[table["table_name"] for table in catalog],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {"schema": table["schema"], "table_name": table["table_name"]}
            for table in catalog
        ],
    )

    print(f"Indexed {len(catalog)} tables into Chroma at {CHROMA_DIR}")


if __name__ == "__main__":
    main()
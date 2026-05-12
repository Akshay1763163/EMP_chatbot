import chromadb
from sentence_transformers import SentenceTransformer

from .DB_schema import SCHEMAS

client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection(name="schema_store")
embedder = SentenceTransformer("all-MiniLM-L6-v2")


def build_schema_store():
    """Embed all schemas into ChromaDB."""
    for table_name, schema_text in SCHEMAS.items():
        embedding = embedder.encode([schema_text]).tolist()
        collection.upsert(
            ids=[f"{table_name}_schema"],
            documents=[schema_text],
            embeddings=embedding,
        )
    print(f"Embedded {len(SCHEMAS)} schema(s) into ChromaDB.")


def get_relevant_schema(question: str) -> str:
    """Find the most relevant schema for the user's question."""
    question_embedding = embedder.encode([question]).tolist()
    results = collection.query(
        query_embeddings=question_embedding,
        n_results=1,
    )
    docs = results.get("documents", [[]])
    return docs[0][0] if docs and docs[0] else ""

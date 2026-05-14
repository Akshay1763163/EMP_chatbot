import chromadb
from sentence_transformers import SentenceTransformer

from .db import get_connection

client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection(name="schema_store")
embedder = SentenceTransformer("all-MiniLM-L6-v2")


def build_schema_store():
    """Pull live schema from INFORMATION_SCHEMA and embed into ChromaDB."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE
            FROM INFORMATION_SCHEMA.TABLES t
            JOIN INFORMATION_SCHEMA.COLUMNS c
                ON t.TABLE_NAME = c.TABLE_NAME
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
            """
        )
        rows = cursor.fetchall()

    # Group columns by table
    tables = {}
    for row in rows:
        if row.TABLE_NAME not in tables:
            tables[row.TABLE_NAME] = []
        nullable = "nullable" if row.IS_NULLABLE == "YES" else "not null"
        tables[row.TABLE_NAME].append(
            f"{row.COLUMN_NAME} ({row.DATA_TYPE}, {nullable})"
        )

    # Upsert each table as one document
    for table_name, columns in tables.items():
        schema_text = f"Table: {table_name}\nColumns: {', '.join(columns)}"
        embedding = embedder.encode([schema_text]).tolist()
        collection.upsert(
            ids=[f"{table_name}_schema"],
            documents=[schema_text],
            embeddings=embedding,
        )

    # Remove tables that no longer exist in the DB
    stored = collection.get()["ids"]
    live_ids = {f"{t}_schema" for t in tables}
    stale = [i for i in stored if i not in live_ids]
    if stale:
        collection.delete(ids=stale)

    print(f"ChromaDB synced: {len(tables)} table(s), {len(stale)} removed.")
    return {"synced": len(tables), "deleted": len(stale)}


def get_relevant_schema(question: str) -> str:
    """Find the most relevant schema for the user's question."""
    question_embedding = embedder.encode([question]).tolist()
    results = collection.query(
        query_embeddings=question_embedding,
        n_results=3,  # get top 3 tables, not just 1
    )
    docs = results.get("documents", [[]])
    # Join all relevant tables into one context block
    return "\n\n".join(docs[0]) if docs and docs[0] else ""

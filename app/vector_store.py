import chromadb
import json
from sentence_transformers import SentenceTransformer

from .db import get_connection

client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection(name="schema_store")
embedder = SentenceTransformer("all-MiniLM-L6-v2")


def fetch_rich_schema():
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. All columns with type info
        cursor.execute(
            """
            SELECT
                c.TABLE_NAME,
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.IS_NULLABLE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.NUMERIC_PRECISION
            FROM INFORMATION_SCHEMA.COLUMNS c
            JOIN INFORMATION_SCHEMA.TABLES t
                ON c.TABLE_NAME = t.TABLE_NAME
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION
            """
        )
        columns = cursor.fetchall()

        # 2. Primary keys
        cursor.execute(
            """
            SELECT
                tc.TABLE_NAME,
                kcu.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            """
        )
        primary_keys = {}
        for row in cursor.fetchall():
            primary_keys.setdefault(row.TABLE_NAME, []).append(row.COLUMN_NAME)

        # 3. Foreign keys and relationships
        cursor.execute(
            """
            SELECT
                fk.TABLE_NAME AS from_table,
                fk_col.COLUMN_NAME AS from_column,
                pk.TABLE_NAME AS to_table,
                pk_col.COLUMN_NAME AS to_column
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS fk
                ON rc.CONSTRAINT_NAME = fk.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS pk
                ON rc.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE fk_col
                ON rc.CONSTRAINT_NAME = fk_col.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pk_col
                ON rc.UNIQUE_CONSTRAINT_NAME = pk_col.CONSTRAINT_NAME
            """
        )
        relationships = {}
        for row in cursor.fetchall():
            relationships.setdefault(row.from_table, []).append(
                {
                    "foreign_key": row.from_column,
                    "references_table": row.to_table,
                    "references_column": row.to_column,
                }
            )

    return columns, primary_keys, relationships


def build_schema_store():
    columns, primary_keys, relationships = fetch_rich_schema()

    # Group columns by table
    tables = {}
    for row in columns:
        if row.TABLE_NAME not in tables:
            tables[row.TABLE_NAME] = []
        tables[row.TABLE_NAME].append(
            {
                "name": row.COLUMN_NAME,
                "type": row.DATA_TYPE,
                "nullable": row.IS_NULLABLE == "YES",
                "primary_key": row.COLUMN_NAME
                in primary_keys.get(row.TABLE_NAME, []),
            }
        )

    # Build rich document per table
    ids, documents, metadatas = [], [], []

    for table_name, cols in tables.items():
        # Build structured schema text for the LLM
        col_lines = []
        for col in cols:
            pk = " [PRIMARY KEY]" if col["primary_key"] else ""
            nullable = " nullable" if col["nullable"] else ""
            col_lines.append(f"  - {col['name']} ({col['type']}{nullable}){pk}")

        rel_lines = []
        for rel in relationships.get(table_name, []):
            rel_lines.append(
                f"  - {table_name}.{rel['foreign_key']} -> "
                f"{rel['references_table']}.{rel['references_column']}"
            )

        # This is what gets embedded and sent to the LLM as context
        schema_text = f"Table: {table_name}\nColumns:\n" + "\n".join(col_lines)
        if rel_lines:
            schema_text += "\nRelationships:\n" + "\n".join(rel_lines)

        # Store full metadata as JSON for debugging / future use
        metadata = {
            "table": table_name,
            "schema_json": json.dumps(
                {
                    "table": table_name,
                    "columns": cols,
                    "relationships": relationships.get(table_name, []),
                }
            ),
        }

        ids.append(f"{table_name}_schema")
        documents.append(schema_text)
        metadatas.append(metadata)

    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    # Remove stale tables
    stored = collection.get()["ids"]
    live_ids = set(ids)
    stale = [i for i in stored if i not in live_ids]
    if stale:
        collection.delete(ids=stale)

    print(f"ChromaDB synced: {len(tables)} table(s), {len(stale)} removed.")
    return {"synced": len(tables), "deleted": len(stale)}


def get_relevant_schema(question: str) -> str:
    question_embedding = embedder.encode([question]).tolist()
    results = collection.query(
        query_embeddings=question_embedding,
        n_results=3,
    )
    docs = results.get("documents", [[]])
    return "\n\n".join(docs[0]) if docs and docs[0] else ""

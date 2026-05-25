import asyncio
import logging
from .db import get_connection
from .vector_store import build_schema_store

logger = logging.getLogger(__name__)

async def poll_schema_changes(interval_seconds: int = 60):
    """
    Background worker that polls SchemaChangeLog every `interval_seconds`.
    When unprocessed changes are found, re-syncs ChromaDB and marks them done.
    """
    logger.info("Schema sync worker started.")

    while True:
        try:
            await _check_and_sync()
        except Exception as e:
            logger.error(f"Schema sync worker error: {e}")

        await asyncio.sleep(interval_seconds)


async def _check_and_sync():
    with get_connection() as conn:
        cursor = conn.cursor()

        # Find unprocessed schema changes
        cursor.execute("""
            SELECT id, event_type, table_name
            FROM dbo.SchemaChangeLog
            WHERE processed = 0
            ORDER BY changed_at ASC
        """)
        changes = cursor.fetchall()

        if not changes:
            return  # nothing to do

        logger.info(f"Found {len(changes)} schema change(s). Syncing ChromaDB...")

        # Re-sync ChromaDB with the latest schema
        result = build_schema_store()
        logger.info(f"ChromaDB synced: {result['synced']} tables, {result['deleted']} removed.")

        # Mark all as processed
        ids = [str(row.id) for row in changes]
        cursor.execute(
            f"UPDATE dbo.SchemaChangeLog SET processed = 1 WHERE id IN ({','.join(ids)})"
        )
        conn.commit()

        for row in changes:
            logger.info(f"  Processed: {row.event_type} on '{row.table_name}'")
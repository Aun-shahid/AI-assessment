"""Async MongoDB connection and collection accessors."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING
from pymongo.operations import SearchIndexModel

from src.config import settings

# ---------------------------------------------------------------------------
# Client & database
# ---------------------------------------------------------------------------
client: AsyncIOMotorClient = AsyncIOMotorClient(settings.DATABASE_URI)
db: AsyncIOMotorDatabase = client[settings.DATABASE_NAME]

# ---------------------------------------------------------------------------
# Collection accessors
# ---------------------------------------------------------------------------
domains_col = db["domains"]
subdomains_col = db["subdomains"]
learning_outcomes_col = db["learning_outcomes"]
textbook_chunks_col = db["textbook_chunks"]
sessions_col = db["sessions"]
rag_metrics_col = db["rag_metrics"]


# ---------------------------------------------------------------------------
# Index creation
# ---------------------------------------------------------------------------
async def create_indexes() -> None:
    """Create required indexes (idempotent)."""
    await learning_outcomes_col.create_index([("code", ASCENDING)], unique=True)
    await textbook_chunks_col.create_index([("chunk_id", ASCENDING)], unique=True)
    await sessions_col.create_index([("session_id", ASCENDING)], unique=True)


async def ensure_vector_search_index() -> None:
    """
    Create an Atlas Vector Search index on textbook_chunks.embedding.

    This requires MongoDB Atlas (M10+ cluster) with Atlas Search enabled.
    If running locally or on a non-Atlas deployment, this will be skipped
    gracefully — you would need to create the index via the Atlas UI:

        Index name : "vector_index"
        Field      : embedding
        Type       : vector
        Dimensions : 1536
        Similarity : cosine
    """
    try:
        existing = await textbook_chunks_col.list_search_indexes().to_list()
        if any(idx.get("name") == "vector_index_3k" for idx in existing):
            return

        search_index = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": settings.EMBEDDING_DIMENSIONS,
                        "similarity": "cosine",
                    },
                    {
                        "type": "filter",
                        "path": "associated_lo_codes",
                    },
                ]
            },
            name="vector_index_3k",
            type="vectorSearch",
        )
        await textbook_chunks_col.create_search_index(model=search_index)
        print("[db] Atlas Vector Search index 'vector_index_3k' created.")
    except Exception as exc:
        print(
            f"[db] Could not auto-create vector search index "
            f"(create it manually in Atlas UI): {exc}"
        )

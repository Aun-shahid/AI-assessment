"""MongoDB Atlas Vector Search over textbook chunks."""

from src.database import textbook_chunks_col
from src.services.embedding import embed_text


async def search_chunks(query: str, top_k: int = 5) -> list[dict]:
    """
    Embed *query* and run a ``$vectorSearch`` aggregation against
    the ``textbook_chunks`` collection.

    Returns the top-*k* matching chunk documents (without the embedding
    field to keep payloads small).
    """
    query_vector = await embed_text(query)

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": top_k * 10,
                "limit": top_k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "chunk_id": 1,
                "content": 1,
                "page_start": 1,
                "page_end": 1,
                "associated_lo_codes": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    results: list[dict] = []
    async for doc in textbook_chunks_col.aggregate(pipeline):
        results.append(doc)
    return results


async def search_chunks_by_los(
    lo_descriptions: list[str], top_k: int = 10
) -> list[dict]:
    """
    Combine several LO descriptions into one search query and return
    the most relevant textbook chunks.
    """
    combined = " ".join(lo_descriptions)
    # Truncate to ~6000 chars to stay within embedding token limits.
    if len(combined) > 6000:
        combined = combined[:6000]
    return await search_chunks(combined, top_k=top_k)

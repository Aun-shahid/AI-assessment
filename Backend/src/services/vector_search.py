"""MongoDB Atlas Vector Search over textbook chunks.

Provides multiple search strategies:
- ``search_chunks``: basic vector search with a raw query string
- ``search_chunks_filtered``: vector search with metadata pre-filter
- ``search_chunks_by_lo_codes``: metadata-first lookup by LO code tags
- ``search_chunks_per_lo``: per-LO targeted vector search (code + name)
- ``search_chunks_by_los``: per-LO description search (improved)
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from src.database import (
    textbook_chunks_col,
)
from src.database import learning_outcomes_col, rag_metrics_col
from src.services.embedding import embed_text
from src.config import settings

logger = logging.getLogger(__name__)

# Configurable RAG params (can be set in `settings`)
RAG_TOP_K = getattr(settings, "RAG_TOP_K", 10)
RAG_SIMILARITY_THRESHOLD = getattr(settings, "RAG_SIMILARITY_THRESHOLD", 0.65)


async def log_rag_metric(method: str, lo_codes: List[str], result_count: int, extra: dict | None = None):
    try:
        await rag_metrics_col.insert_one(
            {
                "ts": datetime.utcnow().isoformat(),
                "method": method,
                "lo_codes": lo_codes,
                "result_count": result_count,
                "extra": extra or {},
            }
        )
    except Exception:
        logger.exception("Failed to write RAG metric")


async def search_relevant_chunks(
    lo_codes: List[str], subdomain_code: Optional[str] = None, top_k: Optional[int] = None
) -> list[dict]:
    """
    Safe retrieval wrapper used by the agent.

    Strategy:
    1) Metadata-first: query `associated_lo_codes` (fast, high-precision).
    2) If no metadata hits, perform per-LO semantic search using LO
       descriptions (embed LO description/name only — never raw user text).

    Logs which method was used into `rag_metrics` collection.
    """
    limit = top_k or RAG_TOP_K
    logger.info(
        "[tool] vector_search.search_relevant_chunks lo_codes=%s subdomain=%s top_k=%s",
        lo_codes,
        subdomain_code,
        limit,
    )

    # 1) Metadata lookup
    meta_query: dict = {"associated_lo_codes": {"$in": lo_codes}}
    if subdomain_code:
        meta_query["subdomain_code"] = subdomain_code
    meta_cursor = textbook_chunks_col.find(meta_query).sort([("page_start", 1)])
    meta_results = await meta_cursor.to_list(length=limit)
    if meta_results:
        logger.info("[tool] vector_search.metadata_hit count=%s", len(meta_results))
        await log_rag_metric("metadata", lo_codes, len(meta_results))
        return meta_results[:limit]

    # 2) Fallback: per-LO semantic search
    async def _search_one(lo_code: str):
        lo_doc = await learning_outcomes_col.find_one({"code": lo_code}, projection={"name": 1, "description": 1})
        short_query = lo_code
        if lo_doc:
            # Include description for richer semantic signal
            name = lo_doc.get('name', '')
            desc = lo_doc.get('description', '')
            short_query = f"{name} {desc[:300]}".strip() or lo_code
        # embed LO metadata only
        vec = await embed_text(short_query, source="lo_description")
        # reuse existing vector pipeline via search_chunks (which will embed again if passed a string),
        # so call lower-level aggregation directly to avoid double-embedding
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index_3k",
                    "path": "embedding",
                    "queryVector": vec,
                    "numCandidates": limit * 10,
                    "limit": limit,
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

    tasks = [_search_one(code) for code in lo_codes]
    per_lo_results = await asyncio.gather(*tasks, return_exceptions=True)

    # flatten + dedupe, apply minimum score threshold
    min_score = RAG_SIMILARITY_THRESHOLD
    seen = set()
    flat = []
    for res in per_lo_results:
        if isinstance(res, Exception):
            logger.exception("Vector search task failed for one LO")
            continue
        if not isinstance(res, list):
            continue
        for c in res:
            cid = c.get("chunk_id") or c.get("_id")
            score = c.get("score", 0)
            if score < min_score:
                continue
            if cid and cid not in seen:
                seen.add(cid)
                flat.append(c)
            if len(flat) >= limit:
                break
        if len(flat) >= limit:
            break

    await log_rag_metric("vector_fallback", lo_codes, len(flat))
    return flat[:limit]



# ---------------------------------------------------------------------------
# Core vector search
# ---------------------------------------------------------------------------

async def search_chunks(query: str, top_k: int = 5) -> list[dict]:
    """
    Embed *query* and run a ``$vectorSearch`` aggregation against
    the ``textbook_chunks`` collection.

    Returns the top-*k* matching chunk documents (without the embedding
    field to keep payloads small).
    """
    logger.info("[tool] vector_search.search_chunks query=%s top_k=%s", query[:120], top_k)
    query_vector = await embed_text(query)

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index_3k",
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


async def search_chunks_filtered(
    query: str, lo_codes: list[str], top_k: int = 5
) -> list[dict]:
    """
    Vector search with a metadata pre-filter on ``associated_lo_codes``.

    Only searches chunks that are tagged with at least one of the given
    LO codes, then ranks by embedding similarity.  Requires the Atlas
    Vector Search index to include ``associated_lo_codes`` as a filter
    field.
    """
    logger.info(
        "[tool] vector_search.search_chunks_filtered query=%s lo_codes=%s top_k=%s",
        query[:120],
        lo_codes,
        top_k,
    )
    query_vector = await embed_text(query)

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index_3k",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": top_k * 10,
                "limit": top_k,
                "filter": {
                    "associated_lo_codes": {"$in": lo_codes},
                },
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


# ---------------------------------------------------------------------------
# Metadata-first search (precise)
# ---------------------------------------------------------------------------

async def search_chunks_by_lo_codes(
    lo_codes: list[str], top_k: int = 3
) -> list[dict]:
    """
    Look up chunks that are explicitly tagged with the given LO codes
    via ``associated_lo_codes`` metadata.

    Strategy:
    1. Direct MongoDB ``find()`` on ``associated_lo_codes`` (fast, precise).
    2. If that yields results, return them.
    3. Otherwise fall back to filtered vector search.
    4. If still nothing, fall back to ``search_chunks_per_lo``.
    """
    # Delegate to the centralized safe retrieval function which implements
    # metadata-first lookup and per-LO semantic fallbacks while logging
    # fallback metrics. This keeps behavior consistent across the codebase.
    if not lo_codes:
        return []
    logger.info("[tool] vector_search.search_chunks_by_lo_codes lo_codes=%s top_k=%s", lo_codes, top_k)
    return await search_relevant_chunks(lo_codes, subdomain_code=None, top_k=top_k)


# ---------------------------------------------------------------------------
# Per-LO targeted vector search
# ---------------------------------------------------------------------------

async def search_chunks_per_lo(
    selected_los: list[dict], top_k: int = 3
) -> list[dict]:
    """
    Search for chunks per individual LO using short, targeted queries
    (LO code + name).  Avoids the noise caused by concatenating many
    descriptions into one long embedding query.
    """
    all_chunks: list[dict] = []
    seen_ids: set[str] = set()
    logger.info("[tool] vector_search.search_chunks_per_lo lo_count=%s top_k=%s", len(selected_los), top_k)

    for lo in selected_los:
        code = lo.get("code", "")
        name = lo.get("name", "")
        desc = lo.get("description", "")
        # Richer query — include description for better semantic matching
        query = f"{name} {desc[:300]}".strip() or f"{code} {name}".strip()
        if not query:
            continue

        chunks = await search_chunks(query, top_k=top_k)
        for ch in chunks:
            cid = ch.get("chunk_id", "")
            if cid not in seen_ids:
                seen_ids.add(cid)
                all_chunks.append(ch)

    return all_chunks


# ---------------------------------------------------------------------------
# Improved combined search (legacy interface, now per-LO)
# ---------------------------------------------------------------------------

async def search_chunks_by_los(
    lo_descriptions: list[str], top_k: int = 10
) -> list[dict]:
    """
    Search per-LO description individually for better precision (instead
    of concatenating all descriptions into one noisy query).
    """
    if not lo_descriptions:
        return []
    logger.info("[tool] vector_search.search_chunks_by_los description_count=%s top_k=%s", len(lo_descriptions), top_k)

    all_chunks: list[dict] = []
    seen_ids: set[str] = set()
    per_lo_k = max(2, top_k // len(lo_descriptions))

    for desc in lo_descriptions:
        # Keep individual queries short and focused
        query = desc[:500] if len(desc) > 500 else desc
        chunks = await search_chunks(query, top_k=per_lo_k)
        for ch in chunks:
            cid = ch.get("chunk_id", "")
            if cid not in seen_ids:
                seen_ids.add(cid)
                all_chunks.append(ch)

    return all_chunks[:top_k]

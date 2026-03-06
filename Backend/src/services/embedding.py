"""Thin wrapper around the OpenAI embeddings API.

This module enforces a policy: do not embed raw user text. Embeddings
used for semantic retrieval must be derived from curriculum metadata
(LO codes, LO names, LO descriptions) or canonical textbook content.
"""

from typing import List
import logging
from openai import AsyncOpenAI

from src.config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
logger = logging.getLogger(__name__)


async def embed_text(text: str, *, source: str = "textbook_content") -> List[float]:
    """Embed a single text string and return its vector.

    Parameters
    - text: canonical text to embed (LO description, textbook passage)
    - source: one of {"textbook_content", "lo_description", "lo_name"}.
      Embedding raw user messages (source="user") is explicitly disallowed.
    """
    if source == "user":
        raise ValueError("Embedding raw user text is disallowed. Use LO metadata or textbook content instead.")

    logger.info(
        "[tool] embedding.create source=%s model=%s chars=%s",
        source,
        settings.OPENAI_EMBEDDING_MODEL,
        len(text),
    )

    response = await _client.embeddings.create(
        input=[text],
        model=settings.OPENAI_EMBEDDING_MODEL,
    )
    return response.data[0].embedding


async def embed_texts(texts: list[str], *, source: str = "textbook_content") -> list[list[float]]:
    """Embed a batch of texts (max ~8 k tokens per text recommended).

    The `source` parameter is required to ensure callers think about the
    provenance of the text being embedded.
    """
    if source == "user":
        raise ValueError("Embedding raw user text is disallowed. Use LO metadata or textbook content instead.")
    if not texts:
        return []
    logger.info(
        "[tool] embedding.batch_create source=%s model=%s count=%s",
        source,
        settings.OPENAI_EMBEDDING_MODEL,
        len(texts),
    )
    response = await _client.embeddings.create(
        input=texts,
        model=settings.OPENAI_EMBEDDING_MODEL,
    )
    # The API returns embeddings in the same order as the input list.
    return [item.embedding for item in response.data]

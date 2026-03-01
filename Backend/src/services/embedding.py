"""Thin wrapper around the OpenAI embeddings API."""

from openai import AsyncOpenAI

from src.config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def embed_text(text: str) -> list[float]:
    """Embed a single text string and return its vector."""
    response = await _client.embeddings.create(
        input=[text],
        model=settings.OPENAI_EMBEDDING_MODEL,
    )
    return response.data[0].embedding


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts (max ~8 k tokens per text recommended)."""
    if not texts:
        return []
    response = await _client.embeddings.create(
        input=texts,
        model=settings.OPENAI_EMBEDDING_MODEL,
    )
    # The API returns embeddings in the same order as the input list.
    return [item.embedding for item in response.data]

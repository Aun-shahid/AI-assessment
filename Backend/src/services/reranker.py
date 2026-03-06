"""LLM-based reranker that filters retrieved chunks for relevance to selected LOs.

Uses a cheap, fast model (default: gpt-4.1-nano-2025-04-14) to decide KEEP/DROP
for each chunk, ensuring only genuinely on-topic content reaches the assessment
generator. Falls back to the original list if the model fails or drops everything.
"""

import json
import logging

from openai import AsyncOpenAI

from src.config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
logger = logging.getLogger(__name__)

_RERANK_SYSTEM = """\
You are a relevance filter for a Grade 6 science textbook retrieval system.

Given a set of Learning Outcomes (LOs) and a numbered list of textbook chunks,
decide which chunks are genuinely useful for building a student assessment on
those LOs.

Rules:
- KEEP  → chunk directly explains, discusses, or provides examples related to the LOs.
- DROP  → chunk is about a completely different topic, is mainly administrative
           instructions, answer keys for unrelated lessons, or image/credit metadata.

Respond with ONLY a JSON array of decisions, one per chunk, in the SAME order,
e.g.:  ["KEEP", "DROP", "KEEP"]

Do not include explanations. Output valid JSON only.
"""


async def rerank_chunks(chunks: list[dict], selected_los: list[dict]) -> list[dict]:
    """Filter *chunks* for relevance to *selected_los* using a small LLM.

    Parameters
    ----------
    chunks:       Raw chunks returned by the vector search / metadata lookup.
    selected_los: The LOs the teacher has confirmed for the assessment.

    Returns
    -------
    The subset of chunks the LLM marked KEEP, preserving original order.
    Falls back to the full *chunks* list on any error or if everything is dropped.
    """
    if not chunks:
        return chunks

    if not getattr(settings, "RERANK_WITH_LLM", True):
        logger.info("[reranker] disabled via RERANK_WITH_LLM=False, skipping")
        return chunks

    lo_summary = "\n".join(
        f"- [{lo.get('code', '')}] {lo.get('name', '')}: {lo.get('description', '')}"
        for lo in selected_los
    )

    chunk_list = "\n\n".join(
        f"Chunk {i + 1} (id={ch.get('chunk_id', i)}):\n{ch.get('content', '')[:600]}"
        for i, ch in enumerate(chunks)
    )

    messages = [
        {"role": "system", "content": _RERANK_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Learning Outcomes to assess:\n{lo_summary}\n\n"
                f"Textbook chunks to evaluate:\n{chunk_list}"
            ),
        },
    ]

    try:
        logger.info(
            "[reranker] scoring %s chunks with model=%s lo_codes=%s",
            len(chunks),
            settings.RERANK_MODEL,
            [lo.get("code") for lo in selected_los],
        )
        response = await _client.chat.completions.create(
            model=settings.RERANK_MODEL,
            messages=messages,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        decisions: list = json.loads(raw)

        if not isinstance(decisions, list) or len(decisions) != len(chunks):
            logger.warning(
                "[reranker] unexpected response length (%s vs %s), skipping filter",
                len(decisions) if isinstance(decisions, list) else "?",
                len(chunks),
            )
            return chunks

        kept = [ch for ch, dec in zip(chunks, decisions) if str(dec).strip().upper() == "KEEP"]
        dropped_count = len(chunks) - len(kept)
        logger.info("[reranker] kept=%s dropped=%s", len(kept), dropped_count)

        return kept

    except Exception:
        logger.exception("[reranker] reranking failed, returning original chunks unchanged")
        return chunks

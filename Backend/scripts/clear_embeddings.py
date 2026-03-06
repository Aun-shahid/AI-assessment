import asyncio
import sys
from pathlib import Path
import argparse

# Ensure Backend package is importable when run from project root
ROOT = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(ROOT / "Backend"))

from src.database import textbook_chunks_col


async def clear_embeddings(only_with_embedding: bool = True) -> None:
    query = {"embedding": {"$exists": True}} if only_with_embedding else {}
    total = await textbook_chunks_col.count_documents(query)
    if total == 0:
        print("No embeddings matched the query — nothing to clear.")
        return
    res = await textbook_chunks_col.update_many(query, {"$unset": {"embedding": ""}})
    print(f"Unset 'embedding' on {res.modified_count} documents (queried {total}).")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Clear embeddings from textbook_chunks so seed will re-embed.")
    p.add_argument("--all", action="store_true", help="Unset embedding on all documents (not just those with embeddings).")
    args = p.parse_args()
    asyncio.run(clear_embeddings(not args.all))

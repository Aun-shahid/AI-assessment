"""Quick script to inspect chunks.json content."""
import json
from pathlib import Path

chunks_path = Path(__file__).resolve().parents[2] / "docs" / "chunks.json"
chunks = json.load(open(chunks_path, "r", encoding="utf-8"))

print(f"Total chunks: {len(chunks)}")
print()
for c in chunks:
    cid = c["chunkId"]
    ps = c["pageSpan"]["pageStart"]
    pe = c["pageSpan"]["pageEnd"]
    preview = c["content"][:120].replace("\n", " ")
    print(f"{cid} | pages {ps}-{pe} | {preview}")

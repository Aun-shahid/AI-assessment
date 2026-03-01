"""Seed the database with curriculum data and textbook chunk embeddings."""

import json
import os
from pathlib import Path

from src.database import (
    domains_col,
    learning_outcomes_col,
    subdomains_col,
    textbook_chunks_col,
)
from src.services.embedding import embed_texts

# ---------------------------------------------------------------------------
# Curriculum data (from the project specification)
# ---------------------------------------------------------------------------

DOMAINS = [
    {"code": "1", "name": "Life Sciences", "subdomain_codes": ["1.1", "1.2", "1.3", "1.4"]},
    {"code": "2", "name": "Physical Sciences", "subdomain_codes": ["2.1", "2.2", "2.3", "2.4", "2.5"]},
    {"code": "3", "name": "Earth and Space Sciences", "subdomain_codes": ["3.1", "3.2"]},
]

SUBDOMAINS = [
    # Domain 1 – Life Sciences
    {"code": "1.1", "name": "Structure & Function", "domain_code": "1",
     "learning_outcome_codes": ["6.5.1.1.1", "6.5.1.1.2", "6.5.1.1.3", "6.5.1.1.4"]},
    {"code": "1.2", "name": "Organization", "domain_code": "1",
     "learning_outcome_codes": ["6.5.1.2.1"]},
    {"code": "1.3", "name": "Ecosystems", "domain_code": "1",
     "learning_outcome_codes": ["6.5.1.3.1", "6.5.1.3.2", "6.5.1.3.3", "6.5.1.3.4", "6.5.1.3.5"]},
    {"code": "1.4", "name": "Genetics", "domain_code": "1",
     "learning_outcome_codes": ["6.5.1.4.1"]},
    # Domain 2 – Physical Sciences
    {"code": "2.1", "name": "Matter", "domain_code": "2",
     "learning_outcome_codes": ["6.5.2.1.1", "6.5.2.1.2", "6.5.2.1.3", "6.5.2.1.4"]},
    {"code": "2.2", "name": "Motion & Forces", "domain_code": "2",
     "learning_outcome_codes": ["6.5.2.2.1", "6.5.2.2.2", "6.5.2.2.3"]},
    {"code": "2.3", "name": "Energy", "domain_code": "2",
     "learning_outcome_codes": ["6.5.2.3.1", "6.5.2.3.2"]},
    {"code": "2.4", "name": "Waves", "domain_code": "2",
     "learning_outcome_codes": ["6.5.2.4.1", "6.5.2.4.2"]},
    {"code": "2.5", "name": "Electromagnetism", "domain_code": "2",
     "learning_outcome_codes": ["6.5.2.5.1", "6.5.2.5.2"]},
    # Domain 3 – Earth and Space Sciences
    {"code": "3.1", "name": "Universe & Solar System", "domain_code": "3",
     "learning_outcome_codes": ["6.5.3.1.1", "6.5.3.1.2", "6.5.3.1.3", "6.5.3.1.4"]},
    {"code": "3.2", "name": "Earth System", "domain_code": "3",
     "learning_outcome_codes": ["6.5.3.2.1", "6.5.3.2.2", "6.5.3.2.3", "6.5.3.2.4", "6.5.3.2.5"]},
]

LEARNING_OUTCOMES = [
    # 1.1 Structure & Function
    {
        "code": "6.5.1.1.1", "name": "Cell structures",
        "subdomain_code": "1.1", "domain_code": "1",
        "description": (
            "Students identify and describe the basic structures of cells, "
            "including the cell membrane, nucleus, cytoplasm, and organelles. "
            "They explain how each structure contributes to the cell's overall function."
        ),
    },
    {
        "code": "6.5.1.1.2", "name": "Plant vs. animal cells",
        "subdomain_code": "1.1", "domain_code": "1",
        "description": (
            "Students compare and contrast plant and animal cells, identifying "
            "unique structures such as the cell wall, chloroplasts, and large central "
            "vacuole in plant cells and explaining functional differences."
        ),
    },
    {
        "code": "6.5.1.1.3", "name": "Body systems",
        "subdomain_code": "1.1", "domain_code": "1",
        "description": (
            "Students describe the major body systems (digestive, circulatory, "
            "respiratory, nervous, etc.) and explain how they interact to maintain "
            "life and homeostasis in multicellular organisms."
        ),
    },
    {
        "code": "6.5.1.1.4", "name": "Life cycles",
        "subdomain_code": "1.1", "domain_code": "1",
        "description": (
            "Students describe the stages of life cycles for various organisms, "
            "including birth, growth, reproduction, and death, and compare life "
            "cycle patterns across species."
        ),
    },
    # 1.2 Organization
    {
        "code": "6.5.1.2.1", "name": "Phenotypic classification",
        "subdomain_code": "1.2", "domain_code": "1",
        "description": (
            "Students classify organisms based on observable phenotypic "
            "characteristics such as body structure, coloring, and behavior, "
            "and explain the reasoning behind classification systems."
        ),
    },
    # 1.3 Ecosystems
    {
        "code": "6.5.1.3.1", "name": "Interrelationships",
        "subdomain_code": "1.3", "domain_code": "1",
        "description": (
            "Students analyze the interrelationships among organisms in an "
            "ecosystem, including predator-prey, symbiotic, and competitive "
            "relationships, and how they affect population dynamics."
        ),
    },
    {
        "code": "6.5.1.3.2", "name": "Resource impact",
        "subdomain_code": "1.3", "domain_code": "1",
        "description": (
            "Students evaluate how the availability of resources such as water, "
            "food, and shelter affects organisms and populations within an ecosystem."
        ),
    },
    {
        "code": "6.5.1.3.3", "name": "Energy circulation",
        "subdomain_code": "1.3", "domain_code": "1",
        "description": (
            "Students trace the flow of energy through an ecosystem via food "
            "chains and food webs, explaining the roles of producers, consumers, "
            "and decomposers in energy transfer."
        ),
    },
    {
        "code": "6.5.1.3.4", "name": "Environmental adaptation",
        "subdomain_code": "1.3", "domain_code": "1",
        "description": (
            "Students explain how organisms adapt to their environment through "
            "structural, behavioral, and physiological adaptations, and how these "
            "adaptations increase survival and reproduction."
        ),
    },
    {
        "code": "6.5.1.3.5", "name": "Human activity impact",
        "subdomain_code": "1.3", "domain_code": "1",
        "description": (
            "Students assess the positive and negative impacts of human activity "
            "on ecosystems, including pollution, deforestation, conservation "
            "efforts, and habitat restoration."
        ),
    },
    # 1.4 Genetics
    {
        "code": "6.5.1.4.1", "name": "Inheritance and variation",
        "subdomain_code": "1.4", "domain_code": "1",
        "description": (
            "Students explain the basic principles of inheritance, how traits "
            "are passed from parents to offspring through genes, and the sources "
            "of genetic variation within a population."
        ),
    },
    # 2.1 Matter
    {
        "code": "6.5.2.1.1", "name": "Physical properties",
        "subdomain_code": "2.1", "domain_code": "2",
        "description": (
            "Students identify and measure physical properties of matter such "
            "as mass, volume, density, color, hardness, and state, and use these "
            "properties to classify and distinguish substances."
        ),
    },
    {
        "code": "6.5.2.1.2", "name": "Chemical changes",
        "subdomain_code": "2.1", "domain_code": "2",
        "description": (
            "Students identify evidence of chemical changes — color change, gas "
            "production, temperature change, precipitate formation — and "
            "distinguish them from physical changes."
        ),
    },
    {
        "code": "6.5.2.1.3", "name": "Chemical reactions",
        "subdomain_code": "2.1", "domain_code": "2",
        "description": (
            "Students describe chemical reactions in terms of reactants and "
            "products, explain conservation of mass, and represent simple "
            "reactions with word equations or models."
        ),
    },
    {
        "code": "6.5.2.1.4", "name": "Acids and bases",
        "subdomain_code": "2.1", "domain_code": "2",
        "description": (
            "Students distinguish between acids and bases using indicators "
            "and pH scale, describe their common properties, and give examples "
            "of acids and bases in everyday life."
        ),
    },
    # 2.2 Motion & Forces
    {
        "code": "6.5.2.2.1", "name": "Force types",
        "subdomain_code": "2.2", "domain_code": "2",
        "description": (
            "Students identify different types of forces — push, pull, applied, "
            "normal, tension, and spring — and describe how forces affect the "
            "motion and shape of objects."
        ),
    },
    {
        "code": "6.5.2.2.2", "name": "Newton's laws",
        "subdomain_code": "2.2", "domain_code": "2",
        "description": (
            "Students explain Newton's three laws of motion, apply them to "
            "predict the effect of forces on objects, and use examples from "
            "everyday life to illustrate each law."
        ),
    },
    {
        "code": "6.5.2.2.3", "name": "Gravity, friction, and magnetism",
        "subdomain_code": "2.2", "domain_code": "2",
        "description": (
            "Students describe the forces of gravity, friction, and magnetism, "
            "explain how they act at a distance or through contact, and analyze "
            "their effects on the motion of objects."
        ),
    },
    # 2.3 Energy
    {
        "code": "6.5.2.3.1", "name": "Energy vs. Work",
        "subdomain_code": "2.3", "domain_code": "2",
        "description": (
            "Students differentiate between energy and work, describe forms "
            "of energy (kinetic, potential, thermal), and explain how work "
            "is done when a force moves an object over a distance."
        ),
    },
    {
        "code": "6.5.2.3.2", "name": "Conservation of energy",
        "subdomain_code": "2.3", "domain_code": "2",
        "description": (
            "Students explain the law of conservation of energy, demonstrate "
            "that energy can be transformed from one form to another but is "
            "neither created nor destroyed, and trace energy transformations "
            "in real-world systems."
        ),
    },
    # 2.4 Waves
    {
        "code": "6.5.2.4.1", "name": "Wave properties",
        "subdomain_code": "2.4", "domain_code": "2",
        "description": (
            "Students describe the basic properties of waves — wavelength, "
            "frequency, amplitude, and speed — and distinguish between "
            "transverse and longitudinal waves."
        ),
    },
    {
        "code": "6.5.2.4.2", "name": "Light/sound reflection and refraction",
        "subdomain_code": "2.4", "domain_code": "2",
        "description": (
            "Students explain reflection and refraction of light and sound "
            "waves, use ray diagrams to model light behavior, and describe "
            "how sound travels through different media."
        ),
    },
    # 2.5 Electromagnetism
    {
        "code": "6.5.2.5.1", "name": "Electric charge and circuits",
        "subdomain_code": "2.5", "domain_code": "2",
        "description": (
            "Students describe electric charge, current, voltage, and "
            "resistance; build and analyze simple series and parallel circuits; "
            "and explain the function of components like batteries, resistors, "
            "and switches."
        ),
    },
    {
        "code": "6.5.2.5.2", "name": "Magnets",
        "subdomain_code": "2.5", "domain_code": "2",
        "description": (
            "Students describe the properties of magnets, explain magnetic "
            "fields and poles, investigate the relationship between electricity "
            "and magnetism, and describe applications of electromagnets."
        ),
    },
    # 3.1 Universe & Solar System
    {
        "code": "6.5.3.1.1", "name": "Moon phases",
        "subdomain_code": "3.1", "domain_code": "3",
        "description": (
            "Students explain the phases of the moon as a result of its "
            "orbital position relative to Earth and the Sun, and predict "
            "the sequence of lunar phases over a monthly cycle."
        ),
    },
    {
        "code": "6.5.3.1.2", "name": "Earth/Moon/Sun movements",
        "subdomain_code": "3.1", "domain_code": "3",
        "description": (
            "Students describe the rotation and revolution of Earth, the "
            "orbit of the Moon around Earth, and how these movements cause "
            "day/night cycles, seasons, tides, and eclipses."
        ),
    },
    {
        "code": "6.5.3.1.3", "name": "Gravity effects",
        "subdomain_code": "3.1", "domain_code": "3",
        "description": (
            "Students explain how gravity governs the motion of objects in "
            "the solar system, keeps planets in orbit around the Sun, and "
            "the Moon in orbit around Earth, and affects weight on different "
            "celestial bodies."
        ),
    },
    {
        "code": "6.5.3.1.4", "name": "Solar system vs. Galaxy",
        "subdomain_code": "3.1", "domain_code": "3",
        "description": (
            "Students compare the scale and structure of the solar system "
            "with the Milky Way galaxy, describe components of each (planets, "
            "stars, nebulae), and explain Earth's position within the galaxy."
        ),
    },
    # 3.2 Earth System
    {
        "code": "6.5.3.2.1", "name": "Atmospheric layers",
        "subdomain_code": "3.2", "domain_code": "3",
        "description": (
            "Students identify and describe the layers of Earth's atmosphere "
            "(troposphere, stratosphere, mesosphere, thermosphere), their "
            "characteristics, and the role of the atmosphere in sustaining life."
        ),
    },
    {
        "code": "6.5.3.2.2", "name": "Earth's spheres",
        "subdomain_code": "3.2", "domain_code": "3",
        "description": (
            "Students describe the four major Earth systems — atmosphere, "
            "hydrosphere, geosphere, and biosphere — and explain how they "
            "interact and influence one another."
        ),
    },
    {
        "code": "6.5.3.2.3", "name": "Surface changes",
        "subdomain_code": "3.2", "domain_code": "3",
        "description": (
            "Students explain how Earth's surface is changed by weathering, "
            "erosion, and deposition processes, and identify landforms created "
            "by these processes over time."
        ),
    },
    {
        "code": "6.5.3.2.4", "name": "Rocks and minerals",
        "subdomain_code": "3.2", "domain_code": "3",
        "description": (
            "Students classify rocks as igneous, sedimentary, or metamorphic, "
            "describe the rock cycle, identify common minerals by their "
            "properties, and explain how rocks and minerals form."
        ),
    },
    {
        "code": "6.5.3.2.5", "name": "Earthquakes and volcanoes",
        "subdomain_code": "3.2", "domain_code": "3",
        "description": (
            "Students explain the causes of earthquakes and volcanic eruptions "
            "in terms of plate tectonics, describe how seismic waves travel, "
            "and identify patterns of earthquake/volcano distribution."
        ),
    },
]


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

async def seed_curriculum() -> None:
    """Upsert all domains, subdomains, and LOs into MongoDB (idempotent)."""
    for domain in DOMAINS:
        await domains_col.update_one(
            {"code": domain["code"]}, {"$set": domain}, upsert=True,
        )
    for sub in SUBDOMAINS:
        await subdomains_col.update_one(
            {"code": sub["code"]}, {"$set": sub}, upsert=True,
        )
    for lo in LEARNING_OUTCOMES:
        await learning_outcomes_col.update_one(
            {"code": lo["code"]}, {"$set": lo}, upsert=True,
        )
    print(
        f"[seed] Curriculum seeded: {len(DOMAINS)} domains, "
        f"{len(SUBDOMAINS)} subdomains, {len(LEARNING_OUTCOMES)} LOs."
    )


async def seed_chunks() -> None:
    """
    Load textbook chunks from ``docs/chunks.json``, embed them via OpenAI,
    and upsert into MongoDB.  Chunks that already have an embedding are
    skipped to keep the process idempotent and cost-efficient.
    """
    # Resolve path relative to the project root (one level above Backend/)
    chunks_path = Path(__file__).resolve().parents[2] / "docs" / "chunks.json"
    if not chunks_path.exists():
        # Also try relative to cwd
        alt = Path(os.getcwd()).parent / "docs" / "chunks.json"
        if alt.exists():
            chunks_path = alt
        else:
            print(f"[seed] chunks.json not found at {chunks_path} — skipping.")
            return

    with open(chunks_path, "r", encoding="utf-8") as f:
        raw_chunks: list[dict] = json.load(f)

    print(f"[seed] Loaded {len(raw_chunks)} chunks from {chunks_path}")

    # Determine which chunks still need embedding
    to_embed: list[dict] = []
    for chunk in raw_chunks:
        cid = chunk.get("chunkId", chunk.get("chunk_id"))
        existing = await textbook_chunks_col.find_one(
            {"chunk_id": cid, "embedding": {"$exists": True, "$ne": None}},
        )
        if existing is None:
            to_embed.append(chunk)

    if not to_embed:
        print("[seed] All chunks already embedded — nothing to do.")
        return

    print(f"[seed] Embedding {len(to_embed)} new chunks …")

    batch_size = 20
    for i in range(0, len(to_embed), batch_size):
        batch = to_embed[i : i + batch_size]
        texts = [c.get("content", "") for c in batch]
        vectors = await embed_texts(texts)

        for chunk, vec in zip(batch, vectors):
            cid = chunk.get("chunkId", chunk.get("chunk_id"))
            page_span = chunk.get("pageSpan", {})
            doc = {
                "chunk_id": cid,
                "content": chunk.get("content", ""),
                "page_start": page_span.get("pageStart", 0),
                "page_end": page_span.get("pageEnd", 0),
                "embedding": vec,
                "associated_lo_codes": chunk.get("associated_lo_codes", []),
            }
            await textbook_chunks_col.update_one(
                {"chunk_id": cid}, {"$set": doc}, upsert=True,
            )
        print(f"[seed]   … embedded batch {i // batch_size + 1}")

    print("[seed] Chunk seeding complete.")

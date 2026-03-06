"""EduAssess – AI-Driven Agentic Assessment System (FastAPI entrypoint)."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.database import create_indexes, ensure_vector_search_index
from src.routers.answer import router as answer_router
from src.routers.session import router as session_router
from src.services.seed import seed_chunks, seed_curriculum


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


# ---------------------------------------------------------------------------
# Lifespan – runs once at startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: seed data & create indexes. Shutdown: nothing to clean up."""
    print("[startup] Creating indexes …")
    await create_indexes()
    await ensure_vector_search_index()

    print("[startup] Seeding curriculum …")
    await seed_curriculum()

    print("[startup] Seeding textbook chunks (embedding on first run) …")
    await seed_chunks()

    print("[startup] Ready ✓")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EduAssess API",
    description=(
        "AI-driven agentic assessment system that helps teachers generate "
        "student assessments from curriculum data and textbook content."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS.split(",") if settings.BACKEND_CORS_ORIGINS else [settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(answer_router)
app.include_router(session_router)


# Health check (used by Railway / load balancers)
@app.get("/health")
async def health():
    return {"status": "ok"}

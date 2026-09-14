"""
FastAPI application entry point.

Mounts all routers, configures CORS for the Vite dev server,
and initializes the database on startup.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.review_routes import router as review_router
from backend.api.byzantine_routes import router as byzantine_router
from backend.api.experiment_routes import router as experiment_router
from backend.database.db import init_db

# ── Logging setup ────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-30s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")


# ── App ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Wiki Curator — Decision & Adversarial Engine",
    description=(
        "Person 2 subsystem: Reviewer agents, Byzantine agent, "
        "consensus engine, reputation system, and experiment framework."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Vite dev server (localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(review_router, prefix="/api", tags=["Review Pipeline"])
app.include_router(byzantine_router, prefix="/api/byzantine", tags=["Byzantine Agent"])
app.include_router(experiment_router, prefix="/api/experiments", tags=["Experiments"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "wiki-curator-p2"}

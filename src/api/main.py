"""FastAPI application entry-point for the Judo Tournament Manager.

Run with:  uv run uvicorn api.main:app --reload
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database.database import init_db

from .routers import auth, clubs, matches, results, tokens, tournaments

# Comma-separated list of allowed origins (the SvelteKit dev server by default).
_ALLOWED_ORIGINS = os.environ.get(
    "JUDO_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Judo Tournament Manager API", version="1.0.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _ALLOWED_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


for _router in (auth, clubs, tournaments, tokens, matches, results):
    app.include_router(_router.router, prefix="/api")

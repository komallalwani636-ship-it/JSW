"""Application entry point for the CPL-2 Scheduling System.

Creates the FastAPI application, registers middleware, includes routers, and
defines the global exception handler and health-check endpoint.

Design references: Requirements 11.7
"""

from __future__ import annotations

import logging
import os

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import auth, export, schedules, uploads

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CPL-2 Scheduling System",
    description="REST API for the CPL-2 cold rolling line scheduling system.",
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

_raw_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"),
)
_origins = [orig.strip() for orig in _raw_origins.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if "*" not in _origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(schedules.router)
app.include_router(export.router)

# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler that logs the error but never exposes a stack trace.

    Returns a plain 500 response so that internal details are never leaked to
    clients.

    Requirements: 11.7
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
async def health_check() -> dict:
    """Liveness probe — returns HTTP 200 with a static JSON body."""
    return {"status": "ok"}

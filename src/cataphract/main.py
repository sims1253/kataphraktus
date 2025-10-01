"""
Cataphract Game System - Main FastAPI Application

This module provides the main FastAPI application entry point for the
Cataphract medieval-fantasy wargame backend. It includes health checks,
database connectivity validation, and API routing.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from cataphract.config import get_settings
from cataphract.database import check_database_health, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Application lifespan handler.

    Runs on startup and shutdown to manage application resources.

    Args:
        app: FastAPI application instance (unused but required by FastAPI)

    Yields:
        Control to the application
    """
    # Startup: verify database connectivity
    try:
        check_database_health()
        print("Database connection verified")
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise

    yield

    # Shutdown: cleanup if needed
    print("Shutting down Cataphract server...")


# Create FastAPI application
app = FastAPI(
    title="Cataphract Game System",
    description="Backend API for Cataphract medieval-fantasy wargame",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check(db: Session = Depends(get_db)) -> dict[str, Any]:  # noqa: B008
    """Health check endpoint.

    Verifies that the API server and database are operational.

    Args:
        db: Database session (injected via dependency)

    Returns:
        Health status with database connectivity information

    Example Response:
        {
            "status": "healthy",
            "database": "connected",
            "version": "1.0.0"
        }
    """
    try:
        # Test database connectivity with a simple query
        db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "disconnected"

    settings = get_settings()

    return {
        "status": "healthy" if database_status == "connected" else "degraded",
        "database": database_status,
        "version": "1.0.0",
        "environment": "development" if settings.DATABASE_ECHO else "production",
    }


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint.

    Provides basic API information.

    Returns:
        API information
    """
    return {
        "name": "Cataphract Game System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "cataphract.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info" if settings.DATABASE_ECHO else "warning",
    )

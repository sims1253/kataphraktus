"""FastAPI application wiring for Cataphract."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cataphract.api import routes
from cataphract.api.runtime import ApiState, build_state
from cataphract.config import get_settings


def create_app(*, state_factory: Callable[[], ApiState] = build_state) -> FastAPI:
    """Instantiate the FastAPI application with routing and lifecycle hooks."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state = state_factory()
        app.state.api_state = state
        try:
            yield
        finally:
            await state.shutdown()

    app = FastAPI(title="Cataphract API", version="0.1.0", lifespan=lifespan)
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes.router)
    return app


app = create_app()

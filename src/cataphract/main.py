"""Minimal FastAPI entrypoint serving the Cataphract domain."""

from __future__ import annotations

from fastapi import FastAPI

from cataphract.domain import rules_config

app = FastAPI(
    title="Cataphract",
    description="Lightweight API surface for the Cataphract campaign tools",
    version="0.2.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple readiness probe."""

    return {"status": "ok", "rules_version": "1.1"}


@app.get("/rules")
async def rules_overview() -> dict[str, object]:
    """Expose a snapshot of configurable rule constants for clients."""

    supply = rules_config.DEFAULT_RULES.supply
    return {
        "supply": {
            "infantry_capacity": supply.infantry_capacity,
            "cavalry_capacity": supply.cavalry_capacity,
            "wagon_capacity": supply.wagon_capacity,
            "foraging_multiplier": supply.foraging_multiplier,
            "torch_revolt_chance": supply.torch_revolt_chance,
        }
    }


if __name__ == "__main__":  # pragma: no cover - manual launch helper
    import uvicorn

    uvicorn.run("cataphract.main:app", host="0.0.0.0", port=8000, reload=True)

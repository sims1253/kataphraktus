"""Integration tests for the FastAPI layer."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from cataphract.api.app import create_app
from cataphract.api.runtime import ApiState
from cataphract.config import Settings
from cataphract.domain import models as dm
from cataphract.domain.enums import ArmyStatus
from cataphract.repository import JsonCampaignRepository


def _make_app(tmp_path):
    def factory() -> ApiState:
        settings = Settings(
            data_dir=tmp_path,
            tick_interval_seconds=0.5,
            debug_tick_speed_multiplier=0.5,
        )
        return ApiState(settings=settings)

    app = create_app(state_factory=factory)
    transport = ASGITransport(app=app)
    return app, transport


async def _create_campaign(client: AsyncClient) -> int:
    response = await client.post(
        "/campaigns",
        json={
            "name": "Dev Campaign",
            "start_date": date(1325, 3, 1).isoformat(),
            "season": "spring",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["current_day"] == 0
    return payload["id"]


def _seed_army(tmp_path, campaign_id: int) -> None:
    repo = JsonCampaignRepository(tmp_path)
    model = repo.load(dm.CampaignID(campaign_id))

    commander = dm.Commander(
        id=dm.CommanderID(1),
        campaign_id=model.id,
        name="Commander",
        faction_id=dm.FactionID(1),
        age=35,
    )

    hex_tile = dm.Hex(
        id=dm.HexID(1),
        campaign_id=model.id,
        q=0,
        r=0,
        terrain="flatland",
        settlement=15,
    )
    model.map.hexes[hex_tile.id] = hex_tile

    army = dm.Army(
        id=dm.ArmyID(1),
        campaign_id=model.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        detachments=[],
        status=ArmyStatus.IDLE,
    )

    model.commanders[commander.id] = commander
    model.armies[army.id] = army
    repo.save(model)


@pytest.mark.asyncio
async def test_campaign_lifecycle_via_api(tmp_path):
    app, transport = _make_app(tmp_path)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"

        campaign_id = await _create_campaign(client)

        response = await client.post(
            f"/campaigns/{campaign_id}/tick/advance",
            json={"days": 2},
        )
        assert response.status_code == 200
        advanced = response.json()
        assert advanced["current_day"] == 2

        response = await client.post(
            f"/campaigns/{campaign_id}/tick/schedule",
            json={"enabled": True, "interval_seconds": 1.5, "debug_multiplier": 0.2},
        )
        assert response.status_code == 200
        schedule = response.json()
        assert schedule["enabled"] is True
        assert schedule["interval_seconds"] == 1.5
        assert schedule["effective_interval_seconds"] == pytest.approx(0.3)

        response = await client.get(f"/campaigns/{campaign_id}/tick/schedule")
        assert response.status_code == 200
        status_payload = response.json()
        assert status_payload["enabled"] is True

    repo = JsonCampaignRepository(tmp_path)
    stored = repo.load(dm.CampaignID(campaign_id))
    assert stored.current_day == 2


@pytest.mark.asyncio
async def test_order_endpoints_via_api(tmp_path):
    app, transport = _make_app(tmp_path)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        campaign_id = await _create_campaign(client)
        _seed_army(tmp_path, campaign_id)

        response = await client.get(f"/campaigns/{campaign_id}/armies")
        assert response.status_code == 200
        armies_payload = response.json()
        assert len(armies_payload) == 1
        assert armies_payload[0]["status"] == ArmyStatus.IDLE

        response = await client.post(
            f"/campaigns/{campaign_id}/orders",
            json={
                "army_id": 1,
                "commander_id": 1,
                "order_type": "rest",
                "parameters": {"duration": 1},
                "execute_part": "morning",
                "priority": 2,
            },
        )
        assert response.status_code == 201
        created_order = response.json()
        order_id = created_order["id"]
        assert created_order["status"] == "pending"

        response = await client.get(f"/campaigns/{campaign_id}/orders")
        assert response.status_code == 200
        orders_payload = response.json()
        assert any(order["id"] == order_id for order in orders_payload)

        response = await client.get(
            f"/campaigns/{campaign_id}/orders", params={"status": "pending"}
        )
        assert response.status_code == 200
        filtered = response.json()
        assert len(filtered) == 1
        assert filtered[0]["id"] == order_id

        response = await client.post(f"/campaigns/{campaign_id}/orders/{order_id}/cancel")
        assert response.status_code == 200
        cancelled = response.json()
        assert cancelled["status"] == "cancelled"

    repo = JsonCampaignRepository(tmp_path)
    stored = repo.load(dm.CampaignID(campaign_id))
    order = stored.orders[dm.OrderID(order_id)]
    assert order.status.value == "cancelled"

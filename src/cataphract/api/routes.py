"""HTTP routes for the Cataphract API."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from cataphract.api.runtime import ApiState, OrderDraft
from cataphract.domain import models as dm
from cataphract.domain.enums import DayPart, OrderStatus, Season

router = APIRouter()


def get_state(request: Request) -> ApiState:
    state = getattr(request.app.state, "api_state", None)
    if state is None:  # pragma: no cover - FastAPI should always initialise state
        raise RuntimeError("API state not initialised")
    return state


ApiStateDep = Annotated[ApiState, Depends(get_state)]


class CampaignSummary(BaseModel):
    id: int
    name: str
    start_date: date
    current_day: int
    current_part: str
    season: str
    status: str
    faction_count: int
    commander_count: int
    army_count: int
    pending_orders: int


class CampaignDetail(CampaignSummary):
    map: dict[str, int]
    armies: dict[str, dict[str, object]]
    strongholds: dict[str, dict[str, object]]
    orders: dict[str, dict[str, object]]


class CreateCampaignRequest(BaseModel):
    name: str = Field(min_length=1)
    start_date: date
    season: Season = Season.SPRING
    status: str = Field(default="active", min_length=1)


class TickAdvanceRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=30)


class TickScheduleRequest(BaseModel):
    enabled: bool
    interval_seconds: float | None = Field(default=None, gt=0.0)
    debug_multiplier: float | None = Field(default=None, gt=0.0)


class TickStatusResponse(BaseModel):
    enabled: bool
    interval_seconds: float
    debug_multiplier: float
    effective_interval_seconds: float


class ArmySummary(BaseModel):
    id: int
    commander_id: int
    status: str
    current_hex_id: int | None
    supplies_current: int
    supplies_capacity: int
    morale_current: int
    movement_points_remaining: float
    orders_queue: list[int]


class OrderSummary(BaseModel):
    id: int
    army_id: int | None
    commander_id: int
    order_type: str
    status: str
    priority: int
    issued_at: str
    execute_at: str
    execute_day: int | None
    execute_part: str | None
    parameters: dict[str, object]
    result: dict[str, object] | None


class OrderCreateRequest(BaseModel):
    army_id: int | None = None
    commander_id: int
    order_type: str
    parameters: dict[str, object] = Field(default_factory=dict)
    execute_day: int | None = None
    execute_part: DayPart | None = None
    priority: int = 0


class ScenarioSummary(BaseModel):
    slug: str
    kind: str
    name: str
    description: str | None
    author: str | None
    created_at: datetime


class ScenarioImportRequest(BaseModel):
    slug: str


@router.get("/health")
async def health(state: ApiStateDep) -> dict[str, object]:
    return {
        "status": "ok",
        "rules_version": state.settings.rules_version,
        "tick_interval_seconds": state.ticks.interval_seconds,
        "debug_tick_multiplier": state.ticks.debug_multiplier,
    }


@router.get("/campaigns", response_model=list[CampaignSummary])
async def list_campaigns(state: ApiStateDep) -> list[CampaignSummary]:
    campaigns = state.campaigns.list_campaigns()
    return [CampaignSummary.model_validate(state.campaigns.to_summary_dict(c)) for c in campaigns]


@router.post(
    "/campaigns",
    response_model=CampaignDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(request: CreateCampaignRequest, state: ApiStateDep) -> CampaignDetail:
    campaign = state.campaigns.create_campaign(
        name=request.name,
        start_date=request.start_date,
        season=request.season,
        status=request.status,
    )
    return CampaignDetail.model_validate(state.campaigns.to_detail_dict(campaign))


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(campaign_id: int, state: ApiStateDep) -> CampaignDetail:
    try:
        campaign = state.campaigns.get_campaign(dm.CampaignID(campaign_id))
    except FileNotFoundError as exc:  # pragma: no cover - exercised in functional tests
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        ) from exc
    return CampaignDetail.model_validate(state.campaigns.to_detail_dict(campaign))


@router.post("/campaigns/{campaign_id}/tick/advance", response_model=CampaignSummary)
async def advance_tick(
    campaign_id: int,
    request: TickAdvanceRequest,
    state: ApiStateDep,
) -> CampaignSummary:
    campaign_key = dm.CampaignID(campaign_id)
    try:
        state.campaigns.get_campaign(campaign_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        ) from exc

    await state.ticks.advance_now(campaign_key, days=request.days)
    updated = state.campaigns.get_campaign(campaign_key)
    return CampaignSummary.model_validate(state.campaigns.to_summary_dict(updated))


@router.get("/campaigns/{campaign_id}/tick/schedule", response_model=TickStatusResponse)
async def get_tick_schedule(campaign_id: int, state: ApiStateDep) -> TickStatusResponse:
    campaign_key = dm.CampaignID(campaign_id)
    enabled = state.ticks.is_enabled(campaign_key)
    return TickStatusResponse(
        enabled=enabled,
        interval_seconds=state.ticks.base_interval_seconds,
        debug_multiplier=state.ticks.debug_multiplier,
        effective_interval_seconds=state.ticks.interval_seconds,
    )


@router.post("/campaigns/{campaign_id}/tick/schedule", response_model=TickStatusResponse)
async def update_tick_schedule(
    campaign_id: int,
    request: TickScheduleRequest,
    state: ApiStateDep,
) -> TickStatusResponse:
    campaign_key = dm.CampaignID(campaign_id)
    try:
        state.campaigns.get_campaign(campaign_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        ) from exc

    if request.interval_seconds is not None:
        state.ticks.set_base_interval(request.interval_seconds)
    if request.debug_multiplier is not None:
        state.ticks.set_debug_multiplier(request.debug_multiplier)

    await state.ticks.set_enabled(campaign_key, request.enabled)

    return TickStatusResponse(
        enabled=state.ticks.is_enabled(campaign_key),
        interval_seconds=state.ticks.base_interval_seconds,
        debug_multiplier=state.ticks.debug_multiplier,
        effective_interval_seconds=state.ticks.interval_seconds,
    )


@router.get("/campaigns/{campaign_id}/armies", response_model=list[ArmySummary])
async def list_armies(campaign_id: int, state: ApiStateDep) -> list[ArmySummary]:
    campaign_key = dm.CampaignID(campaign_id)
    try:
        campaign = state.campaigns.get_campaign(campaign_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        ) from exc

    armies = state.campaigns.list_armies(campaign)
    return [ArmySummary.model_validate(army) for army in armies]


@router.get("/campaigns/{campaign_id}/orders", response_model=list[OrderSummary])
async def list_orders(
    campaign_id: int,
    state: ApiStateDep,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
) -> list[OrderSummary]:
    campaign_key = dm.CampaignID(campaign_id)
    try:
        campaign = state.campaigns.get_campaign(campaign_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        ) from exc

    statuses = {status_filter} if status_filter is not None else None
    payload = state.campaigns.list_orders(campaign, statuses=statuses)
    return [OrderSummary.model_validate(order) for order in payload]


@router.post(
    "/campaigns/{campaign_id}/orders",
    response_model=OrderSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    campaign_id: int,
    request: OrderCreateRequest,
    state: ApiStateDep,
) -> OrderSummary:
    campaign_key = dm.CampaignID(campaign_id)
    army_id = dm.ArmyID(request.army_id) if request.army_id is not None else None
    commander_id = dm.CommanderID(request.commander_id)

    draft = OrderDraft(
        army_id=army_id,
        commander_id=commander_id,
        order_type=request.order_type,
        parameters=request.parameters,
        execute_day=request.execute_day,
        execute_part=request.execute_part,
        priority=request.priority,
    )

    try:
        order = state.campaigns.create_order(campaign_key, draft)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        ) from exc

    return OrderSummary.model_validate(state.campaigns.to_order_dict(order))


@router.get("/scenarios", response_model=list[ScenarioSummary])
async def list_scenarios(state: ApiStateDep) -> list[ScenarioSummary]:
    result: list[ScenarioSummary] = []
    for item in state.campaigns.list_scenarios():
        metadata = item.get("metadata", {})
        created_at = metadata.get("created_at")
        created = (
            datetime.fromisoformat(created_at) if isinstance(created_at, str) else datetime.now(UTC)
        )
        result.append(
            ScenarioSummary(
                slug=item["slug"],
                kind=str(item["kind"]),
                name=metadata.get("name", item["slug"]),
                description=metadata.get("description"),
                author=metadata.get("author"),
                created_at=created,
            )
        )
    return result


@router.post(
    "/scenarios/import", response_model=CampaignSummary, status_code=status.HTTP_201_CREATED
)
async def import_scenario(
    request: ScenarioImportRequest,
    state: ApiStateDep,
) -> CampaignSummary:
    try:
        campaign = state.campaigns.import_scenario(request.slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CampaignSummary.model_validate(state.campaigns.to_summary_dict(campaign))


@router.post(
    "/campaigns/{campaign_id}/orders/{order_id}/cancel",
    response_model=OrderSummary,
)
async def cancel_order(
    campaign_id: int,
    order_id: int,
    state: ApiStateDep,
) -> OrderSummary:
    campaign_key = dm.CampaignID(campaign_id)
    try:
        order = state.campaigns.cancel_order(campaign_key, dm.OrderID(order_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        ) from exc

    return OrderSummary.model_validate(state.campaigns.to_order_dict(order))

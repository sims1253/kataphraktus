"""Runtime primitives backing the Cataphract HTTP API."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from cataphract.config import Settings, get_settings
from cataphract.domain import models as dm
from cataphract.domain.enums import DayPart, OrderStatus, Season
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.domain.tick import run_daily_tick
from cataphract.repository import JsonCampaignRepository
from cataphract import savegame

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OrderDraft:
    """API-facing initializer for new orders."""

    army_id: dm.ArmyID | None
    commander_id: dm.CommanderID
    order_type: str
    parameters: dict[str, object] | None = None
    execute_day: int | None = None
    execute_part: DayPart | None = None
    priority: int = 0


class CampaignService:
    """Utilities for loading and mutating campaign aggregates."""

    def __init__(
        self,
        repository: JsonCampaignRepository,
        *,
        scenario_dir: Path | None = None,
    ) -> None:
        self._repository = repository
        self._scenario_dir = scenario_dir

    def list_campaigns(self) -> list[dm.Campaign]:
        """Return every persisted campaign ordered by identifier."""

        campaigns: list[dm.Campaign] = []
        for campaign_id in self._repository.list_campaigns():
            with suppress(FileNotFoundError):
                campaigns.append(self._repository.load(campaign_id))
        return campaigns

    def get_campaign(self, campaign_id: dm.CampaignID) -> dm.Campaign:
        """Load a single campaign or raise ``FileNotFoundError``."""

        return self._repository.load(campaign_id)

    def save_campaign(self, campaign: dm.Campaign) -> dm.Campaign:
        """Persist the provided campaign and return it."""

        self._repository.save(campaign)
        return campaign

    def create_campaign(
        self,
        name: str,
        start_date: date,
        *,
        season: Season = Season.SPRING,
        status: str = "active",
    ) -> dm.Campaign:
        """Create and persist a minimally populated campaign."""

        next_id = self._next_identifier()
        campaign = dm.Campaign(
            id=next_id,
            name=name,
            start_date=start_date,
            current_day=0,
            current_part=DayPart.MORNING,
            season=season,
            status=status,
        )
        self._repository.save(campaign)
        return campaign

    def _next_identifier(self) -> dm.CampaignID:
        existing = self._repository.list_campaigns()
        if not existing:
            return dm.CampaignID(1)
        last = max(existing, key=int)
        return dm.CampaignID(int(last) + 1)

    @staticmethod
    def _next_order_identifier(campaign: dm.Campaign) -> dm.OrderID:
        if not campaign.orders:
            return dm.OrderID(1)
        last = max(campaign.orders.keys(), key=int)
        return dm.OrderID(int(last) + 1)

    def import_from_manifest(
        self,
        manifest: savegame.SaveManifest,
        *,
        assign_new_id: bool = True,
    ) -> dm.Campaign:
        """Persist a campaign described by a savegame manifest."""

        if assign_new_id:
            next_id = self._next_identifier()
            campaign = savegame.import_campaign_from_manifest(
                manifest, assign_new_id=True, next_id=int(next_id)
            )
            campaign.id = next_id
        else:
            campaign = manifest.campaign
        self._repository.save(campaign)
        return campaign

    def import_from_file(
        self, manifest_path: Path | str, *, assign_new_id: bool = True
    ) -> dm.Campaign:
        """Load a `.cataphract` archive and persist the contained campaign."""

        manifest = savegame.load_manifest(manifest_path)
        return self.import_from_manifest(manifest, assign_new_id=assign_new_id)

    def list_scenarios(self) -> list[dict[str, object]]:
        """Enumerate available scenario manifests."""

        if self._scenario_dir is None:
            return []
        summaries: list[dict[str, object]] = []
        for path in sorted(self._scenario_dir.glob("*.cataphract")):
            try:
                manifest = savegame.load_manifest(path)
            except (FileNotFoundError, json.JSONDecodeError):  # pragma: no cover - invalid archive
                continue
            summaries.append(
                {
                    "slug": path.name,
                    "kind": manifest.kind,
                    "metadata": manifest.metadata.model_dump(),
                }
            )
        return summaries

    def import_scenario(self, slug: str, *, assign_new_id: bool = True) -> dm.Campaign:
        """Load a scenario archive from the configured directory."""

        if self._scenario_dir is None:
            raise FileNotFoundError("Scenario directory not configured")
        manifest_path = self._scenario_dir / slug
        if not manifest_path.exists():
            raise FileNotFoundError(f"Scenario '{slug}' not found")
        return self.import_from_file(manifest_path, assign_new_id=assign_new_id)

    def export_campaign(
        self,
        campaign_id: dm.CampaignID,
        *,
        kind: savegame.SaveKind = savegame.SaveKind.SAVE,
        metadata: savegame.SaveMetadata | None = None,
        players: list[savegame.SavePlayer] | None = None,
        rules_overrides: dict[str, Any] | None = None,
    ) -> savegame.SaveManifest:
        """Produce a save manifest for the requested campaign."""

        campaign = self.get_campaign(campaign_id)
        return savegame.export_campaign(
            campaign,
            kind=kind,
            metadata=metadata,
            players=players,
            rules_overrides=rules_overrides,
        )

    @staticmethod
    def pending_orders(campaign: dm.Campaign) -> list[dm.Order]:
        return [
            order
            for order in campaign.orders.values()
            if order.status in (OrderStatus.PENDING, OrderStatus.EXECUTING)
        ]

    @staticmethod
    def to_summary_dict(campaign: dm.Campaign) -> dict[str, object]:
        """Return a JSON-friendly overview of a campaign."""

        pending = CampaignService.pending_orders(campaign)
        return {
            "id": int(campaign.id),
            "name": campaign.name,
            "start_date": campaign.start_date,
            "current_day": campaign.current_day,
            "current_part": str(campaign.current_part),
            "season": str(campaign.season),
            "status": campaign.status,
            "faction_count": len(campaign.factions),
            "commander_count": len(campaign.commanders),
            "army_count": len(campaign.armies),
            "pending_orders": len(pending),
        }

    @staticmethod
    def to_detail_dict(campaign: dm.Campaign) -> dict[str, object]:
        """Return a richer JSON-compatible representation for clients."""

        summary = CampaignService.to_summary_dict(campaign)
        summary.update(
            {
                "map": {
                    "hex_count": len(campaign.map.hexes),
                    "road_count": len(campaign.map.roads),
                    "river_crossing_count": len(campaign.map.river_crossings),
                },
                "armies": {
                    int(army_id): CampaignService.to_army_dict(campaign, army)
                    for army_id, army in campaign.armies.items()
                },
                "strongholds": {
                    int(stronghold_id): {
                        "type": stronghold.type,
                        "hex_id": int(stronghold.hex_id),
                        "controlling_faction_id": (
                            int(stronghold.controlling_faction_id)
                            if stronghold.controlling_faction_id is not None
                            else None
                        ),
                        "current_threshold": stronghold.current_threshold,
                    }
                    for stronghold_id, stronghold in campaign.strongholds.items()
                },
                "commanders": {
                    int(commander_id): {
                        "name": commander.name,
                        "faction_id": int(commander.faction_id),
                        "current_hex_id": int(commander.current_hex_id)
                        if commander.current_hex_id is not None
                        else None,
                    }
                    for commander_id, commander in campaign.commanders.items()
                },
                "orders": {
                    int(order_id): CampaignService.to_order_dict(order)
                    for order_id, order in campaign.orders.items()
                },
            }
        )
        return summary

    @staticmethod
    def to_army_dict(campaign: dm.Campaign, army: dm.Army) -> dict[str, object]:
        commander = campaign.commanders.get(army.commander_id)
        commander_name = commander.name if commander is not None else None
        faction_id = commander.faction_id if commander is not None else None
        return {
            "commander_id": int(army.commander_id),
            "commander_name": commander_name,
            "status": str(army.status),
            "current_hex_id": int(army.current_hex_id) if army.current_hex_id else None,
            "supplies_current": army.supplies_current,
            "supplies_capacity": army.supplies_capacity,
            "morale_current": army.morale_current,
            "movement_points_remaining": army.movement_points_remaining,
            "orders_queue": [int(order_id) for order_id in army.orders_queue],
            "faction_id": int(faction_id) if faction_id is not None else None,
        }

    @staticmethod
    def to_order_dict(order: dm.Order) -> dict[str, object]:
        issued = order.issued_at.isoformat()
        execute_at = order.execute_at.isoformat()
        return {
            "id": int(order.id),
            "army_id": int(order.army_id) if order.army_id is not None else None,
            "commander_id": int(order.commander_id),
            "order_type": order.order_type,
            "status": str(order.status),
            "priority": order.priority,
            "issued_at": issued,
            "execute_at": execute_at,
            "execute_day": order.execute_day,
            "execute_part": str(order.execute_part) if order.execute_part else None,
            "parameters": order.parameters,
            "result": order.result,
        }

    def list_armies(self, campaign: dm.Campaign) -> list[dict[str, object]]:
        return [
            {"id": int(army_id), **self.to_army_dict(campaign, army)}
            for army_id, army in sorted(campaign.armies.items(), key=lambda item: int(item[0]))
        ]

    def list_orders(
        self,
        campaign: dm.Campaign,
        *,
        statuses: set[OrderStatus] | None = None,
    ) -> list[dict[str, object]]:
        def _issued_key(order: dm.Order) -> float:
            issued_at = order.issued_at
            if issued_at.tzinfo is None:
                issued_at = issued_at.replace(tzinfo=UTC)
            return issued_at.timestamp()

        orders = sorted(
            campaign.orders.values(),
            key=lambda o: (
                o.execute_day if o.execute_day is not None else campaign.current_day,
                o.priority,
                _issued_key(o),
            ),
        )
        if statuses is not None:
            orders = [order for order in orders if order.status in statuses]
        return [self.to_order_dict(order) for order in orders]

    def create_order(self, campaign_id: dm.CampaignID, draft: OrderDraft) -> dm.Order:
        campaign = self.get_campaign(campaign_id)

        commander = campaign.commanders.get(draft.commander_id)
        if commander is None:
            raise ValueError(f"Commander {int(draft.commander_id)} not found")

        army = None
        if draft.army_id is not None:
            army = campaign.armies.get(draft.army_id)
            if army is None:
                raise ValueError(f"Army {int(draft.army_id)} not found")
            if army.commander_id != draft.commander_id:
                raise ValueError("Commander does not control the specified army")

        execute_day = draft.execute_day or campaign.current_day
        if execute_day < campaign.current_day:
            raise ValueError("execute_day cannot be in the past")

        order_id = self._next_order_identifier(campaign)
        issued_at = datetime.now(UTC)

        order = dm.Order(
            id=order_id,
            campaign_id=campaign.id,
            army_id=draft.army_id,
            commander_id=draft.commander_id,
            order_type=draft.order_type,
            parameters=draft.parameters or {},
            issued_at=issued_at,
            execute_at=issued_at,
            execute_day=execute_day,
            execute_part=draft.execute_part,
            status=OrderStatus.PENDING,
            priority=draft.priority,
        )

        campaign.orders[order_id] = order
        if army is not None and order_id not in army.orders_queue:
            army.orders_queue.append(order_id)

        self.save_campaign(campaign)
        return order

    def cancel_order(self, campaign_id: dm.CampaignID, order_id: dm.OrderID) -> dm.Order:
        campaign = self.get_campaign(campaign_id)
        order = campaign.orders.get(order_id)
        if order is None:
            raise ValueError(f"Order {int(order_id)} not found")

        if order.status in {OrderStatus.COMPLETED, OrderStatus.FAILED}:
            raise ValueError("Cannot cancel a resolved order")

        order.status = OrderStatus.CANCELLED
        order.result = {"detail": "cancelled via API"}

        if order.army_id is not None:
            army = campaign.armies.get(order.army_id)
            if army is not None:
                army.orders_queue = [oid for oid in army.orders_queue if oid != order_id]

        self.save_campaign(campaign)
        return order


class TickManager:
    """Background scheduler that advances campaigns using the rules engine."""

    MIN_INTERVAL_SECONDS = 0.1

    def __init__(
        self,
        repository: JsonCampaignRepository,
        *,
        rules: RulesConfig = DEFAULT_RULES,
        base_interval_seconds: float,
        debug_multiplier: float = 1.0,
    ) -> None:
        self._repository = repository
        self._rules = rules
        self._base_interval = max(base_interval_seconds, self.MIN_INTERVAL_SECONDS)
        self._debug_multiplier = max(debug_multiplier, 0.01)
        self._auto_campaigns: set[dm.CampaignID] = set()
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._advance_lock = asyncio.Lock()

    @property
    def interval_seconds(self) -> float:
        return max(self.MIN_INTERVAL_SECONDS, self._base_interval * self._debug_multiplier)

    @property
    def base_interval_seconds(self) -> float:
        return self._base_interval

    @property
    def debug_multiplier(self) -> float:
        return self._debug_multiplier

    def set_base_interval(self, seconds: float) -> None:
        self._base_interval = max(seconds, self.MIN_INTERVAL_SECONDS)

    def set_debug_multiplier(self, multiplier: float) -> None:
        self._debug_multiplier = max(multiplier, 0.01)

    def enabled_campaigns(self) -> set[dm.CampaignID]:
        return set(self._auto_campaigns)

    def is_enabled(self, campaign_id: dm.CampaignID) -> bool:
        return campaign_id in self._auto_campaigns

    async def set_enabled(self, campaign_id: dm.CampaignID, enabled: bool) -> None:
        if enabled:
            self._auto_campaigns.add(campaign_id)
            self._ensure_running()
        else:
            self._auto_campaigns.discard(campaign_id)
            if not self._auto_campaigns:
                await self.stop()

    def _ensure_running(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_loop(), name="cataphract-tick-loop")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._stop_event.set()
        await task
        self._task = None

    async def advance_now(self, campaign_id: dm.CampaignID, days: int = 1) -> None:
        if days <= 0:
            return
        async with self._advance_lock:
            success = await asyncio.to_thread(self._advance_campaign_sync, campaign_id, days)
        if not success:
            self._auto_campaigns.discard(campaign_id)

    async def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
                    break
                except TimeoutError:
                    pass
                await self._run_cycle()
        finally:
            self._task = None

    async def _run_cycle(self) -> None:
        if not self._auto_campaigns:
            return
        ids = list(self._auto_campaigns)
        async with self._advance_lock:
            for campaign_id in ids:
                success = await asyncio.to_thread(self._advance_campaign_sync, campaign_id, 1)
                if not success:
                    self._auto_campaigns.discard(campaign_id)

    def _advance_campaign_sync(self, campaign_id: dm.CampaignID, days: int) -> bool:
        try:
            campaign = self._repository.load(campaign_id)
        except FileNotFoundError:
            logger.warning(
                "campaign %s missing from repository; disabling autotick", int(campaign_id)
            )
            return False

        for _ in range(days):
            run_daily_tick(campaign, rules=self._rules)

        self._repository.save(campaign)
        return True


class ApiState:
    """Aggregated services shared by the FastAPI layer."""

    def __init__(
        self, *, settings: Settings | None = None, rules: RulesConfig = DEFAULT_RULES
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = JsonCampaignRepository(self.settings.data_dir)
        self.rules = rules
        self.campaigns = CampaignService(
            self.repository,
            scenario_dir=self.settings.scenarios_dir,
        )
        self.ticks = TickManager(
            self.repository,
            rules=rules,
            base_interval_seconds=self.settings.tick_interval_seconds,
            debug_multiplier=self.settings.debug_tick_speed_multiplier,
        )

    async def shutdown(self) -> None:
        await self.ticks.stop()


def build_state() -> ApiState:
    """Factory used by the API to initialize state."""

    return ApiState()

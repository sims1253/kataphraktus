"""Import and export helpers for Cataphract campaign save files."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from cataphract.domain import models as dm

CAMPAIGN_ADAPTER: TypeAdapter[dm.Campaign] = TypeAdapter(dm.Campaign)


class SaveKind(StrEnum):
    """Distinguish between templates and full running saves."""

    TEMPLATE = "template"
    SAVE = "save"


class PlayerRole(StrEnum):
    """Enumerate supported player roles."""

    ADMIN = "admin"
    CONTROLLER = "controller"
    OBSERVER = "observer"


class SavePlayer(BaseModel):
    """Describe a player account bundled with a save file."""

    id: int
    name: str
    role: PlayerRole
    faction_id: int | None = None


class SaveMetadata(BaseModel):
    """High-level information about the packaged scenario or save."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str | None = None
    author: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rules_version: str = "1.1"
    game_version: str = "0.2.0"


class SaveManifest(BaseModel):
    """Top-level manifest stored in a `.cataphract` archive."""

    format_version: int = 1
    kind: SaveKind
    metadata: SaveMetadata
    players: list[SavePlayer]
    campaign: dm.Campaign
    rules_overrides: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _convert_campaign(cls, values: dict[str, Any]) -> dict[str, Any]:
        raw = values.get("campaign")
        if raw is not None and not isinstance(raw, dm.Campaign):
            values["campaign"] = CAMPAIGN_ADAPTER.validate_python(raw)
        return values

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(*args, **kwargs)
        data["campaign"] = CAMPAIGN_ADAPTER.dump_python(self.campaign, mode="json")
        return data


MANIFEST_PATH = "cataphract/manifest.json"


def load_manifest(path: Path | str) -> SaveManifest:
    """Load a savegame manifest from a `.cataphract` archive."""

    zip_path = Path(path)
    with ZipFile(zip_path, "r") as archive:
        try:
            with archive.open(MANIFEST_PATH) as manifest_file:
                payload = json.load(manifest_file)
        except KeyError as exc:  # pragma: no cover - invalid archive
            raise FileNotFoundError("manifest.json not found in archive") from exc
    return SaveManifest.model_validate(payload)


def save_manifest(manifest: SaveManifest, path: Path | str) -> Path:
    """Write a manifest to a `.cataphract` archive."""

    payload = json.dumps(
        manifest.model_dump(mode="json", by_alias=True),
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_PATH, payload)
    return target


def import_campaign_from_manifest(
    manifest: SaveManifest,
    *,
    assign_new_id: bool = False,
    next_id: int | None = None,
) -> dm.Campaign:
    """Return a campaign instance derived from a saved manifest.

    Parameters
    ----------
    manifest:
        The loaded manifest describing the scenario/save.
    assign_new_id:
        When `True`, a new contiguous `CampaignID` is assigned, either using
        `next_id` or derived from the current value stored on the campaign.
    next_id:
        Optional explicit campaign identifier to use when `assign_new_id` is
        `True`.
    """

    campaign = manifest.campaign
    if assign_new_id:
        new_id = dm.CampaignID(next_id if next_id is not None else int(campaign.id) + 1)
        _reassign_campaign_id(campaign, new_id)
    return campaign


def export_campaign(
    campaign: dm.Campaign,
    *,
    kind: SaveKind = SaveKind.SAVE,
    metadata: SaveMetadata | None = None,
    players: list[SavePlayer] | None = None,
    rules_overrides: dict[str, Any] | None = None,
) -> SaveManifest:
    """Produce a manifest from an in-memory campaign."""

    return SaveManifest(
        kind=kind,
        metadata=metadata or SaveMetadata(name=campaign.name),
        players=players or [],
        campaign=campaign,
        rules_overrides=rules_overrides,
    )


def _reassign_campaign_id(campaign: dm.Campaign, new_id: dm.CampaignID) -> None:
    """Mutate a campaign graph to adopt a new identifier."""

    old_id = campaign.id
    if old_id == new_id:
        return
    campaign.id = new_id

    def _swap(mapping: dict, attr: str | None = None) -> None:
        for obj in mapping.values():
            if hasattr(obj, "campaign_id"):
                obj.campaign_id = new_id
            if attr and hasattr(obj, attr):
                nested = getattr(obj, attr)
                if isinstance(nested, dict):
                    _swap(nested)

    for hexagon in campaign.map.hexes.values():
        hexagon.campaign_id = new_id

    _swap(campaign.factions)
    _swap(campaign.commanders)
    _swap(campaign.armies)
    _swap(campaign.strongholds)
    _swap(campaign.ships)
    _swap(campaign.unit_types)
    _swap(campaign.sieges)
    _swap(campaign.battles)
    _swap(campaign.mercenary_companies)
    _swap(campaign.mercenary_contracts)
    _swap(campaign.operations)
    _swap(campaign.orders)
    _swap(campaign.messages)
    for event in campaign.events:
        event.campaign_id = new_id
    for weather in campaign.weather.values():
        weather.campaign_id = new_id

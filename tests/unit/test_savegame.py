"""Tests for the savegame import/export helpers."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from uuid import UUID

import pytest

from cataphract.domain import enums as de
from cataphract.domain import models as dm
from cataphract.savegame import (
    SaveKind,
    SaveManifest,
    SaveMetadata,
    SavePlayer,
    PlayerRole,
    export_campaign,
    import_campaign_from_manifest,
    load_manifest,
    save_manifest,
)


def _sample_campaign() -> dm.Campaign:
    campaign = dm.Campaign(
        id=dm.CampaignID(1),
        name="Sample",
        start_date=date(1325, 3, 1),
        current_day=0,
        current_part=de.DayPart.MORNING,
        season=de.Season.SPRING,
        status="active",
    )

    hex_main = dm.Hex(
        id=dm.HexID(1),
        campaign_id=campaign.id,
        q=0,
        r=0,
        terrain="flatland",
        settlement=40,
        controlling_faction_id=dm.FactionID(1),
    )
    campaign.map.hexes[hex_main.id] = hex_main

    faction = dm.Faction(
        id=dm.FactionID(1),
        campaign_id=campaign.id,
        name="Imperials",
        color="#AA0000",
    )
    campaign.factions[faction.id] = faction

    unit_type = dm.UnitType(
        id=dm.UnitTypeID(1),
        name="Cohort",
        category="infantry",
        battle_multiplier=1.0,
        supply_cost_per_day=4,
        can_travel_offroad=True,
    )
    campaign.unit_types[unit_type.id] = unit_type

    commander = dm.Commander(
        id=dm.CommanderID(1),
        campaign_id=campaign.id,
        name="Marcus",
        faction_id=faction.id,
        age=38,
        current_hex_id=hex_main.id,
    )
    campaign.commanders[commander.id] = commander

    detachment = dm.Detachment(id=dm.DetachmentID(1), unit_type_id=unit_type.id, soldiers=500)
    army = dm.Army(
        id=dm.ArmyID(1),
        campaign_id=campaign.id,
        commander_id=commander.id,
        current_hex_id=hex_main.id,
        detachments=[detachment],
        status=de.ArmyStatus.IDLE,
        supplies_current=200,
        supplies_capacity=400,
        daily_supply_consumption=20,
    )
    campaign.armies[army.id] = army

    return campaign


def test_roundtrip_save_manifest(tmp_path: Path):
    campaign = _sample_campaign()
    manifest = export_campaign(
        campaign,
        kind=SaveKind.TEMPLATE,
        metadata=SaveMetadata(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            name="Example",
            author="Unit Test",
        ),
        players=[SavePlayer(id=1, name="Admin", role=PlayerRole.ADMIN)],
    )

    archive_path = tmp_path / "sample.cataphract"
    save_manifest(manifest, archive_path)

    loaded = load_manifest(archive_path)
    assert loaded.kind is SaveKind.TEMPLATE
    assert loaded.metadata.name == "Example"
    assert loaded.players[0].role is PlayerRole.ADMIN
    assert loaded.campaign == campaign


def test_reassign_campaign_identifier():
    manifest = export_campaign(_sample_campaign(), kind=SaveKind.SAVE)
    imported = import_campaign_from_manifest(manifest, assign_new_id=True, next_id=42)
    assert int(imported.id) == 42
    for faction in imported.factions.values():
        assert faction.campaign_id == imported.id
    for hexagon in imported.map.hexes.values():
        assert hexagon.campaign_id == imported.id


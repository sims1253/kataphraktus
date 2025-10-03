from datetime import date
from typing import Any

import pytest

from src.cataphract.schemas import (
    ArmyCreate,
    ArmyRead,
    ArmyUpdate,
    CommanderCreate,
    CommanderRead,
    DetachmentCreate,
    DetachmentRead,
    FactionCreate,
    FactionRead,
    GameCreate,
    GameRead,
    GameUpdate,
    HexRead,
)


@pytest.fixture
def sample_game_data() -> dict[str, Any]:
    return {
        "name": "Test Game",
        "start_date": date(2025, 10, 1),
        "map_width": 50,
        "map_height": 50,
        "season": "fall",
    }


def test_game_create(sample_game_data):
    game = GameCreate(**sample_game_data)
    assert game.name == "Test Game"
    assert game.current_day == 0
    json_data = game.model_dump()
    assert "name" in json_data
    assert "id" not in json_data


def test_game_read():
    sample_game_data = {
        "name": "Test Game",
        "start_date": date(2025, 10, 1),
        "map_width": 50,
        "map_height": 50,
        "season": "fall",
        "current_day": 5,
        "current_day_part": "midday",
    }
    data = {**sample_game_data, "id": 1}
    game = GameRead(**data)
    assert game.id == 1
    assert game.current_day == 5
    json_data = game.model_dump()
    assert "id" in json_data


def test_game_update():
    update = GameUpdate(name="Updated Game", status="active")
    assert update.name == "Updated Game"
    json_data = update.model_dump(exclude_unset=True)
    assert "name" in json_data
    assert "status" in json_data


def test_hex_read():
    hex_data = {
        "id": 1,
        "game_id": 1,
        "q": 0,
        "r": 0,
        "terrain_type": "flatland",
        "is_good_country": True,
        "has_road": True,
        "settlement_score": 20,
        "river_sides": ["NE"],
        "foraging_times_remaining": 3,
        "is_torched": False,
        "last_foraged_day": 10,
        "last_recruited_day": None,
        "last_torched_day": None,
        "controlling_faction_id": 1,
        "last_control_change_day": 5,
    }
    hex_obj = HexRead(**hex_data)
    assert hex_obj.id == 1
    assert hex_obj.terrain_type == "flatland"
    json_data = hex_obj.model_dump()
    assert "id" in json_data


def test_faction_create():
    faction_data = {
        "game_id": 1,
        "name": "Test Faction",
        "color": "#FF0000",
        "description": "A test faction",
    }
    faction = FactionCreate(**faction_data)
    assert faction.name == "Test Faction"
    json_data = faction.model_dump()
    assert "game_id" in json_data
    assert "id" not in json_data


def test_faction_read():
    faction_data = {
        "game_id": 1,
        "name": "Test Faction",
        "color": "#FF0000",
        "description": "A test faction",
    }
    data = {**faction_data, "id": 1}
    faction = FactionRead(**data)
    assert faction.id == 1
    json_data = faction.model_dump()
    assert "id" in json_data


def test_commander_create():
    commander_data = {
        "game_id": 1,
        "faction_id": 1,
        "name": "Test Commander",
        "age": 25,
    }
    commander = CommanderCreate(**commander_data)
    assert commander.name == "Test Commander"
    assert commander.age == 25
    json_data = commander.model_dump()
    assert "id" not in json_data


def test_commander_read():
    commander_data = {
        "game_id": 1,
        "faction_id": 1,
        "name": "Test Commander",
        "age": 25,
    }
    data = {**commander_data, "id": 1}
    commander = CommanderRead(**data)
    assert commander.id == 1
    json_data = commander.model_dump()
    assert "id" in json_data


def test_army_create():
    army_data = {
        "game_id": 1,
        "commander_id": 1,
        "current_hex_id": 1,
        "status": "idle",
    }
    army = ArmyCreate(**army_data)
    assert army.status == "idle"
    assert army.morale_current == 9
    json_data = army.model_dump()
    assert "id" not in json_data


def test_army_read():
    army_data = {
        "game_id": 1,
        "commander_id": 1,
        "current_hex_id": 1,
        "status": "idle",
    }
    data = {**army_data, "id": 1}
    army = ArmyRead(**data)
    assert army.id == 1
    json_data = army.model_dump()
    assert "id" in json_data


def test_army_update():
    update = ArmyUpdate(status="marching", morale_current=8)
    assert update.status == "marching"
    json_data = update.model_dump(exclude_unset=True)
    assert "status" in json_data


def test_detachment_create():
    detachment_data = {
        "army_id": 1,
        "unit_type_id": 1,
        "name": "Test Detachment",
        "soldier_count": 100,
        "formation_position": 1,
    }
    detachment = DetachmentCreate(**detachment_data)
    assert detachment.name == "Test Detachment"
    assert detachment.soldier_count == 100
    json_data = detachment.model_dump()
    assert "id" not in json_data


def test_detachment_read():
    detachment_data = {
        "army_id": 1,
        "unit_type_id": 1,
        "name": "Test Detachment",
        "soldier_count": 100,
        "formation_position": 1,
    }
    data = {**detachment_data, "id": 1}
    detachment = DetachmentRead(**data)
    assert detachment.id == 1
    json_data = detachment.model_dump()
    assert "id" in json_data

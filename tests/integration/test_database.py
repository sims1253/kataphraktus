"""Integration tests for database functionality.

Tests database initialization, migrations, session management, and seed data.
Uses the main cataphract.db database file for testing.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from cataphract.database import (
    check_database_health,
    count_rows,
    get_session_factory,
    get_table_names,
)
from cataphract.models import Trait, UnitType


@pytest.fixture(scope="module")
def project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def test_db(project_root):
    """Use the main cataphract.db database (should already be created)."""
    db_path = project_root / "cataphract.db"

    # Ensure database exists with migrations applied
    if not db_path.exists():
        # Run migrations using the current interpreter to avoid external wrappers
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=False,
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Migration failed: {result.stderr}")

    return str(db_path)


@pytest.fixture
def test_session(test_db):  # noqa: ARG001
    """Create a test database session."""
    SessionLocal = get_session_factory()  # noqa: N806
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_database_creation(self, test_db):
        """Test that database file is created."""
        db_path = Path(test_db)
        assert db_path.exists()
        assert db_path.stat().st_size > 0

    def test_all_tables_created(self, test_db):  # noqa: ARG002
        """Test that all expected tables are created."""
        tables = get_table_names()

        # Expected tables (31 game tables + alembic_version)
        expected_tables = {
            "alembic_version",
            "armies",
            "battles",
            "commander_traits",
            "commander_visibility",
            "commanders",
            "crossing_queues",
            "detachments",
            "events",
            "faction_relations",
            "factions",
            "games",
            "hexes",
            "map_features",
            "mercenary_companies",
            "mercenary_contracts",
            "message_legs",
            "messages",
            "movement_legs",
            "operations",
            "orders",
            "orders_log_entries",
            "players",
            "river_crossings",
            "road_edges",
            "ship_types",
            "ships",
            "sieges",
            "strongholds",
            "traits",
            "unit_types",
            "weather",
        }

        assert set(tables) == expected_tables

    def test_database_health_check(self, test_db):  # noqa: ARG002
        """Test database health check function."""
        assert check_database_health() is True


class TestSeedData:
    """Tests for seed data population."""

    def test_traits_seeded(self, test_session):
        """Test that traits are properly seeded."""
        traits_count = count_rows(test_session, "traits")
        assert traits_count == 20

    def test_unit_types_seeded(self, test_session):
        """Test that unit types are properly seeded."""
        unit_types_count = count_rows(test_session, "unit_types")
        assert unit_types_count == 7

    def test_trait_data_integrity(self, test_session):
        """Test that trait data has proper structure."""
        trait = test_session.query(Trait).filter_by(name="beloved").first()

        assert trait is not None
        assert trait.description == "+1 resting morale"
        assert trait.ruleset_version == "1.1"
        assert isinstance(trait.scope_tags, list)
        assert "morale" in trait.scope_tags
        assert isinstance(trait.effect_data, dict)
        assert trait.effect_data is not None

    def test_unit_type_data_integrity(self, test_session):
        """Test that unit type data has proper structure."""
        infantry = test_session.query(UnitType).filter_by(name="infantry").first()

        assert infantry is not None
        assert infantry.category == "infantry"
        assert infantry.battle_multiplier == 1.0
        assert infantry.supply_cost_per_day == 1
        assert infantry.can_travel_offroad is True

    def test_all_traits_present(self, test_session):
        """Test that all expected traits are present."""
        expected_traits = {
            "beloved",
            "brutal",
            "commando",
            "crusader",
            "defensive_engineer",
            "duelist",
            "guardian",
            "honorable",
            "ironsides",
            "logistician",
            "outrider",
            "poet",
            "raider",
            "ranger",
            "scholar",
            "siege_engineer",
            "spartan",
            "stubborn",
            "vanquisher",
            "veteran",
        }

        traits = test_session.query(Trait).all()
        trait_names = {t.name for t in traits}

        assert trait_names == expected_traits

    def test_all_unit_types_present(self, test_session):
        """Test that all expected unit types are present."""
        expected_unit_types = {
            "infantry",
            "heavy_infantry",
            "cavalry",
            "heavy_cavalry",
            "skirmisher",
            "siege_engines",
            "wizard",
        }

        unit_types = test_session.query(UnitType).all()
        unit_type_names = {ut.name for ut in unit_types}

        assert unit_type_names == expected_unit_types


class TestSessionManagement:
    """Tests for session factory and management."""

    def test_session_creation(self, test_db):  # noqa: ARG002
        """Test that sessions can be created."""
        SessionLocal = get_session_factory()  # noqa: N806
        session = SessionLocal()

        assert session is not None
        session.close()

    def test_session_transaction(self, test_session):
        """Test that transactions work properly."""
        import uuid  # noqa: PLC0415

        # Add a trait with unique name
        unique_name = f"test_trait_{uuid.uuid4().hex[:8]}"
        trait = Trait(
            name=unique_name,
            description="Test trait",
            scope_tags=["test"],
            effect_data={},
        )
        test_session.add(trait)
        test_session.commit()

        # Verify it was added
        found_trait = test_session.query(Trait).filter_by(name=unique_name).first()
        assert found_trait is not None
        assert found_trait.description == "Test trait"

        # Clean up
        test_session.delete(found_trait)
        test_session.commit()

    def test_session_rollback(self, test_session):
        """Test that rollback works properly."""
        initial_count = test_session.query(Trait).count()

        # Add a trait but rollback
        trait = Trait(
            name="rollback_trait",
            description="This should be rolled back",
            scope_tags=["test"],
            effect_data={},
        )
        test_session.add(trait)
        test_session.rollback()

        # Verify it was not added
        final_count = test_session.query(Trait).count()
        assert final_count == initial_count

        found_trait = test_session.query(Trait).filter_by(name="rollback_trait").first()
        assert found_trait is None


class TestMigrations:
    """Tests for Alembic migrations."""

    def test_migration_version_recorded(self, test_session):
        """Test that migration version is recorded (non-empty)."""
        result = test_session.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar_one()

        assert version is not None
        assert isinstance(version, str)
        assert len(version) > 0

    def test_migration_idempotent(self, project_root):
        """Test that migration can be applied multiple times."""
        # Apply migration twice - should not raise error
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                check=False,
                cwd=project_root,
                capture_output=True,
            )
            assert result.returncode == 0


class TestSQLiteConfiguration:
    """Tests for SQLite-specific configuration."""

    def test_wal_mode_enabled(self, test_session):
        """Test that WAL mode is enabled."""
        result = test_session.execute(text("PRAGMA journal_mode"))
        journal_mode = result.scalar()

        assert journal_mode.lower() == "wal"

    def test_foreign_keys_enabled(self, test_session):
        """Test that foreign keys are enabled."""
        result = test_session.execute(text("PRAGMA foreign_keys"))
        foreign_keys = result.scalar()

        assert foreign_keys == 1

    def test_synchronous_mode(self, test_session):
        """Test that synchronous mode is set to NORMAL."""
        result = test_session.execute(text("PRAGMA synchronous"))
        sync_mode = result.scalar()

        # 1 = NORMAL
        assert sync_mode == 1


class TestDatabaseUtilities:
    """Tests for database utility functions."""

    def test_count_rows(self, test_session):
        """Test the count_rows utility function."""
        count = count_rows(test_session, "traits")
        # Should be at least 20 (the seeded traits), may have test traits
        assert count >= 20

    def test_count_rows_invalid_table(self, test_session):
        """Test that count_rows rejects invalid table names."""
        with pytest.raises(ValueError, match="Invalid table name"):
            count_rows(test_session, "malicious_table'; DROP TABLE users; --")

    def test_get_table_names(self, test_db):  # noqa: ARG002
        """Test the get_table_names utility function."""
        tables = get_table_names()

        assert isinstance(tables, list)
        assert len(tables) == 32
        assert "traits" in tables
        assert "unit_types" in tables


class TestDatabaseIndexes:
    """Tests for database indexes."""

    def test_traits_content_pack_index(self, test_session):
        """Test that traits content_pack index exists."""
        result = test_session.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='traits' AND name='idx_traits_content_pack'"
            )
        )
        assert result.scalar() is not None

    def test_unit_types_content_pack_index(self, test_session):
        """Test that unit_types content_pack index exists."""
        result = test_session.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='unit_types' AND name='idx_unit_types_content_pack'"
            )
        )
        assert result.scalar() is not None


class TestDatabaseConstraints:
    """Tests for database constraints."""

    def test_trait_unique_name(self, test_session):
        """Test that trait names must be unique."""
        trait = Trait(
            name="beloved",  # Duplicate name
            description="Duplicate",
            scope_tags=["test"],
            effect_data={},
        )
        test_session.add(trait)

        with pytest.raises(Exception):  # noqa: B017, PT011
            test_session.commit()

        test_session.rollback()

    def test_unit_type_unique_name(self, test_session):
        """Test that unit type names must be unique."""
        unit_type = UnitType(
            name="infantry",  # Duplicate name
            category="infantry",
            battle_multiplier=1.0,
            supply_cost_per_day=1,
            can_travel_offroad=True,
        )
        test_session.add(unit_type)

        with pytest.raises(Exception):  # noqa: B017, PT011
            test_session.commit()

        test_session.rollback()

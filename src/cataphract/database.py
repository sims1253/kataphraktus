"""Database connection and session management.

This module provides database connection management, session factories,
and utility functions for database operations.
"""

import subprocess
from collections.abc import Generator
from contextlib import suppress
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from cataphract.config import get_settings
from cataphract.models import Base


def _configure_sqlite_wal(
    dbapi_connection: Any, connection_record: Any  # noqa: ARG001
) -> None:
    """Configure SQLite to use WAL mode for better concurrency.

    Args:
        dbapi_connection: The DBAPI connection
        connection_record: Connection record (required by SQLAlchemy event API)

    Note:
        WAL mode provides better concurrency for SQLite databases by allowing
        readers and writers to operate simultaneously.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine() -> Engine:
    """Create and configure the database engine.

    Returns:
        Engine: Configured SQLAlchemy engine

    Note:
        For SQLite databases, automatically configures WAL mode and foreign keys.
    """
    settings = get_settings()

    if settings.DATABASE_URL.startswith("sqlite"):
        # SQLite engine: simpler pooling, enable SQLite pragmas on connect
        engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            pool_pre_ping=True,
        )
        event.listen(engine, "connect", _configure_sqlite_wal)
    else:
        # Non-SQLite (e.g., PostgreSQL): honor pool settings for production use
        engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            pool_pre_ping=True,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        )

    return engine


# Global engine and session factory
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Get or create the global database engine.

    Returns:
        Engine: The SQLAlchemy engine instance
    """
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Get or create the global session factory.

    Returns:
        sessionmaker: Session factory for creating database sessions
    """
    global _SessionLocal  # noqa: PLW0603
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
    return _SessionLocal


def get_db() -> Generator[Session]:
    """FastAPI dependency for getting database sessions.

    This generator function creates a database session and ensures it's
    properly closed after the request completes.

    Yields:
        Database session

    Example:
        ```python
        @app.get("/games")
        def get_games(db: Session = Depends(get_db)):
            return db.query(Game).all()
        ```
    """
    SessionLocal = get_session_factory()  # noqa: N806
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize the database by creating all tables.

    Note:
        This creates tables directly without migrations. For production,
        use alembic migrations instead.
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def check_database_health() -> bool:
    """Check if the database is accessible and valid.

    Returns:
        bool: True if database is healthy, False otherwise

    Example:
        ```python
        if not check_database_health():
            print("Database is not accessible!")
        ```
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def reset_database() -> None:
    """Fully reset the database and re-apply migrations.

    Warning:
        This will DELETE ALL DATA in the database. Use only for testing!

    Behavior:
        - For SQLite file databases: remove the database file (if not :memory:)
        - For other databases: run "alembic downgrade base" then "alembic upgrade head"
    """
    settings = get_settings()
    project_root = Path(__file__).parent.parent.parent

    # Dispose any existing engine/connection before destructive actions
    global _engine, _SessionLocal  # noqa: PLW0603
    if _engine is not None:
        with suppress(Exception):
            _engine.dispose()
    _engine = None
    _SessionLocal = None

    if settings.DATABASE_URL.startswith("sqlite"):
        # Handle sqlite:///path or sqlite:////abs/path
        url = settings.DATABASE_URL
        db_path = url.replace("sqlite:///", "")
        if db_path and db_path != ":memory:":
            db_file = Path(db_path)
            # If relative, consider project root
            if not db_file.is_absolute():
                db_file = project_root / db_file
            if db_file.exists():
                db_file.unlink()

        # Fresh DB: just upgrade head to create everything
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            check=True,
            cwd=project_root,
        )
        return

    # Non-SQLite: use alembic to recreate schema
    subprocess.run(
        ["uv", "run", "alembic", "downgrade", "base"],
        check=True,
        cwd=project_root,
    )
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        check=True,
        cwd=project_root,
    )


def get_table_names() -> list[str]:
    """Get list of all table names in the database.

    Returns:
        list[str]: List of table names

    Example:
        ```python
        tables = get_table_names()
        print(f"Database has {len(tables)} tables")
        ```
    """
    engine = get_engine()
    inspector = inspect(engine)
    return inspector.get_table_names()


def count_rows(session: Session, table_name: str) -> int:
    """Count rows in a specific table.

    Args:
        session: Database session
        table_name: Name of the table to count.
                   Must be a valid table in the schema.

    Returns:
        int: Number of rows in the table

    Raises:
        ValueError: If table_name is not a valid table in the schema

    Example:
        ```python
        with Session(engine) as session:
            trait_count = count_rows(session, "traits")
            print(f"Found {trait_count} traits")
        ```
    """
    # Validate table_name against known tables
    if table_name not in Base.metadata.tables:
        valid_tables = sorted(Base.metadata.tables.keys())
        raise ValueError(
            f"Invalid table name: {table_name}. Valid tables: {', '.join(valid_tables)}"
        )

    # Use ORM-based counting for safety
    table = Base.metadata.tables[table_name]
    result = session.execute(select(func.count()).select_from(table)).scalar()
    return result or 0

# Cataphract Game System

Asynchronous, real-time medieval-fantasy operational wargame focused on logistics,
communication delays, and command under uncertainty.

## Features

- Operational command with delayed, fallible communications
- Logistics-first gameplay (foraging, supply, column length, harrying)
- Simple resolution mechanics with deterministic RNG + audit trail
- Roads-as-graph movement and river crossing constraints
- FastAPI backend, SQLAlchemy ORM, Alembic migrations
- Extensive tests including property-based tests

## Quick Start

### Prerequisites

- Python 3.13+
- uv (Python package manager)
- SQLite3

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/cataphract.git
cd cataphract

# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Run tests
uv run pytest

# Start the development server
uv run uvicorn cataphract.main:app --reload
```

### Docker

```bash
# Build and run with Docker Compose
docker compose -f docker/docker-compose.yml up --build

# Or build the Docker image manually
docker build -f docker/Dockerfile -t cataphract:latest .
docker run -p 8000:8000 cataphract:latest
```

## Development

### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_models.py

# Run with verbose output
uv run pytest -v
```

### Code Quality

```bash
# Run linter
ruff check src/ tests/

# Format code
ruff format src/ tests/

# Type checking (experimental)
uv run ty check src/cataphract/
```

### Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback migration
uv run alembic downgrade -1
```

## Project Structure

```
cataphract/
  src/cataphract/       # Main application code
    models/             # SQLAlchemy models
    api/                # API routes (future)
    database.py         # Database configuration
    config.py           # Application configuration
    main.py             # FastAPI application
  tests/                # Test suite
  alembic/              # Database migrations
  docker/               # Docker configuration
  pyproject.toml        # Project dependencies
```

## Using PostgreSQL (Optional)

Set `DATABASE_URL` to a PostgreSQL DSN and the app will use production-grade pooling:

```bash
export DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/cataphract
export DATABASE_POOL_SIZE=10
export DATABASE_MAX_OVERFLOW=20
export DATABASE_POOL_RECYCLE=1800
export DATABASE_POOL_TIMEOUT=30
```

Install a PostgreSQL driver when using Postgres (example using uv):

```bash
uv add psycopg[binary]
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

See LICENSE file for details.

## Documentation

For detailed game rules and mechanics, see `CATAPHRACT Ruleset.md`.

For architecture details, see `ARCHITECTURE.md`.

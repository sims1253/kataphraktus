#!/bin/bash
set -e

echo "Running database migrations..."
uv run alembic upgrade head

echo "Starting Cataphract API server..."
exec uvicorn cataphract.main:app --host 0.0.0.0 --port 8000

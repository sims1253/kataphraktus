# Docker Setup for Cataphract

## Quick Start

1. Build and start services:
   ```bash
   cd docker
   docker-compose up --build
   ```

2. Access the API:
   - Health check: http://localhost:8000/health
   - API docs: http://localhost:8000/docs
   - Root: http://localhost:8000

3. Stop services:
   ```bash
   docker-compose down
   ```

## Development Mode

For hot reload during development:
```bash
docker-compose up
```

The `src/` directory is mounted as a volume for live code updates.

## Production Mode

Build and run in detached mode:
```bash
docker-compose up -d --build
```

View logs:
```bash
docker-compose logs -f app
```

## Services

- **app**: Cataphract API server (port 8000)
- **redis**: Redis for sessions/WebSocket (port 6379)

## Volumes

- `cataphract-data`: Persistent SQLite database
- `redis-data`: Redis persistence

## Health Checks

Both services include health checks:
```bash
docker-compose ps
```

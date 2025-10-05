# Cataphract Commandery UI

A parchment-toned React + Vite single-page interface that talks to the
Cataphract API.  It provides campaign oversight, tick orchestration, and the
full order ledger with tooling for every order type.

## Features

- **Campaign Ledger** – list, create, and open campaigns.
- **Chronomancer Panel** – advance time manually or configure debug-friendly
  auto-tick cadence.
- **Army Roster** – inspect supplies, morale, and statuses; select hosts to
  issue directives.
- **Order Builder** – guided forms (with advanced options) for all order
  handlers, including movement leg editors and JSON descriptors where needed.
- **Order Ledger** – filter by status, review parameters/results, cancel
  pending directives.

## Stack

- React 18 with TypeScript
- Vite for dev server and bundling
- React Query for data fetching/caching
- CSS modules with custom medieval/retro theming (Unifraktur + VT323)

## Developing

```bash
cd frontend
npm install
npm run dev
```

The dev server expects the API at `http://localhost:8000`.  Override by setting
`VITE_API_BASE_URL`.

### End-to-end tests

Playwright drives the SPA against a real API instance.

```bash
cd frontend
npm install         # if not already done
npx playwright install
npm run test:e2e
```

The runner starts a temporary FastAPI server on port 8001 and launches the Vite
dev server with `VITE_API_BASE_URL` pointed at it.  Use `npm run test:e2e:headed`
or `npm run test:e2e:ui` for interactive debugging.

To exercise the Docker deployment stack instead, run:

```bash
npm run test:e2e:docker
```

This builds and starts the containers defined in `docker/docker-compose.yml`
before executing the same browser suite against the live stack.

## Building

```bash
npm run build
```

Outputs to `frontend/dist`.  Serve the generated files behind whichever web
server you prefer.

## Testing

At present the UI relies on the backend unit tests; hook up Vitest or Playwright
as narratives evolve.

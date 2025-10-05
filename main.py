"""Development entrypoint for the Cataphract HTTP API."""

from __future__ import annotations

import argparse

import uvicorn

from cataphract.api.app import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Cataphract API server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="TCP port to listen on")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable autoreload (dev mode)",
    )
    args = parser.parse_args()

    if args.reload:
        uvicorn.run(
            "cataphract.api.app:app",
            host=args.host,
            port=args.port,
            reload=True,
            factory=False,
        )
    else:
        uvicorn.run(app, host=args.host, port=args.port, reload=False, factory=False)


if __name__ == "__main__":
    main()

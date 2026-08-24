"""Local command-line entry points."""

import argparse

import uvicorn

from tickeye.config import get_settings


def main() -> None:
    """Run the local TickEye API and built frontend."""

    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the TickEye local web application")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        "tickeye.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )

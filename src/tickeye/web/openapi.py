"""Export the backend OpenAPI schema for frontend type generation."""

import argparse
import json
from pathlib import Path

from tickeye.web.app import create_app


def export_openapi(destination: Path) -> None:
    """Write the deterministic API contract to the requested path."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export TickEye's OpenAPI schema")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    export_openapi(args.destination)

"""Serve the built React application without a separate web server."""

from mimetypes import guess_type
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import Response


def mount_frontend(app: FastAPI, dist_dir: Path) -> bool:
    """Mount a Vite build when present and leave API-only development untouched."""

    index_file = dist_dir / "index.html"
    if not index_file.is_file():
        return False

    resolved_dist = dist_dir.resolve()
    resolved_index = index_file.resolve()

    def file_response(path: Path, *, cache: bool) -> Response:
        media_type = guess_type(path.name)[0] or "application/octet-stream"
        cache_control = "public, max-age=31536000, immutable" if cache else "no-cache"
        return Response(
            content=path.read_bytes(),
            media_type=media_type,
            headers={"Cache-Control": cache_control},
        )

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API endpoint not found.",
            )
        candidate = (resolved_dist / path).resolve()
        if candidate.is_relative_to(resolved_dist) and candidate.is_file():
            return file_response(candidate, cache=path.startswith("assets/"))
        return file_response(resolved_index, cache=False)

    return True

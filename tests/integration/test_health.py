from pathlib import Path

import httpx2
import pytest

from tickeye.config import Settings
from tickeye.web.app import create_app

pytestmark = pytest.mark.anyio


def build_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'tickeye.db'}",
        frontend_dist_dir=tmp_path / "missing-frontend",
        cors_origins=("http://localhost:5173",),
    )


async def test_health_checks_the_database(tmp_path: Path) -> None:
    app = create_app(build_test_settings(tmp_path))
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    app.state.engine.dispose()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "tickeye-api",
        "version": "2.0.0.dev0",
        "database": {"status": "ok"},
    }
    assert (tmp_path / "tickeye.db").is_file()


async def test_openapi_contains_health_contract(tmp_path: Path) -> None:
    app = create_app(build_test_settings(tmp_path))
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
        missing_response = await client.get("/api/v1/not-found")
    app.state.engine.dispose()

    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]
    assert missing_response.json() == {
        "error": {"code": "http_error", "message": "Not Found"}
    }


async def test_production_app_serves_frontend_and_spa_routes(tmp_path: Path) -> None:
    frontend_dist = tmp_path / "dist"
    assets_dir = frontend_dist / "assets"
    assets_dir.mkdir(parents=True)
    (frontend_dist / "index.html").write_text("<h1>TickEye</h1>", encoding="utf-8")
    (assets_dir / "app.js").write_text("export {}", encoding="utf-8")

    settings = build_test_settings(tmp_path)
    settings.frontend_dist_dir = frontend_dist
    app = create_app(settings)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        root_response = await client.get("/")
        route_response = await client.get("/portfolio/current")
        asset_response = await client.get("/assets/app.js")
        health_response = await client.get("/api/v1/health")
        missing_api_response = await client.get("/api/v1/not-found")
    app.state.engine.dispose()

    assert root_response.text == "<h1>TickEye</h1>"
    assert route_response.text == "<h1>TickEye</h1>"
    assert asset_response.text == "export {}"
    assert health_response.json()["status"] == "ok"
    assert missing_api_response.status_code == 404
    assert missing_api_response.json() == {
        "error": {"code": "http_error", "message": "API endpoint not found."}
    }

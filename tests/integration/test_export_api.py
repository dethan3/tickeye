from pathlib import Path

import httpx2
import pytest

from tests.integration.test_risk_api import build_risk_app, positions_payload
from tests.integration.test_watchlist_api import candidate_payload

pytestmark = pytest.mark.anyio


async def test_export_contains_user_facts_and_excludes_rebuildable_caches(
    tmp_path: Path,
) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.put(
            "/api/v1/portfolio/positions", json=positions_payload()
        )
        instrument_id = next(
            item["instrument_id"]
            for item in created.json()["data"]["positions"]
            if item["code"] == "510300"
        )
        group = await client.post("/api/v1/watchlists", json={"name": "待比较"})
        watchlist_id = group.json()["data"]["items"][0]["watchlist_id"]
        watched = await client.post(
            f"/api/v1/watchlists/{watchlist_id}/items",
            json=candidate_payload(),
        )
        candidate_id = watched.json()["data"]["items"][0]["items"][0][
            "instrument_id"
        ]
        await client.put(
            "/api/v1/policies",
            json={
                "expected_revision": 0,
                "rules": [
                    {
                        "rule_type": "instrument_max_weight",
                        "subject_key": str(instrument_id),
                        "threshold": "0.60",
                        "tolerance": None,
                        "warning_ratio": "0.20",
                        "enabled": True,
                    }
                ],
            },
        )
        await client.post(
            "/api/v1/market-data/refresh", json={"instrument_ids": None}
        )
        await client.post(
            "/api/v1/scenarios",
            json={"name": "候选比较", "candidate_instrument_id": candidate_id},
        )
        await client.post("/api/v1/risk/recalculate")
        exported = await client.get("/api/v1/export")

    app.state.engine.dispose()
    body = exported.json()
    assert exported.status_code == 200
    assert exported.headers["content-disposition"] == (
        'attachment; filename="tickeye-user-data.json"'
    )
    assert body["schema_version"] == "tickeye-user-data-v1"
    assert {item["code"] for item in body["data"]["positions"]} == {
        "510300",
        "CASH-CNY",
    }
    assert body["data"]["watchlists"][0]["items"][0]["instrument"]["code"] == (
        "159915"
    )
    assert body["data"]["policies"][0]["threshold"] == "0.60000000"
    assert body["data"]["scenarios"][0]["candidate_instrument_id"] == candidate_id
    assert "market_data_cache" in body["excluded_data"]
    assert "market_data" not in body["data"]
    assert "risk_snapshots" not in body["data"]

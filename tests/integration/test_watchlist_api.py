from pathlib import Path

import httpx2
import pytest
from sqlalchemy import func, select

from tests.integration.test_risk_api import build_risk_app, positions_payload
from tickeye.infrastructure.db import PositionRecord, WatchlistItemRecord, WatchlistRecord

pytestmark = pytest.mark.anyio


def candidate_payload() -> dict[str, object]:
    return {
        "code": "159915",
        "name": "创业板ETF",
        "instrument_type": "etf",
        "market": "CN",
        "currency": "CNY",
        "asset_class": "equity",
        "region": "中国",
        "reason": "观察它能否降低现有标的依赖",
        "tags": ["候选", "成长", "候选"],
    }


async def test_watchlist_crud_keeps_actual_portfolio_isolated(tmp_path: Path) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.put("/api/v1/portfolio/positions", json=positions_payload())
        empty = await client.get("/api/v1/watchlists")
        created = await client.post("/api/v1/watchlists", json={"name": "候选基金"})
        watchlist_id = created.json()["data"]["items"][0]["watchlist_id"]
        duplicate_group = await client.post(
            "/api/v1/watchlists", json={"name": " 候选基金 "}
        )
        added = await client.post(
            f"/api/v1/watchlists/{watchlist_id}/items",
            json=candidate_payload(),
        )
        item = added.json()["data"]["items"][0]["items"][0]
        duplicate_item = await client.post(
            f"/api/v1/watchlists/{watchlist_id}/items",
            json=candidate_payload(),
        )
        updated = await client.put(
            f"/api/v1/watchlists/{watchlist_id}/items/{item['item_id']}",
            json={"reason": "等待更多数据", "tags": ["待研究"]},
        )
        portfolio = await client.get("/api/v1/portfolio")
        removed = await client.delete(
            f"/api/v1/watchlists/{watchlist_id}/items/{item['item_id']}"
        )
        deleted = await client.delete(f"/api/v1/watchlists/{watchlist_id}")

    assert empty.json()["coverage"]["item_count"] == 0
    assert added.status_code == 201
    assert item["tags"] == ["候选", "成长"]
    assert item["held"] is False
    assert duplicate_group.status_code == 409
    assert duplicate_group.json()["error"]["code"] == "duplicate_watchlist"
    assert duplicate_item.status_code == 409
    updated_item = updated.json()["data"]["items"][0]["items"][0]
    assert updated_item["reason"] == "等待更多数据"
    assert updated_item["tags"] == ["待研究"]
    assert len(portfolio.json()["data"]["positions"]) == 2
    assert portfolio.json()["data"]["revision"] == 1
    assert removed.json()["coverage"]["item_count"] == 0
    assert deleted.json()["coverage"]["watchlist_count"] == 0

    with app.state.session_factory() as session:
        positions = session.scalar(select(func.count(PositionRecord.id)))
        watchlists = session.scalar(select(func.count(WatchlistRecord.id)))
        watch_items = session.scalar(select(func.count(WatchlistItemRecord.id)))
    app.state.engine.dispose()
    assert positions == 2
    assert watchlists == 0
    assert watch_items == 0


async def test_watched_candidate_can_be_refreshed_and_compared_without_becoming_held(
    tmp_path: Path,
) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.put("/api/v1/portfolio/positions", json=positions_payload())
        group = await client.post("/api/v1/watchlists", json={"name": "待比较"})
        watchlist_id = group.json()["data"]["items"][0]["watchlist_id"]
        watched = await client.post(
            f"/api/v1/watchlists/{watchlist_id}/items",
            json=candidate_payload(),
        )
        candidate = watched.json()["data"]["items"][0]["items"][0]
        candidate_id = candidate["instrument_id"]
        quality_before = await client.get("/api/v1/data-quality")
        refreshed = await client.post(
            "/api/v1/market-data/refresh",
            json={"instrument_ids": None},
        )
        scenario = await client.post(
            "/api/v1/scenarios",
            json={
                "name": "候选基金买入实验",
                "candidate_instrument_id": candidate_id,
            },
        )
        scenario_id = scenario.json()["data"]["scenario_id"]
        compared = await client.post(
            f"/api/v1/scenarios/{scenario_id}/operations",
            json={
                "operation_type": "buy",
                "instrument_id": candidate_id,
                "amount": "100.00",
                "estimated_cost": "1.00",
            },
        )
        actual = await client.get("/api/v1/portfolio")

    quality_items = quality_before.json()["data"]["items"]
    candidate_quality = next(
        item for item in quality_items if item["instrument_id"] == candidate_id
    )
    assert candidate_quality["status"] == "missing"
    refresh_results = refreshed.json()["data"]["results"]
    candidate_refresh = next(
        item for item in refresh_results if item["instrument_id"] == candidate_id
    )
    assert candidate_refresh["status"] == "success"
    assert scenario.json()["data"]["candidate_instrument_id"] == candidate_id
    assert scenario.json()["data"]["before"]["analysis"]["status"] == "available"
    before_exposure = next(
        item
        for item in scenario.json()["data"]["before"]["analysis"][
            "instrument_exposures"
        ]
        if item["key"] == str(candidate_id)
    )
    after_exposure = next(
        item
        for item in compared.json()["data"]["after"]["analysis"][
            "instrument_exposures"
        ]
        if item["key"] == str(candidate_id)
    )
    assert before_exposure["weight"] == "0E-8"
    assert float(after_exposure["weight"]) > 0
    assert all(
        item["instrument_id"] != candidate_id
        for item in actual.json()["data"]["positions"]
    )
    assert actual.json()["data"]["revision"] == 1
    app.state.engine.dispose()


async def test_scenario_rejects_candidate_not_owned_by_watchlist(tmp_path: Path) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/scenarios",
            json={"name": "越权候选", "candidate_instrument_id": 999},
        )

    app.state.engine.dispose()
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["code"] == "candidate_not_watched"

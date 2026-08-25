from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx2
import pytest
from sqlalchemy import func, select

from tickeye.application.market_data_provider import (
    MarketDataRequest,
    MarketPoint,
    MarketSeries,
    MarketValueType,
)
from tickeye.config import Settings
from tickeye.infrastructure.db import Base, RiskSnapshotRecord
from tickeye.web.app import create_app

pytestmark = pytest.mark.anyio


class RiskFixtureProvider:
    name = "risk-fixture"

    def fetch(self, request: MarketDataRequest) -> MarketSeries:
        today = date.today()
        points = tuple(
            MarketPoint(
                observed_on=today - timedelta(days=129 - index),
                value=Decimal("1") + Decimal(index) / Decimal("100"),
            )
            for index in range(130)
        )
        return MarketSeries(
            points=points,
            value_type=MarketValueType.ADJUSTED_CLOSE,
            source=f"fixture:{request.code}",
            fetched_at=datetime.now(UTC),
            received_rows=len(points),
            invalid_rows=0,
        )


def build_risk_app(tmp_path: Path) -> Any:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'risk.db'}",
        frontend_dist_dir=tmp_path / "missing-frontend",
    )
    app = create_app(settings, market_data_provider=RiskFixtureProvider())
    Base.metadata.create_all(app.state.engine)
    return app


def positions_payload(
    *, expected_revision: int = 0, etf_manual_value: str = "999.00"
) -> dict[str, Any]:
    today = date.today().isoformat()
    return {
        "expected_revision": expected_revision,
        "positions": [
            {
                "account_name": "长期账户",
                "institution": None,
                "account_currency": "CNY",
                "code": "510300",
                "name": "沪深300ETF",
                "instrument_type": "etf",
                "market": "CN",
                "instrument_currency": "CNY",
                "asset_class": "equity",
                "region": "中国",
                "quantity": "10.00000000",
                "manual_value": etf_manual_value,
                "cost": None,
                "as_of": today,
            },
            {
                "account_name": "现金账户",
                "institution": None,
                "account_currency": "CNY",
                "code": "CASH-CNY",
                "name": "人民币现金",
                "instrument_type": "cash",
                "market": "CASH",
                "instrument_currency": "CNY",
                "asset_class": "cash",
                "region": "中国",
                "quantity": None,
                "manual_value": "1000.00",
                "cost": None,
                "as_of": today,
            },
        ],
    }


async def test_risk_snapshot_lifecycle_and_market_valuation(tmp_path: Path) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        empty = await client.get("/api/v1/risk/current")
        portfolio = await client.put(
            "/api/v1/portfolio/positions", json=positions_payload()
        )
        refreshed = await client.post(
            "/api/v1/market-data/refresh", json={"instrument_ids": None}
        )
        calculated = await client.post("/api/v1/risk/recalculate")
        current = await client.get("/api/v1/risk/current")

    assert empty.status_code == 200
    assert empty.json()["data"] is None
    assert portfolio.status_code == 200
    assert refreshed.status_code == 200
    assert calculated.status_code == 200
    body = calculated.json()
    analysis = body["data"]["analysis"]
    assert analysis["status"] == "available"
    assert analysis["methodology_version"] == "historical-risk-v1"
    assert analysis["metrics"]["aligned_observations"] == 130
    assert analysis["metrics"]["return_samples"] == 129
    etf = next(item for item in analysis["positions"] if item["code"] == "510300")
    assert etf["valuation_source"] == "market_data"
    assert etf["value"] == "22.90"
    assert analysis["coverage"]["known_portfolio_value"] == "1022.90"
    assert body["data"]["is_current"] is True
    assert current.json()["data"]["snapshot_id"] == body["data"]["snapshot_id"]

    with app.state.session_factory() as session:
        count = session.scalar(select(func.count(RiskSnapshotRecord.id)))
    app.state.engine.dispose()
    assert count == 1


async def test_portfolio_change_marks_snapshot_outdated_without_overwriting_it(
    tmp_path: Path,
) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.put(
            "/api/v1/portfolio/positions", json=positions_payload()
        )
        positions = created.json()["data"]["positions"]
        await client.post(
            "/api/v1/market-data/refresh", json={"instrument_ids": None}
        )
        first = await client.post("/api/v1/risk/recalculate")
        changed_payload = positions_payload(expected_revision=1, etf_manual_value="888.00")
        for new_position, old_position in zip(
            changed_payload["positions"], positions, strict=True
        ):
            new_position["id"] = old_position["id"]
        changed = await client.put(
            "/api/v1/portfolio/positions", json=changed_payload
        )
        outdated = await client.get("/api/v1/risk/current")
        second = await client.post("/api/v1/risk/recalculate")

    assert changed.status_code == 200
    assert outdated.json()["data"]["is_current"] is False
    assert outdated.json()["data"]["stale_reasons"] == ["portfolio_changed"]
    assert outdated.json()["warnings"]
    assert second.json()["data"]["snapshot_id"] > first.json()["data"]["snapshot_id"]
    with app.state.session_factory() as session:
        snapshots = list(
            session.scalars(select(RiskSnapshotRecord).order_by(RiskSnapshotRecord.id))
        )
    app.state.engine.dispose()
    assert len(snapshots) == 2
    assert snapshots[0].portfolio_revision == 1
    assert snapshots[1].portfolio_revision == 2


async def test_missing_market_history_returns_unknown_not_fake_metrics(
    tmp_path: Path,
) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.put("/api/v1/portfolio/positions", json=positions_payload())
        response = await client.post("/api/v1/risk/recalculate")

    app.state.engine.dispose()
    analysis = response.json()["data"]["analysis"]
    assert analysis["status"] == "unknown"
    assert analysis["metrics"]["annualized_volatility"] is None
    assert analysis["evidence"][0]["code"] == "missing_history"

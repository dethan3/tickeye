from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx2
import pytest
from sqlalchemy import func, select

from tickeye.application.market_data_provider import (
    MarketDataNetworkError,
    MarketDataRequest,
    MarketPoint,
    MarketSeries,
    MarketValueType,
)
from tickeye.config import Settings
from tickeye.infrastructure.db import (
    Base,
    MarketObservationRecord,
    MarketRefreshRecord,
)
from tickeye.web.app import create_app

pytestmark = pytest.mark.anyio


class FixedMarketDataProvider:
    name = "fixed-test-provider"

    def __init__(self) -> None:
        self.fail = False
        self.calls: list[MarketDataRequest] = []

    def fetch(self, request: MarketDataRequest) -> MarketSeries:
        self.calls.append(request)
        if self.fail:
            raise MarketDataNetworkError("测试网络故障")
        today = date.today()
        return MarketSeries(
            points=(
                MarketPoint(today - timedelta(days=1), Decimal("4.12345678")),
                MarketPoint(today, Decimal("4.20000000")),
            ),
            value_type=MarketValueType.ADJUSTED_CLOSE,
            source="fixed:test",
            fetched_at=datetime.now(UTC),
            received_rows=3,
            invalid_rows=1,
            limitations=("qfq_history_can_be_revised",),
        )


def build_market_data_app(
    tmp_path: Path, provider: FixedMarketDataProvider
) -> Any:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'market-data.db'}",
        frontend_dist_dir=tmp_path / "missing-frontend",
    )
    app = create_app(settings, market_data_provider=provider)
    Base.metadata.create_all(app.state.engine)
    return app


def portfolio_payload() -> dict[str, Any]:
    today = date.today().isoformat()
    return {
        "expected_revision": 0,
        "positions": [
            {
                "account_name": "长期账户",
                "institution": "手工录入",
                "account_currency": "CNY",
                "code": "510300",
                "name": "沪深300ETF",
                "instrument_type": "etf",
                "market": "CN",
                "instrument_currency": "CNY",
                "asset_class": "equity",
                "region": "中国",
                "quantity": "2500.00000000",
                "manual_value": "12500.00",
                "cost": "12000.00",
                "as_of": today,
            },
            {
                "account_name": "活钱账户",
                "institution": "手工录入",
                "account_currency": "CNY",
                "code": "CASH-CNY",
                "name": "人民币现金",
                "instrument_type": "cash",
                "market": "CASH",
                "instrument_currency": "CNY",
                "asset_class": "cash",
                "region": "中国",
                "quantity": "10000.00000000",
                "manual_value": "10000.00",
                "cost": "10000.00",
                "as_of": today,
            },
        ],
    }


async def seed_portfolio(client: httpx2.AsyncClient) -> dict[str, int]:
    response = await client.put(
        "/api/v1/portfolio/positions", json=portfolio_payload()
    )
    assert response.status_code == 200
    return {
        position["code"]: position["instrument_id"]
        for position in response.json()["data"]["positions"]
    }


async def test_quality_refresh_is_cached_idempotently_and_skips_cash(
    tmp_path: Path,
) -> None:
    provider = FixedMarketDataProvider()
    app = build_market_data_app(tmp_path, provider)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        ids = await seed_portfolio(client)
        before = await client.get("/api/v1/data-quality")
        first = await client.post(
            "/api/v1/market-data/refresh", json={"instrument_ids": None}
        )
        second = await client.post(
            "/api/v1/market-data/refresh",
            json={"instrument_ids": [ids["510300"]]},
        )

    assert before.status_code == 200
    before_items = {item["code"]: item for item in before.json()["data"]["items"]}
    assert before_items["510300"]["status"] == "missing"
    assert before_items["CASH-CNY"]["status"] == "not_applicable"

    assert first.status_code == 200
    first_results = {
        item["code"]: item for item in first.json()["data"]["results"]
    }
    assert first_results["510300"]["written_rows"] == 2
    assert first_results["CASH-CNY"]["status"] == "skipped"
    quality = {
        item["code"]: item
        for item in first.json()["data"]["quality"]["data"]["items"]
    }
    assert quality["510300"]["status"] == "short_history"
    assert quality["510300"]["sample_count"] == 2
    assert quality["510300"]["rejected_rate"] == "0.3333"
    assert quality["510300"]["limitations"] == [
        "qfq_history_can_be_revised"
    ]
    assert second.json()["data"]["results"][0]["written_rows"] == 0

    with app.state.session_factory() as session:
        observation_count = session.scalar(
            select(func.count(MarketObservationRecord.id))
        )
        refresh_count = session.scalar(select(func.count(MarketRefreshRecord.id)))
    app.state.engine.dispose()

    assert observation_count == 2
    assert refresh_count == 2
    assert len(provider.calls) == 2


async def test_refresh_failure_keeps_last_good_observations(tmp_path: Path) -> None:
    provider = FixedMarketDataProvider()
    app = build_market_data_app(tmp_path, provider)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        ids = await seed_portfolio(client)
        succeeded = await client.post(
            "/api/v1/market-data/refresh",
            json={"instrument_ids": [ids["510300"]]},
        )
        provider.fail = True
        failed = await client.post(
            "/api/v1/market-data/refresh",
            json={"instrument_ids": [ids["510300"]]},
        )

    app.state.engine.dispose()
    assert succeeded.status_code == 200
    assert failed.status_code == 200
    result = failed.json()["data"]["results"][0]
    quality = failed.json()["data"]["quality"]["data"]["items"]
    fund_quality = next(item for item in quality if item["code"] == "510300")
    assert result["status"] == "error"
    assert result["error_code"] == "network_error"
    assert fund_quality["status"] == "refresh_failed"
    assert fund_quality["sample_count"] == 2
    assert fund_quality["latest_value"] == "4.20000000"
    assert failed.json()["data"]["quality"]["warnings"]


async def test_refresh_rejects_instruments_outside_current_portfolio(
    tmp_path: Path,
) -> None:
    provider = FixedMarketDataProvider()
    app = build_market_data_app(tmp_path, provider)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        await seed_portfolio(client)
        response = await client.post(
            "/api/v1/market-data/refresh", json={"instrument_ids": [999999]}
        )
    app.state.engine.dispose()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_market_data_instruments"
    assert response.json()["error"]["details"][0]["instrument_id"] == 999999

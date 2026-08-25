from decimal import Decimal
from pathlib import Path

import httpx2
import pytest
from sqlalchemy import func, select

from tests.integration.test_risk_api import build_risk_app, positions_payload
from tickeye.infrastructure.db import (
    PositionRecord,
    ScenarioComparisonRecord,
    ScenarioOperationRecord,
    ScenarioRecord,
)

pytestmark = pytest.mark.anyio


async def test_scenario_comparison_is_frozen_and_never_changes_positions(
    tmp_path: Path,
) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        portfolio = await client.put(
            "/api/v1/portfolio/positions", json=positions_payload()
        )
        instrument_id = next(
            item["instrument_id"]
            for item in portfolio.json()["data"]["positions"]
            if item["code"] == "510300"
        )
        await client.post(
            "/api/v1/market-data/refresh", json={"instrument_ids": None}
        )
        created = await client.post(
            "/api/v1/scenarios",
            json={
                "name": "增加沪深300仓位",
                "stress_assumptions": [
                    {"asset_class": "equity", "shock": "-0.20"}
                ],
            },
        )
        scenario_id = created.json()["data"]["scenario_id"]
        compared = await client.post(
            f"/api/v1/scenarios/{scenario_id}/operations",
            json={
                "operation_type": "buy",
                "instrument_id": instrument_id,
                "amount": "10.00",
                "target_weight": None,
                "estimated_cost": "1.00",
            },
        )
        actual = await client.get("/api/v1/portfolio")
        listed = await client.get("/api/v1/scenarios")
        fetched = await client.get(
            f"/api/v1/scenarios/{scenario_id}/comparison"
        )

    assert created.status_code == 200
    assert created.json()["data"]["operation_count"] == 0
    body = compared.json()
    assert compared.status_code == 200
    assert body["data"]["operation_count"] == 1
    assert body["data"]["policy_revision"] == 0
    assert body["data"]["comparison_window"]["observations"] == 130
    assert body["data"]["before"]["analysis"]["metrics"]["window_start"] == body[
        "data"
    ]["after"]["analysis"]["metrics"]["window_start"]
    assert body["data"]["before"]["analysis"]["metrics"]["window_end"] == body[
        "data"
    ]["after"]["analysis"]["metrics"]["window_end"]
    assert body["data"]["before"]["analysis"]["methodology_version"] == body[
        "data"
    ]["after"]["analysis"]["methodology_version"]
    after_weights = body["data"]["after"]["analysis"]["instrument_exposures"]
    assert sum((Decimal(item["weight"]) for item in after_weights), Decimal(0)) == Decimal(1)
    assert body["data"]["total_estimated_cost"] == "1.00"
    assert body["data"]["before"]["stressed_value"] == "1018.32"
    assert body["data"]["after"]["stressed_value"] == "1015.32"
    assert body["data"]["warnings"][0].startswith("这是未执行的方案")
    assert body["data"]["summary"]["worsenings"]
    assert body["data"]["summary"]["objections"]
    actual_etf = next(
        item for item in actual.json()["data"]["positions"] if item["code"] == "510300"
    )
    assert actual_etf["quantity"] == "10.00000000"
    assert actual.json()["data"]["revision"] == 1
    assert listed.json()["data"]["items"][0]["operation_count"] == 1
    assert fetched.json()["data"] == body["data"]

    with app.state.session_factory() as session:
        scenarios = session.scalar(select(func.count(ScenarioRecord.id)))
        operations = session.scalar(select(func.count(ScenarioOperationRecord.id)))
        comparisons = session.scalar(select(func.count(ScenarioComparisonRecord.id)))
        positions = session.scalar(select(func.count(PositionRecord.id)))
    app.state.engine.dispose()
    assert scenarios == 1
    assert operations == 1
    assert comparisons == 2
    assert positions == 2


async def test_invalid_operations_do_not_pollute_scenario_history(tmp_path: Path) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        portfolio = await client.put(
            "/api/v1/portfolio/positions", json=positions_payload()
        )
        instrument_id = next(
            item["instrument_id"]
            for item in portfolio.json()["data"]["positions"]
            if item["code"] == "510300"
        )
        await client.post(
            "/api/v1/market-data/refresh", json={"instrument_ids": None}
        )
        scenario = await client.post(
            "/api/v1/scenarios", json={"name": "非法操作测试"}
        )
        scenario_id = scenario.json()["data"]["scenario_id"]
        oversell = await client.post(
            f"/api/v1/scenarios/{scenario_id}/operations",
            json={
                "operation_type": "sell",
                "instrument_id": instrument_id,
                "amount": "100.00",
                "estimated_cost": "0",
            },
        )
        negative_cash = await client.post(
            f"/api/v1/scenarios/{scenario_id}/operations",
            json={
                "operation_type": "buy",
                "instrument_id": instrument_id,
                "amount": "1001.00",
                "estimated_cost": "0",
            },
        )
        missing = await client.get("/api/v1/scenarios/999/comparison")

    assert oversell.status_code == 422
    assert oversell.json()["error"]["details"][0]["code"] == "oversell"
    assert negative_cash.status_code == 422
    assert negative_cash.json()["error"]["details"][0]["code"] == "negative_cash"
    assert missing.status_code == 404
    with app.state.session_factory() as session:
        operations = session.scalar(select(func.count(ScenarioOperationRecord.id)))
        comparisons = session.scalar(select(func.count(ScenarioComparisonRecord.id)))
    app.state.engine.dispose()
    assert operations == 0
    assert comparisons == 1


async def test_trade_without_frozen_price_is_marked_uncomputable(tmp_path: Path) -> None:
    app = build_risk_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        portfolio = await client.put(
            "/api/v1/portfolio/positions", json=positions_payload()
        )
        instrument_id = next(
            item["instrument_id"]
            for item in portfolio.json()["data"]["positions"]
            if item["code"] == "510300"
        )
        scenario = await client.post(
            "/api/v1/scenarios", json={"name": "缺少价格"}
        )
        scenario_id = scenario.json()["data"]["scenario_id"]
        response = await client.post(
            f"/api/v1/scenarios/{scenario_id}/operations",
            json={
                "operation_type": "buy",
                "instrument_id": instrument_id,
                "amount": "10.00",
                "estimated_cost": "0",
            },
        )

    app.state.engine.dispose()
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["code"] == "unknown_price"

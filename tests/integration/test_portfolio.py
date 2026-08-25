import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx2
import pytest
from sqlalchemy import func, select

from tickeye.config import Settings
from tickeye.infrastructure.db import Base, PositionSnapshotRecord
from tickeye.web.app import create_app

pytestmark = pytest.mark.anyio


def build_portfolio_app(tmp_path: Path) -> Any:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'portfolio.db'}",
        frontend_dist_dir=tmp_path / "missing-frontend",
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    return app


def position_payload(
    *, position_id: int | None = None, manual_value: str = "12500.00"
) -> dict[str, Any]:
    return {
        "id": position_id,
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
        "manual_value": manual_value,
        "cost": "12000.00",
        "as_of": date.today().isoformat(),
    }


async def test_manual_position_lifecycle_creates_recoverable_snapshots(tmp_path: Path) -> None:
    app = build_portfolio_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        empty = await client.get("/api/v1/portfolio")
        created = await client.put(
            "/api/v1/portfolio/positions",
            json={"expected_revision": 0, "positions": [position_payload()]},
        )
        created_position = created.json()["data"]["positions"][0]
        updated = await client.put(
            "/api/v1/portfolio/positions",
            json={
                "expected_revision": 1,
                "positions": [
                    position_payload(
                        position_id=created_position["id"],
                        manual_value="13000.00",
                    )
                ],
            },
        )
        deleted = await client.put(
            "/api/v1/portfolio/positions",
            json={"expected_revision": 2, "positions": []},
        )

    assert empty.json()["data"]["revision"] == 0
    assert created.status_code == 200
    assert created.json()["data"]["revision"] == 1
    assert updated.json()["data"]["positions"][0]["manual_value"] == "13000.00"
    assert deleted.json()["data"]["revision"] == 3
    assert deleted.json()["data"]["positions"] == []

    with app.state.session_factory() as session:
        snapshots = list(
            session.scalars(select(PositionSnapshotRecord).order_by(PositionSnapshotRecord.id))
        )
    app.state.engine.dispose()

    assert len(snapshots) == 3
    assert json.loads(snapshots[0].payload_json)["revision"] == 1
    assert json.loads(snapshots[-1].payload_json)["positions"] == []
    assert all(len(snapshot.payload_hash) == 64 for snapshot in snapshots)


async def test_stale_revision_and_invalid_values_do_not_change_portfolio(tmp_path: Path) -> None:
    app = build_portfolio_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.put(
            "/api/v1/portfolio/positions",
            json={"expected_revision": 0, "positions": [position_payload()]},
        )
        stale = await client.put(
            "/api/v1/portfolio/positions",
            json={"expected_revision": 0, "positions": []},
        )
        position_id = created.json()["data"]["positions"][0]["id"]
        invalid_position = position_payload(position_id=position_id)
        invalid_position["quantity"] = "-1"
        invalid = await client.put(
            "/api/v1/portfolio/positions",
            json={"expected_revision": 1, "positions": [invalid_position]},
        )
        current = await client.get("/api/v1/portfolio")

    app.state.engine.dispose()
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "portfolio_revision_conflict"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["details"][0]["field"] == "quantity"
    assert current.json()["data"]["revision"] == 1
    assert len(current.json()["data"]["positions"]) == 1


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("manual_value", "12.345", "numeric_precision"),
        ("account_currency", "USD", "unsupported_currency"),
        ("instrument_currency", "USD", "unsupported_currency"),
    ],
)
async def test_unsupported_currency_and_silent_rounding_are_rejected(
    tmp_path: Path,
    field: str,
    value: str,
    expected_code: str,
) -> None:
    app = build_portfolio_app(tmp_path)
    invalid_position = position_payload()
    invalid_position[field] = value
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/v1/portfolio/positions",
            json={"expected_revision": 0, "positions": [invalid_position]},
        )
    app.state.engine.dispose()

    assert response.status_code == 422
    assert expected_code in {
        detail["code"] for detail in response.json()["error"]["details"]
    }


async def test_conflicting_instrument_facts_across_accounts_are_rejected(tmp_path: Path) -> None:
    app = build_portfolio_app(tmp_path)
    first = position_payload()
    second = position_payload()
    second["account_name"] = "短期账户"
    second["name"] = "冲突的名称"
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/v1/portfolio/positions",
            json={"expected_revision": 0, "positions": [first, second]},
        )
    app.state.engine.dispose()

    assert response.status_code == 422
    assert "inconsistent_instrument" in {
        detail["code"] for detail in response.json()["error"]["details"]
    }


async def test_csv_requires_clean_preview_before_confirm_and_blocks_duplicates(
    tmp_path: Path,
) -> None:
    app = build_portfolio_app(tmp_path)
    today = date.today().isoformat()
    csv_content = (
        "account,code,name,type,market,currency,asset_class,region,quantity,manual_value,cost,as_of\n"
        f"基金账户,007360,美元债基金,qdii_fund,CN,CNY,fixed_income,全球,1000,10250,10000,{today}\n"
    )
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        preview = await client.post(
            "/api/v1/portfolio/import",
            json={"mode": "preview", "csv_content": csv_content},
        )
        preview_body = preview.json()
        confirmed = await client.post(
            "/api/v1/portfolio/import",
            json={
                "mode": "confirm",
                "csv_content": csv_content,
                "preview_token": preview_body["data"]["preview_token"],
                "expected_revision": 0,
            },
        )
        duplicate_preview = await client.post(
            "/api/v1/portfolio/import",
            json={"mode": "preview", "csv_content": csv_content},
        )
        duplicate_confirm = await client.post(
            "/api/v1/portfolio/import",
            json={
                "mode": "confirm",
                "csv_content": csv_content,
                "preview_token": preview_body["data"]["preview_token"],
                "expected_revision": 1,
            },
        )

    with app.state.session_factory() as session:
        snapshot_count = session.scalar(select(func.count(PositionSnapshotRecord.id)))
    app.state.engine.dispose()

    assert preview.status_code == 200
    assert preview_body["data"]["valid"] is True
    assert confirmed.status_code == 200
    assert confirmed.json()["portfolio"]["data"]["revision"] == 1
    assert duplicate_preview.json()["data"]["duplicate_import"] is True
    assert duplicate_confirm.status_code == 409
    assert snapshot_count == 1


@pytest.mark.parametrize(
    ("csv_content", "expected_code"),
    [
        (
            "account,code,name,type,market,currency,asset_class,region,quantity,as_of\n"
            "账户,510300,ETF,etf,CN,CNY,equity,中国,1,not-a-date\n",
            "invalid_date",
        ),
        (
            "account,code,market,quantity,as_of\n账户,UNKNOWN,CN,1,2026-01-01\n",
            "unknown_instrument",
        ),
        (
            "account,code,name,type,market,currency,asset_class,region,quantity,as_of\n"
            "账户,510300,ETF,etf,CN,CNY,equity,中国,1,2026-01-01\n"
            "账户,510300,ETF,etf,CN,CNY,equity,中国,2,2026-01-01\n",
            "duplicate_position",
        ),
    ],
)
async def test_csv_preview_returns_row_level_errors(
    tmp_path: Path,
    csv_content: str,
    expected_code: str,
) -> None:
    app = build_portfolio_app(tmp_path)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/portfolio/import",
            json={"mode": "preview", "csv_content": csv_content},
        )
    app.state.engine.dispose()

    assert response.status_code == 200
    assert response.json()["data"]["valid"] is False
    assert expected_code in {issue["code"] for issue in response.json()["data"]["issues"]}

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_empty_database_upgrades_to_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("TICKEYE_DATABASE_URL", database_url)

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert revision == "20260825_0007"
    assert {
        "profiles",
        "instruments",
        "accounts",
        "positions",
        "position_snapshots",
        "market_observations",
        "market_refreshes",
        "risk_snapshots",
        "policy_rules",
        "risk_evaluations",
        "insight_events",
        "scenarios",
        "scenario_operations",
        "scenario_comparisons",
        "watchlists",
        "watchlist_items",
    } <= tables

"""Deterministic local app used only by browser E2E tests."""

import os
from pathlib import Path

from tests.integration.test_risk_api import RiskFixtureProvider
from tickeye.config import Settings
from tickeye.infrastructure.db import Base
from tickeye.web.app import create_app

database_path = Path(os.environ["TICKEYE_E2E_DATABASE_PATH"])
settings = Settings(
    environment="test",
    database_url=f"sqlite:///{database_path}",
    frontend_dist_dir=database_path.parent / "missing-frontend",
)
app = create_app(settings, market_data_provider=RiskFixtureProvider())
Base.metadata.create_all(app.state.engine)

"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tickeye import __version__
from tickeye.application.export_service import ExportService
from tickeye.application.market_data_provider import MarketDataProvider
from tickeye.application.market_data_service import MarketDataService
from tickeye.application.policy_service import PolicyService, RiskEvaluationService
from tickeye.application.portfolio_service import PortfolioService
from tickeye.application.risk_service import RiskService
from tickeye.application.scenario_service import ScenarioService
from tickeye.application.watchlist_service import WatchlistService
from tickeye.config import Settings, get_settings
from tickeye.infrastructure.db import create_db_engine, create_session_factory
from tickeye.infrastructure.market_data import AkShareMarketDataProvider
from tickeye.logging import configure_logging
from tickeye.web.api import api_router
from tickeye.web.errors import register_error_handlers
from tickeye.web.static_app import mount_frontend


def create_app(
    settings: Settings | None = None,
    market_data_provider: MarketDataProvider | None = None,
) -> FastAPI:
    """Build the HTTP application with explicit, replaceable infrastructure."""

    runtime_settings = settings or get_settings()
    configure_logging(debug=runtime_settings.debug)
    engine = create_db_engine(
        runtime_settings.database_url,
        echo=runtime_settings.debug,
    )
    session_factory = create_session_factory(engine)
    provider = market_data_provider or AkShareMarketDataProvider(
        max_attempts=runtime_settings.market_data_max_attempts,
        retry_delay_seconds=runtime_settings.market_data_retry_delay_seconds,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    application = FastAPI(
        title=runtime_settings.app_name,
        version=__version__,
        debug=runtime_settings.debug,
        lifespan=lifespan,
    )
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.portfolio_service = PortfolioService(session_factory)
    application.state.export_service = ExportService(session_factory)
    application.state.market_data_service = MarketDataService(session_factory, provider)
    risk_service = RiskService(session_factory)
    application.state.risk_service = risk_service
    application.state.policy_service = PolicyService(session_factory)
    application.state.risk_evaluation_service = RiskEvaluationService(session_factory)
    application.state.scenario_service = ScenarioService(session_factory, risk_service)
    application.state.watchlist_service = WatchlistService(session_factory)
    application.state.settings = runtime_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(application)
    application.include_router(api_router)
    mount_frontend(application, runtime_settings.frontend_dist_dir)
    return application


app = create_app()

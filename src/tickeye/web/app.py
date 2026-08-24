"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tickeye import __version__
from tickeye.config import Settings, get_settings
from tickeye.infrastructure.db import create_db_engine
from tickeye.logging import configure_logging
from tickeye.web.api import api_router
from tickeye.web.errors import register_error_handlers
from tickeye.web.static_app import mount_frontend


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the HTTP application with explicit, replaceable infrastructure."""

    runtime_settings = settings or get_settings()
    configure_logging(debug=runtime_settings.debug)
    engine = create_db_engine(
        runtime_settings.database_url,
        echo=runtime_settings.debug,
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

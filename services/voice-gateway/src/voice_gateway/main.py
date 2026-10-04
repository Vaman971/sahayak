from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from sahayak_core.config import get_settings
from sahayak_core.logging import configure_logging

from voice_gateway.api.health import router as health_router

log = structlog.get_logger()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        log.info("gateway.startup", env=settings.env)
        # Later: open Redis pool, warn Sarvam connections, load VAD model
        yield
        log.info("gataeway.shutdown")
        # Later: drain active calls, close pools

    app = FastAPI(title="Sahayak Voice Gateway", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    return app

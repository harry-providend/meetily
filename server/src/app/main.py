from fastapi import FastAPI

from app.core.exception_handlers import register_exception_handlers
from app.routers import (
    health_router,
    meeting_router,
    notes_router,
    summary_router,
    sync_router,
    template_router,
    transcript_router,
    transcript_search_router,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Providend Meeting Assistant API",
        version="0.1.0",
        description=(
            "Resource server for the Providend Meeting Assistant desktop app. Validates Entra ID "
            "access tokens; every read and write is scoped to the token's oid/tid."
        ),
    )

    register_exception_handlers(app)

    app.include_router(health_router.router)
    app.include_router(meeting_router.router)
    app.include_router(transcript_router.router)
    app.include_router(transcript_search_router.router)
    app.include_router(summary_router.router)
    app.include_router(notes_router.router)
    app.include_router(template_router.router)
    app.include_router(sync_router.router)

    return app

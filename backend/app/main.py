"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    chat,
    context,
    dashboard,
    graph,
    journal,
    objectives,
    onboarding,
    projects,
    reflections,
    usage,
)
from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware
from app.db.migrations import run_migrations


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await run_migrations()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="hadi-os", version="0.1.0", lifespan=lifespan)

    # Order: SecurityHeaders added first => CORS wraps it (outermost), so CORS
    # handles preflight and error responses too.
    app.add_middleware(SecurityHeadersMiddleware, is_prod=settings.is_prod)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(context.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")
    app.include_router(journal.router, prefix="/api")
    app.include_router(objectives.router, prefix="/api")
    app.include_router(onboarding.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(reflections.router, prefix="/api")
    app.include_router(usage.router, prefix="/api")

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

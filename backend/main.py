from __future__ import annotations

from fastapi import FastAPI

from backend.api.v1 import router as v1_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Weather Smarter API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.include_router(v1_router)
    return app


app = create_app()

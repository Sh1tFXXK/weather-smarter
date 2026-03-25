from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.api.agent_v1 import router as agent_v1_router
from backend.api.v1 import router as v1_router


def _cors_allowed_origins() -> list[str]:
    defaults = [
        "null",
        "http://127.0.0.1",
        "http://localhost",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]
    configured = [
        item.strip()
        for item in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
        if item.strip()
    ]
    return [*defaults, *configured]


def create_app() -> FastAPI:
    project_root = Path(__file__).resolve().parents[1]
    frontend_file = project_root / "frontend" / "index.html"

    app = FastAPI(
        title="Weather Smarter API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allowed_origins(),
        allow_origin_regex=os.getenv(
            "CORS_ALLOW_ORIGIN_REGEX",
            r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(v1_router)
    app.include_router(agent_v1_router)

    @app.get("/", include_in_schema=False, response_model=None)
    def index() -> Response:
        if frontend_file.exists():
            return FileResponse(
                frontend_file,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        return JSONResponse({"status": "ok"})

    return app


app = create_app()

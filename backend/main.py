from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.api.v1 import router as v1_router


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
    app.include_router(v1_router)

    @app.get("/", include_in_schema=False, response_model=None)
    def index() -> Response:
        if frontend_file.exists():
            return FileResponse(frontend_file)
        return JSONResponse({"status": "ok"})

    return app


app = create_app()

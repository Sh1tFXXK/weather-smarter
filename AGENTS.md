# Repository Guidelines

This guide aligns contributors on structure, workflow, and quality bars for weather-smarter (Python backend). Prefer small, focused PRs with clear scope and tests.

## Project Structure & Module Organization
- `backend/` — Python services
  - `agent/` (LLM、RAG、Memory)  `data/` (weather/AQI/calendar)  `tts_asr/` (ASR/TTS)
  - `api/` (FastAPI routes)  `main.py` (ASGI app entry)
- `database/` — `schema.sql`, `seed_data.sql`
- `config/` — `config.yaml`, `.env.example`
- `tests/` — pytest tests: `test_*.py`
- `docs/` — project docs; `frontend/`（如有）与后端解耦

## Build, Test, and Development Commands
- Create venv
  - Windows: `py -3 -m venv .venv && .\\.venv\\Scripts\\activate`
  - macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run API: `uvicorn main:app --reload`
- Test: `pytest -q`  | Coverage: `pytest --cov=backend --cov-report=term-missing`
- Lint/format: `ruff check .`  and  `black .`
- Type check (optional): `mypy backend`

## Coding Style & Naming Conventions
- Python 3.10+; 4-space indent; format with Black; lint with Ruff.
- Files/modules: `snake_case.py`; classes: `PascalCase`; functions/vars: `snake_case`.
- Keep modules single-purpose; avoid long functions; prefer dependency injection for services.
- Public APIs validated with Pydantic; handle timeouts/retries centrally.

## Testing Guidelines
- Framework: pytest; discovery `tests/test_*.py`.
- Mock network I/O (`responses`/`pytest-httpx`); use FastAPI `TestClient` for API tests.
- Aim for ≥80% line coverage; test behavior (e.g., `/api/v1/query` decisions) over internals.

## Commit & Pull Request Guidelines
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- PRs include: clear description, linked issues (`Fixes #123`), API examples or screenshots (如前端变更), and tests.
- Keep PRs small (≈300–500 LOC); split refactors; update docs when behavior changes.

## Security & Configuration Tips
- Do not commit secrets. Provide `.env.example`; use local `.env`/runtime env vars.
- Typical keys: `WEATHER_API_KEY`, `GEO_API_KEY`, `TTS_API_KEY` (read via config loader).
- Validate inputs; never log secrets; set request timeouts/retries; pin critical deps in `requirements.txt`.

import sys
from pathlib import Path

# Allow `python src/main.py` from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import api_router
from backend.config import get_settings

_settings_for_sentry = get_settings()
if _settings_for_sentry.sentry_dsn:
    import sentry_sdk

    # Initialized once at process start, before the app handles any request —
    # no-op (never imported/called) when SENTRY_DSN is unset, matching every
    # other optional integration in this codebase (optimize_Plan.html §5).
    sentry_sdk.init(dsn=_settings_for_sentry.sentry_dsn, environment=_settings_for_sentry.app_env, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    yield
    print("Shutting down...")


app = FastAPI(
    title="PaperPulse",
    description="Academic Research Assistant — automated literature review with citation verification",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


if __name__ == "__main__":
    import uvicorn

    # Exclude data/ — PDF Agent output/figures and LaTeX export files write here
    # during a request, and reload-on-write would kill in-flight streams
    # mid-pipeline. (LangGraph checkpointer + paper embeddings now live in
    # Supabase, not under ./data/ — see optimize_Plan.html §3.)
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        reload_excludes=["data/*"],
    )

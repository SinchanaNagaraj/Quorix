from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, query
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(query.router, prefix=settings.api_prefix)

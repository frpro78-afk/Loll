from fastapi import FastAPI

from app.api import health, market, paper
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Paper-trading, spot-only backend for MahaQuant.",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(market.router)
app.include_router(paper.router)

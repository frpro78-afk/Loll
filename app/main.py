from fastapi import FastAPI

from app.api import health, market, paper, strategy
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Paper-trading, spot-only backend for MahaQuant with a strategy engine.",
    version="0.2.0",
)

app.include_router(health.router)
app.include_router(market.router)
app.include_router(paper.router)
app.include_router(strategy.router)

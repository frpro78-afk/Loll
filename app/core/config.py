from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MahaQuant"
    environment: str = "development"

    # Public spot market data (no API key needed).
    market_data_base_url: str = "https://api.binance.com"
    market_data_timeout_seconds: float = 5.0

    # Paper trading: simulated funds only.
    paper_starting_balance: Decimal = Decimal("10000")
    paper_quote_asset: str = "USDT"


@lru_cache
def get_settings() -> Settings:
    """Return one cached Settings object for the whole app."""
    return Settings()

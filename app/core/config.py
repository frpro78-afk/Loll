from decimal import Decimal
from functools import lru_cache

from pydantic import Field
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

    # Risk management (percentages, deterministic rules).
    risk_per_trade_pct: Decimal = Field(default=Decimal("1"), gt=0, le=100)
    risk_stop_loss_pct: Decimal = Field(default=Decimal("2"), gt=0, le=100)
    risk_take_profit_pct: Decimal = Field(default=Decimal("4"), gt=0, le=1000)
    risk_max_position_pct: Decimal = Field(default=Decimal("25"), gt=0, le=100)
    risk_max_open_positions: int = Field(default=3, ge=1, le=50)
    risk_min_order_notional: Decimal = Field(default=Decimal("10"), ge=0)

    # Strategy engine eligibility rules.
    engine_min_confidence: float = Field(default=0.55, ge=0, le=1)
    engine_min_backtest_trades: int = Field(default=3, ge=0)
    engine_min_backtest_return_pct: float = 0.0
    engine_max_backtest_drawdown_pct: float = Field(default=20.0, gt=0, le=100)

    # Backtest realism: fee charged on each side of a trade, in percent.
    backtest_fee_pct: float = Field(default=0.1, ge=0, le=5)


@lru_cache
def get_settings() -> Settings:
    """Return one cached Settings object for the whole app."""
    return Settings()

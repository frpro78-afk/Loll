from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    trading_mode: str


class PriceResponse(BaseModel):
    symbol: str
    price: Decimal


class PaperOrderRequest(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,12}$", examples=["BTCUSDT"])
    side: OrderSide
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=8)


class PaperOrderResponse(BaseModel):
    symbol: str
    side: OrderSide
    quantity: Decimal
    fill_price: Decimal
    notional: Decimal
    simulated: bool = True


class PortfolioResponse(BaseModel):
    quote_asset: str
    cash_balance: Decimal
    positions: dict[str, Decimal]

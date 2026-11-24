from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.trading import PaperOrderResponse

Interval = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
SYMBOL_PATTERN = r"^[A-Z0-9]{5,12}$"


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Candle(BaseModel):
    """One closed OHLCV candle. Floats are fine for indicator math."""

    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class StrategySignal(BaseModel):
    strategy: str
    action: SignalAction
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class StrategyInfo(BaseModel):
    name: str
    description: str


class RiskDecision(BaseModel):
    approved: bool
    reason: str
    quantity: Decimal
    notional: Decimal
    entry_price: Decimal
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None


class BacktestTrade(BaseModel):
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    return_pct: float
    exit_reason: str


class BacktestSummary(BaseModel):
    strategy: str
    symbol: str
    interval: str
    candles_used: int
    starting_cash: float
    ending_equity: float
    total_return_pct: float
    buy_and_hold_return_pct: float
    trade_count: int
    win_rate_pct: float
    max_drawdown_pct: float
    fee_pct: float


class BacktestResult(BacktestSummary):
    trades: list[BacktestTrade] = Field(default_factory=list)


class StrategyEvaluation(BaseModel):
    signal: StrategySignal
    backtest: BacktestSummary
    eligible: bool
    ineligible_reasons: list[str]


class EngineDecision(BaseModel):
    symbol: str
    interval: str
    price: Decimal
    candles_used: int
    evaluations: list[StrategyEvaluation]
    selected: StrategySignal | None
    risk: RiskDecision | None
    message: str


class StrategyRunRequest(BaseModel):
    symbol: str = Field(pattern=SYMBOL_PATTERN, examples=["BTCUSDT"])
    interval: Interval = "1h"
    limit: int = Field(default=500, ge=100, le=999)


class BacktestRequest(StrategyRunRequest):
    strategy: str | None = Field(
        default=None, description="Strategy name. Omit to backtest all strategies."
    )
    include_trades: bool = False


class StrategyExecutionResponse(BaseModel):
    decision: EngineDecision
    executed: bool
    order: PaperOrderResponse | None = None

from app.schemas.strategy import Candle, SignalAction, StrategySignal
from app.strategies.base import Strategy


def candles_from_closes(closes: list[float], step_ms: int = 3_600_000) -> list[Candle]:
    """Build candles where each open equals the previous close."""
    candles = []
    for i, close in enumerate(closes):
        open_ = closes[i - 1] if i > 0 else close
        candles.append(
            Candle(
                open_time=i * step_ms,
                open=open_,
                high=max(open_, close) * 1.001,
                low=min(open_, close) * 0.999,
                close=close,
                volume=100.0,
            )
        )
    return candles


class StubStrategy(Strategy):
    """Always returns the same signal."""

    description = "Test stub with a constant signal."

    def __init__(self, name: str, action: SignalAction, confidence: float) -> None:
        self.name = name
        self._action = action
        self._confidence = confidence

    @property
    def min_candles(self) -> int:
        return 1

    def generate_signal(self, candles) -> StrategySignal:
        return self._signal(self._action, self._confidence, "stub signal")


class ScriptedStrategy(Strategy):
    """BUY when exactly `buy_at` candles are visible, SELL at `sell_at`."""

    name = "scripted"
    description = "Test stub with signals at fixed candle counts."

    def __init__(self, buy_at: int | None = None, sell_at: int | None = None) -> None:
        self.buy_at = buy_at
        self.sell_at = sell_at

    @property
    def min_candles(self) -> int:
        return 1

    def generate_signal(self, candles) -> StrategySignal:
        n = len(candles)
        if self.buy_at is not None and n == self.buy_at:
            return self._signal(SignalAction.BUY, 0.9, "scripted buy")
        if self.sell_at is not None and n == self.sell_at:
            return self._signal(SignalAction.SELL, 0.9, "scripted sell")
        return self._hold("scripted hold")

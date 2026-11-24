from app.schemas.strategy import Candle, SignalAction, StrategySignal
from app.strategies import indicators
from app.strategies.base import Strategy


class RsiStrategy(Strategy):
    name = "rsi"
    description = "Buy when RSI is oversold (below 30); sell when overbought (above 70)."

    def __init__(
        self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0
    ) -> None:
        if period < 1 or not (0 < oversold < overbought < 100):
            raise ValueError("Require period >= 1 and 0 < oversold < overbought < 100")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    @property
    def min_candles(self) -> int:
        return self.period + 1

    def generate_signal(self, candles: list[Candle]) -> StrategySignal:
        if len(candles) < self.min_candles:
            return self._hold("Not enough candles.")

        latest = indicators.rsi(self._closes(candles), self.period)[-1]
        if latest is None:
            return self._hold("Indicator not ready.")

        if latest < self.oversold:
            confidence = 0.5 + (self.oversold - latest) / self.oversold * 0.5
            return self._signal(
                SignalAction.BUY, confidence, f"RSI {latest:.1f} is below {self.oversold:.0f} (oversold)."
            )
        if latest > self.overbought:
            confidence = 0.5 + (latest - self.overbought) / (100.0 - self.overbought) * 0.5
            return self._signal(
                SignalAction.SELL, confidence, f"RSI {latest:.1f} is above {self.overbought:.0f} (overbought)."
            )
        return self._hold(f"RSI {latest:.1f} is in the neutral zone.")

from app.schemas.strategy import Candle, SignalAction, StrategySignal
from app.strategies import indicators
from app.strategies.base import Strategy


class MomentumStrategy(Strategy):
    name = "momentum"
    description = "Buy when price rose at least the threshold over the period; sell when it fell by that much."

    def __init__(self, period: int = 10, threshold_pct: float = 2.0) -> None:
        if period < 1 or threshold_pct <= 0:
            raise ValueError("Require period >= 1 and threshold_pct > 0")
        self.period = period
        self.threshold_pct = threshold_pct

    @property
    def min_candles(self) -> int:
        return self.period + 1

    def generate_signal(self, candles: list[Candle]) -> StrategySignal:
        if len(candles) < self.min_candles:
            return self._hold("Not enough candles.")

        roc = indicators.momentum(self._closes(candles), self.period)[-1]
        if roc is None:
            return self._hold("Indicator not ready.")

        excess = abs(roc) - self.threshold_pct
        confidence = 0.5 + min(0.5, max(excess, 0.0) / (2.0 * self.threshold_pct))

        if roc >= self.threshold_pct:
            return self._signal(
                SignalAction.BUY, confidence, f"Price rose {roc:.2f}% over {self.period} candles."
            )
        if roc <= -self.threshold_pct:
            return self._signal(
                SignalAction.SELL, confidence, f"Price fell {abs(roc):.2f}% over {self.period} candles."
            )
        return self._hold(f"Momentum {roc:.2f}% is inside the ±{self.threshold_pct:.1f}% threshold.")

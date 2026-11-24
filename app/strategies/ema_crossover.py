from app.schemas.strategy import Candle, SignalAction, StrategySignal
from app.strategies import indicators
from app.strategies.base import Strategy


class EmaCrossoverStrategy(Strategy):
    name = "ema_crossover"
    description = "Buy when the fast EMA crosses above the slow EMA; sell on the opposite cross."

    def __init__(self, fast_period: int = 9, slow_period: int = 21) -> None:
        if fast_period < 1 or fast_period >= slow_period:
            raise ValueError("fast_period must be at least 1 and smaller than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period

    @property
    def min_candles(self) -> int:
        return self.slow_period + 2

    def generate_signal(self, candles: list[Candle]) -> StrategySignal:
        if len(candles) < self.min_candles:
            return self._hold("Not enough candles.")

        closes = self._closes(candles)
        fast = indicators.ema(closes, self.fast_period)
        slow = indicators.ema(closes, self.slow_period)
        f_prev, f_now, s_prev, s_now = fast[-2], fast[-1], slow[-2], slow[-1]
        if any(v is None for v in (f_prev, f_now, s_prev, s_now)):
            return self._hold("Indicators not ready.")

        spread_pct = abs(f_now - s_now) / s_now * 100.0
        confidence = 0.6 + spread_pct

        if f_prev <= s_prev and f_now > s_now:
            return self._signal(
                SignalAction.BUY,
                confidence,
                f"Fast EMA({self.fast_period}) crossed above slow EMA({self.slow_period}).",
            )
        if f_prev >= s_prev and f_now < s_now:
            return self._signal(
                SignalAction.SELL,
                confidence,
                f"Fast EMA({self.fast_period}) crossed below slow EMA({self.slow_period}).",
            )
        return self._hold("No EMA crossover on the latest candle.")

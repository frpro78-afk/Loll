from app.schemas.strategy import Candle, SignalAction, StrategySignal
from app.strategies import indicators
from app.strategies.base import Strategy


class MacdStrategy(Strategy):
    name = "macd"
    description = "Buy when the MACD line crosses above its signal line; sell on the opposite cross."

    def __init__(
        self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
    ) -> None:
        if fast_period < 1 or fast_period >= slow_period or signal_period < 1:
            raise ValueError("Require 1 <= fast_period < slow_period and signal_period >= 1")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    @property
    def min_candles(self) -> int:
        return self.slow_period + self.signal_period + 2

    def generate_signal(self, candles: list[Candle]) -> StrategySignal:
        if len(candles) < self.min_candles:
            return self._hold("Not enough candles.")

        macd_line, _signal_line, histogram = indicators.macd(
            self._closes(candles),
            self.fast_period,
            self.slow_period,
            self.signal_period,
        )
        h_prev, h_now, m_now = histogram[-2], histogram[-1], macd_line[-1]
        if any(v is None for v in (h_prev, h_now, m_now)):
            return self._hold("Indicators not ready.")

        if h_prev <= 0 < h_now:
            confidence = 0.6 + (0.2 if m_now > 0 else 0.0)
            return self._signal(
                SignalAction.BUY, confidence, "MACD line crossed above its signal line."
            )
        if h_prev >= 0 > h_now:
            confidence = 0.6 + (0.2 if m_now < 0 else 0.0)
            return self._signal(
                SignalAction.SELL, confidence, "MACD line crossed below its signal line."
            )
        return self._hold("No MACD crossover on the latest candle.")

from app.schemas.strategy import Candle, SignalAction, StrategySignal
from app.strategies import indicators
from app.strategies.base import Strategy


class BollingerBandsStrategy(Strategy):
    name = "bollinger_bands"
    description = "Buy when the close is below the lower band; sell when above the upper band."

    def __init__(self, period: int = 20, num_std: float = 2.0) -> None:
        if period < 2 or num_std <= 0:
            raise ValueError("Require period >= 2 and num_std > 0")
        self.period = period
        self.num_std = num_std

    @property
    def min_candles(self) -> int:
        return self.period

    def generate_signal(self, candles: list[Candle]) -> StrategySignal:
        if len(candles) < self.min_candles:
            return self._hold("Not enough candles.")

        window = self._closes(candles)[-self.period :]
        _middle, upper_series, lower_series = indicators.bollinger_bands(
            window, self.period, self.num_std
        )
        upper, lower, close = upper_series[-1], lower_series[-1], window[-1]
        if upper is None or lower is None or upper == lower:
            return self._hold("Bands are not usable (flat prices or not enough data).")

        percent_b = (close - lower) / (upper - lower)
        confidence = 0.6 + min(0.4, abs(percent_b))

        if close < lower:
            return self._signal(SignalAction.BUY, confidence, "Close is below the lower Bollinger band.")
        if close > upper:
            return self._signal(SignalAction.SELL, confidence, "Close is above the upper Bollinger band.")
        return self._hold("Close is inside the Bollinger bands.")

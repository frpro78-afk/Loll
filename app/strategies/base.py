from abc import ABC, abstractmethod

from app.schemas.strategy import Candle, SignalAction, StrategySignal

# Strategies only look at this many of the most recent candles.
LOOKBACK = 200


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class Strategy(ABC):
    name: str
    description: str

    @property
    @abstractmethod
    def min_candles(self) -> int:
        """Minimum number of candles needed to produce a real signal."""

    @abstractmethod
    def generate_signal(self, candles: list[Candle]) -> StrategySignal:
        """Return a signal based on the most recent candle."""

    def _signal(
        self, action: SignalAction, confidence: float, reason: str
    ) -> StrategySignal:
        return StrategySignal(
            strategy=self.name,
            action=action,
            confidence=round(clamp(confidence), 4),
            reason=reason,
        )

    def _hold(self, reason: str) -> StrategySignal:
        return self._signal(SignalAction.HOLD, 0.0, reason)

    @staticmethod
    def _closes(candles: list[Candle]) -> list[float]:
        return [candle.close for candle in candles[-LOOKBACK:]]

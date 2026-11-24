from app.strategies.base import Strategy
from app.strategies.bollinger_strategy import BollingerBandsStrategy
from app.strategies.ema_crossover import EmaCrossoverStrategy
from app.strategies.macd_strategy import MacdStrategy
from app.strategies.momentum_strategy import MomentumStrategy
from app.strategies.rsi_strategy import RsiStrategy


class StrategyNotFoundError(Exception):
    """Raised when a strategy name is unknown."""


def get_all_strategies() -> list[Strategy]:
    return [
        EmaCrossoverStrategy(),
        RsiStrategy(),
        MacdStrategy(),
        BollingerBandsStrategy(),
        MomentumStrategy(),
    ]


def get_strategy(name: str) -> Strategy:
    for strategy in get_all_strategies():
        if strategy.name == name:
            return strategy
    available = ", ".join(s.name for s in get_all_strategies())
    raise StrategyNotFoundError(f"Unknown strategy '{name}'. Available: {available}.")

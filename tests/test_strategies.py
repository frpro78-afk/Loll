import math

import pytest

from app.schemas.strategy import SignalAction
from app.strategies import indicators
from app.strategies.bollinger_strategy import BollingerBandsStrategy
from app.strategies.ema_crossover import EmaCrossoverStrategy
from app.strategies.macd_strategy import MacdStrategy
from app.strategies.momentum_strategy import MomentumStrategy
from app.strategies.registry import (
    StrategyNotFoundError,
    get_all_strategies,
    get_strategy,
)
from app.strategies.rsi_strategy import RsiStrategy
from tests.helpers import candles_from_closes


def scan_actions(strategy, candles):
    return [
        strategy.generate_signal(candles[: i + 1]).action for i in range(len(candles))
    ]


@pytest.mark.parametrize("strategy", get_all_strategies(), ids=lambda s: s.name)
def test_not_enough_candles_returns_hold(strategy):
    signal = strategy.generate_signal(candles_from_closes([100.0] * 5))
    assert signal.action is SignalAction.HOLD
    assert signal.confidence == 0.0


@pytest.mark.parametrize("strategy", get_all_strategies(), ids=lambda s: s.name)
def test_confidence_is_bounded_and_output_is_deterministic(strategy):
    closes = [100.0 + 10 * math.sin(i / 5) + 0.05 * i for i in range(300)]
    candles = candles_from_closes(closes)
    first = [strategy.generate_signal(candles[: i + 1]) for i in range(len(candles))]
    second = [strategy.generate_signal(candles[: i + 1]) for i in range(len(candles))]
    assert first == second
    assert all(0.0 <= s.confidence <= 1.0 for s in first)


def test_ema_crossover_buys_on_upturn_and_sells_on_downturn():
    closes = (
        [100.0 - 0.5 * i for i in range(40)]
        + [80.0 + 2.0 * i for i in range(30)]
        + [138.0 - 3.0 * i for i in range(1, 31)]
    )
    actions = scan_actions(EmaCrossoverStrategy(), candles_from_closes(closes))
    first_buy = actions.index(SignalAction.BUY)
    first_sell = actions.index(SignalAction.SELL)
    assert 40 <= first_buy < 70
    assert first_sell >= 70
    assert first_buy < first_sell


def test_ema_crossover_rejects_bad_periods():
    with pytest.raises(ValueError):
        EmaCrossoverStrategy(fast_period=20, slow_period=10)


def test_ema_and_macd_signal_both_directions_on_oscillating_prices():
    closes = [100.0 + 10 * math.sin(i / 5) for i in range(300)]
    candles = candles_from_closes(closes)
    for strategy in (EmaCrossoverStrategy(), MacdStrategy()):
        actions = scan_actions(strategy, candles)
        assert SignalAction.BUY in actions
        assert SignalAction.SELL in actions


def test_rsi_buys_when_oversold_and_sells_when_overbought():
    falling = RsiStrategy().generate_signal(
        candles_from_closes([100.0 - i for i in range(40)])
    )
    assert falling.action is SignalAction.BUY
    assert falling.confidence == pytest.approx(1.0)

    rising = RsiStrategy().generate_signal(
        candles_from_closes([100.0 + i for i in range(40)])
    )
    assert rising.action is SignalAction.SELL
    assert rising.confidence == pytest.approx(1.0)


def test_rsi_holds_in_neutral_zone():
    closes = [100.0 if i % 2 == 0 else 101.0 for i in range(40)]
    assert RsiStrategy().generate_signal(candles_from_closes(closes)).action is SignalAction.HOLD


def test_macd_decision_logic_with_controlled_indicator_output(monkeypatch):
    candles = candles_from_closes([100.0] * 40)
    strategy = MacdStrategy()

    monkeypatch.setattr(
        indicators, "macd", lambda *a, **k: ([0.0, 1.0], [0.0, 0.5], [-0.5, 0.5])
    )
    buy = strategy.generate_signal(candles)
    assert buy.action is SignalAction.BUY
    assert buy.confidence == pytest.approx(0.8)

    monkeypatch.setattr(
        indicators, "macd", lambda *a, **k: ([0.0, -1.0], [0.0, -0.5], [0.5, -0.5])
    )
    sell = strategy.generate_signal(candles)
    assert sell.action is SignalAction.SELL
    assert sell.confidence == pytest.approx(0.8)

    monkeypatch.setattr(
        indicators, "macd", lambda *a, **k: ([0.0, 1.0], [0.0, 0.5], [0.5, 0.4])
    )
    assert strategy.generate_signal(candles).action is SignalAction.HOLD

    monkeypatch.setattr(
        indicators, "macd", lambda *a, **k: ([None, 1.0], [None, 0.5], [None, 0.5])
    )
    assert strategy.generate_signal(candles).action is SignalAction.HOLD


def test_bollinger_buys_below_lower_band_and_sells_above_upper_band():
    buy = BollingerBandsStrategy().generate_signal(
        candles_from_closes([100.0] * 19 + [90.0])
    )
    assert buy.action is SignalAction.BUY
    assert 0.6 <= buy.confidence <= 1.0

    sell = BollingerBandsStrategy().generate_signal(
        candles_from_closes([100.0] * 19 + [110.0])
    )
    assert sell.action is SignalAction.SELL


def test_bollinger_holds_on_flat_prices():
    signal = BollingerBandsStrategy().generate_signal(candles_from_closes([100.0] * 25))
    assert signal.action is SignalAction.HOLD


def test_momentum_thresholds():
    buy = MomentumStrategy().generate_signal(candles_from_closes([100.0] * 10 + [103.0]))
    assert buy.action is SignalAction.BUY
    assert buy.confidence == pytest.approx(0.75)

    sell = MomentumStrategy().generate_signal(candles_from_closes([100.0] * 10 + [97.0]))
    assert sell.action is SignalAction.SELL
    assert sell.confidence == pytest.approx(0.75)

    hold = MomentumStrategy().generate_signal(candles_from_closes([100.0] * 10 + [101.0]))
    assert hold.action is SignalAction.HOLD


def test_registry_lookup():
    names = [s.name for s in get_all_strategies()]
    assert names == ["ema_crossover", "rsi", "macd", "bollinger_bands", "momentum"]
    assert get_strategy("rsi").name == "rsi"
    with pytest.raises(StrategyNotFoundError):
        get_strategy("does_not_exist")

import math

import pytest

from app.services.backtest import run_backtest
from app.services.risk import RiskParams
from app.strategies.ema_crossover import EmaCrossoverStrategy
from app.strategies.macd_strategy import MacdStrategy
from app.strategies.rsi_strategy import RsiStrategy
from tests.helpers import ScriptedStrategy, candles_from_closes


def test_signal_exit_fills_on_the_next_candle_open():
    from decimal import Decimal

    candles = candles_from_closes([100.0 + i for i in range(40)])
    wide = RiskParams(stop_loss_pct=Decimal("50"), take_profit_pct=Decimal("500"))
    result = run_backtest(
        ScriptedStrategy(buy_at=10, sell_at=20), candles, risk=wide, fee_pct=0.0
    )
    assert result.trade_count == 1
    trade = result.trades[0]
    # Signals appeared after candle 9 and candle 19; fills happen one candle later.
    assert trade.entry_index == 10
    assert trade.exit_index == 20
    assert trade.entry_price == pytest.approx(109.0)
    assert trade.exit_price == pytest.approx(119.0)
    assert trade.exit_reason == "signal"
    assert trade.pnl > 0


def test_stop_loss_exit():
    closes = [100.0] * 10 + [100.0 - 2 * i for i in range(1, 31)]
    result = run_backtest(
        ScriptedStrategy(buy_at=10), candles_from_closes(closes), fee_pct=0.0
    )
    trade = result.trades[0]
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price == pytest.approx(98.0)
    assert trade.pnl == pytest.approx(-50.0)
    assert result.max_drawdown_pct > 0


def test_take_profit_exit():
    closes = [100.0] * 10 + [100.0 + 3 * i for i in range(1, 31)]
    result = run_backtest(
        ScriptedStrategy(buy_at=10), candles_from_closes(closes), fee_pct=0.0
    )
    trade = result.trades[0]
    assert trade.exit_reason == "take_profit"
    assert trade.exit_price == pytest.approx(104.0)
    assert trade.pnl > 0
    assert result.win_rate_pct == 100.0


def test_open_position_is_closed_at_end_of_data():
    candles = candles_from_closes([100.0] * 30)
    result = run_backtest(ScriptedStrategy(buy_at=10), candles, fee_pct=0.0)
    assert result.trades[0].exit_reason == "end_of_data"
    assert result.trades[0].pnl == pytest.approx(0.0)


def test_fees_reduce_profit():
    candles = candles_from_closes([100.0] * 30)
    result = run_backtest(ScriptedStrategy(buy_at=10), candles, fee_pct=0.1)
    # 25 units * 100 = 2500 notional; 0.1% per side = 5.0 total.
    assert result.trades[0].pnl == pytest.approx(-5.0)
    assert result.ending_equity < result.starting_cash


def test_no_signals_means_no_trades():
    candles = candles_from_closes([100.0 + i for i in range(50)])
    result = run_backtest(ScriptedStrategy(), candles, starting_cash=5000.0)
    assert result.trade_count == 0
    assert result.ending_equity == pytest.approx(5000.0)
    assert result.total_return_pct == 0.0
    assert result.win_rate_pct == 0.0
    assert result.max_drawdown_pct == 0.0


def test_buy_and_hold_benchmark():
    candles = candles_from_closes([100.0, 110.0, 121.0])
    result = run_backtest(ScriptedStrategy(), candles)
    assert result.buy_and_hold_return_pct == pytest.approx(21.0)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        run_backtest(ScriptedStrategy(), [])
    with pytest.raises(ValueError):
        run_backtest(ScriptedStrategy(), candles_from_closes([100.0]), starting_cash=0)
    with pytest.raises(ValueError):
        run_backtest(ScriptedStrategy(), candles_from_closes([100.0]), fee_pct=-1)


@pytest.mark.parametrize(
    "strategy", [EmaCrossoverStrategy(), RsiStrategy(), MacdStrategy()], ids=lambda s: s.name
)
def test_real_strategies_run_and_are_repeatable(strategy):
    closes = [100.0 + 10 * math.sin(i / 5) + 0.05 * i for i in range(400)]
    candles = candles_from_closes(closes)
    first = run_backtest(strategy, candles, symbol="BTCUSDT", interval="1h")
    second = run_backtest(strategy, candles, symbol="BTCUSDT", interval="1h")
    assert first == second
    assert first.candles_used == 400
    assert 0.0 <= first.max_drawdown_pct <= 100.0
    assert first.ending_equity > 0

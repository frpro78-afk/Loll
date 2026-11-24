from decimal import Decimal

from app.schemas.strategy import SignalAction
from app.services.risk import RiskParams
from app.services.strategy_engine import EngineParams, evaluate_strategies
from tests.helpers import StubStrategy, candles_from_closes

CANDLES = candles_from_closes([100.0 + (i % 7) for i in range(120)])

# Gates wide open, so these tests focus on selection logic.
PERMISSIVE = EngineParams(
    min_confidence=0.55,
    min_backtest_trades=0,
    min_backtest_return_pct=-1000.0,
    max_backtest_drawdown_pct=100.0,
    backtest_fee_pct=0.0,
    backtest_starting_cash=10_000.0,
)


def run(strategies, held="0", open_positions=0, params=PERMISSIVE):
    return evaluate_strategies(
        symbol="BTCUSDT",
        interval="1h",
        candles=CANDLES,
        price=Decimal("100"),
        held_quantity=Decimal(held),
        cash=Decimal("10000"),
        equity=Decimal("10000"),
        open_positions=open_positions,
        strategies=strategies,
        risk=RiskParams(),
        params=params,
    )


def test_highest_confidence_eligible_buy_wins():
    decision = run(
        [
            StubStrategy("a", SignalAction.BUY, 0.70),
            StubStrategy("b", SignalAction.BUY, 0.90),
            StubStrategy("c", SignalAction.SELL, 0.99),
        ]
    )
    assert decision.selected.strategy == "b"
    assert decision.risk.approved
    assert decision.risk.quantity > 0
    by_name = {e.signal.strategy: e for e in decision.evaluations}
    assert not by_name["c"].eligible
    assert any("No position" in r for r in by_name["c"].ineligible_reasons)


def test_ties_are_broken_by_name():
    decision = run(
        [
            StubStrategy("beta", SignalAction.BUY, 0.80),
            StubStrategy("alpha", SignalAction.BUY, 0.80),
        ]
    )
    assert decision.selected.strategy == "alpha"


def test_when_holding_a_position_only_sell_is_eligible():
    decision = run(
        [
            StubStrategy("buyer", SignalAction.BUY, 0.90),
            StubStrategy("seller", SignalAction.SELL, 0.80),
        ],
        held="3",
    )
    assert decision.selected.strategy == "seller"
    assert decision.selected.action is SignalAction.SELL
    assert decision.risk.approved
    assert decision.risk.quantity == Decimal("3")
    buyer = next(e for e in decision.evaluations if e.signal.strategy == "buyer")
    assert any("Already holding" in r for r in buyer.ineligible_reasons)


def test_low_confidence_is_not_eligible():
    decision = run([StubStrategy("weak", SignalAction.BUY, 0.40)])
    assert decision.selected is None
    assert decision.risk is None
    assert "No eligible" in decision.message


def test_hold_signals_are_never_selected():
    decision = run([StubStrategy("idle", SignalAction.HOLD, 0.0)])
    assert decision.selected is None


def test_backtest_gate_blocks_buy_entries():
    strict = EngineParams(
        min_confidence=0.55,
        min_backtest_trades=10_000,
        min_backtest_return_pct=-1000.0,
        max_backtest_drawdown_pct=100.0,
        backtest_fee_pct=0.0,
    )
    decision = run([StubStrategy("a", SignalAction.BUY, 0.9)], params=strict)
    assert decision.selected is None
    assert any("backtest" in r.lower() for r in decision.evaluations[0].ineligible_reasons)


def test_risk_rejection_is_reported_not_hidden():
    decision = run([StubStrategy("a", SignalAction.BUY, 0.9)], open_positions=3)
    assert decision.selected is not None
    assert decision.risk is not None and not decision.risk.approved
    assert "rejected" in decision.message


def test_every_strategy_is_evaluated_even_when_one_is_selected():
    decision = run(
        [StubStrategy("a", SignalAction.BUY, 0.9), StubStrategy("b", SignalAction.HOLD, 0.0)]
    )
    assert len(decision.evaluations) == 2
    assert decision.candles_used == len(CANDLES)

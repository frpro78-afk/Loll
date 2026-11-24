from decimal import Decimal

import pytest

from app.services.risk import RiskParams, assess_buy, assess_sell

D = Decimal


def test_position_is_capped_by_max_position_pct():
    decision = assess_buy(D("100"), D("10000"), D("10000"), 0, RiskParams())
    assert decision.approved
    # Risk-based size would be 50 units (5000), but the 25% cap allows 25 units.
    assert decision.quantity == D("25")
    assert decision.stop_loss == D("98")
    assert decision.take_profit == D("104")


def test_position_is_sized_by_risk_when_below_cap():
    params = RiskParams(max_position_pct=D("100"))
    decision = assess_buy(D("100"), D("10000"), D("10000"), 0, params)
    # Lose 1% of 10000 = 100 if the 2% stop is hit: 100 / 2 = 50 units.
    assert decision.quantity == D("50")


def test_position_is_capped_by_available_cash():
    params = RiskParams(max_position_pct=D("100"))
    decision = assess_buy(D("100"), D("10000"), D("1000"), 0, params)
    assert decision.quantity == D("10")


def test_rejects_when_max_open_positions_reached():
    decision = assess_buy(D("100"), D("10000"), D("10000"), 3, RiskParams())
    assert not decision.approved
    assert decision.quantity == 0


def test_rejects_order_below_minimum_notional():
    decision = assess_buy(D("100"), D("20"), D("20"), 0, RiskParams())
    assert not decision.approved


@pytest.mark.parametrize(
    "price,equity,cash",
    [(D("0"), D("1000"), D("1000")), (D("100"), D("0"), D("1000")), (D("100"), D("1000"), D("0"))],
)
def test_rejects_invalid_inputs(price, equity, cash):
    assert not assess_buy(price, equity, cash, 0, RiskParams()).approved


def test_quantity_is_rounded_down_and_never_exceeds_cap():
    decision = assess_buy(D("3"), D("10000"), D("10000"), 0, RiskParams())
    assert decision.quantity == decision.quantity.quantize(D("0.00000001"))
    assert decision.quantity * D("3") <= D("2500")


def test_stop_and_target_bracket_the_entry():
    decision = assess_buy(D("250"), D("10000"), D("10000"), 0, RiskParams())
    assert decision.stop_loss < decision.entry_price < decision.take_profit


def test_assess_buy_is_deterministic():
    args = (D("123.45"), D("5000"), D("4000"), 1, RiskParams())
    assert assess_buy(*args) == assess_buy(*args)


def test_sell_closes_full_position_and_rejects_when_flat():
    ok = assess_sell(D("2"), D("100"))
    assert ok.approved and ok.quantity == D("2") and ok.notional == D("200")
    assert not assess_sell(D("0"), D("100")).approved


def test_invalid_risk_params_are_rejected():
    with pytest.raises(ValueError):
        RiskParams(stop_loss_pct=D("0"))
    with pytest.raises(ValueError):
        RiskParams(max_open_positions=0)
    with pytest.raises(ValueError):
        RiskParams(max_position_pct=D("150"))

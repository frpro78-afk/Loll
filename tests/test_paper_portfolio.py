from decimal import Decimal

import pytest

from app.schemas.trading import OrderSide
from app.services.paper_trading import PaperPortfolio, PaperTradingError


def make_portfolio() -> PaperPortfolio:
    return PaperPortfolio(Decimal("1000"), "USDT")


def test_buy_reduces_cash_and_adds_position():
    p = make_portfolio()
    p.execute_market_order("BTCUSDT", OrderSide.BUY, Decimal("0.01"), Decimal("50000"))
    assert p.cash == Decimal("500")
    assert p.positions["BTCUSDT"] == Decimal("0.01")


def test_cannot_spend_more_than_cash():
    p = make_portfolio()
    with pytest.raises(PaperTradingError):
        p.execute_market_order("BTCUSDT", OrderSide.BUY, Decimal("1"), Decimal("50000"))


def test_cannot_sell_more_than_held():
    p = make_portfolio()
    with pytest.raises(PaperTradingError):
        p.execute_market_order("BTCUSDT", OrderSide.SELL, Decimal("1"), Decimal("50000"))


def test_sell_all_removes_position_and_restores_cash():
    p = make_portfolio()
    p.execute_market_order("BTCUSDT", OrderSide.BUY, Decimal("0.01"), Decimal("50000"))
    p.execute_market_order("BTCUSDT", OrderSide.SELL, Decimal("0.01"), Decimal("60000"))
    assert "BTCUSDT" not in p.positions
    assert p.cash == Decimal("1100")

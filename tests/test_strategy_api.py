from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.strategy import SignalAction
from app.services.market_data import MarketDataError
from app.services.paper_trading import get_portfolio
from app.services.risk import RiskParams
from app.services.strategy_engine import EngineParams
from tests.helpers import StubStrategy, candles_from_closes

client = TestClient(app)

CANDLES = candles_from_closes([100.0 + (i % 10) for i in range(150)])
PERMISSIVE = EngineParams(
    min_confidence=0.55,
    min_backtest_trades=0,
    min_backtest_return_pct=-1000.0,
    max_backtest_drawdown_pct=100.0,
    backtest_fee_pct=0.0,
)


def quote_symbol() -> str:
    return "BTC" + get_portfolio().quote_asset


@pytest.fixture(autouse=True)
def reset_portfolio():
    get_portfolio().reset()
    yield
    get_portfolio().reset()


@pytest.fixture
def mock_market(monkeypatch):
    async def fake_candles(symbol, interval, limit, settings):
        return CANDLES

    async def fake_price(symbol, settings):
        return Decimal("100")

    monkeypatch.setattr("app.api.strategy.get_historical_candles", fake_candles)
    monkeypatch.setattr("app.api.strategy.get_spot_price", fake_price)


def use_stub_strategies(monkeypatch, strategies):
    monkeypatch.setattr("app.api.strategy.get_all_strategies", lambda: strategies)
    monkeypatch.setattr(
        "app.api.strategy.engine_params_from_settings", lambda settings: PERMISSIVE
    )
    monkeypatch.setattr(
        "app.api.strategy.risk_params_from_settings", lambda settings: RiskParams()
    )


def test_phase_1_routes_are_still_registered():
    paths = app.openapi()["paths"]
    for path in ("/health", "/market/price/{symbol}", "/paper/orders", "/paper/portfolio", "/paper/reset"):
        assert path in paths


def test_list_strategies():
    response = client.get("/strategy/list")
    assert response.status_code == 200
    assert [s["name"] for s in response.json()] == [
        "ema_crossover", "rsi", "macd", "bollinger_bands", "momentum",
    ]


def test_backtest_all_strategies(mock_market):
    response = client.post(
        "/strategy/backtest", json={"symbol": "BTCUSDT", "interval": "1h", "limit": 150}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 5
    assert all(result["trades"] == [] for result in body)


def test_backtest_single_strategy_with_trades(mock_market):
    response = client.post(
        "/strategy/backtest",
        json={"symbol": "BTCUSDT", "limit": 150, "strategy": "rsi", "include_trades": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1 and body[0]["strategy"] == "rsi"
    assert isinstance(body[0]["trades"], list)


def test_backtest_unknown_strategy_returns_404(mock_market):
    response = client.post(
        "/strategy/backtest", json={"symbol": "BTCUSDT", "limit": 150, "strategy": "nope"}
    )
    assert response.status_code == 404


def test_request_validation():
    assert client.post("/strategy/analyze", json={"symbol": "btcusdt"}).status_code == 422
    assert client.post("/strategy/analyze", json={"symbol": "BTCUSDT", "interval": "2h"}).status_code == 422
    assert client.post("/strategy/analyze", json={"symbol": "BTCUSDT", "limit": 50}).status_code == 422


def test_market_data_failure_returns_502(monkeypatch):
    async def failing_candles(symbol, interval, limit, settings):
        raise MarketDataError("boom")

    monkeypatch.setattr("app.api.strategy.get_historical_candles", failing_candles)
    response = client.post("/strategy/analyze", json={"symbol": quote_symbol(), "limit": 150})
    assert response.status_code == 502


def test_analyze_never_changes_the_portfolio(mock_market):
    portfolio = get_portfolio()
    cash_before = portfolio.cash
    response = client.post("/strategy/analyze", json={"symbol": quote_symbol(), "limit": 150})
    assert response.status_code == 200
    body = response.json()
    assert len(body["evaluations"]) == 5
    assert "message" in body
    assert portfolio.cash == cash_before
    assert portfolio.positions == {}


def test_paper_execute_buy_then_sell(mock_market, monkeypatch):
    portfolio = get_portfolio()
    cash_before = portfolio.cash
    symbol = quote_symbol()

    use_stub_strategies(monkeypatch, [StubStrategy("stub_buy", SignalAction.BUY, 0.9)])
    buy = client.post("/strategy/paper-execute", json={"symbol": symbol, "limit": 150})
    assert buy.status_code == 200
    buy_body = buy.json()
    assert buy_body["executed"] is True
    assert buy_body["order"]["side"] == "buy"
    assert buy_body["order"]["simulated"] is True
    quantity = Decimal(buy_body["order"]["quantity"])
    assert quantity > 0
    assert portfolio.positions[symbol] == quantity

    use_stub_strategies(monkeypatch, [StubStrategy("stub_sell", SignalAction.SELL, 0.9)])
    sell = client.post("/strategy/paper-execute", json={"symbol": symbol, "limit": 150})
    assert sell.json()["executed"] is True
    assert portfolio.positions == {}
    assert portfolio.cash == cash_before  # same price both ways, no paper fees


def test_paper_execute_does_nothing_without_an_eligible_signal(mock_market, monkeypatch):
    portfolio = get_portfolio()
    cash_before = portfolio.cash
    use_stub_strategies(monkeypatch, [StubStrategy("idle", SignalAction.HOLD, 0.0)])
    response = client.post("/strategy/paper-execute", json={"symbol": quote_symbol(), "limit": 150})
    assert response.status_code == 200
    assert response.json()["executed"] is False
    assert response.json()["order"] is None
    assert portfolio.cash == cash_before


def test_paper_execute_rejects_symbols_not_in_the_quote_asset(mock_market):
    response = client.post("/strategy/paper-execute", json={"symbol": "BTCZZZ", "limit": 150})
    assert response.status_code == 400

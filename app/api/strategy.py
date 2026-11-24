from decimal import Decimal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.schemas.strategy import (
    BacktestRequest,
    BacktestResult,
    Candle,
    EngineDecision,
    SignalAction,
    StrategyExecutionResponse,
    StrategyInfo,
    StrategyRunRequest,
)
from app.schemas.trading import OrderSide, PaperOrderResponse
from app.services.backtest import run_backtest
from app.services.candle_data import get_historical_candles
from app.services.market_data import MarketDataError, get_spot_price
from app.services.paper_trading import (
    PaperPortfolio,
    PaperTradingError,
    get_portfolio,
)
from app.services.risk import RiskParams, risk_params_from_settings
from app.services.strategy_engine import (
    EngineParams,
    engine_params_from_settings,
    evaluate_strategies,
)
from app.strategies.base import Strategy
from app.strategies.registry import (
    StrategyNotFoundError,
    get_all_strategies,
    get_strategy,
)

router = APIRouter(prefix="/strategy", tags=["strategy engine"])

MIN_CANDLES_REQUIRED = 100


async def _load_candles(request: StrategyRunRequest, settings: Settings) -> list[Candle]:
    try:
        candles = await get_historical_candles(
            request.symbol, request.interval, request.limit, settings
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if len(candles) < MIN_CANDLES_REQUIRED:
        raise HTTPException(
            status_code=502,
            detail=f"Only {len(candles)} candles returned; at least {MIN_CANDLES_REQUIRED} required.",
        )
    return candles


async def _fetch_price(symbol: str, settings: Settings) -> Decimal:
    try:
        return await get_spot_price(symbol, settings)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _require_quote_asset(symbol: str, quote_asset: str) -> None:
    if not symbol.endswith(quote_asset):
        raise HTTPException(
            status_code=400, detail=f"Symbol must be quoted in {quote_asset}."
        )


async def _estimate_equity(
    portfolio: PaperPortfolio, symbol: str, price: Decimal, settings: Settings
) -> Decimal:
    """Cash plus the current value of every paper position."""
    equity = portfolio.cash
    for held_symbol, quantity in list(portfolio.positions.items()):
        if held_symbol == symbol:
            held_price = price
        else:
            held_price = await _fetch_price(held_symbol, settings)
        equity += quantity * held_price
    return equity


def _run_backtests(
    strategies: list[Strategy],
    candles: list[Candle],
    request: BacktestRequest,
    settings: Settings,
    risk: RiskParams,
) -> list[BacktestResult]:
    results = []
    for strategy in strategies:
        result = run_backtest(
            strategy,
            candles,
            symbol=request.symbol,
            interval=request.interval,
            starting_cash=float(settings.paper_starting_balance),
            risk=risk,
            fee_pct=settings.backtest_fee_pct,
        )
        if not request.include_trades:
            result = result.model_copy(update={"trades": []})
        results.append(result)
    return results


async def _build_decision(request: StrategyRunRequest, settings: Settings) -> EngineDecision:
    portfolio = get_portfolio()
    _require_quote_asset(request.symbol, portfolio.quote_asset)

    candles = await _load_candles(request, settings)
    price = await _fetch_price(request.symbol, settings)
    equity = await _estimate_equity(portfolio, request.symbol, price, settings)
    held_quantity = portfolio.positions.get(request.symbol, Decimal("0"))

    engine_params: EngineParams = engine_params_from_settings(settings)
    risk = risk_params_from_settings(settings)

    return await run_in_threadpool(
        evaluate_strategies,
        symbol=request.symbol,
        interval=request.interval,
        candles=candles,
        price=price,
        held_quantity=held_quantity,
        cash=portfolio.cash,
        equity=equity,
        open_positions=len(portfolio.positions),
        strategies=get_all_strategies(),
        risk=risk,
        params=engine_params,
    )


@router.get("/list", response_model=list[StrategyInfo])
async def list_strategies() -> list[StrategyInfo]:
    return [
        StrategyInfo(name=s.name, description=s.description)
        for s in get_all_strategies()
    ]


@router.post("/backtest", response_model=list[BacktestResult])
async def backtest(request: BacktestRequest) -> list[BacktestResult]:
    settings = get_settings()

    if request.strategy is not None:
        try:
            strategies = [get_strategy(request.strategy)]
        except StrategyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        strategies = get_all_strategies()

    candles = await _load_candles(request, settings)
    risk = risk_params_from_settings(settings)
    return await run_in_threadpool(
        _run_backtests, strategies, candles, request, settings, risk
    )


@router.post("/analyze", response_model=EngineDecision)
async def analyze(request: StrategyRunRequest) -> EngineDecision:
    """Evaluate all strategies and return the decision. Places no order."""
    return await _build_decision(request, get_settings())


@router.post("/paper-execute", response_model=StrategyExecutionResponse)
async def paper_execute(request: StrategyRunRequest) -> StrategyExecutionResponse:
    """Run the engine once and, if approved, place a SIMULATED order on the paper portfolio."""
    settings = get_settings()
    portfolio = get_portfolio()
    decision = await _build_decision(request, settings)

    selected, risk = decision.selected, decision.risk
    if selected is None or risk is None or not risk.approved:
        return StrategyExecutionResponse(decision=decision, executed=False, order=None)

    side = OrderSide.BUY if selected.action is SignalAction.BUY else OrderSide.SELL
    try:
        notional = portfolio.execute_market_order(
            request.symbol, side, risk.quantity, decision.price
        )
    except PaperTradingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    order = PaperOrderResponse(
        symbol=request.symbol,
        side=side,
        quantity=risk.quantity,
        fill_price=decision.price,
        notional=notional,
    )
    return StrategyExecutionResponse(decision=decision, executed=True, order=order)

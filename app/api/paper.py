from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.trading import (
    PaperOrderRequest,
    PaperOrderResponse,
    PortfolioResponse,
)
from app.services.market_data import MarketDataError, get_spot_price
from app.services.paper_trading import PaperTradingError, get_portfolio

router = APIRouter(prefix="/paper", tags=["paper trading"])


@router.post("/orders", response_model=PaperOrderResponse)
async def place_paper_order(order: PaperOrderRequest) -> PaperOrderResponse:
    settings = get_settings()
    portfolio = get_portfolio()

    if not order.symbol.endswith(portfolio.quote_asset):
        raise HTTPException(
            status_code=400,
            detail=f"Symbol must be quoted in {portfolio.quote_asset}.",
        )

    try:
        price = await get_spot_price(order.symbol, settings)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        notional = portfolio.execute_market_order(
            order.symbol, order.side, order.quantity, price
        )
    except PaperTradingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PaperOrderResponse(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        fill_price=price,
        notional=notional,
    )


@router.get("/portfolio", response_model=PortfolioResponse)
async def view_portfolio() -> PortfolioResponse:
    portfolio = get_portfolio()
    return PortfolioResponse(
        quote_asset=portfolio.quote_asset,
        cash_balance=portfolio.cash,
        positions=portfolio.positions,
    )


@router.post("/reset", response_model=PortfolioResponse)
async def reset_portfolio() -> PortfolioResponse:
    portfolio = get_portfolio()
    portfolio.reset()
    return PortfolioResponse(
        quote_asset=portfolio.quote_asset,
        cash_balance=portfolio.cash,
        positions=portfolio.positions,
    )

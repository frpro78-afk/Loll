from fastapi import APIRouter, HTTPException, Path

from app.core.config import get_settings
from app.schemas.trading import PriceResponse
from app.services.market_data import MarketDataError, get_spot_price

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/price/{symbol}", response_model=PriceResponse)
async def spot_price(
    symbol: str = Path(pattern=r"^[A-Z0-9]{5,12}$", examples=["BTCUSDT"]),
) -> PriceResponse:
    try:
        price = await get_spot_price(symbol, get_settings())
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PriceResponse(symbol=symbol, price=price)

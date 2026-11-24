import httpx

from app.core.config import Settings
from app.schemas.strategy import Candle
from app.services.market_data import MarketDataError


async def get_historical_candles(
    symbol: str, interval: str, limit: int, settings: Settings
) -> list[Candle]:
    """Fetch up to `limit` closed spot candles, oldest first."""
    url = f"{settings.market_data_base_url.rstrip('/')}/api/v3/klines"
    # Ask for one extra: the newest candle is still open and gets dropped.
    params = {"symbol": symbol, "interval": interval, "limit": limit + 1}
    try:
        async with httpx.AsyncClient(
            timeout=settings.market_data_timeout_seconds
        ) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            rows = response.json()
        candles = [
            Candle(
                open_time=int(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
            )
            for row in rows
        ]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise MarketDataError(
            f"Could not fetch historical candles for {symbol}."
        ) from exc
    return candles[:-1]

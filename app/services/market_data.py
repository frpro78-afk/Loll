from decimal import Decimal, InvalidOperation

import httpx

from app.core.config import Settings


class MarketDataError(Exception):
    """Raised when a spot price cannot be fetched or understood."""


async def get_spot_price(symbol: str, settings: Settings) -> Decimal:
    """Fetch the latest spot price for a symbol such as BTCUSDT."""
    url = f"{settings.market_data_base_url.rstrip('/')}/api/v3/ticker/price"
    try:
        async with httpx.AsyncClient(
            timeout=settings.market_data_timeout_seconds
        ) as client:
            response = await client.get(url, params={"symbol": symbol})
            response.raise_for_status()
            data = response.json()
        return Decimal(data["price"])
    except (httpx.HTTPError, KeyError, ValueError, InvalidOperation) as exc:
        raise MarketDataError(f"Could not fetch spot price for {symbol}.") from exc

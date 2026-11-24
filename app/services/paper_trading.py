from decimal import Decimal
from functools import lru_cache

from app.core.config import get_settings
from app.schemas.trading import OrderSide


class PaperTradingError(Exception):
    """Raised when a simulated order breaks a paper-trading rule."""


class PaperPortfolio:
    """In-memory simulated portfolio. Resets when the server restarts."""

    def __init__(self, starting_balance: Decimal, quote_asset: str) -> None:
        self._starting_balance = starting_balance
        self.quote_asset = quote_asset
        self.cash: Decimal = starting_balance
        self.positions: dict[str, Decimal] = {}

    def reset(self) -> None:
        self.cash = self._starting_balance
        self.positions = {}

    def execute_market_order(
        self, symbol: str, side: OrderSide, quantity: Decimal, price: Decimal
    ) -> Decimal:
        """Apply a simulated fill and return its notional value."""
        notional = quantity * price

        if side == OrderSide.BUY:
            if notional > self.cash:
                raise PaperTradingError("Insufficient paper cash balance.")
            self.cash -= notional
            self.positions[symbol] = self.positions.get(symbol, Decimal("0")) + quantity
        else:
            held = self.positions.get(symbol, Decimal("0"))
            if quantity > held:
                raise PaperTradingError("Insufficient paper position to sell.")
            self.cash += notional
            remaining = held - quantity
            if remaining == 0:
                self.positions.pop(symbol, None)
            else:
                self.positions[symbol] = remaining

        return notional


@lru_cache
def get_portfolio() -> PaperPortfolio:
    """Return the single shared paper portfolio for this server process."""
    settings = get_settings()
    return PaperPortfolio(
        starting_balance=settings.paper_starting_balance,
        quote_asset=settings.paper_quote_asset,
    )

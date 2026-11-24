from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from app.core.config import Settings
from app.schemas.strategy import RiskDecision

QUANTITY_STEP = Decimal("0.00000001")
PRICE_STEP = Decimal("0.00000001")
HUNDRED = Decimal("100")
ZERO = Decimal("0")


@dataclass(frozen=True)
class RiskParams:
    risk_per_trade_pct: Decimal = Decimal("1")
    stop_loss_pct: Decimal = Decimal("2")
    take_profit_pct: Decimal = Decimal("4")
    max_position_pct: Decimal = Decimal("25")
    max_open_positions: int = 3
    min_order_notional: Decimal = Decimal("10")

    def __post_init__(self) -> None:
        for name in (
            "risk_per_trade_pct",
            "stop_loss_pct",
            "take_profit_pct",
            "max_position_pct",
        ):
            value = getattr(self, name)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_position_pct > 100 or self.stop_loss_pct > 100:
            raise ValueError("percentages above 100 are not allowed here")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1")
        if self.min_order_notional < 0:
            raise ValueError("min_order_notional cannot be negative")


def risk_params_from_settings(settings: Settings) -> RiskParams:
    return RiskParams(
        risk_per_trade_pct=settings.risk_per_trade_pct,
        stop_loss_pct=settings.risk_stop_loss_pct,
        take_profit_pct=settings.risk_take_profit_pct,
        max_position_pct=settings.risk_max_position_pct,
        max_open_positions=settings.risk_max_open_positions,
        min_order_notional=settings.risk_min_order_notional,
    )


def _reject(reason: str, entry_price: Decimal) -> RiskDecision:
    return RiskDecision(
        approved=False,
        reason=reason,
        quantity=ZERO,
        notional=ZERO,
        entry_price=entry_price,
    )


def assess_buy(
    entry_price: Decimal,
    equity: Decimal,
    cash: Decimal,
    open_positions: int,
    params: RiskParams,
) -> RiskDecision:
    """Size a spot buy and set stop-loss / take-profit levels, or reject it."""
    if entry_price <= 0:
        return _reject("Entry price must be positive.", entry_price)
    if equity <= 0:
        return _reject("Account equity must be positive.", entry_price)
    if cash <= 0:
        return _reject("No cash available.", entry_price)
    if open_positions >= params.max_open_positions:
        return _reject(
            f"Max open positions ({params.max_open_positions}) reached.", entry_price
        )

    stop_fraction = params.stop_loss_pct / HUNDRED
    take_profit_fraction = params.take_profit_pct / HUNDRED

    # Size so that being stopped out loses risk_per_trade_pct of equity.
    risk_amount = equity * params.risk_per_trade_pct / HUNDRED
    quantity_by_risk = risk_amount / (entry_price * stop_fraction)
    # Never put more than max_position_pct of equity in one position.
    quantity_by_cap = (equity * params.max_position_pct / HUNDRED) / entry_price
    # Spot only: never spend more cash than we have.
    quantity_by_cash = cash / entry_price

    quantity = min(quantity_by_risk, quantity_by_cap, quantity_by_cash).quantize(
        QUANTITY_STEP, rounding=ROUND_DOWN
    )
    notional = quantity * entry_price
    if quantity <= 0 or notional < params.min_order_notional:
        return _reject(
            f"Order size {notional:.2f} is below the minimum {params.min_order_notional}.",
            entry_price,
        )

    stop_loss = (entry_price * (1 - stop_fraction)).quantize(
        PRICE_STEP, rounding=ROUND_HALF_UP
    )
    take_profit = (entry_price * (1 + take_profit_fraction)).quantize(
        PRICE_STEP, rounding=ROUND_HALF_UP
    )
    return RiskDecision(
        approved=True,
        reason="Approved.",
        quantity=quantity,
        notional=notional,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )


def assess_sell(held_quantity: Decimal, price: Decimal) -> RiskDecision:
    """Closing a held position fully is always allowed. Shorting is not."""
    if held_quantity <= 0:
        return _reject("No open position to sell.", price)
    return RiskDecision(
        approved=True,
        reason="Approved: close the full position.",
        quantity=held_quantity,
        notional=held_quantity * price,
        entry_price=price,
    )

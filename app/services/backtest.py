from dataclasses import dataclass
from decimal import Decimal

from app.schemas.strategy import BacktestResult, BacktestTrade, Candle, SignalAction
from app.services.risk import RiskParams, assess_buy
from app.strategies.base import LOOKBACK, Strategy

DEFAULT_STARTING_CASH = 10_000.0


@dataclass
class _OpenPosition:
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_index: int
    entry_fee: float


def _open_position(
    open_price: float, cash: float, index: int, risk: RiskParams, fee_rate: float
) -> _OpenPosition | None:
    price = Decimal(str(open_price))
    equity = Decimal(str(cash))
    # Leave room for the entry fee.
    spendable = equity / (1 + Decimal(str(fee_rate)))
    decision = assess_buy(
        entry_price=price,
        equity=equity,
        cash=spendable,
        open_positions=0,
        params=risk,
    )
    if not decision.approved:
        return None
    quantity = float(decision.quantity)
    return _OpenPosition(
        quantity=quantity,
        entry_price=open_price,
        stop_loss=float(decision.stop_loss),
        take_profit=float(decision.take_profit),
        entry_index=index,
        entry_fee=quantity * open_price * fee_rate,
    )


def _close_position(
    position: _OpenPosition,
    exit_price: float,
    exit_index: int,
    reason: str,
    fee_rate: float,
) -> tuple[float, BacktestTrade]:
    exit_fee = position.quantity * exit_price * fee_rate
    proceeds = position.quantity * exit_price - exit_fee
    cost = position.quantity * position.entry_price + position.entry_fee
    pnl = proceeds - cost
    trade = BacktestTrade(
        entry_index=position.entry_index,
        exit_index=exit_index,
        entry_price=position.entry_price,
        exit_price=exit_price,
        quantity=position.quantity,
        pnl=round(pnl, 4),
        return_pct=round(pnl / cost * 100.0, 4),
        exit_reason=reason,
    )
    return proceeds, trade


def _check_exit(position: _OpenPosition, candle: Candle) -> tuple[float, str] | None:
    """Stop-loss is checked first: if both levels hit in one candle, assume the worse outcome."""
    if candle.low <= position.stop_loss:
        return min(candle.open, position.stop_loss), "stop_loss"
    if candle.high >= position.take_profit:
        return max(candle.open, position.take_profit), "take_profit"
    return None


def run_backtest(
    strategy: Strategy,
    candles: list[Candle],
    symbol: str = "",
    interval: str = "",
    starting_cash: float = DEFAULT_STARTING_CASH,
    risk: RiskParams | None = None,
    fee_pct: float = 0.1,
) -> BacktestResult:
    """Simulate a long-only spot strategy. A signal on candle i fills at the open of candle i+1."""
    if not candles:
        raise ValueError("Backtest needs at least one candle.")
    if starting_cash <= 0:
        raise ValueError("starting_cash must be positive.")
    if fee_pct < 0:
        raise ValueError("fee_pct cannot be negative.")

    risk = risk or RiskParams()
    fee_rate = fee_pct / 100.0
    cash = starting_cash
    position: _OpenPosition | None = None
    pending: SignalAction | None = None
    trades: list[BacktestTrade] = []
    peak_equity = starting_cash
    max_drawdown_pct = 0.0
    last_index = len(candles) - 1

    for i, candle in enumerate(candles):
        # 1. Fill the order decided on the previous candle, at this candle's open.
        if pending is SignalAction.BUY and position is None:
            position = _open_position(candle.open, cash, i, risk, fee_rate)
            if position is not None:
                cash -= position.quantity * position.entry_price + position.entry_fee
        elif pending is SignalAction.SELL and position is not None:
            proceeds, trade = _close_position(position, candle.open, i, "signal", fee_rate)
            cash += proceeds
            trades.append(trade)
            position = None
        pending = None

        # 2. Check stop-loss / take-profit inside this candle.
        if position is not None:
            exit_info = _check_exit(position, candle)
            if exit_info is not None:
                exit_price, reason = exit_info
                proceeds, trade = _close_position(position, exit_price, i, reason, fee_rate)
                cash += proceeds
                trades.append(trade)
                position = None

        # 3. Mark to market and track drawdown.
        equity = cash + (position.quantity * candle.close if position is not None else 0.0)
        peak_equity = max(peak_equity, equity)
        max_drawdown_pct = max(max_drawdown_pct, (peak_equity - equity) / peak_equity * 100.0)

        # 4. Decide what to do on the next candle.
        if i < last_index and i >= strategy.min_candles - 1:
            window = candles[max(0, i + 1 - LOOKBACK) : i + 1]
            signal = strategy.generate_signal(window)
            if signal.action is SignalAction.BUY and position is None:
                pending = SignalAction.BUY
            elif signal.action is SignalAction.SELL and position is not None:
                pending = SignalAction.SELL

    if position is not None:
        proceeds, trade = _close_position(
            position, candles[-1].close, last_index, "end_of_data", fee_rate
        )
        cash += proceeds
        trades.append(trade)

    wins = sum(1 for t in trades if t.pnl > 0)
    first_close = candles[0].close
    buy_and_hold = (
        (candles[-1].close / first_close - 1.0) * 100.0 if first_close > 0 else 0.0
    )

    return BacktestResult(
        strategy=strategy.name,
        symbol=symbol,
        interval=interval,
        candles_used=len(candles),
        starting_cash=starting_cash,
        ending_equity=round(cash, 4),
        total_return_pct=round((cash / starting_cash - 1.0) * 100.0, 4),
        buy_and_hold_return_pct=round(buy_and_hold, 4),
        trade_count=len(trades),
        win_rate_pct=round(wins / len(trades) * 100.0, 4) if trades else 0.0,
        max_drawdown_pct=round(max_drawdown_pct, 4),
        fee_pct=fee_pct,
        trades=trades,
    )

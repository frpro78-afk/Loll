from dataclasses import dataclass
from decimal import Decimal

from app.core.config import Settings
from app.schemas.strategy import (
    BacktestSummary,
    Candle,
    EngineDecision,
    SignalAction,
    StrategyEvaluation,
    StrategySignal,
)
from app.services.backtest import DEFAULT_STARTING_CASH, run_backtest
from app.services.risk import RiskParams, assess_buy, assess_sell
from app.strategies.base import Strategy


@dataclass(frozen=True)
class EngineParams:
    min_confidence: float = 0.55
    min_backtest_trades: int = 3
    min_backtest_return_pct: float = 0.0
    max_backtest_drawdown_pct: float = 20.0
    backtest_fee_pct: float = 0.1
    backtest_starting_cash: float = DEFAULT_STARTING_CASH


def engine_params_from_settings(settings: Settings) -> EngineParams:
    return EngineParams(
        min_confidence=settings.engine_min_confidence,
        min_backtest_trades=settings.engine_min_backtest_trades,
        min_backtest_return_pct=settings.engine_min_backtest_return_pct,
        max_backtest_drawdown_pct=settings.engine_max_backtest_drawdown_pct,
        backtest_fee_pct=settings.backtest_fee_pct,
        backtest_starting_cash=float(settings.paper_starting_balance),
    )


def _ineligible_reasons(
    signal: StrategySignal,
    backtest: BacktestSummary,
    held_quantity: Decimal,
    params: EngineParams,
) -> list[str]:
    if signal.action is SignalAction.HOLD:
        return ["No actionable signal (hold)."]

    reasons: list[str] = []
    if signal.confidence < params.min_confidence:
        reasons.append(
            f"Confidence {signal.confidence:.2f} is below the minimum {params.min_confidence:.2f}."
        )

    if signal.action is SignalAction.BUY:
        if held_quantity > 0:
            reasons.append("Already holding a position in this symbol.")
        if backtest.trade_count < params.min_backtest_trades:
            reasons.append(
                f"Backtest produced {backtest.trade_count} trades; at least {params.min_backtest_trades} required."
            )
        if backtest.total_return_pct < params.min_backtest_return_pct:
            reasons.append(
                f"Backtest return {backtest.total_return_pct:.2f}% is below the minimum {params.min_backtest_return_pct:.2f}%."
            )
        if backtest.max_drawdown_pct > params.max_backtest_drawdown_pct:
            reasons.append(
                f"Backtest drawdown {backtest.max_drawdown_pct:.2f}% exceeds the maximum {params.max_backtest_drawdown_pct:.2f}%."
            )
    else:
        if held_quantity <= 0:
            reasons.append("No position to sell (spot only, no shorting).")
    return reasons


def evaluate_strategies(
    *,
    symbol: str,
    interval: str,
    candles: list[Candle],
    price: Decimal,
    held_quantity: Decimal,
    cash: Decimal,
    equity: Decimal,
    open_positions: int,
    strategies: list[Strategy],
    risk: RiskParams,
    params: EngineParams,
) -> EngineDecision:
    """Compare all strategies and pick the best eligible one. Never places an order."""
    evaluations: list[StrategyEvaluation] = []
    for strategy in strategies:
        signal = strategy.generate_signal(candles)
        result = run_backtest(
            strategy,
            candles,
            symbol=symbol,
            interval=interval,
            starting_cash=params.backtest_starting_cash,
            risk=risk,
            fee_pct=params.backtest_fee_pct,
        )
        summary = BacktestSummary(**result.model_dump(exclude={"trades"}))
        reasons = _ineligible_reasons(signal, summary, held_quantity, params)
        evaluations.append(
            StrategyEvaluation(
                signal=signal,
                backtest=summary,
                eligible=not reasons,
                ineligible_reasons=reasons,
            )
        )

    eligible = [e for e in evaluations if e.eligible]
    if not eligible:
        return EngineDecision(
            symbol=symbol,
            interval=interval,
            price=price,
            candles_used=len(candles),
            evaluations=evaluations,
            selected=None,
            risk=None,
            message="No eligible strategy signal. No action taken.",
        )

    # Highest confidence, then best backtest return, then name (fully deterministic).
    best = sorted(
        eligible,
        key=lambda e: (-e.signal.confidence, -e.backtest.total_return_pct, e.signal.strategy),
    )[0]

    if best.signal.action is SignalAction.BUY:
        risk_decision = assess_buy(price, equity, cash, open_positions, risk)
    else:
        risk_decision = assess_sell(held_quantity, price)

    outcome = "approved" if risk_decision.approved else f"rejected ({risk_decision.reason})"
    message = (
        f"Selected '{best.signal.strategy}' ({best.signal.action.value}, "
        f"confidence {best.signal.confidence:.2f}). Risk check {outcome}."
    )
    return EngineDecision(
        symbol=symbol,
        interval=interval,
        price=price,
        candles_used=len(candles),
        evaluations=evaluations,
        selected=best.signal,
        risk=risk_decision,
        message=message,
    )

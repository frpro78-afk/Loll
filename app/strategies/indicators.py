"""Indicator math on plain lists of floats. No network, no randomness."""

Series = list[float | None]


def ema(values: list[float], period: int) -> Series:
    """Exponential moving average, seeded with the simple average of the first `period` values."""
    if period < 1:
        raise ValueError("period must be at least 1")
    result: Series = [None] * len(values)
    if len(values) < period:
        return result
    k = 2.0 / (period + 1)
    prev = sum(values[:period]) / period
    result[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1.0 - k)
        result[i] = prev
    return result


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def rsi(values: list[float], period: int = 14) -> Series:
    """Relative Strength Index using Wilder's smoothing."""
    if period < 1:
        raise ValueError("period must be at least 1")
    n = len(values)
    result: Series = [None] * n
    if n <= period:
        return result

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    result[period] = _rsi_value(avg_gain, avg_loss)

    for i in range(period + 1, n):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        result[i] = _rsi_value(avg_gain, avg_loss)
    return result


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[Series, Series, Series]:
    """Return (macd_line, signal_line, histogram)."""
    if fast >= slow:
        raise ValueError("fast period must be smaller than slow period")
    fast_ema = ema(values, fast)
    slow_ema = ema(values, slow)
    macd_line: Series = [
        f - s if f is not None and s is not None else None
        for f, s in zip(fast_ema, slow_ema)
    ]
    first = next((i for i, v in enumerate(macd_line) if v is not None), len(macd_line))
    valid = list(macd_line[first:])
    signal_line: Series = [None] * first + ema(valid, signal)
    histogram: Series = [
        m - s if m is not None and s is not None else None
        for m, s in zip(macd_line, signal_line)
    ]
    return macd_line, signal_line, histogram


def bollinger_bands(
    values: list[float], period: int = 20, num_std: float = 2.0
) -> tuple[Series, Series, Series]:
    """Return (middle, upper, lower) bands using population standard deviation."""
    if period < 2:
        raise ValueError("period must be at least 2")
    n = len(values)
    middle: Series = [None] * n
    upper: Series = [None] * n
    lower: Series = [None] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance**0.5
        middle[i] = mean
        upper[i] = mean + num_std * std
        lower[i] = mean - num_std * std
    return middle, upper, lower


def momentum(values: list[float], period: int = 10) -> Series:
    """Rate of change over `period` candles, in percent."""
    if period < 1:
        raise ValueError("period must be at least 1")
    result: Series = [None] * len(values)
    for i in range(period, len(values)):
        base = values[i - period]
        if base != 0:
            result[i] = (values[i] - base) / base * 100.0
    return result

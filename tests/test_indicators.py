import pytest

from app.strategies import indicators


def test_ema_is_seeded_with_simple_average():
    result = indicators.ema([1, 2, 3, 4, 5], 3)
    assert result[:2] == [None, None]
    assert result[2] == pytest.approx(2.0)
    assert result[3] == pytest.approx(3.0)
    assert result[4] == pytest.approx(4.0)


def test_ema_keeps_input_length_and_rejects_bad_period():
    assert len(indicators.ema([1.0, 2.0], 5)) == 2
    with pytest.raises(ValueError):
        indicators.ema([1.0, 2.0], 0)


def test_rsi_is_100_when_only_rising():
    values = [float(i) for i in range(1, 30)]
    assert indicators.rsi(values, 14)[-1] == pytest.approx(100.0)


def test_rsi_is_0_when_only_falling():
    values = [float(i) for i in range(30, 1, -1)]
    assert indicators.rsi(values, 14)[-1] == pytest.approx(0.0)


def test_rsi_is_50_when_flat_and_has_warmup():
    result = indicators.rsi([10.0] * 30, 14)
    assert result[:14] == [None] * 14
    assert result[-1] == pytest.approx(50.0)


def test_macd_alignment_and_sign_on_rising_series():
    values = [100.0 + i for i in range(60)]
    macd_line, signal_line, histogram = indicators.macd(values, 12, 26, 9)
    assert len(macd_line) == len(signal_line) == len(histogram) == 60
    assert macd_line[24] is None and macd_line[25] is not None
    assert signal_line[32] is None and signal_line[33] is not None
    assert macd_line[-1] > 0
    assert histogram[-1] == pytest.approx(macd_line[-1] - signal_line[-1])


def test_bollinger_known_values():
    middle, upper, lower = indicators.bollinger_bands([1, 2, 3, 4, 5], 5, 2.0)
    std = 2 ** 0.5
    assert middle[4] == pytest.approx(3.0)
    assert upper[4] == pytest.approx(3.0 + 2 * std)
    assert lower[4] == pytest.approx(3.0 - 2 * std)
    assert middle[3] is None


def test_bollinger_flat_series_has_zero_width():
    middle, upper, lower = indicators.bollinger_bands([7.0] * 25, 20, 2.0)
    assert upper[-1] == pytest.approx(lower[-1])


def test_momentum_percent_change():
    result = indicators.momentum([100.0, 102.0, 110.0], 2)
    assert result[:2] == [None, None]
    assert result[2] == pytest.approx(10.0)

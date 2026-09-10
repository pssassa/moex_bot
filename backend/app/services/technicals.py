from __future__ import annotations

from app.models import Candle


def _closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    chunk = values[-window:]
    return sum(chunk) / window


def _rsi(values: list[float], window: int = 14) -> float | None:
    if len(values) <= window:
        return None
    gains = 0.0
    losses = 0.0
    for prev, current in zip(values[-window - 1 : -1], values[-window:]):
        delta = current - prev
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    if losses == 0:
        return 100.0
    rs = (gains / window) / (losses / window)
    return 100 - (100 / (1 + rs))


def _return_pct(values: list[float], bars: int) -> float | None:
    if len(values) <= bars:
        return None
    return (values[-1] / values[-1 - bars] - 1) * 100


def technical_snapshot(candles: list[Candle]) -> dict:
    values = _closes(candles)
    if not values:
        return {}
    last = values[-1]
    sma20 = _sma(values, 20)
    sma50 = _sma(values, 50)
    trend = "боковик"
    if sma20:
        if last > sma20 * 1.01:
            trend = "восходящий"
        elif last < sma20 * 0.99:
            trend = "нисходящий"
    return {
        "last_close": round(last, 4),
        "change_1d_pct": round(_return_pct(values, 1) or 0, 2),
        "change_5d_pct": None if _return_pct(values, 5) is None else round(_return_pct(values, 5), 2),
        "change_20d_pct": None if _return_pct(values, 20) is None else round(_return_pct(values, 20), 2),
        "sma20": None if sma20 is None else round(sma20, 4),
        "sma50": None if sma50 is None else round(sma50, 4),
        "rsi14": None if _rsi(values) is None else round(_rsi(values), 1),
        "trend_vs_sma20": trend,
        "bars": len(values),
    }
